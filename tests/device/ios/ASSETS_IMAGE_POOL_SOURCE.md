# Selected ImageReader admission, slot and execution edges

The selected host suite passes all 135 distinct cases: 30 new Pool cases,
102 existing Storage/Processing/Queue/lifecycle cases and three offline Qt
source-patch checks. The new connected host case passes in 227.727 seconds
within its fixed 300-second outer bound. No configure, compiler, link, SDK
installation, Qt runtime or physical-device operation has been performed for
this packet. The adapter completion count remains 5/14.

This source adds an optional Qt6.11.1 private SDK diagnostic protocol. It binds
an actual successful ImageReader allocation generation and live QRunnable base
conversion to the existing original constructor TaskContext before admission.
Source1, Queue, Processing and Storage wire contracts remain unchanged. The
separate [storage source](ASSETS_IMAGE_STORAGE_SOURCE.md) remains the authority
for selected successful constructor, derived destructor and global delete-call
return observations. Its prior host results do not qualify this new revision.

`observedSelectedRunnablePoolEdgesClosed` is a partial observation: selected
original admission APIs, physical queue slots, run/delete calls and their
instrumented scope returns have matching original events. It never means that
the global pool has drained or that all worker/thread/pool object lifetimes
ended. Bytes, decoder/plugins, GPU/fences/recycler and whole Resource retirement
remain unavailable; all corresponding broad completion flags remain false.

## Exact SDK source and bootstrap

The optional [patch](../../../ios/patches/qtbase-overte-e2e-runnable-pool.patch)
targets only the official `qt/qtbase` tag `v6.11.1`:

- [qthreadpool_p.h](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/thread/qthreadpool_p.h), SHA-256 `205faa562f40bcdf2723e78f3002809830e8ec16af2c9f4e6ef9bc180b1129f7`.
- [qthreadpool.cpp](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/thread/qthreadpool.cpp), SHA-256 `36e6f7e77253f15cf113ac06f052136baf164fe7a9ef63a46bcfec55db4ff7fb`.

The [source manifest](qt-runnable-pool-source-patch.json) pins both originals.
The source-only verifier accepts those exact bytes, creates retained 0700
private copies, checks apply/reverse and exact reverse restoration, and rereads
the originals. It never configures, compiles, links or executes Qt. Actual
private apply/reverse and exact restoration of both sources pass; corrupt
source and an external scratch destination are rejected before Git runs.
These source checks establish no native ABI or runtime behavior.

The patch changes private QueuePage and QThreadPoolPrivate layouts. A matching
complete SDK and every private-header consumer must be rebuilt together in a
separately authorized build. The earlier metacall patch touches different Qt
files; combined source compatibility and native linkage still need validation.
The current class allocation/delete instrumentation is diagnostic test-build
code. No claim is made that its sized-deallocation macro reconstructs the
previous compiled virtual deleting-destructor ABI.

The first statement of main attempts bootstrap only under all three dedicated
iOS E2E build gates and an actual nonempty `--testScript` argument. This happens
before qputenv, QtWebView initialization and QCoreApplication construction.
Only the exact Qt6.11.1 optional protocol is accepted. An absent/unpatched SDK
returns unavailable. A pool created before bootstrap keeps an unknown zero
generation; selecting it fails rather than retrospectively adopting its
address. Shutdown disarms the observer. Ordinary non-test builds add no app
observer hooks.

## Concrete native protocol

The SDK stores fixed-capacity POD rows and immutable published event cells.
Pool-locked hook points do not allocate, call app callbacks or acquire blocking
observer locks. Compile-time atomic lock-free requirements cover booleans,
64-bit counters, internal runnable pointers and opaque thread handles. SDK epoch and steady-nanosecond
clocks retain their own domain; 64-bit steady values are decimal strings over
JSON. App binding and native-main getter clocks remain separate originals.

The protocol uses 128 fixed atomic thread-context slots, without observer
`thread_local` objects or dynamic per-thread initialization. Exactly retained
Qt6.11.1 `qthread.h` and `qthread_unix.cpp` show the Darwin ARM64 thread-ID fallback
calling `pthread_self`; no QThread or foreign QObject is acquired or read. Raw
handles remain internal. Exported `threadSlotId` values are generated slot
indices, not addresses and not OS-thread lifetime generations; an OS handle can
be reused. They check context consistency inside the actual observed scopes,
not whole-thread retirement. Native platform cost/ABI behavior remains unrun.

The constructor registration carries the actual Storage allocation UUID. The
raw base pointer stays private to the SDK, never appears in a packet, and never
pins a product object. Storage copies the opaque registration before global
free and retires it outside its metadata mutex. Registration lookup is removed
before the allocator can reuse the address. Post-free callbacks use captured
registration/admission tokens, never a dead object or a fresh address lookup.

The admission generation is captured at start/tryStart/startOnReservedThread,
carried in parallel metadata for every real QueuePage slot, and carried in the
actual worker runnable field. Looking up a generation only when dequeuing would
be vulnerable to address reuse. Promotion preserves the original admission,
including the legitimate transient old/new physical slots when Qt enqueues a
waiting-thread task before popping the previous slot. Every slot must retire.

