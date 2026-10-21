# Original Android Web runtime and renderer observation

`native-web-runtime` v2 is an opt-in original source. It advertises no feature
capability. The frozen selection and hashes are in the Pico adapter's
`WEB_RUNTIME_SELECTION.json`; Phone's v1 namespace remains a distinct sibling
contract to reconcile during later integration. The neutral reader supports v1
explicitly, while the Pico factory requires v2.

The real Pico `+android_picoInterface/Web3DSurface.qml` resolves the shared
`+android_interface/Web3DSurface.qml`, whose backend is `NativeWebViewItem` and
`org.overte.web.EmbeddedWebView`. This source observes those actual instances.
It cannot stand in for legacy `PicoLegacyWebSurface`/`OffscreenWebView` lifetimes.
A feature using that other backend needs its own original source.

Only schema/nonce/run and the owned canonical fixture resource root enter the
private command. No wanted counts, selector, input, JavaScript, URL load or
cleanup operation is accepted. The existing default-off E2E build configuration
and actual test-script/results launch are required. Provider registration here
is Pico-only; other product routes are unchanged.

## Native and Android queue fence

The native GUI owner snapshots its actual weak item registry and original
session/document/creation generations, authorities, loading, retry/create state,
script network replies and callbacks. Original scoped handle history is bounded
at 256 handles per run and 32 runs. A fresh Java MAIN queue fence then supplies
actual views and creations; a second original native snapshot closes the fence.
Capture ordering, native/Java births, original PID, advancing cursors and the
1.5-second freshness window are mandatory. Pending packets retain their original
time and body. A completed nonce is never recaptured or retimed. The native
nonce history is bounded at 4096; exhaustion is unavailable.

Original native JS callback expiry lambdas retain an observational token. Weak
tracking continues counting the actual original lambda after its JS result has
already arrived, until Qt releases that lambda. The observation does not extend
the product object's lifetime, change its timer or cancel it.

## Renderer version 2

A view-list deletion alone cannot establish renderer release. The lazy Java
observer retains only primitive provenance and weak renderer/thread/callback
references, bounded at 128 original renderers per process. The actual creation
handle/revision/source is associated immediately after the original constructor.
An incomplete or exhausted inventory cannot publish an empty success.

Unchanged immediate MAIN and GL queue operations carry observation wrappers;
they run on the original handlers and decrement their counts in `finally` after
the original callback returns. Handler delays and the `retryCapture` Runnable
identity used by `removeCallbacks` remain original. Failed dispatch retains
uncertainty. A renderer's original Chromium VisualStateCallbacks are tracked
weakly, even after a callback has run; a still-retained original remains visible.
No garbage collection or extra product callback is requested to force retirement.

The source separately records the actual close transition, completion of the
original release function, original EGL surface/context destroy return values,
current worker-thread liveness and current queued/retained callbacks. A release
exception or failed EGL operation cannot become successful release. Observation
never retries release or changes any EGL/GL operation or application decision.

Readiness requires the same original active native item, Java document and live
renderer creation. Cleanup requires revoked original documents/replies/callbacks,
no owned pending creation, all observed renderers closed and successfully
released, terminated original workers and zero queued/retained callbacks. A
reachable inert renderer shell is not an active resource by itself. Its primitive
identity/history remains evidence; it is never deleted to make cleanup pass.
The full area owner must also prove entity absence, restore preferences/scene,
retire original capture/receipt owners and observe the required quiet interval.

## Verification limits

Python/Node simulations verify closed schemas, provenance, refusal and lifetime
joins only. C++, JNI, Java, QML, EGL and Chromium additions have not been compiled
or exercised on devices. Retained Chromium objects may keep cleanup unavailable;
the observer must report that fact. Actual native owner-thread placement,
renderer dispatch overhead and physical cleanup timing require later dedicated
Proxmox qualification. No local device service, compiler or build was run.
