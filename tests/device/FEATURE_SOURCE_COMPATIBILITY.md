# Source compatibility review during adapter implementation

The fourteen-area extension has executable assertion logic and host
counterexamples. It has **no qualified product producer**. Native adapter work
has now exposed assumptions in several draft workflows that do not describe the
actual product UI. Host-model success does not resolve those mismatches. No
complete area capability may be advertised as implemented on that basis.

The current contract is version 3. Version 2 corrected Scripts to the ordinary
file-bundle picker and actual relative companion execution, with negative
cases for execution after cancellation, missing companions and frozen ticks.
Version 3 now corrects Audio to its automatic memory-preview cycle.
See [the explicit migration](feature_journeys/CONTRACT_MIGRATION.md).

These are test-contract corrections to make, not permission to add functional
product features merely to satisfy a test. The user has authorized E2E-only
instrumentation; functional product changes, builds and device runs remain
outside the current task. A changed published semantic contract must be
versioned before any complete area producer is enabled.

| Area | Actual reviewed source behavior | Draft v1 assumption requiring correction |
| --- | --- | --- |
| Audio | `interface/resources/qml/hifi/audio/LoopbackAudio.qml` exposes one Record-and-Play button, automatic three-second in-memory capture/playback and cancellation. `AudioClient::startRecordedVoiceTest`, `finishRecordedVoiceTest` and its native timer own those real phases. | **Common flow corrected in version 3.** It checks automatic capture/play/drain/completion, native phase/history/frame relations, muted rejection and mute/background/cancel behavior, original input PCM and independent acoustic output. OS permission denial/recovery remains in the composed foundation. File recording is a different API; no Save/Preview/Discard control is invented. |
| Graphics on Phone | `scripts/system/+android_phoneInterface/phoneGraphics.js` restores a safe 0.65 default and accepts resolution 0.5..0.7. Its native settings switches/slider apply and persist immediately. | Universal resolution 1.0/shadows-on startup, a preview preset and an Apply/Cancel transaction do not describe this surface. Observe/restore the actual controlled original state and test real controls/persistence; no synthetic preset modal. |
| Scripts | `Application::loadScriptURLDialog()` loads the submitted URL directly. `Application::loadDialog()` opens **Open Script and Companion Files** and loads the selected local source. `TabletRunningScripts.qml` provides the normal From URL/File controls. Entity-script consent is separate. | **Common flow corrected in version 2.** Native actual engine/require histories now exist on all three source branches. All three branches now have normal source-bound file-bundle controls and private original-byte staging/cleanup intent. Picker/engine ownership, restart handoff and the full companion/effect observer joins remain missing; URL foundations do not establish them. |
| Emotes | On the Phone adapter product base, `scripts/system/+android_phoneInterface/phoneEmote.js` selects a real bundled clip, calls the one-shot override, hides the tablet, and restores the rig on its timer. The common-base PhoneEmote copy does not hide the tablet; the desktop/Pico `emote.js` surface has different Sit/cancel behavior. Choosing the actually running startup script must precede binding an input recipe. | A native override is active for ordinary plays too. The panel lifetime and Sit restoration cannot be assumed identical across these sources. Reopen the actual chooser as required and judge loaded/evaluated native clips, original poses/images and real peer effects. No product change is authorized to make a draft test pass. |

Additional source checks remain open, particularly the local JSON import versus
model creation/picker paths in NativeCreate, and the platform-specific private
Snapshot capture versus user export/share permission paths. Absence is not
inferred from a single source search. The other ten area drafts still require
their own final source/input/observer joins and independent actor evidence.

Implemented source packets remain useful and independently reviewable:
Phone's ordinary Create/Scripts foundations; Pico's ordinary native Script
foundation; iOS's explicitly unbound native Script component; and the shared
native lifecycle, evaluated animation/pose and memory-preview status sources.
They do not complete the fourteen version 2 triples. Required capability gates stay
closed, original compiler-dependent tests remain excluded from no-build runs,
and all physical qualification remains unperformed.