Worker execution and stealAndRun retain the actual autoDelete value read by Qt;
no extra product autoDelete read is added. Events distinguish run return,
actual delete-expression entry/return and the instrumented selected execution
scope return. In the worker path that scope ends after mutex relock and before
the next scheduler bookkeeping; it is not worker-loop/thread completion.
Clear deletion has its own delete and post-relock scope events. The final marker inside the pool destructor is a body-tail observation only;
it does not establish return from that destructor body or full QObject/base end.

Every tryTake call has a distinct operation generation. Its matched queue slot
retains its original admission even if the compared raw address belongs to a
newer current registration. A mismatch, untracked selected slot, duplicate
admission or overflow fails closed. One original ImageReader admission per
registration is supported; resubmission/autoDelete-false lifetimes require
another protocol and cannot silently pass this one.

A concurrent snapshot is not a global lock. Writers, mutation serials and
release-published cells identify an incomplete cut. Such a cut is a valid
pending original, with reserved counts and possibly unpublished holes. The
collector preserves it without treating a benign concurrent publication as
unknown transport delivery. Closure requires a later healthy complete cut.
Old immutable events may publish later with their original older clock; no
cross-thread global timestamp order is fabricated from reservation order.

## Original files and pure composition

The request is an exact nonce-only command. It cannot supply task, allocation,
address, expected result or requested pool emptiness. The native getter and
Probe consume the nonce once; missing APIs remain unavailable. The new filename
uses the existing dedicated-build gate, compact size bound and private atomic
QSaveFile path. Processing stays the first writer-condition member.

The source owner journals query intent before each attempt and retains the
literal Pool, Storage, Source1 and canonical-clock originals. It rereads actual
parents and validates process, candidate/session guard, IDs, clocks, immutable
history and weak/deallocation facts within the original 1.5-second binding
limit. Opened prefixes, unknown sends, orphan files and interrupted writes stay
responsibilities. Saved adoption can recover exact original bytes without a
query, normal input, delete or cache operation replay. Historical inventory is
read-only and always retains image-pool-resource-retirement responsibility.

The pure join first requires the selected Storage edges, then exact admission,
slot, generation, original-event and scope chains. It distinguishes normal
worker deletion, clear cancellation, successful tryTake with independently
observed deallocation, stealAndRun, and a declined tryStart whose caller-owned
storage is separately deallocated. Queue absence, weak expiry, global delete
return or a pool-idle claim cannot replace a missing execution scope return.

Normal Delete/Home composition extends the existing image, processing and
storage compositions with independent Pool samples. It checks original ordering
and repeated quiet samples spanning at least three seconds, including original
Qt steady time, and rechecks immutable original files. It cannot query, deliver
input, clear a pool/cache, release a runnable, open a process/socket or write a
state file. The new connected host model holds a declared pool iteration tail
after actual host block release: Storage must close while Pool refuses. Only
the test driver releases its own barrier before fresh samples. One normal
Delete/Home and all Resource responsibilities remain.

## Host validation and remaining scope

The fifteen core cases cover worker/clear/transfer/stolen/declined routes,
promotion slots, incomplete publication, old-generation reuse, overlapping
tryTake IDs, missing tails, malformed packets, immutable-history loss, clock
and thread substitution, pure effects and Probe nonce behavior. Eleven cases
exercise actual host-file WAL/inventory/routing and four exercise canonical
factory/session/AFC methods over an explicit SDK producer. One connected case
uses the existing normal removal flow. All 135 selected cases pass in 9.754
seconds without skips. The separate connected case preserves exactly one
normal Delete/Home, proves Storage closure while the declared pool iteration
is still held, and rejects Pool closure until the test driver releases its
own barrier and fresh quiet samples are collected. The original 20/1.5/3/1.6
limits are unchanged. All 5,681 source/launcher/reference pins, including
main.cpp, remain unchanged across each run; 279 small-suite and 443 connected
original files are retained with two matching post-stop censuses. All owned
test processes have exited. These are host models, not native scheduler tests.

Python weak markers, independent bytearray blocks and immutable host files are
real host objects. The pool, native ABI, physical pointer reuse, SDK threads,
Qt serializer/QSaveFile and device paths are explicit models or uncompiled
source. Native compile/link, SDK patch execution, allocator/constructor-failure
ABI, actual scheduler concurrency and independently retained byte/GPU/product
resources remain required. No whole-resource end claim is introduced.


## Canonical runtime source factory

`IOSAssetsRuntime._assets_image_pool_source` now constructs the existing
Pool/Storage/Source1 owner through the selected candidate, session, PID,
foreground and held SDK lock. Construction makes no Pool reservation or query.
Explicit capture uses the existing transport and durable original store.
Reopening validates retained Pool originals without querying that Pool again;
the normal installed-binding verification can still update its own journal.

Seven selected host cases pass in 2.090 seconds, preserving 46 original files
in seven actual fixture roots and all 7,687 source/launcher/reference pins.
They reject a valid foreign SDK lock, changed candidate/PID/foreground, late
source loss and same-byte inode replacement; lost delivery remains owned
without resend. The test selects consistent declared producer clocks before
capture. Earlier clock-fixture and missing-parent failures remain retained,
alongside all 722 previous originals. Owned processes and new threads are gone.

These execute canonical transport methods over declared HTTP/AFC, SDK and
native response models. No actual HTTP server, SDK, Qt allocator or native
resource retirement is qualified. Byte/decoder/GPU and whole Assets end remain
open; this factory enables no complete capability.
