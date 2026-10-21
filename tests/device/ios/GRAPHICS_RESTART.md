# Ordinary iOS Graphics restart and original ownership transfer

`IOSGraphicsRuntime._graphics_restart` composes `IOSGraphicsRestart` with the
existing strict `RestartInputs`, canonical app stop/launch, installed-code
recovery and original kernel-process reader. This internal version-1 owner does
not advertise a Graphics capability or substitute transfer for fresh role images.

Before stop, both role indexes must have independent original samples and be
ready. The controller validates their original PNG/chunk/source archives and
freshly drains every owned native Vulkan consumer. An indexed acquisition with
no native owner does not satisfy this restart precondition. Original scene,
preferences, role indexes and actual drain packets are retained before input.
The existing restart input plan names exactly the scene and two stage-0 role
indexes. The surrounding source lock excludes concurrent role acquisition.

Stop and launch each persist one-send intent. A lost terminate reply can be
recovered through original stopped-process/source observations; a lost launch
reply uses the existing explicit installed-code recovery path and never sends
another launch. New observations must prove a different numeric PID/native
birth, exactly one actual launch-counter increment, an activation increment,
unchanged complete Graphics preferences and the same candidate/session/target.
The new original kernel source must report the old PID absent with `ESRCH`.
An ACK, app-state integer, new source label or native empty counters cannot
replace these joins.

The actual new subject v3 and scene-load source must show the seven owned scene
UUIDs absent and a distinct scene-load birth before transfer. Original generic
UI confirms no tablet/address overlay. Complete scene/preference proposals are
persisted before either mutable owner file. Reconstruction validates the exact
proposal contents against their preserved original inputs, including the native
packet, rather than accepting an arbitrary later-looking packet. Applying two
CAS writes can recover when only the first succeeded. Foreign owner contents
are rejected. Normal Go To and View-menu inputs then rebuild the measurement
scene and the measured original preference baseline remains available for
ordinary final restoration.

Historical role/source headers and original native retirement receipts remain
decodable after separately authorized final cleanup removes old files. This
decoder is explicitly not PNG/effect validation or a live process check. Actual
PNG/chunk archives are validated through the private files before stop. Current
images, actor publication, WK view/callback lifetime and the final three-second
quiet/metadata retirement still belong to the unfinished whole-run coordinator.
The controller's final-retirement path is present but has not yet been exercised
through that complete lifetime/finalization composition.

The ownership decomposition was reviewed at frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`. iOS retains original numeric PIDs,
independent clocks, generic controls, source/installed-code recovery, existing
input sessions and private original Vulkan files. Phone package/ADB/QML, empty
world-capture-store and relaxed restart assumptions are not iOS behavior.

Twelve no-build restart cases pass: ordinary restart/restoration, lost stop,
lost launch, ignored stop, live old PID, reused birth, missing launch counter,
changed candidate, reset preferences, partial CAS recovery, failed persisted
intent and altered native proposal. An earlier 56-case selection also passed
restart/background/samples/preferences/scene/history regressions; the final
proposal check and its additional case then passed the twelve-case selection.
Tests use real temporary ownership/image files and loopback scene responses,
actual existing iOS HTTP/AFC UI framing and synthetic native/OS/kernel/candidate
SDK boundaries. They do not establish native compilation, physical process
behavior, GPU timing or device qualification. Graphics remains partial.
