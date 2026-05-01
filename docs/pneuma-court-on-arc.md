# PneumaCourt on Arc Testnet

## Contract

| Field | Value |
|---|---|
| Address | `0x3371e96b29b5565EF2622A141cDAD3912Daa66AC` |
| Network | Arc Testnet |
| Source | Pneuma Protocol — `contracts/src/PneumaCourt.sol` |
| Tests | 21 / 21 forge tests passing |
| ABI | [`abi/PneumaCourt.json`](../abi/PneumaCourt.json) (50 entries) |

## Functions used by this project

```solidity
function fileDispute(uint256 callId, string evidence) external returns (uint256 disputeId);
function vote(uint256 disputeId, Verdict verdict) external;
function finalize(uint256 disputeId) external;
function getDispute(uint256 disputeId) external view returns (Dispute memory);
function hasVoted(uint256 disputeId, address juror) external view returns (bool);
function jurorVerdict(uint256 disputeId, address juror) external view returns (Verdict);
```

## Verdict enum

```solidity
enum Verdict { NONE, PLAINTIFF, DEFENDANT, ABSTAIN }
```

The Python side mirrors this via plain string literals in `verdict.py`.

## Roles

`finalize()` requires `JUROR_ROLE`. The wallet you put in
`COURT_FINALIZER_PRIVATE_KEY` (see `.env.example`) must have this role granted.

To grant from the Pneuma main project:

```bash
cast send $PNEUMA_COURT \
  "grantRole(bytes32,address)" \
  $(cast keccak "JUROR_ROLE") \
  $YOUR_FINALIZER_ADDRESS \
  --private-key $ADMIN_KEY \
  --rpc-url $ARC_RPC_URL
```

## Why the off-chain mesh deliberates first

The on-chain `vote()` accepts only `PLAINTIFF | DEFENDANT | ABSTAIN`. It has no
notion of *why* a juror voted that way. The off-chain anet mesh handles:

- Reasoning generation (Claude per juror with domain prompt)
- Real-time SSE streaming of deliberation to the caller
- Per-call settlement in 🐚 Shell credits

When deliberation closes, the **single aggregated verdict** is what hits the
chain — keeping on-chain gas low while preserving the multi-juror audit trail
in each daemon's `svc_call_log`.

## What this project does NOT do

- ❌ Modify the `PneumaCourt` contract (frozen — 21 tests passing)
- ❌ Deploy a new contract (re-uses the existing Arc Testnet deployment)
- ❌ Replace the on-chain dispute lifecycle (it adds an off-chain mesh layer above it)
- ❌ Require Pneuma Protocol's other contracts (Soul NFT, SkillRegistry) to be present — only `PneumaCourt` is read/written

## Pneuma Protocol parent project

The full Pneuma Protocol (Soul NFT + SkillRegistry + PneumaCourt + x402
payments + multi-rater attestation) is a separate codebase. This repo
intentionally focuses on the **Court module + P2P deliberation layer** as the
南客松 Agent Network 龙虾赛道 sponsor-track submission.
