# Retained Pico People request and cancel source

Feature 3/14 remains partial. The existing `PicoAvatarParent` now has a bounded
People child for the normal common-v16 `connection-request` and
`connection-cancel` actions. It observes the original two-role consent protocol,
not a relationship, authenticated account, loaded avatar or complete feature.
The complete observation and cleanup operations still refuse; no capability
triple is advertised.

## Existing Parent, separate role authority

The canonical router must resolve and pin Primary and Peer runtime bindings
under their respective source locks separately, before constructing the Parent
reservation. It must never obtain a Peer runtime while holding the Primary
source lock. `PicoAvatarParent(..., people=child_factory)` uses this sequence:

1. `reserve_people(request)` under the original Primary source lock captures
   the Parent before-original and persists the exact pending call. The child
   independently reads its actual full Parent file before reserving its call.
2. `execute_people(request)` runs after the real outer lock exit. Every source
   collection/input acquires only its own role's existing lock. All waits occur
   outside both locks.
3. `complete_people(request, receipt)` reacquires the original Primary lock and
   binds the exact child's immutable receipt, fresh Parent preferences/callback
   source and unchanged original phase. Child clocks remain checked through
   this completion; a fresh Parent sample cannot refresh old Peer facts.

`PicoAvatarPeople(store, binding, phase, primary_lock, roles, monotonic=..., sleep=...)`
receives exactly two role records. Each contains `binding`, `lock`, `native`,
`widgets`, `controls`, and `guard`. `native()` is the existing readonly
`NativePicoAvatarState`; `widgets()` supplies the complete original Navigation
survey. `controls(intent, before_send)` returns the existing
`TokenAvatarPeopleUI` and original Pico normal input transport. Candidate,
installation, process/session and foreground checks belong to each role's
existing runtime/guard. Distinct target fingerprints, process identities,
bridge sessions and actually observed avatar session IDs are required.

Each call pins the actual complete reserved Parent JSON bytes, SHA-256,
device/inode/owner/mode/link count/length/mtime/ctime. Every phase and final
issued-input fence rereads that same file using its original descriptor and
physical identity; no Parent SDK query or nested lock is needed. Changing even
the Parent inode with identical bytes prevents the first input. Historical
receipts validate this retained pending original without pretending that the
current, normally completed Parent file is still pending.

## Actual source and normal operations

The child navigates existing Home/pages/People controls, selects exactly the
nearby row matching the separately observed Peer avatar session, and presses
the existing Request Connection control. The original Pal consent must report
outgoing on Primary and incoming on Peer, with the same actual protocol request
UUID and mutually matching actual avatar sessions. Requested/ACK values cannot
supply these facts. Every visible Pal control must agree with the same original
page consent state.

Normal Cancel retains the original cancelled states on both sides. Actual
`Pal.qml::fromScript` keeps its prompt open for every state except `idle`,
including `cancelled`. Another normal Close is therefore required on Primary
and independently on Peer. The child does not import Phone's older assumption
that the first Cancel implies dialog absence. The peer persists its own exact
intent and final issued normal command under the Peer lock; it links that
original into the Primary child only after releasing the Peer lock.

After both original pages reach idle, original Native epochs, surveyed UI
elapsed clocks and the host clock must remain quiet for at least three seconds,
with gaps at most 500 ms, inside the unchanged 20-second observation window.
The original Avatar load/geometry/scale/storage state must remain unchanged
through each People call. A missing result, ignored input, changed role, foreign
request ID or expired original remains pending; a second execution cannot
repeat any attempted input.

Original native raw callbacks are archived before the existing reader parses
or validates them. Even a malformed/unavailable Peer response remains owned.
Successful full role observations are persisted before joining another role.
The child and separate Primary/Peer journals retain their complete originals;
cold receipts reread hashes, bytes and physical file identities. No private
journal is discarded or called retired.

Limits remain 128 paired frames, 128 source/raw frames per role, 128 inputs,
16 calls, 512 files and 16 MiB of complete stored/decoded owner originals in
this child namespace. Existing 64-KiB private files and 48-KiB packed envelopes
are unchanged. Overflow fails closed without eviction, truncation, retry or
larger limits. Source groups and original clock ages stay within 1.5 seconds
through the actual outer lock exit, copy and input/completion fences. The
combined Parent also counts these People/role journals in its existing
512-file/16-MiB target/run budget. These namespace budgets do not claim to count
all product caches, compiler files or the complete test fixture workload.

