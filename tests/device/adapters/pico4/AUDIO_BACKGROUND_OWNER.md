# Normal Audio background and return

`PicoAudioBackground` continues an actually capturing `PicoAudioCaptureOwner`
through the existing normal OS HOME and controlled activation routes in
`PicoGraphicsBinding`. The current Audio `PhaseFixtureReader` supplies the
original background-resume input ticket. The owning PID/start, installed
candidate, target fingerprint and input-session identity stay fixed.

A durable HOME intent precedes its single possible delivery. The returned
acknowledgement does not establish background state. Independent original OS
process/foreground reads must observe that same process backgrounded over a
250 ms host sample window; gaps over 500 ms reset the window while retaining
all earlier original samples. A separate durable activation intent precedes
its single delivery. Cold recovery uses only private archives and those OS
sources until the original process is independently foreground again. A host
monotonic clock regression cannot reuse an earlier observation window. It never
repeats an uncertain HOME or activation or initializes/queries Qt while hidden.

After return, fresh original native, Audio settings, canonical Audio.qml page
and Lifecycle samples must agree. The original native instance/cycle must show
`cancelled` with `backgrounded`, `lifecycle-stopped` or
`input-or-lifecycle-changed` and empty live product buffers. That event must
follow the actual last pre-HOME source fence and original fixture activation.
Original [Qt lifecycle counters](../../native/FeatureLifecycle.h) must advance
in both background and activation, preserve launches, and then stay fixed over
three seconds of fresh original quiet across all nine native/host clocks.
The shipped [AudioClient pause/stop paths](../../../../libraries/audio-client/src/AudioClient.cpp)
publish these actual cancellation causes; requested outcomes do not enter the
source query or recorded history. The actual Qt host contract also executes the
entire unchanged `setAudioPaused` body and original 250 ms preview polling
callback after explicit input availability loss. Their cancellation events and
actual stopped timer are measured independently. These explicit format/input
boundaries do not claim to execute Android HOME or a physical microphone.

The page identities and current page, original input peak setting, settings,
mixer gains, absent editor/VRKeyboard and original mute state must persist.
All full raw packets, the immutable pre-input capture archive and original OS
samples remain private. A crash after a read-only returned observation can
accept only its exact capture-journal frame prefix extension, with the same
original operations/ticket/source scope and no ordinary action. Changed or
missing parents, foreign processes/candidates, acknowledgements without actual
OS/native effects, stale terminal events and interrupted final quiet fail with
journals retained. Standalone background journals also block base cleanup and
competing native Preview release.

This source does not claim continuous native hidden editor/keyboard history.
The existing `LifecycleBackgroundHistory` v1 is bound to an original Chat
editor; an Audio page is not such an editor. No Chat/editor original, hidden
timer frame or new sampling timer is invented or repurposed here. No native or
product code changes, process restart or journal retirement are performed.
Accepted sink PCM remains distinct from an independent acoustic observation.
Complete Audio qualification still needs its independent acoustic/peer channels,
normal final X/settings/peak/PCM closure and actual remaining resource closure.

The existing `audio-capture-owner` selection runs these owners and original
readers with explicit independent host OS/audio boundaries. This is device-free
source/host evidence, not a physical or device result.
