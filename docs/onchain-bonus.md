# On-chain Settlement (default behavior)

> **TL;DR**: Every verdict is written on-chain by default. Gas is paid by the
> court operator's wallet using free Arc Testnet ETH. Callers never need an
> EVM wallet. If the court isn't configured for on-chain, it falls back to
> advisory-only mode automatically — no setup is forced on you.

## Who reads this page?

- **Court operators** setting up `pneuma-court` for the first time — you need
  the JUROR_ROLE grant + faucet steps below.
- **Curious callers** who want to understand what happens behind the scenes
  when they get a `tx_hash` back. (You don't need to do anything; the court
  handles it for you.)

## Gas model

- **Court operator** (whoever runs `court-main`) pays gas via
  `COURT_FINALIZER_PRIVATE_KEY`.
- **Callers** pay nothing extra in EVM tokens. They pay 🐚 Shell — the price
  is set by the court operator's `COURT_COST_PER_CALL` (default 20🐚).
- A reasonable pricing strategy: charge more 🐚 Shell when
  `want_onchain_proof=true` arrives in the payload (e.g. 50🐚 vs 20🐚) so the
  operator's gas is covered by the premium.

> **Why not let callers pay gas directly?**
> 99% of anet users do not hold an EVM wallet. Forcing them to acquire one
> would defeat the point of anet's "agent即刻互联" zero-onboarding promise.
> Server-side gas sponsorship is the only viable bridge between anet's 🐚
> Shell economy and any external chain. Future versions may use account
> abstraction / paymasters; for now, the operator-pays model works.

## Setup (court operator only)

### 1. Get an EVM wallet funded on Arc Testnet

Any wallet with a small testnet ETH balance is enough. A few cents per
finalize call is typical.

### 2. Grant `JUROR_ROLE` to your wallet

The deployed `PneumaCourt` contract on Arc Testnet at
[`0x3371e96b29b5565EF2622A141cDAD3912Daa66AC`](https://explorer.arc-testnet.example/address/0x3371e96b29b5565EF2622A141cDAD3912Daa66AC)
restricts `vote()` and `finalize()` to addresses with `JUROR_ROLE`.

If you control the contract admin key:

```bash
# bytes32 keccak256("JUROR_ROLE")
ROLE=$(cast keccak "JUROR_ROLE")

cast send 0x3371e96b29b5565EF2622A141cDAD3912Daa66AC \
  "grantRole(bytes32,address)" \
  $ROLE \
  $YOUR_FINALIZER_ADDRESS \
  --private-key $ADMIN_KEY \
  --rpc-url $ARC_RPC_URL
```

If you don't control the admin key, the parent Pneuma Protocol team can
grant it on request.

### 3. Configure `.env`

```ini
ARC_RPC_URL=https://rpc.arc-testnet.example
PNEUMA_COURT_ADDRESS=0x3371e96b29b5565EF2622A141cDAD3912Daa66AC
COURT_FINALIZER_PRIVATE_KEY=0x...   # the wallet you funded + granted role to
```

If you skip any one of these three, the court silently falls back to
advisory-only mode — no breakage.

### 4. Verify

Submit any case via `examples/run_case.py`. The response should contain a
non-null `tx_hash` and `dispute_id`. Look the tx up on the Arc Testnet
block explorer to confirm `DisputeFiled` and `DisputeFinalized` events.

## What gets written on-chain

When opt-in is triggered, the court operator's wallet sends two transactions:

1. `vote(disputeId, verdictCode)` — the operator casts the **aggregated**
   verdict from the off-chain juror deliberation. This is a single
   on-chain vote representing the multi-juror majority.
2. `finalize(disputeId)` — closes the dispute. The contract tallies all
   on-chain votes and emits `DisputeFinalized(disputeId, verdict)`.

The off-chain audit trail (each juror's reasoning, peer ID, timestamp)
**stays in the daemons' `svc_call_log`** — that's where the multi-juror
detail lives. The chain only sees the aggregated outcome.

## What does NOT get written on-chain

- Individual juror votes / reasoning (off-chain in `svc_call_log`)
- The case evidence text (off-chain — only `caseId` is referenced)
- 🐚 Shell payment flows (those settle in anet, not on Ethereum)

This separation keeps gas costs minimal (~one ERC-20 transfer worth) while
preserving full deliberation provenance in the anet mesh.

## Failure mode

If on-chain finalize fails (RPC down, gas underfunded, role not granted):

- The verdict still returns to the caller over anet.
- `result.error` will explain the on-chain failure.
- The caller can retry later, or accept the off-chain-only ruling.

The off-chain ruling is **the source of truth**. The on-chain write is a
portable cache of it, not a parallel authority.
