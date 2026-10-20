# Android Phone native browser DOM component

The common native browser/DOM v1 source is now wired through the actual
`android/common/web` backend used by Phone. The older Phone WebView activity
and old Pico offscreen copies are not the current embedded backend.
This is source implementation plus host-tested adapter logic. C++/Java/JNI
and resource packaging remain uncompiled and physically untested. No complete
world/tablet Web feature capability is enabled.

## Source and observations

With `OVERTE_E2E_FEATURE_TESTS` **and** explicit test-script/results launch flags,
the target conditionally includes `feature-web.qrc` and appends the exact
[passive DOM source](../../native/WEB_DOM_OBSERVATION.md) to the existing
all-main-frame private editor bootstrap. The factory runs at document start
in a local scope and is installed as a frozen, nonwritable/nonconfigurable
native-query object. Ordinary builds do not include or inject that resource.
The JNI enable check is false outside the dedicated runtime boundary.

The fixed typed native provider is registered at native type startup. It
selects exactly one actual native item by actual surface and original source:
the controlled run's `tickets/<32hex>/index.html|reference.html`. More than 128
items, ambiguous sources, a foreign owning Qt thread or missing source fail.
There is no unbounded cross-thread blocking call or arbitrary root selector.
Inline sources remain excluded until actual carrier/owned-byte qualification.

`featureRead` accepts only an actual handle/grant/page plus nonce. The Java side
checks actual current instance/host/activity/foreground/window focus/document
and original native editor admission before and after the fixed read-only
JavaScript expression. It accepts no script, DOM selector or expected result.
Native callbacks recheck the actual request, original source, epochs, main-frame
URL and unchanged ownership before returning any original DOM fields. A changed
or absent DOM owner cannot export private page text as the requested source.

`nativeFinished` comes from the actual `onPageFinished` callback for the exact
native document. It is independent of `loading:false`, polling and command ACKs.
`httpErrorStatus` comes from actual `onReceivedHttpError` main-frame response
status (400..599); zero remains unknown/no error callback, never HTTP 200.
Full status/byte qualification still needs the separately consumed original DOM
response ID joined to the independently read original server receipt.

Pending requests retain their original owner before evaluation. Only one
pending acquisition exists per native item; unrelated replacement is refused.
Native progress has a four-second ceiling inside the existing five-second /
51-read component budget. Completed repeated nonces return the same original
packet without retiming; changed original native page/grant/document fails.
Handle, creation, native source instance, actual OS PID and original timestamps
are reported as actual sources, not requested identifiers or verdicts.
The current per-view sampler cursor/page token is not a completed-document count.

## Adapter and handoff

The private `_web_dom(selector)` factory reuses the original installed-APK,
Appium session/generation/fingerprint, Linux PID/start and guarded private debug
file transport. It reads only `files/overte-e2e/feature-web-dom-observation.json`
and uses the original independent device epoch clock. The shared reader pins
one native view/document and both source histories. Unknown/replaced documents
need explicit lifecycle qualification in the future full owner; they cannot
silently reset this reader.

The Phone feature adapter group passes **97** host cases, including three new
original-transport cases for actual raw DOM fields, ignored requests, foreign
PID and changed installed APK. Nine shared source-reader/probe cases, nine
pinned-original-reference VM cases and twelve browser resource cases also pass.
Their native/DOM/OS boundaries are synthetic and do not validate a native build,
actual trusted browser click, installation or device behavior.

Still required for complete Web journeys: native cumulative completion and
actual admission/script-delivery journals across view reconstruction, normal
browser input geometry, independent source publisher, native inline carrier /
original-byte ownership, one original pre-admission delayed callback, observed
buffer/document/view/file cleanup and image correlation. A successful JavaScript
retire call, native `destroy` ACK or stopped script alone is not proof of cleanup.
No `feature.*` capability may be added until those required pieces exist.
