# Original host observer return transport

`ObserverReturnSender` and `ObserverReturnReceiver` version 1 move opaque
original bytes between two originally owned Linux host processes. They do not
qualify a feature graph, native build, device effect or whole cleanup. A typed
feature owner must validate the payload through the receiver's `admit(bytes,
source_stamp)` callback. No Actor live objects cross the process boundary.

The producer holds one warm sender, pins its actual PID/start/boot identity,
original private directory, typed source stamp and payload SHA-256, and writes
one immutable `reading` to `ready` root with one to four original 16-KiB chunks.
The maximum opaque payload is 64 KiB. Existing roots or rootless chunks prevent
acquisition. Every use verifies the original physical child identities, root
bytes and stamp, cache digest, private paths and the typed producer guard.
The guard must verify historical ownership; it cannot refresh old native facts.

The Parent must originally acquire `LinuxChatObserverProcess` while that exact
reviewed host entrypoint is live. The transport currently requires that exact
passive process owner; it does not discover or launch an observer. The Parent
then validates the original ready bytes, physical root and child stamps, scope
and independently typed payload. Child identity snapshots precede loading, so
a same-byte replacement between verification and loading is refused.

`acknowledge()` issues one durable Parent nonce, including the exact original
ready-root SHA-256 and physical stamp, scope, payload SHA-256, producer identity
and the Parent's actual host PID/start/boot identity. The producer independently
reads this private consumption file, checks the actual live Parent identity,
and echoes the complete original nonce and original consumption bytes/stamp
into its `consumed` root before normal process return. This is transport
consumption evidence, not an effect ACK. A lost write response may be reconciled
only by the same warm issued nonce, its independent consumed echo and actual
original process absence; there is no second write or cold reconstruction.

A receipt requires the pinned consumed-root bytes and physical identity,
unchanged original chunks and consumed Parent intent, plus two actual ESRCH
queries and absence of the original PID in `/proc`. A live or zombie observer,
PID reuse, original file replacement or lost descriptor refuses completion.
A live polling refusal pins the consumed root, so a later same-byte replacement
cannot become its original. The actual original absence sample remains within
its unchanged 1.5-second host monotonic/epoch bounds through the final receipt
copy, physical checks and final passive process guard. Historical payload
facts are not made fresh by this process query. All originals remain retained.

The closed metadata families are `observerReturnTransportVersion: 1`,
`observerReturnConsumptionVersion: 1` and `observerReturnReceiptVersion: 1`.
Each scope binds the run, typed family, original request and actual producer
identity; the fresh Parent nonce and producer return ID have separate roles.
No generic `success`, feature result or expected state field is provided.
The existing `ChatSourceChunks` implementation supplies immutable opaque chunk
storage; its original format is unchanged. The host identity function is shared
with the existing Pico host-close owner, preserving its previous import path.

`self_tests.test_observer_return` uses two actual owned Python stdin processes,
original kernel identities/executable and entry hashes, real private files,
real immutable chunks, independent consumption reads and real reaped ESRCH.
Its opaque model payload and its typed admission callback are explicit feature
seams. Eleven cases cover original return, lost write response without replay,
wrong nonce, source and consumed-root replacements, replacement during initial
load, rootless consumption chunks, mutable caches, late receipt copy under a
frozen monotonic clock, and refusal of late original acquisition. Together with
the seven original process-owner cases, 18/18 passed in 2.403 seconds. No product
App, AssignmentClient, observer entrypoint, device or service was started.

The typed Pico Chat producer and Parent composition must explicitly use this
transport before it can close their process boundary. Existing v1 host-close
files gain no new return, native or whole-feature qualification from this API.

The literal-byte reader also owns an actual paired open-file description. It
checks the original kernel alias before returning bytes and before closing.
A recycled FD number pointing at the very same file is refused; neither
uncertain half is closed by the reader. They remain for actual host process
finalization. The adversarial fixture atomically replaces the worker's known
original read FD with a separate open description using `dup2`, verifies that
the foreign handle survives, then reaps that actual worker and obtains ESRCH.
The original reader failed this case (`accepted:closed`, 0.206 seconds).
After the narrow OFD fix, all 12 return cases plus the seven original process
cases passed, 19/19 in 2.474 seconds. No wire format or feature admission changed.
