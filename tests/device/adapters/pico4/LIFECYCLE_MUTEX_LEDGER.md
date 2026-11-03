# Lifecycle capacity-only mutex ledger 2

This is an explicit warm storage option on the existing namespace bill. It
records host metadata progress, never a native event, product effect, source
sample, input acknowledgement or proof of which process performed a chmod.
Default `LifecycleNamespaceBill(..., mutex_layout=1)` keeps the original tuple
ledger and its 512-transition bound. The canonical private Background3 factory
selects `mutex_layout=2` before admission. No cold files select or resume it.

Each version 2 cohort retains one exact admitted `session-<32hex>.lock` name,
the original seven unchanged stat fields and an immutable chain containing the
first actual before-ctime followed by EVERY actual observed after-ctime. A
separate immutable `(cohortIndex, localTransitionIndex)` order vector preserves
global ordering when actual mutexes interleave. Every complete before8/after8
pair reconstructs exactly from adjacent ctimes and its original prefix. No
unobserved intermediate change, new file, inode adoption or new clock is added.

All old guards remain: exact admitted namespace, original directory OFD,
original file dev/ino/mode0600/uid/nlink1/size0/mtime, monotonic observed ctime,
original SourceLock and unchanged other source/root/part pins. Same-node
same-mode ABA is still only observed metadata; it cannot authorize a dead
candidate or native source. Namespace or ledger identity/cost substitution
refuses before the next source query. The ledger never calls a native reader.

Before copying either ctime or order tuples, the exact compact canonical size,
retained old/new ledger and canonical overlap are charged by the same actual
immutable namespace budget and pinned original raw-capacity callback. Cohorts
remain bounded at 512. The global 512 file-part and 16MiB limits, all actual native
read/frame quotas, source clocks, phase fences and action budgets are unchanged.
The compact metadata chain is byte-admitted, independently of native event
counters. It creates no files and never discards or evicts transitions.

A separately reserved 2334-byte window covers up to six reconstructed complete
rows, using the actual accepted unsigned 64-bit stat bounds. The ordinary view
supports constant-size length, individual rows and bounded slices. An implicit
whole-list conversion or larger slice is refused. No full expanded DTO cache
or stale cost supplies admission. The compact state and cost share an immutable
identity seal; a one-use internal permit cannot commit before the original
full byte-budget check, including from a reentrant original capacity callback.

An already-observed pair is held before validation/admission. Refusal leaves the
exact pair or permit and old immutable ledger intact, poisons further work and
makes close return false. Existing `close_or_retain` preserves that namespace
strongly. Optional constructor failure retains the partial ledger on the
namespace before invoking its initializer. The same helper closes known-correct
original directory handles or preserves uncertainty; it never force-closes a
foreign/recycled descriptor. The original constructor exception is rethrown.
Default ledger 1 construction is unaffected.

The real kernel counter executes 513 calls to the existing actual
`PicoOpenXrAdapterSession.require_process_identity`/mutex-fchmod path, retaining
and comparing every original pair in order. The SDK/process/Qt producers remain
explicit existing device-free fixtures. Additional counters use two actual
admitted mutex files, real inode/mode/size/mtime/other-root changes, same-mode
ABA, actual durable pending-raw reservations to exhaust the unchanged byte
budget, cache/view/layout substitution, original-callback reentry and a failed
constructor after a real original directory OFD was acquired. They establish
storage/host responsibility, not device behavior or native effects.

The same canonical seven-normal-action flow retains 173 raw returns, 19 raw
parts and 1,185,370 literal bytes, with all 508 observed mutex transitions.
Its compact ledger is 14,313 bytes; including the reconstruction window costs
16,647 bytes, compared with 105,665 bytes for ledger 1 metadata. Its final measured
decoded/copy bill is 12,746,261 bytes; this is not a claimed full-journey maximum.
Only the three original baseline Actor publications are sampled. The native
Qt/SDK/GPU execution, full 24 groups, all 16 effects, image checkpoints, subsequent
pending/Scripts identity composition and device acceptance remain open.

Private original code, SHA/eight-stat freezes and retained test artifacts:
`/home/user/.local/state/pico-lifecycle-storage3-20261103-work/`.

The final explicit `test_lifecycle_mutex_ledger` wrapper ran all ten storage
counters plus the unchanged canonical entry: 11 cases GREEN in 55.493s
(56.666s including source freeze), all 300 loaded repository source SHA/eight-stat
pins unchanged. The default ledger1 raw group separately passed 31 cases in
14.708s (15.751s including freeze), all 150 loaded sources unchanged. Both groups
retained the original real 120-second watchdog. No compiler/device/whole 24 run
was invoked. The tested Root factory selects 2 only in its existing explicit
`raw_layout=True` namespace constructor branch.
