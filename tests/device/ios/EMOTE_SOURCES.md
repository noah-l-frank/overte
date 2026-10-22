# iOS Emote original sources and ordinary input ownership

Feature **5/14 remains partial**. These components supply actual source selection,
ordinary controls, immutable original acquisition and one-send action ownership.
They enable no complete Emote capability. Native C++ remains uncompiled and all
iOS devices are untested. Host simulations establish adapter logic only.

## Actual selected product

The iOS selector order in `CapabilityProfile.h` includes
`ios,mobile,touch,android_phoneInterface,android_interface,webview`. The selected
`+android_phoneInterface/defaultScripts.js` loads its native-QML `phoneEmote.js`.
The existing reviewed touch source keeps its chooser open and uses automatic
one-shot completion for Sit too. The tablet Web source has different Sit
semantics and is not substituted for iOS input.

`native_script_roots.py` reads actual `PathUtils::defaultScriptsLocation()`.
`emote_source_profile.select_from_roots` joins original root snapshots, actual
assigned manager membership and submitted UTF-16 source bytes against the
existing reviewed pins. A basename, normalized `~` manager key, platform name or
requested URL is insufficient. Unknown or multiple active sources are errors.

`NormalEmoteControls.h` surveys the actual selected QML component, real model,
active selection, button indices, grid clipping and scroll state. Its
`componentSourceSha256` hashes the original **component URL**, not QML bytes or
compiled execution identity; installed-candidate binding remains a separate gate.
The iOS `IOSEmoteIO` projection preserves original native UUID tokens and clocks.
Inputs use existing native source-token sequences and ordinary Qt mouse/wheel
events. No `fromQml`, `overrideAnimation`, requested pose or product property is
injected. Generic tablet navigation remains normal input.

## Original Rig and actual replicated effects

Animation history v2 records the actual VM method invocation's manager, submitted
code identity and original invocation time. Queued `MyAvatar` delivery carries
that native-only context to the actual Rig call. Instrumentation is compile gated
and inactive outside `--testScript`; ordinary product dispatch is preserved.
The reader still accepts history v1 for existing callers, while Emote measurements
require v2. Original range/rate, loaded clip evaluations, changed joints, restore
calls and later inactive evaluations remain independent of chooser ACKs.

`emote_rig_measurements.py` derives the actual name and Sit1/2/3 from loaded native
URLs, never from the requested name. `poseProgress` counts changed actual joints.
The early-restoration boolean uses the measured original clip interval with the
250 ms margin; no button/timer cause is invented.

`AvatarReceiveObservation.h` adds a separate original receive ledger. It records
only a successful `AvatarData` parser tail inside an actual sourced AvatarMixer
context. Locally generated replicas and Script pose setters do not enter it.
Records preserve actual session/mixer identity hashes, consumed packet digest and
length, native receive time, sampled incoming joints with explicit null default
pose components, advertised model URL and target scale. Advertised resources are
not loaded renderer evidence. No raw network or session selector enters public
facts. `native_avatar_receive.py` validates immutable source/process/counter
continuity and real fresh incoming motion; frozen or antipodal quaternions and
missing/default-only joints cannot satisfy motion. Incoming rotations are
absolute Rig rotations; existing Emote final poses are relative. They are not
compared as if they shared coordinates. Actual remote renderer/Rig observations
remain a separately acquired source.

## Durable ownership and clocks

`IOSEmoteSources` stores one role's immutable original frames through the private
inode/hash-checked archive and bounded manifest index. Each read journals
responsibility before fixture/native dispatch, then retains every accepted
original. A partial interrupted acquisition stays owned on reconstruction and
cannot be silently reread. Historical reconstruction restores original source
floors and never claims a current read. All selected source, native Rig,
QML/control, fixture-phase and process identities are checked together.

One `NativeClockAcquisition` brackets the unchanged root/Script/Rig/UI packets.
Host fixture activation and acquisition times remain separate from original
native epochs. A phase crossing is archived but cannot become a stable current
sample. A slow final durable write cannot mint a fresh envelope around that frame.

`IOSEmoteActions` journals every Qt or UIKit delivery before sending it. It accepts
only the existing v16 action grammar. Repeating a completed call returns its
retained ACK without another input; a lost SDK/Qt/source return prevents resending
or skipping responsibility with another ticket. `wait-complete` sends no input,
restore call or expected-duration sleep. Actual animation success must still be
measured independently. Initial admission refuses an unowned tablet or active
override. These actions alone do not restore arbitrary pre-existing overrides.

`IOSEmoteRuntime` provides internal factories on the existing candidate-qualified
session and shared source lock. It does not create sessions, modify capability
advertisement or introduce an alternate feature-dispatch path.

## Verification and remaining integration

The prerequisite regression contains 95 host tests: legacy animation history,
source/root/caller/Rig joins, real Node probe and fixture dispatcher, ten normal
Emote controls, original receive motion, original archive/clock joins and durable
lost-delivery action behavior. See the corresponding `test_ios_emote_*`,
`test_native_avatar_receive`, `test_native_script_roots`,
`test_emote_rig_measurements` and `test_token_emote_ui` suites. Tests use synthetic
native/SDK/Rig observations and do not execute C++, a renderer or a device.

Remaining whole-area obligations are an owned ordinary scene/view setup and
restoration; real original challenge and changed-avatar pixels; independently
acquired timing plus actual remote received/rendered pose effects; complete
act/observe/cleanup dispatch and independent publication; actual callback/timer,
UI/scene/GPU lifetime drainage; repeated three-second quiet cleanup and safe
retirement without resetting native history. The whole v16 journey must pass
before the complete triple is advertised.

Shared reconciliation manifest: `native-animation-history` writes2/reads1,2;
`native-animation-caller`, `native-script-roots`, `native-emote-controls`,
`native-avatar-receive`, `native-avatar-receive-observation`, `ios-emote-controls`,
`ios-emote-originals`, `ios-emote-sources`, `ios-emote-actions` are v1;
`emote-rig-measurements` is v2. `emote-source-profile` remains v1. The reusable
frozen Phone provenance is `fe4684bf46585088370b3a328a738f147e670b97`; Android
transport, package and host/native clock assumptions were not ported as iOS facts.
