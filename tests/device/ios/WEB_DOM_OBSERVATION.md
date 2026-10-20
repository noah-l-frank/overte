# iOS native browser DOM component

The actual `ios/web/IOSWebView` WKWebView backend now supplies the common
[native Web/DOM v1 acquisition](../native/WEB_DOM_NATIVE_OBSERVATION.md).
The source, resource packaging and Objective-C++ are uncompiled; all physical
behavior remains untested. No complete world/tablet Web adapter is advertised.
The separate contained text-only browser is unchanged.

## Native source and original document binding

Under the default-off E2E feature-test option and explicit test-script/results
launch, `feature-web.qrc` packages the exact shared passive DOM factory. Native
`prepareDocument` installs it as an additional main-frame document-start user
script, with a frozen read-only object in a local scope. Missing observer bytes
block evidence without changing product navigation or its existing scripts.
No input, expected data, bridge grant or page handler invocation is introduced
by this read-only source.

The fixed typed provider selects one actual active native view by original
source and surface, with a 128-item cap and the original UIKit/Qt owner-thread
checks. Ambiguous, missing, unowned or inline views are unavailable. Original
source is the exact controlled run's ticket/index or reference document; the
current document may legitimately be B/recovery/the second controlled origin.
Neither a requested URL nor a DOM owner label authorizes an arbitrary view.

Ready evidence requires BOTH the actual `didFinishNavigation` callback for the
current original WK view/generation/document AND the existing independent native
nonce verification result. `nativeNavigationFinished()` is also called for
presentation changes; those calls alone cannot qualify a completion. A stale
back-forward cached JavaScript context therefore cannot become a fresh source.
The original callback time and native view identity are retained separately.

A closed nonce-only query uses the original native document guard around the
fixed factory read. The async completion pins a weak reference to the exact
original WK view, generation, native document epoch/nonce/URL, request owner,
foreground window and four-second acquisition deadline. It rechecks actual DOM
owner, request and current original native view before publishing private data.
There is no arbitrary JavaScript parameter and no strong-view callback cycle.
Completed repeated nonces preserve the same packet and original timestamps.

Actual `NSHTTPURLResponse.statusCode` is observed at the original main-frame
navigation-response policy callback and retained with original URL/epoch.
Version 1 exposes only its HTTP error status (400..599), or 0 for unknown/no
error callback; zero is not measured HTTP 200. Full status qualification still
needs the actual consumed DOM response ID joined to its independently read
original server receipt. A later typed response extension may expose the
already observed successful native status without inventing a default.

## Adapter transport, limits and remaining work

`FeatureObservation.web_dom()` reads only the fixed original AFC result file,
then separately issues a nonce-bound original native-clock observation. It uses
that actual native time and PID for freshness, never host UTC. Component
`_web_dom()` reuses the existing Script/native session continuity closure. The
canonical physical path requires its installed-code gate; legacy simulator and
cleanup-only paths refuse this new factory before target I/O.

The iOS no-build host selection passes **376** cases with zero failures/errors/
skips/compiler attempts. Four new cases exercise original component factory,
private HTTP/AFC grammar, independent native clock, ignored/stale/foreign source,
PID change and canonical unbound refusal. Native/OS positives are synthetic;
they do not test native compilation, installation, WK rendering or actual input.
The separate common source-reader/probe, pinned-reference VM and real loopback
resource groups pass 9/9/12 cases.

Version 1 qualifies HTTP documents only. Full Web adapters still require actual
cumulative document/native admission/original script-delivery journals,
independent publication, native inline carrier/original-byte association, the
original pre-admission held callback, image correlation and independently
observed native/file cleanup. JavaScript retire, a closed presentation or a
successful native stop acknowledgment alone cannot prove that cleanup.

An additional source-specific input join is mandatory for iOS **world** Web
surfaces: the existing product `IOSWebView::pointerEvent` forwards normal world
pointer events through `dispatchEvent` and `el.click()`. Their DOM `isTrusted`
flag is consequently false. Adapter code must still drive the original native
input route and independently correlate its actual native dispatch with the
resulting DOM click/bridge delivery. It must not directly call those handlers,
relax the passive trust filter, manufacture an attempt, or substitute the native
browser presentation for a required world-surface interaction. That E2E-only
native dispatch witness remains open; product input behavior is unchanged.
