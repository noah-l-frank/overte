# Durable ordinary Pico Emote inputs

`PicoEmoteInputs` v1 joins normal `open`, `play`, `sit`, `override`, `cancel`,
`wait-complete` and `close` inputs to the existing original phase reader and
[Pico original sources](EMOTE_SOURCES.md). It remains a private component:
`performed` means the input was handled, never that playback, pixels or release
have been proved. It advertises no complete feature capability.

The durable phase, intent, receipt and immutable archival design is selected
from fixed Phone commit `abb7f6b60d97daf17752aadf94e2b5df099bb7ba` and documented
in [the selection manifest](PHONE_SHARED_EMOTE_INPUTS_20261022.json). Actual
`PicoScriptIO.tablet`, the existing OpenXR controller path and original
`PicoEmoteIO`/`TokenEmoteUI` pointer transport replace the Phone SDK/UI boundary.
The private factory requires the actual primary source journal, shared source
lock, candidate/process/VR binding and original existing input session.

## Original input ownership

A new call is tied to its actual closed fixture ticket/verb/inputs. Each Qt
pointer or scroll intent is saved before delivery. A play/cancel intent first
acquires and retains a fresh original source barrier matching the exact UI
control/token. Cancel additionally requires the original active chooser name
and native active Rig. A native Qt receipt joins advancing source cursors and
the actual original command sequence; it does not claim a playback effect.

Each tablet controller operation similarly retains an original before-frame
and writes `issuing` before the existing OpenXR transport. Its independent
after-frame must show the actual visibility edge and newly observed generation
while Qt command sequence and process/bridge stay bound. Neither a transport
ACK nor a requested target visibility is substituted for that original source.

Lost delivery/receipt, ignored effect, changed tokens/context and missing source
response retain the original journals. Reconstruction cannot repeat the input.
An already acknowledged identical call can report input idempotence without
delivery; independent current effect observations remain mandatory.

Completed input records use private immutable originals and bounded manifests.
`recover_archive` finishes only exact frozen archival bytes and matching
manifest prefixes. It invokes neither product input nor a native read and
returns no current observation. Incomplete source acquisition retains its own
responsibility independently. Neither operation retires journals.

## Host checks and remaining composition

The owning `emote-original-sources` group tests normal open/play/cancel/close,
actual controller-generation transitions, ignored/lost Qt and controller
boundaries, missing original sources, archival recovery, fixture/candidate
changes and historical replay. `normal-emote` also verifies the actual private
Pico factory and retained input ownership after base process teardown.
Qt/OpenXR/Rig boundaries in these device-free checks are explicitly synthetic;
the actual native component compiler checks remain separately qualified.

One counterexample deliberately leaves the synthetic native Rig on its older
Waving override after consuming a Crying click. Input acknowledgement contains
no effect state and cannot satisfy the independent playback measurement.

The [original effect join](EMOTE_EFFECTS.md) now supplies measured playback,
natural completion, early cancel and replacement. The complete owner still
needs interruption/background recovery, all Sit variants, current
two-eye images, independent actor and actual callback/timer/Qt/native-resource
retirement. General teardown retains both source and input journals and refuses
success while they remain. No application build or device qualification is
established by these host results.
