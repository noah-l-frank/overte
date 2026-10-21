# Phone Emote setup and input run owner, version 1

`PhoneEmoteRun` joins the existing View, Scene, per-role Source, normal Input,
Background, Namespace and Cleanup Input components under the same source lock.
This internal owner is not a complete feature adapter and is deliberately not
registered as `feature.emotes.*`. Whole approved-world/Script admission, passive
animation readiness, public role/image/motion observations, independently
credentialed actor publication and whole-run resource/file retirement are still
required. Its private `prepared` phase means only that its actual setup children
completed. Native source remains uncompiled; device behavior is untested.

Construct with the real Phone adapter/selector, actual Emote PhaseFixtureReader,
private absolute artifact directory, explicit integral image extent and marker
ROI. Geometry uses the existing native fixture input grammar. Those inputs are
stored unchanged and cannot be replaced on reconstruction. The constructor does
not open a foreground-only target source, so reconstructing the run while an
owned background action is interrupted remains possible.

The private control `phone-emote-run.json` contains exactly `emoteRunVersion:1`,
`runId`, `fixtureUrl`, `artifactRoot`, `imageExtent`, `markerRoi`, `payload`. Its
existing bounded packed payload holds one
`{phase,binding,segment,baseline,call,cleanupTicket}` state. Binding is the actual
existing candidate/process/session context. Baseline references an original
primary frame by revision/hash. Call is an actual normal action or null. Current
segment retains the existing 0..15 bound. Phases are `preparing`, `prepared`,
`acting`, `active`, `switching`, `cleaning-inputs`, `inputs-restored`. The latter
two contain the real cleanup ticket. No phase asserts product rendering or full
resource retirement. General Phone cleanup fails while the run control remains.

`prepare()` requires a real baseline. A new run refuses orphaned Emote component
metadata and persists parent responsibility before any child source request or
setup input. It independently observes original native inactivity and a closed
tablet, then invokes the real normal View preparation and actual Scene fixture
preparation in order. A missing/partial View completion blocks Scene preparation.
Both actual child states and the unchanged actual fixture baseline are checked
before prepared is committed. Interrupted setup stays preparing; it cannot be
completed under a later ordinary fixture phase. This owner still needs the full
approved-world/Script/cache admission fence before a public adapter invokes it.

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
