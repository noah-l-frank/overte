# Mobile Scripts source contract introduced in v16

Version 16 corrects the restart behavior of the reviewed Android Phone, Pico
and iOS sources. `Application::loadDialog()` still uses the normal **Open Script
and Companion Files** picker; accepting a primary calls the ordinary user-loaded
script API without inventing entity-script consent. `saveScripts()` records
user source URLs, but the mobile startup branch deliberately calls
`loadDefaultScripts()`, not the saved-user-list `loadScripts()` path. The iOS
product branch includes `Q_OS_IOS` in that mobile condition. The selected mobile
JavaScript entry points load fixed system defaults and do not replay
`RunningScripts`. A saved setting is therefore not proof of automatic execution.

The declared source recipe is `mobile-defaults-only-v1`. It is a compatibility
description, not a measured result or a substitute for runtime observations.
Desktop saved-user autoload and future product changes require an explicitly
reviewed contract/profile; do not silently stop an automatically restored source
to make this recipe pass. No qualified v15 full-area producer exists to migrate.
The shared registry now reads only v16; previous inventories/matrices remain
historical. Native helper and existing public foundation API versions are separate.

The 19 checkpoints use these exact normal inputs:

| Steps | Verbs and controlled inputs |
| --- | --- |
| 1–3 | `open`, `picker-open`, `picker-cancel` |
| 4–6 | `picker-open`, `picker-accept {resource:'script.js'}`, `stop-owned` |
| 7–8 | `picker-open`, `picker-cancel` |
| 9–10 | `picker-open`, `picker-accept {resource:'script-bundle/main.js'}` |
| 11 | `restart-app`: three seconds of actual absent execution and closed UI |
| 12–14 | `open`, `picker-open`, `picker-cancel`: execution remains absent |
| 15–17 | `picker-open`, `picker-accept {resource:'script-bundle/main.js'}`, `stop-owned` |
| 18–19 | `load-url {resource:'missing.js'}`, `close` |

At each successful import, actual owned engine/code/relative companion and
advancing owned local Box effects remain mandatory. Stop and cancellation must
leave no owned execution/effects.

`restart-app` has **no script-load/restart/stop action and no manager-reopen
action**. Use the existing normal application stop/launch routes. Require an
original old-PID exit observation, a genuinely new qualified process/native
source, complete current owned-engine absence, no current owned companion or
effect, and a closed original Script manager/picker. Retain the empty state for
three seconds, including independent observations, before any next normal input.
The six measured fields are `running`, `effects`, `companions`, `picker`, `error`,
`open`; all six now require independent actor facts. Lifecycle counts must come
from actual native events, not requested operation counts. An ACK, a PID label
change, unsupported source or missing packet cannot establish this transition.

The old fixture effect is explicitly local. The original process-death proof
retires its old local heap; a fresh complete current source must separately
establish absence of new owned execution/effects. Retaining old native IDs,
stamping cached rows with a new sequence, or returning empty on an unavailable
getter is invalid. Kernel permission/unknown results are not process death;
see [the independent exit primitive](../native/PROCESS_PRESENCE.md).

Keep staged-file ownership and original bytes separate from execution. Native
`.owner.v1.json` survives process death. Persist old owner/context before stop;
read the original files with the same owned token after the verified new process
starts. Do not delete, replace, recreate or restage fixtures inside restart to
hide missing inputs. Missing/changed originals or candidate/source replacement
fail and retain ownership. Only an explicit independently verified handoff may
change the host process/session bindings; ordinary context equality stays strict.
The new manager starts with no owned source/load/picker intent after actual
absence is established. Do not adopt a live old source by assumption.

The following `open` is a separate ordinary UI action. Cancelling its file
picker must not resume execution. Only the subsequent normal From File review
and Use Files input may load the controlled bundle again. Verify the new actual
source/manager, relative module and advancing effects independently, then Stop.
The missing URL remains a real controlled HTTP failure through From URL.
Original load-result history must report `NotFound`; the actual visible
`TabletRunningScripts.status` must independently show its current failure.
`scriptLoaded` may also follow a load error and cannot prove successful execution.
Keep this error state for three seconds; closing the actual page clears its UI.

Cleanup must stop any uncertain owned current execution through normal controls,
observe actual engine/effect retirement, close owned dialogs/panels and separately
release/observe absence of original fixture files. A two-phase ownership handoff
must recover partial private-state writes without replaying uncertain product
input or discarding an unverified owner. The new process cannot inherit a green
cleanup result from an old host journal. Full adapters/independent target actors
and device qualification remain absent; the existing internal file-manager and
kernel-presence factories are narrower prerequisites.

Reviewed source locations: `interface/src/Application_UI.cpp` mobile startup and
file/URL dialogs; `libraries/script-engine/src/ScriptEngines.cpp` saved-user
loading/saving; `scripts/+android_phoneInterface/defaultScripts.js` and
`scripts/+android_interface/defaultScripts.js`; the iOS branch's corresponding
startup condition and phone/touch selector. `TabletProxy` starts with an empty
current path and `tabletShown:false`; the mobile app registry starts with an
empty current source. The dedicated Node checks execute original mobile entry
lists with a nonempty simulated `RunningScripts` setting. They do not execute
C++ or included modules and are not device evidence. Shared positive/negative
journey simulations test restart absence, delayed replay, independent UI/error
facts, cancelled reimport and ignored execution separately.
