// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

/// @title CourtEscrow — self-contained dispute enforcement for Pneuma Court
/// @notice Provider stakes USDC. Caller escrows USDC into a call. After the
///         work is done, caller either settles (transfers escrow to provider)
///         or files a dispute. The Court contract authority — set at deploy
///         time — resolves the dispute, slashing a percentage of the
///         provider's stake to the caller if plaintiff wins.
///
///         This contract is intentionally INDEPENDENT of the parent Pneuma
///         Protocol's SkillRegistry. It exists so this repo's submission to
///         the Agent Network sponsor track has a complete dispute-and-
///         enforcement loop without requiring any external project to be
///         deployed or wired up.
///
///         Strict scope: stake + escrow + settle + dispute + slash. No
///         provider discovery, no skill catalog, no reputation graph — those
///         layers belong to the parent project. This contract is the
///         minimum viable enforcement primitive.

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

contract CourtEscrow {
    // ─────────────────────────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────────────────────────
    error NotCourt();
    error NotPlaintiff();
    error NotCaller();
    error CallNotFound();
    error CallAlreadyResolved();
    error AlreadyDisputed();
    error InsufficientStake();
    error TransferFailed();
    error ZeroAddress();
    error ZeroAmount();
    error CaseNotFound();

    // ─────────────────────────────────────────────────────────────────
    // Types
    // ─────────────────────────────────────────────────────────────────
    enum CallStatus {
        Empty,
        Escrowed,
        Settled,
        Disputed,
        Resolved
    }

    enum CaseOutcome {
        Pending,
        PlaintiffWins,
        DefendantWins
    }

    struct Call {
        uint256 callId;
        address caller;
        address provider;
        uint256 escrowedAmount;   // caller put this much in
        uint256 lockedStake;      // how much of provider's stake is locked to this call
        CallStatus status;
    }

    struct Case {
        uint256 caseId;
        uint256 callId;
        bytes32 evidenceHash;
        CaseOutcome outcome;
    }

    // ─────────────────────────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────────────────────────
    IERC20 public immutable paymentToken;
    address public court;       // resolves disputes — settable once
    address public immutable deployer;

    /// @notice slash percentage in basis points (e.g. 5000 = 50%)
    uint16 public constant SLASH_BPS = 5000;
    uint16 public constant BPS_DENOM = 10000;

    mapping(address => uint256) public providerStake;   // total stake
    mapping(address => uint256) public lockedStake;     // currently locked across active calls

    mapping(uint256 => Call) public calls;
    mapping(uint256 => Case) public cases;
    mapping(uint256 => uint256) public callToCase;      // 0 if no dispute filed

    uint256 public callCount;
    uint256 public caseCount;

    // ─────────────────────────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────────────────────────
    event Staked(address indexed provider, uint256 amount, uint256 newTotal);
    event Withdrawn(address indexed provider, uint256 amount, uint256 newTotal);
    event CallEscrowed(uint256 indexed callId, address indexed caller, address indexed provider, uint256 amount, uint256 lockedStake);
    event CallSettled(uint256 indexed callId, address indexed provider, uint256 amount);
    event DisputeFiled(uint256 indexed caseId, uint256 indexed callId, address indexed plaintiff, bytes32 evidenceHash);
    event DisputeResolved(uint256 indexed caseId, uint256 indexed callId, CaseOutcome outcome, uint256 slashAmount, address beneficiary);
    event CourtUpdated(address indexed previous, address indexed next);

    // ─────────────────────────────────────────────────────────────────
    // Modifiers
    // ─────────────────────────────────────────────────────────────────
    modifier onlyCourt() {
        if (msg.sender != court) revert NotCourt();
        _;
    }

    // ─────────────────────────────────────────────────────────────────
    // Construction + admin
    // ─────────────────────────────────────────────────────────────────
    constructor(address _paymentToken, address _court) {
        if (_paymentToken == address(0) || _court == address(0)) revert ZeroAddress();
        paymentToken = IERC20(_paymentToken);
        court = _court;
        deployer = msg.sender;
        emit CourtUpdated(address(0), _court);
    }

    /// @notice Deployer can re-bind the court authority (e.g. on key rotation).
    function setCourt(address newCourt) external {
        if (msg.sender != deployer) revert NotCourt();
        if (newCourt == address(0)) revert ZeroAddress();
        emit CourtUpdated(court, newCourt);
        court = newCourt;
    }

    // ─────────────────────────────────────────────────────────────────
    // Provider: stake / withdraw
    // ─────────────────────────────────────────────────────────────────

    /// @notice Provider deposits USDC stake. They must approve this contract first.
    function stake(uint256 amount) external {
        if (amount == 0) revert ZeroAmount();
        bool ok = paymentToken.transferFrom(msg.sender, address(this), amount);
        if (!ok) revert TransferFailed();
        providerStake[msg.sender] += amount;
        emit Staked(msg.sender, amount, providerStake[msg.sender]);
    }

    /// @notice Provider withdraws unlocked stake.
    function withdrawStake(uint256 amount) external {
        uint256 available = providerStake[msg.sender] - lockedStake[msg.sender];
        if (amount == 0) revert ZeroAmount();
        if (amount > available) revert InsufficientStake();
        providerStake[msg.sender] -= amount;
        bool ok = paymentToken.transfer(msg.sender, amount);
        if (!ok) revert TransferFailed();
        emit Withdrawn(msg.sender, amount, providerStake[msg.sender]);
    }

    // ─────────────────────────────────────────────────────────────────
    // Caller: escrow + settle
    // ─────────────────────────────────────────────────────────────────

    /// @notice Caller escrows USDC for a call. Provider's stake locks an
    ///         equal-or-lesser amount up to their available balance — this
    ///         is the slash ceiling later.
    function escrowCall(address provider, uint256 amount) external returns (uint256 callId) {
        if (provider == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        bool ok = paymentToken.transferFrom(msg.sender, address(this), amount);
        if (!ok) revert TransferFailed();

        // Lock min(amount, provider's available stake) — the slash cap.
        uint256 available = providerStake[provider] - lockedStake[provider];
        uint256 toLock = amount > available ? available : amount;
        lockedStake[provider] += toLock;

        callId = ++callCount;
        calls[callId] = Call({
            callId: callId,
            caller: msg.sender,
            provider: provider,
            escrowedAmount: amount,
            lockedStake: toLock,
            status: CallStatus.Escrowed
        });

        emit CallEscrowed(callId, msg.sender, provider, amount, toLock);
    }

    /// @notice Caller settles — escrow flows to provider. No dispute possible after this.
    function settleCall(uint256 callId) external {
        Call storage c = calls[callId];
        if (c.callId == 0) revert CallNotFound();
        if (c.caller != msg.sender) revert NotCaller();
        if (c.status != CallStatus.Escrowed) revert CallAlreadyResolved();

        c.status = CallStatus.Settled;
        lockedStake[c.provider] -= c.lockedStake;
        bool ok = paymentToken.transfer(c.provider, c.escrowedAmount);
        if (!ok) revert TransferFailed();

        emit CallSettled(callId, c.provider, c.escrowedAmount);
    }

    // ─────────────────────────────────────────────────────────────────
    // Caller: file dispute  (must sign themselves — plaintiff = msg.sender)
    // ─────────────────────────────────────────────────────────────────

    function fileDispute(uint256 callId, bytes32 evidenceHash) external returns (uint256 caseId) {
        Call storage c = calls[callId];
        if (c.callId == 0) revert CallNotFound();
        if (c.caller != msg.sender) revert NotPlaintiff();
        if (c.status != CallStatus.Escrowed) revert CallAlreadyResolved();
        if (callToCase[callId] != 0) revert AlreadyDisputed();

        c.status = CallStatus.Disputed;
        caseId = ++caseCount;
        cases[caseId] = Case({
            caseId: caseId,
            callId: callId,
            evidenceHash: evidenceHash,
            outcome: CaseOutcome.Pending
        });
        callToCase[callId] = caseId;

        emit DisputeFiled(caseId, callId, msg.sender, evidenceHash);
    }

    // ─────────────────────────────────────────────────────────────────
    // Court: resolve  (only court — multi-juror panel off-chain produces
    //                  the outcome, court signs this tx as the trusted
    //                  aggregator. v0.2 will multisig over jurors' Souls.)
    // ─────────────────────────────────────────────────────────────────

    function resolveDispute(uint256 caseId, bool plaintiffWins) external onlyCourt {
        Case storage k = cases[caseId];
        if (k.caseId == 0) revert CaseNotFound();
        if (k.outcome != CaseOutcome.Pending) revert CallAlreadyResolved();

        Call storage c = calls[k.callId];
        c.status = CallStatus.Resolved;

        uint256 slashAmount = 0;
        address beneficiary;

        if (plaintiffWins) {
            // refund caller's escrow + slash provider's locked stake → caller
            slashAmount = (c.lockedStake * SLASH_BPS) / BPS_DENOM;
            providerStake[c.provider] -= slashAmount;
            lockedStake[c.provider] -= c.lockedStake;
            beneficiary = c.caller;

            // refund full escrow + slash to caller in two transfers
            uint256 totalToCaller = c.escrowedAmount + slashAmount;
            bool ok = paymentToken.transfer(c.caller, totalToCaller);
            if (!ok) revert TransferFailed();

            k.outcome = CaseOutcome.PlaintiffWins;
        } else {
            // provider wins — escrow flows to provider, stake unlocks (no slash)
            lockedStake[c.provider] -= c.lockedStake;
            beneficiary = c.provider;
            bool ok = paymentToken.transfer(c.provider, c.escrowedAmount);
            if (!ok) revert TransferFailed();
            k.outcome = CaseOutcome.DefendantWins;
        }

        emit DisputeResolved(caseId, k.callId, k.outcome, slashAmount, beneficiary);
    }

    // ─────────────────────────────────────────────────────────────────
    // Views
    // ─────────────────────────────────────────────────────────────────

    function getCall(uint256 callId) external view returns (Call memory) {
        return calls[callId];
    }

    function getCase(uint256 caseId) external view returns (Case memory) {
        return cases[caseId];
    }

    function availableStake(address provider) external view returns (uint256) {
        return providerStake[provider] - lockedStake[provider];
    }
}
