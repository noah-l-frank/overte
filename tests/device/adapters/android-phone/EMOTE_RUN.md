# Phone Emote setup and input run owner, version 3

`PhoneEmoteRun` joins the existing View, Scene, per-role Source, normal Input,
Background, Namespace and Cleanup Input components under the same source lock.
This internal owner is not a complete feature adapter and is deliberately not
registered as `feature.emotes.*`. Public role/image/motion observations,
independently credentialed actor publication and whole-run resource/file retirement are still
required. Its private `prepared` phase requires the actual original world/Script/
cache admission and completion of its actual setup children. Native source
remains uncompiled; device behavior is untested.

Construct with the real Phone adapter/selector, actual Emote PhaseFixtureReader,
private absolute artifact directory, explicit integral image extent and marker
ROI, plus the explicit [admission policy](EMOTE_ADMISSION.md). Geometry uses the existing native fixture input grammar. Those inputs are
stored unchanged and cannot be replaced on reconstruction. The constructor does
not open a foreground-only target source, so reconstructing the run while an
owned background action is interrupted remains possible.

The private control `phone-emote-run.json` contains exactly `emoteRunVersion:3`,
`runId`, `fixtureUrl`, `artifactRoot`, `imageExtent`, `markerRoi`,
`admissionPolicy`, `payload`. Its
existing bounded packed payload holds one
`{phase,binding,segment,baseline,call,cleanupTicket,admissionSha256}` state. Binding is the actual
existing candidate/process/session context. Baseline references an original
primary frame by revision/hash. Call is an actual normal action or null. Current
segment retains the existing 0..15 bound. Phases are `preparing`, `prepared`,
`acting`, `active`, `switching`, `cleaning-inputs`, `inputs-restored`,
`restoring-resources`, `resources-restored`. All cleanup phases contain the real
cleanup ticket. No phase asserts product rendering or full
resource retirement. General Phone cleanup fails while the run control remains.

`prepare()` requires a real baseline. A new run refuses orphaned Emote component
metadata and persists parent responsibility before any child source request or
setup input. It independently observes original native inactivity and a closed
tablet, completes the real three-sample world/Script/cache admission, then invokes
the real normal View preparation and actual Scene fixture
preparation in order. A missing/partial View completion blocks Scene preparation.
Both actual child states and the unchanged actual fixture baseline are checked
before prepared is committed. Interrupted setup stays preparing; it cannot be
completed under a later ordinary fixture phase. The parent retains the SHA-256 of that exact private admission header. Every
normal action reopens its originals before input; all current sources additionally
enforce the same actual executable/world policy through source version 4.

`act(call)` requires prepared/active ownership and the exact actual fixture
activation. The parent writes acting/call before ordinary input. The normal
Input component supplies durable intent-before-delivery and consumed receipts;
the parent does not turn `performed:true` into measured feature state. Its active
phase records input completion only. A failed parent completion commit can be
reconstructed against the actual acknowledged child without another input. A
lost child return remains incomplete and requires the existing reconciliation.

For background/resume, the OS owner is reconstructed before any foreground-only
source factory. It owns its single Home/activation and actual OS/native cycle;
the parent compares its original binding and actual fixture ticket. Neither a
background retry nor cleanup replays the old cycle. `cleanup_inputs(call)` first
persists the actual cleanup ticket, recovers owned foreground through the OS
owner, releases any pending namespace freeze and invokes the real ordinary
Cleanup Input component. Only after actual native/UI restoration does it commit
inputs-restored and return that original cleanup-input header. It deliberately
retains Scene/View/Background, timer, actor, image, file and parent ownership.
It cannot produce a green public cleanup or delete those records.

`acquire(role)` obtains this role's own original source frame through its actual
namespace acquisition guard. No expected state, primary effect or peer facts
are forwarded. `request_switch(call)` reserves only a real new play/Sit after a
new inactive primary frame. `acknowledge_switch(role)` acquires each unfrozen
role independently before freezing its actual originals. Actor calls occur
under separate, short held-lock operations, not a parent loop that monopolizes
the source channels while waiting for another process. Repeated frozen-role
acknowledgment reopens its existing proof and never acquires/relabels a new one.

`advance_switch()` persists the enclosing transition only after the actual
two-role child lease commits. If that parent write fails, reconstruction observes
the real child current/closed call and commits the same next namespace without
advancing twice. The pending new normal call stays bound in acting state; another
action cannot consume its new namespace. Cleanup also reconciles a committed
child transition before releasing it, without dispatching that reserved play.
Closed source/input headers and original frames remain intact.

