# Original whole-tree iOS scene inventory

This passive source supplements the fixed navigation marker/pose source. It
enumerates the actual whole `EntityTree` map, including local/avatar/domain
entities outside the camera or any spatial radius. It does not publish a feature
capability, import/delete entities, establish a pristine original fixture or
prove renderer/Web/GPU consumer retirement.

Version 2 additionally retains the actual most recent successful import's
[commit origin](../native/SceneCommitOrigin.h). Version-1 originals remain
readable, with no implied origin. The original request's byte count/SHA-256 and
resource hash are captured at the actual local-file or remote import commit,
together with a bounded whole-tree editable-wire snapshot and native UTC and
monotonic brackets. No later query may select or replace that baseline. This
instrumentation is gated by `OVERTE_E2E_FEATURE_TESTS`, iOS and `--testScript`.
It invokes no entity setter, navigation, load, reload or callback cancellation.

The origin records process/source birth, observed current request generation,
successful import count, completeness and its latest original. It is a snapshot
of the latest successful commit, not a full import-history ledger. The separate
scene-load source retains request and delivery lifetime history. Failed/stale
later requests cannot make the old origin current. The original record remains
immutable while its import count stays unchanged. Counter/source rollback,
completeness resurrection or a future/foreign commit clock is rejected. Import
overflow or an incomplete native anchor fails closed until a separately admitted
source cohort. Both current and anchor inventories must fit the existing total
packet limit; oversized combined evidence is unavailable, never truncated.

`unchanged_since_commit(original, actual_scene_url)` requires a current genuinely
committed generation and no live scene-load leases. The actual resource, original
byte count and commit clocks must match that same native request. It compares
every current entity ID/host/editable-wire hash to the independently frozen
commit map. An unsaved edit, addition, deletion or replacement is rejected
before a scene may be left. Notification revisions and creation/edit clocks
remain original and separate from the declared editable semantics. Legacy,
missing or incomplete origins cannot establish this condition. Historical
comparison stays historical; it cannot refresh the original or reset an anchor.

This is one necessary admission condition. The whole coordinator still needs
actual stable original resource-byte availability and matching restored body
hash, original pose/camera/settings/panels, absence of pending work, ordinary
input and independent repeated cleanup. The generic fixture's script may make
real edits after commit; those edits are not silently approved as reloadable.
A separately chosen static base-scene input remains to be supplied. No source
packet alone establishes a pristine whole product or grants a feature capability.

The native `feature-ios-scene-inventory` command is closed: schemaVersion 1,
a new iOS nonce, action and run ID. No expected entities, ID filter, radius,
output digest or requested state is accepted. The existing HTTP/probe/AFC
architecture returns the original fixed `feature-ios-scene-inventory.json`.
Repeated polling does not issue that command again; unavailable stays
unavailable.

`EntityTree::featureEntityInventory` exists only under
`OVERTE_E2E_FEATURE_TESTS` and iOS. Runtime tracking requires explicit
`--testScript`; the query runs on the application thread. It preserves the
existing Tree-to-map read-lock order. The diagnostic tree birth and notification
revision record actual map insert/removal/clear and entity-change notifications.
No product lock, entity update order or function behavior is repaired or changed.
The revision is a notification sequence, not a claim that every notification
changed an editable value.

Each bounded row contains the actual entity ID/host and an opaque fingerprint
under `native-entity-edit-wire-v1`. The native source copies actual properties,
serializes the copy with the existing native entity-edit packet encoder, and
hashes those real bytes without sending a packet or creating a script engine.
Only the detached copy normalizes creation/edit times; requested fields exclude
creation time, last-edit author and simulation ownership. Original creation and
before/after edit clocks remain separate exact decimal uint64 strings, including
unknown/sentinel values. The profile covers the declared editable-wire fields;
it is not an assertion about every non-network/render-cache attribute.

The actual application entity receives no setter. Private property/script/URL
contents are not exported as raw data. The complete map must fit 512 entities,
each encoded row must fit its bounded buffer, and timestamps/revision must agree
across the read. Overflow, unknown entries, encoding failure or a detected change
retain an explicitly incomplete inventory. An empty partial list cannot prove
absence. This profile's native codec/timing behavior remains uncompiled and
physically unqualified.

The native bracket has its own source birth, sequence, PID and original
UTC/elapsed clocks. A nested original scene-load snapshot preserves its own
request generations, resource hashes, phases and pending lease history. No
scene event is retimed. Python acquisition uses the existing distinct native
clock reads and 1.5-second host-monotonic validity boundary. Host UTC or AFC file
metadata is not native freshness.

`semantics` projects only complete ID/host/encoded-byte/hash rows; `same_entities`
can compare separately admitted stages while preserving their original clocks.
It does not admit a new installed candidate/process by itself. `absent` means
only nonmembership in the complete actual map. Objects retained by render jobs,
Web surfaces, callbacks or GPU copies require their separate original lifetime
sources and quiet windows.

Host tests execute the actual command/factory/transport validators and actual
probe dispatcher, with native tree/codec/SDK boundaries modeled. They reject
partial/radius-like absence, missing unowned entities, changed editable data,
stale/foreign process/tree/scene histories, duplicate IDs, count inconsistency,
unsafe uint64 coercion and missing hooks. Native compilation and device execution
remain unperformed. Whole Worlds admission must still establish the supported
original scene, compare actual unowned state and integrate this source into its
pending durable owner, restoration, restart and independent publisher.
