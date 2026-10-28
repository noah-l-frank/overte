# Observed ImageReader runnable destruction and deallocation calls

This independent source binds the actual successful scalar ImageReader
allocation generation to the existing original Source1 constructor task. It
observes the most-derived destructor entry and the actual global deallocation
call return after ordinary virtual destruction. It does not establish whole
QThreadPool drainage, arbitrary byte release or whole Resource retirement.
The adapter completion count remains 5/14; native compilation and device
execution remain unverified. The selected host logic and modeled connected
flow pass within the explicitly limited boundaries below.

The class-specific new/delete and destructor hooks exist only in the dedicated
iOS E2E test build. Other builds retain the original implicit class allocation
and destructor path. The diagnostic build delegates to ordinary scalar global
allocation/deallocation and supports only normal alignment. The feature macro
selects an available declared delegation form; it does not prove which delete
ABI the original compiled virtual deleting destructor chose on a particular
SDK. Both class delete forms are not defined simultaneously because class-scope
lookup would prefer the unsized form. Actual matching-SDK compile, link,
deleting-destructor dispatch and allocator compatibility remain mandatory
unexecuted checks. No global allocator is replaced and no Qt pool is modified.

Each allocation attempt has a fresh opaque generation before the global call.
Only the actual returned address is privately registered; no pointer, address,
URL, content bytes or requested identity leaves native code. The constructor
copies actual Source1 task/resource/marker context after releasing Source1's
mutex and attaches it to that registered live allocation. The allocation,
constructor task and resource identities are independent of size and order.
A nested new-handler can construct another task before its caller, so history
joins use actual IDs rather than assuming equal allocation/constructor order.

Before global delete, the observer captures the exact allocation generation
and a diagnostic-State pin, then removes that address from its live map. The
actual global call runs outside the observer mutex. Return publication uses
only the captured generation/State, never the freed object or an address lookup.
Another thread can register a newer generation at the same address before the
old return is published without rebinding the old event. Native timestamps are
sampled before the metadata mutex; delayed publication preserves those original
clocks and actual native thread contexts.

Constructor failure also invokes a matching deallocator. Its return cannot
stand for a complete most-derived destructor invocation. The pure normal-task
join requires the actual successful Source1 constructor, separate actual
derived destructor entry, expired original marker and actual delete entry/
return. Failed allocation, unbound/failed construction, missing return, source
prefix loss, identity change and known-marker resurrection cannot qualify a
normal task. Unknown/unbound allocations remain separate recorded rows and
never disappear behind a selected task's partial result.

Observer state has bounded fixed metadata, private address keys and weak marker
ownership only. It retains no product object. Reentrant diagnostic callbacks
fail closed before taking its mutex. Disarm is sticky, removes publication
atomically and permits already pinned diagnostic callbacks to finish without
waiting on a product drain. No dead-object access, pool query, cache eviction,
waitForDone, clear, tryTake or SDK operation is performed by this source.

The pinned [Qt6.11.1 QRunnable header](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/thread/qrunnable.h) and
[QThreadPool implementation](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/thread/qthreadpool.cpp) show a virtual destructor and ordinary delete
routes from worker, clear and steal/run. Worker/clear unlock their mutex around
delete; steal/run first returns from tryTake's scoped lock. QueuePage contains
raw runnable pointers, and Qt documents tryTake's ABA problem. Observing a
storage deallocator cannot prove queue membership absence, lack of a stale
entry, all selected invocations returned or pool retirement. Those require a
separate generation-aware native pool admission/removal/running history. The
new source deliberately keeps poolCompletionAvailable false.

A separate one-attempt collector retains actual Storage/Source1 raw originals,
query intent and frame/WAL files before delivery. Unknown delivery or opened
prefixes remain responsibilities; exact saved adoption never resends input or
query. Exact closed namespaces reach their own full historical inspector before
the broad pixel-image prefix, and orphan/unknown records remain blocking.
The original 20-second operation, 1.5-second acquisition and three-second quiet
limits remain unchanged. Host, native Source1, native storage and canonical
native clocks keep their original domains; cross-domain epoch joins do not
pretend their independent monotonic origins are equal.

The planned pure composition joins the existing normal Delete/Home image and
processing originals with these storage originals, three quiet observations and
complete selected task/generation membership. It performs no query, input,
write, deallocation or external cleanup. Historical inspection always retains
image-storage-resource-retirement after this partial join. No complete Assets
capability is advertised.

The host cases use an explicit native/Qt/allocator boundary model
plus real weak markers, private files, opaque address-slot objects and held
bytearray-containing blocks. The normal-flow case holds the declared global
free return after the earlier processing join closes, requires this new join
to refuse, releases only the test allocator barrier, then acquires fresh quiet
originals. The model does not execute C++ new/delete, a QRunnable base, Qt pools,
OS memory release or physical GPU work. The address-slot ABA case models that
native algorithm; it does not claim an observed physical pointer reuse.

The selected 102 host cases pass in 6.314 seconds: thirty new Storage cases,
twenty-nine Processing cases including the writer contract and inert CMake
script metadata matrix, and forty-three Lifecycle/Queue regressions. Complete
source/launcher/actual-own-hunk inventories (5605 files) retain identical bytes,
metadata and membership throughout. Forty-two private roots and 196 original
files remain retained; the CMake script working directory remains empty.

The fresh connected case passes in 204.277 seconds under the fixed 300-second
outer cap. Original operation, 1.5-second acquisition and three-second quiet
limits are unchanged. It performs one ordinary Delete/Home, closes the earlier
observed processing/input edges while the declared allocator still holds free
returns, and verifies that the Storage join refuses. Only the test driver then
releases its own allocator barriers. New quiet originals establish the pure
selected destructor/deallocation-call join; effect prohibitions and the full
historical session inventory pass. That inventory still retains image-reader,
image-processing, image-storage and model-removal Resource responsibilities.
All 5605 source/launcher/own-hunk pins remain identical; 386 original files are
retained. The bound runner and its owned process group leave no processes.

These are host-model/source results. They do not execute the native class
operators, QRunnable, Qt pools, global allocator, Qt serializer or installed SDK.
The successful partial join never enables complete Assets or whole Resource
retirement, and the source-completion count remains 5/14.

Required later checks include actual SDK allocation/deletion ABI, constructor
failure dispatch, all Qt pool deletion/admission routes and real late callbacks.
Arbitrary QByteArray/decoded-data/plugin release, pool/running closure, physical
GPU generations/fences/recycler completion, backend/actor/process/SDK retirement
and whole Resource completion remain unavailable. Existing host results for
other packets retain their original source scope and do not qualify this code.


The image target's existing gated private test-build definition and the
Processing filename's three private compact writer routes are prerequisites
preserved from the preceding fixes. This packet adds only Storage's getter,
exact filename routes and independent protocol. It does not repeat or overwrite
the image-target macro correction, alter Source1/Processing/Queue wire grammars
or modify non-iOS/non-test product allocation behavior.


The separate [selected pool source](ASSETS_IMAGE_POOL_SOURCE.md) provides an
optional matching-SDK admission/slot/run/delete/scope protocol. Its 30 new host
cases, 102 existing component regressions and three private source-patch checks
pass; the new connected flow passes in 227.727 seconds. Storage closes while a
declared selected pool iteration remains held, and the Pool join refuses until
independent release and fresh quiet samples. Storage remains an independent
component. These host results do not execute the Qt SDK patch; global pool
drainage, arbitrary bytes, GPU and whole Resource retirement remain unavailable.