All target acquisition, ordinary input and phase deadlines remain the existing
component deadlines. Every coordinator transition uses the existing private
64 KiB compare-and-swap journal under the held source lock. Failed/ignored parent
writes invalidate that live owner. No higher limits, source reset or expected
measurement are introduced. A partial source acquisition still needs its
explicit original transfer/recovery before that source can be used again.

Host checks use actual Source/Input/Namespace/Background/Cleanup code over
synthetic native/Qt/SDK packets. Setup completion boundaries are explicitly
doubled in these coordinator tests; real View/Scene original-proof internals
remain covered separately. Counterexamples include ignored setup/native effects,
orphaned ownership, wrong phases/configuration/candidate, lost input/parent
commits, partial and committed namespace transitions and background cleanup
ordering. They qualify orchestration/test logic only.


## Resource cleanup and independent quiet windows, version 2

Version 2 reads unchanged version 1 input-owner records; reconstruction alone
never rewrites them. The next explicit transition writes version 2. New resource
phases cannot masquerade as version 1 records.

`cleanup_resources(call)` first runs the real owned input/foreground cleanup,
then writes restoring-resources before invoking Scene cleanup followed by View
cleanup. These real components verify Browser/entity drainage and exact original
camera/zoom/preferences/touch restoration. Missing Scene release blocks View
restoration; missing View restoration blocks resources-restored. The actual same
cleanup ticket is checked between child operations. Failed/partial cleanup keeps
parent and child ownership. Repeated cleanup reobserves actual child restoration
through their existing idempotent paths. The returned private scene/view headers
remain owned; they are not deleted or turned into a public success.

`cleanup_quiet(role)` is allowed only after resource restoration and invokes that
role's own real Lifetime reader. It independently obtains native/UI/configured
source and actual Script-work originals until the existing three-second quiet
window completes. Primary and actor keep separate source/work transcripts; one
role's window cannot replace the other. An actual selected Emote timer, unknown
work, live callback/evaluation, native override or visible UI blocks completion.
Known unrelated default-manager work retains its existing scoped semantics.
The method returns the original role lifetime header and retains its journal.
Its final fixture and binding checks remain inside the original native/host/
monotonic freshness window; a slow final check cannot redate a historical quiet
proof as current. All original timestamps remain unchanged.
It supplies no credentialed actor publication or whole-retirement acknowledgment.

Parent validation and orchestration tests reuse the actual scoped timer source
and independent OS/native/UI sources. Explicit setup/resource completion doubles
still test only child ordering and parent ownership; they do not qualify native
View/Scene product behavior. Original View/Scene/Lifetime counterexamples remain
registered separately. All child and original-file metadata is deliberately
retained until the remaining whole-run transfer/retirement protocol is complete.


## Mandatory original admission, version 3

New runs require `admission={domainUrl,domainId,domainMarkers,probeUrl}`; missing
configuration does not create parent or child ownership. Admission is read-only
and must complete before normal View/Scene setup. Its exact original header hash
is saved in `admissionSha256`. Missing/changed headers or original files block
later inputs. The configured policy remains anchored in the unchanged parent
header and all version 4 primary/actor source headers. Every subsequent source
frame independently acquires the world probe and validates all actual executable
membership, so a late foreign compilation/domain cannot borrow initial approval.
Namespace successors inherit the same policy and cannot downgrade to unchecked
version 3 sources. Checked primary and unchecked actor contexts cannot be joined.

An already owned interrupted background action can check the exact pinned
admission header before OS recovery without creating a foreground-only getter.
The actual same owned background call/binding is required. After foreground is
observed, its originals are reopened before action completion. This exception
permits recovery of the existing cycle only; it does not authorize a new Home.
Cleanup retains its separate foreground-first recovery regardless of failed
admission or input state.

Versions 1 and 2 remain readable for cleanup. Their former prepared/active state
contains no admission hash and cannot authorize new setup or inputs. Cleanup
writes version 3 while preserving the explicit missing approval; it cannot turn
legacy source history into approved current evidence. No old source journal is
silently migrated into a checked namespace. The remaining complete adapter must
still own public observations, credentials/actor publication and verified full
resource/original-file/host-journal retirement before capability registration.