## Versioned compatibility

Original URL/Favorite routes continue writing Parent version 1. Only an actual
reserved People call promotes the existing Parent to version 2; the reader
accepts both versions. Older Parent readers must not adopt the new People child
grammar. Private People owner, role and original-frame formats are version 1.
There is no new public operation, scene setter or parallel journey. The original
shared common scenario, mandatory account/backend peer requirements and nine
independent observation fields remain unchanged.

Frozen Phone `a7be274da152b9d0b77e2fe5bb9874c5b1e18a31` supplies the inspected
role-store, distinct-session, pending-intent, common-operation and unlocked-wait
principles. Its full touch/mono AvatarPeople/Composite class, UI assumptions,
account transport and renderer evidence are not Pico sources and are not copied.

## Device-free evidence and remaining boundary

`test_avatar_people_owner.py` executes the real Parent/child/CAS, strict native
readers, normal token/control validators, private filesystem and a real separate
Node host. That host evaluates the two complete original `pal.js` engines in
separate VM contexts plus the unchanged production `peopleConnection.js` and
request serializer. The existing production world fixture is extracted,
unchanged, into `tests/javascript/support/people-world.js` for reuse.

Native Avatar/Model, Android/candidate/account metadata, Navigation/QML/pointer
delivery, Messages transport and the native/UI/host time sources remain explicit
host models. Separate VM contexts are not independent devices or a qualified
second installed process. The test's simulated clock windows are assertions of
owner logic, not measured hardware quiet windows. No compiler, full application,
live HTTPS account service, GPU/ray or device executes in this packet. No
relationship request is submitted during request/cancel; zero modeled POSTs
does not establish a real backend's relationship absence.

The ten owning cases pass in 28.746 seconds (29.159 externally): normal
request/cancel/Close both sides, cold full-original replay, ignored input with
no resend, foreign Peer request ID, held-Primary lock refusal, reused target,
frozen Native clock through Parent completion, original pre-input frame
substitution, unavailable Native raw retention, and same-byte Parent inode
replacement before the first issued input. Eleven owned/original product files
have matching complete SHA-256 and physical signatures before/after.

Evidence is retained under
`/home/user/.local/state/overte-pico-people-parent-authority-20261102-k09sbgf0`:
`owning.log`, `result.json`, complete before/after/source copies, all original
Node command/reply bytes and exact retained test-owned fixture roots. Earlier
six legacy Parent fences pass in 21.550 seconds and thirteen original Pal
production checks pass separately under
`/home/user/.local/state/overte-pico-people-final-20261102-tf789fs6`. Their sources
and command scopes are recorded separately; they are not mislabeled as one
full application run. Initial diagnostic errors and prior eight-/nine-case runs
remain separately retained, including the initial test-inventory/UUID errors
and the integer epoch-envelope correction. Full source copies are available for
the final owning stages; no complete source freeze is claimed for every earlier
diagnostic attempt.

The canonical factory/dispatcher and private registry/catalog integration is
now selected on the common tree. Set `OVERTE_PICO_AVATAR_PEER_TARGET` before
constructing the candidate adapter: its existing candidate seal pins the full
environment. The canonical route acquires Primary and Peer runtimes outside
both role locks, reserves under Primary, executes under each separate role
lock and completes under Primary. Orphan People/role journals block generic
cleanup even if the Parent root is missing.

Five canonical cases plus six legacy Parent cases pass35.886s with14 source
files' SHA-256 and full physical identities unchanged; final fixture originals
are retained in
`/home/user/.local/state/overte-pico-avatar-canonical-final-20261102-6sx59l2i`.
Native/candidate/UI/time remain explicit host models. Initial setup diagnostics
are separate; the earliest failed setup did not retain temporary originals.
Actual independent account/native consent histories, peer lifecycle/ownership,
relationship backend, accept/reject/remove, normal page restoration,
stereo/loaded-model evidence and complete callback/file/host retirement still
need composition. These are open
requirements, not successful skips or a completed Avatar feature.
