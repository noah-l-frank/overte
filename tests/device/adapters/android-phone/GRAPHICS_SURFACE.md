# Ordinary Phone Graphics input surface v1

`PhoneGraphicsSurface` composes the existing native SDK input, original Qt
Graphics recipe and passive subject-v2 source. It supplies normal Go To,
Graphics open/close/settings and View-menu camera input. It returns input
receipts, not loaded-world, rendered-effect, persistence or feature-success
results. It advertises no capability. Native instrumentation is uncompiled;
all physical clients remain untested.

## Existing-session factory and caller ownership

`_graphics_surface(selector,run,intent,owns,lease,allow_url,lock=...,role="primary")`
requires the already-held `phone-script-sources.lock` at the selected session's
exact state path. Actor input is refused. Construction uses the existing SDK
session/input admission and verifies installed candidate/process/session state;
it cannot reach the repairing parent SDK path. The returned SDK, passive source
and original Qt IO guards also require that same lock during every operation.
Using the object after releasing the lock fails before input.

The caller must supply a durable whole-action ledger and these callbacks:

- `intent(stage,original_subject,original_graphics_or_none,control_id)` validates
  and saves input intent before every possible mutation. Subject originals must
  have version 2 and actual feet/orientation/scale; missing v1 pose cannot fall
  back to guessed camera coordinates. Qt snapshots preserve actual source tokens.
- `owns(field)` reads a strict boolean lease for `tablet`, `address` or `menu`.
- `lease(field,boolean)` durably writes that lease. The surface verifies the
  readback before input; observed SDK control absence precedes lease retirement.
- `allow_url(url)` must return exactly true only for the caller's frozen original
  or controlled scene/viewpoint URLs. This callback grants no measured success.

An already-issued whole action must never be redelivered after a lost response.
The surface provides no ticket deduplication, restart handoff or whole-run owner;
those remain mandatory in the complete coordinator. Its scalar recipe retains
the existing one-send input and independently observed Qt/native value waits.

## Normal inputs and observations

Go To uses the actual `Go to destination` control and `PhoneAddressField`,
`PhoneAddressGoButton` and `PhoneAddressCancelButton`. It sends one normal text
replacement, reads actual resulting field text, and clicks Go once. Only reads
wait/retry. URL schemes are restricted to normal HTTP/HTTPS/file/Overte input,
with bounded text and no userinfo, control characters or fragment. A denied URL
does not open the editor. The complete scene owner must separately prove actual
HTTP delivery, all run-owned native entities and actual avatar/camera placement;
editor dismissal is not that evidence.

Graphics open follows actual Tablet Home/page controls, the original
`settings.entry`, then `graphics.settings-entry`. It requires the original
`phone-immediate-v1` page. Resolution/Haze/Mirrors use the existing original-token
slider/switch/scroll recipe. No Render setter, QML handler, script-message or
Entity API shortcut is an input. Closing a panel observes actual absence before
retiring the corresponding lease. A pre-existing foreign editor or Tablet is
preserved. Even an older owned lease cannot adopt an unknown replacement page.
Known Home pagination, actual Settings/Graphics pages or an owned visible menu
are required before returning Home or closing the Tablet.

Camera selection uses normal Tablet Menu > View and exactly the source-reviewed
First Person (`first person look at`), Look At (`look at`) or Selfie (`selfie`)
action. It then acquires new subject observations until the actual mode changes;
an ignored successful click cannot satisfy it. An already matching mode produces
an explicit no-input receipt. Legacy script-only `first person` cannot be
selected/restored through this ordinary menu and is refused as an input value.
The scene owner must preflight whether its original mode/view can be restored.

## Limits, failures and handoff

Each operation shares a 20-second deadline across nested surface calls and owner
callbacks. Native-source, SDK and original Qt waits keep their existing budgets;
camera post-observation is additionally capped at 51 reads. Source/SDK guard
loss, ambiguous or foreign controls, ownership-write failure, missing pose,
unknown page/profile, wrong slider grid, ignored input and absent terminal UI
observations fail without replay. Lost returns retain the appropriate lease.
Cleanup may cancel/close only an owned surface and must still verify independent
native/Tablet/render facts through the complete owner. There is no force close,
candidate repair, device discovery, build, installation or application restart.

Eighteen host cases use real private lease/intent files and explicit synthetic
SDK, Qt and native boundaries. They cover all ordinary paths, pagination,
independent camera readback, ignored text/Go/mode/settings, lost Go response,
foreign/replacement pages, invalid URL, ownership/clock/guard failures and the
actual bound factory with no SDK repair. They establish input logic only.
Normal scene ownership/restoration, complete action/restart ownership and the
independent Graphics coordinator remain to be composed.
