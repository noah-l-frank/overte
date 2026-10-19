# Source compatibility review during adapter implementation

The v1 fourteen-area extension has executable assertion logic and host
counterexamples. It has **no qualified product producer**. Native adapter work
has now exposed assumptions in several draft workflows that do not describe the
actual product UI. Host-model success does not resolve those mismatches. No
complete v1 area capability may be advertised as implemented on that basis.

These are test-contract corrections to make, not permission to add functional
product features merely to satisfy a test. The user has authorized E2E-only
instrumentation; functional product changes, builds and device runs remain
outside the current task. A changed published semantic contract must be
versioned before any complete area producer is enabled.

| Area | Actual reviewed source behavior | Draft v1 assumption requiring correction |
| --- | --- | --- |
| Audio | `interface/resources/qml/hifi/audio/LoopbackAudio.qml` exposes one Record-and-Play button, automatic three-second in-memory capture/playback and cancellation. `AudioClient::startRecordedVoiceTest`, `finishRecordedVoiceTest` and its native timer own those real phases. | Separate manual record-stop, save-file, preview-start/stop and discard controls are not that user flow. File recording is a different API. Test automatic capture/play/drain/completion, real cancellation/mute/background failure and actual original PCM; do not invent those controls. |
| Graphics on Phone | `scripts/system/+android_phoneInterface/phoneGraphics.js` restores a safe 0.65 default and accepts resolution 0.5..0.7. Its native settings switches/slider apply and persist immediately. | Universal resolution 1.0/shadows-on startup, a preview preset and an Apply/Cancel transaction do not describe this surface. Observe/restore the actual controlled original state and test real controls/persistence; no synthetic preset modal. |
| Scripts | `Application::loadScriptURLDialog()` loads the submitted URL directly. `Application::loadDialog()` opens **Open Script and Companion Files** and loads the selected local source. `TabletRunningScripts.qml` provides the normal From URL/File controls. Entity-script consent is a separate security feature/module. | Do not add fake client-script consent cancel/reject/accept to the URL or file workflow. Exercise the real picker selection/cancel/companion boundary and the separately owned entity-script consent contract. |
| Emotes | `scripts/system/+android_phoneInterface/phoneEmote.js` selects a real bundled clip, calls the one-shot override, hides the tablet, and restores the rig on its timer. Choosing the already active emote cancels it. Sit selects one of three actual clips randomly. | The chooser does not remain visible after each Play. A native override is active for ordinary plays too. Reopen the actual chooser for subsequent input and judge loaded/evaluated native clips, original poses/images and real peer effects. |

Additional source checks remain open, particularly the local JSON import versus
model creation/picker paths in NativeCreate, and the platform-specific private
Snapshot capture versus user export/share permission paths. Absence is not
inferred from a single source search. The other ten area drafts still require
their own final source/input/observer joins and independent actor evidence.

Implemented source packets remain useful and independently reviewable:
Phone's ordinary Create/Scripts foundations; Pico's ordinary native Script
foundation; iOS's explicitly unbound native Script component; and the shared
native lifecycle, evaluated animation/pose and memory-preview status sources.
They do not complete the fourteen v1 triples. Required capability gates stay
closed, original compiler-dependent tests remain excluded from no-build runs,
and all physical qualification remains unperformed.
