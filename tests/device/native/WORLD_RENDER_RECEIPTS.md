# Original world-image receipt inventory v1

This E2E-only prerequisite retires measurement transport files. It supplies no
feature success. Native code is uncompiled; all physical clients are untested.
The Phone factory uses it; Pico and iOS adapter implementation remains pending.

## Command and original response

`Test.featureWorldRenderReceipts(command)` accepts exactly `schemaVersion:1`,
`action:"feature-world-render-receipts"`, a fresh `commandId`, original capture
`requestId`, `operation:"remove"|"inspect"`, and `receiptIds`. Selectors are
unique lowercase 32-hex nonces, optionally with `ios-`, consistent with the
capture prefix. No paths, digests, issuance flags or desired results are inputs.
The list contains 1–1024 entries; encoded native input is bounded at 49,152 bytes.
The existing probe admits the closed grammar, invokes the original getter once
per command and writes the original response to private
`world-render-receipts-result.json`. Missing hooks produce unavailable metadata.

The original response contains exactly `receiptInventoryVersion:1`, `commandId`,
`requestId`, `operation`, GPU-context `instance`, advancing native `sequence`,
actual `processId`, original `capturedEpochMs`, and `source`. Source contains
`retired`, `present`, `callbacks`, `pngBytes`, `complete`, `receipts`; removal
also contains boolean `performed`. Each receipt row contains exactly `receiptId`,
original `issued`, actual `exists`, and actual `originalMatches`. A missing file
has `originalMatches:false`; a present file requires native issuance and its
original digest. Native digest values are not replaced by host assertions.

## Required native conditions and cleanup order

The feature build flag, `--testScript`, existing canonical private preview root
and actual GPU context are required. Capture retirement is permanent in that
context. Before either operation, the original issuer requires retirement,
no active PNG memory and no queued/executing callback for the capture. It
compares every retained issued receipt with the host selector set. An omitted
issued receipt or a selector issued for another capture rejects the operation.
The existing private probe channel remains single-flight under
`phone-script-sources.lock`; separate role journals do not permit parallel writes.

Before deleting anything, native code validates the complete set of existing
files against retained issuance/digests and the existing owner/mode/link/root
checks. The dedicated POSIX receipt reader uses non-following/nonblocking open,
actual descriptor/path identity, current UID, exact mode 0600 and one hardlink;
it rechecks the descriptor/path after reading the original digest. Unsupported
non-POSIX hosts fail closed. This stricter helper is limited to this E2E receipt
protocol; the historical general preview helper remains unchanged.
A present unissued file is foreign and is preserved. An absent unissued
selector is an original observation of undelivered intent, not authorization to
delete a file later. Native code rechecks an issued file immediately before its
removal. Partial removal and changed files never authorize dropping ownership.

The Phone owner first releases original native memory and independently inspects
callback/PNG drainage. Those commands append their own durable receipt intents.
It then sends one `remove` for the complete updated intent set and a separate,
fresh `inspect`. Both retain native birth/PID/context and unchanged role-bound
ownership. Only `performed:true` plus original complete absence of every receipt
permits journal discard. An ignored successful removal ACK therefore fails.
The bounded result metadata is retained as evidence, without PNG payload bytes.

## Deadlines and failure behavior

Each original query uses the existing five-second Phone deadline, at most 51
original-file reads, and 1,500 ms original-result freshness including final guard
latency. Partial writes may retry reads, never removal inputs. The complete
remove/inspect pair shares five seconds; the encompassing capture cleanup keeps
its 45-second budget. Clock rollback, changed binding/context/owner, wrong nonce,
PID, source version, cursor, coercible booleans, duplicate/missing/foreign rows,
inconsistent issuance and missing results fail closed. Reader issuance histories
remain immutable per capture, bounded at 256 captures, with a global native
cursor/epoch floor. A later capture cannot borrow the prior capture's proof.

Failure retains the original ownership journal. Retrying cleanup requires the
same verified original scope; app stop or process replacement supplies no file
absence proof. Legacy single-receipt protocol v1 remains separately versioned
and cannot qualify never-issued intent. No host shell unlink bypass is used by
the Phone factory.

## Host verification

Nineteen shared counterexamples use explicit synthetic native issuance and real
private host files. They cover full/partial/foreign issuance, changed originals,
ignored removal, unissued absence, lost host prefixes, native/context/clock loss,
latency, parser bounds, actual JavaScript dispatch/dedup and separate successive
capture histories, exposed/special modes, hardlinks and symlinks. The native
POSIX implementation remains uncompiled. Phone wrapper cases additionally exercise the bound factory,
both roles, cleanup retry and two captures through one original reader. These
prove test logic only; no product/device acceptance is inferred.
