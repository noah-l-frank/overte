# Pico native browser DOM component

The current Pico target calls `overte_target_embedded_web(picoOpenXR)` and uses
`android/common/web/NativeWebViewItem` with `EmbeddedWebView`. This packet adds
E2E observations to that actual shared Android backend. It does not instrument
the retained older Pico offscreen implementation or import Phone product
history. The four original shared backend files were byte-compared before the
local source port; the resulting five native/resource files match the reviewed
Phone E2E implementation.

The [native Web/DOM v1 contract](../../native/WEB_DOM_NATIVE_OBSERVATION.md) and
[passive DOM source](../../native/WEB_DOM_OBSERVATION.md) are unchanged. Native
packaging/injection requires the existing default-off feature-test build option
and explicit test-script/results launch flags. The original same-host/activity/
foreground/current-document/native-editor admission checks guard the fixed
nonce-only JavaScript read before and after completion. A missing observer
resource blocks evidence while ordinary native navigation remains unchanged.

The source reports actual original native handle/creation/grant/page/source,
real main-frame completion, original HTTP error callbacks and original DOM
text/focus/response ID/trusted attempts/accepted echoes. Zero HTTP error status
means unknown/no error callback, never measured HTTP 200. It neither counts a
read as a completed document nor requests bridge authority. Repeated completed
nonces return the unchanged original packet. Ambiguous, foreign-thread,
changed, stale, missing or timed-out sources fail. Hidden cached Qt pages are
excluded from active-view selection; that exclusion is not native cleanup proof.

The Pico `_web_dom(target)` factory reuses the original candidate/install,
OpenXR/Script context, actual Linux PID/start, private debug file transport and
independent device epoch clock. It preserves the existing private error
vocabulary. No source path, target selector or raw tool error is exported.
The actual file is fixed to
`files/overte-e2e/feature-web-dom-observation.json`.

The complete modified normal Script component group passes **47** host cases,
including three new native Web factory cases for original source fields,
unknown HTTP success status, ignored input, foreign PID and changed candidate
before dispatch. Shared reader/probe, pinned-reference VM and loopback browser
resource groups pass 9/9/12 cases. All native/DOM/OS positive boundaries there
are synthetic. C++/Java/JNI/resource packaging is uncompiled; no headset,
controller, browser rendering or actual trusted input was tested.

Full world/tablet Web adapters still need cumulative real document/native
admission/script-delivery journals, ordinary input and projection, independent
publication, image correlation, native inline carrier/original-byte ownership,
one original pre-admission delayed callback and observed native/file cleanup.
Version 1 rejects inline qualification. Pico graphics stereo/Vulkan limitations
are unchanged. No complete `feature.*` capability or physical qualification is
introduced by this packet.
