# Normal Graphics restart and original owner transfer v1

The internal [`GraphicsRestart`](../graphics_journey/restart.py) uses the normal
Pico `app.stop` and controlled `app.launch` paths under the existing shared
source lock. Durable `RestartInputs` intent precedes either input. An uncertain
stop is followed only by the original own-UID Android process query; an
uncertain launch is followed only by native/host binding recovery. Neither
uncertain input is repeated. Unknown process state, ignored input or a changed
owner remains unresolved and cannot authorize a replacement process.

The restart proof uses the explicit Pico Qt bridge policy v2. It requires a new
PID/start and original native bridge UUID, exactly one native launch, unchanged
actual preferences, and original old-PID ESRCH observed from the new process.
The restart owner also reads actual passive Graphics UI v2 and Script manager,
picker and tablet inventories before transfer. A retained root, timer, QML
component, keyboard, focus or visible panel prevents a quiet startup result.

The exact new scene/preference proposals are saved before either mutable owner
is changed. Interrupted transfer resumes those proposals without another
restart. The old scene/avatar/preferences remain original; only the qualified
independently observed new-process framework baseline admits new framework IDs.
The normal Go To and HMD alignment path reenters the controlled scene. Both
roles still require fresh original stereo rendering observations afterward.

Immutable component archives keep nested restart/restoration journals within
the unchanged packed-history bounds. Each `graphics-restart-archive` v1 reference
contains its kind, exact basename and canonical SHA256. The restart envelope
binds the private artifact directory; original 0600 component files are read
and hash-checked during reconstruction. Missing, changed, foreign or escaping
references fail before recovery input. Archives remain private evidence after
ownership retirement; they are not live scene/preference journals.

Final retirement requires independently validated restored scene and cleaned
preference archives, actual absence of both scene/preference and role capture
owner files, fresh original subject/load/native packets, original settings and
qualified framework restoration. The input journal retires before the restart
journal. The complete restart transaction is bounded to 45 seconds per call.

Host tests exercise these durable owners with the real Pico normal navigation,
Graphics UI readers, strict process decoder and synthetic SDK/native sources.
They cover lost replies, ignored commands, uncertain exit, actual setting loss,
partial transfer, retained UI and missing/corrupt archives. All subprocess
access is intercepted; no compiler, device or service runs. Native compilation,
physical restart, VR input/rendering and devices remain unverified. Full feature
and actor coordination and combined quiet resource retirement are still open;
no complete Graphics capability is advertised.
