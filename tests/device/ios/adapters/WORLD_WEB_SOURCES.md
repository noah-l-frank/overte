# Original iOS world Web sources

`world_web_source` reads the actual iOS Web module's cumulative document,
main-frame response, normal native input and Qt bridge transcript. The provider
is installed by the real `registerIOSWebView` startup hook. The Test router must
invoke that registered provider, not a second header-local registry. Metadata
never retains a view, Qt bridge, native callback or GPU resource.

The closed read command is exactly `{schemaVersion:1,commandId:"ios-<32hex>",
action:"feature-ios-world-web",runId:"<32hex>",fixtureUrl:"<actual-run-root>"}`.
The fixed private result file is `feature-ios-world-web.json`, limit 2097152 for writer 3.
The provider uses `IOSWorldWebTrace.h`, `world_web_trace::command`,
`world_web_trace::providerProperty` and its distinct `Provider` metatype.
The result writer is `iosWorldWebVersion=3`, with historical readers 1, 2 and 3.
Version 3 retains the same event/identity grammar and actual callback chronology,
with capacity for 4096 cumulative events and a 2 MiB compact native result.
Historical versions 1/2 retain their original 2048-event/1 MiB bounds. Active
whole input requires version 3 before normal setup. A measured full-callback
host journey reached 1,049,451 compact bytes at step 17, before its next native
read, and failed closed at the old bound. No events are dropped or counters reset.
Version 2 records `owner-destroyed` from the actual `QObject::destroyed` signal
after the derived destructor and its members finish. Version 1 recorded derived
destructor entry, so it remains historical input and cannot qualify whole
retirement or authorize new world input. The gated connection captures only
the original identity value, retains no QObject and changes no product action.
Python preserves native instance,
process, sequence, clock domain, event IDs and complete event prefixes.

`world_web_dom` uses the equally closed `feature-ios-world-web-dom` action and
file `feature-ios-world-web-dom.json`, limit 262144. It invokes the registered
`world_web_trace::domProviderProperty` provider and validates with
`world_web_trace::domCommand`. The native result is
`iosWorldWebDOMNativeVersion=1`, containing the actual WK view, native document,
successful or failed HTTP status, consumed response header ID, original native
finish time, observer source digest and current original DOM acquisition.
The current DOM body is `iosWorldWebDOMVersion=2`, with original DOM1 history
still readable against its actual frozen source pin. Native envelope remains
`iosWorldWebDOMNativeVersion=1`. Each actual element now also reports its own
`focused` bool and original `value` string/null. In particular the ordinary
foreign-URL input can be qualified before the normal Navigate button; the
requested URL never becomes an observed value by implication.

The separately packaged `ios_world_web_dom.js` source is pinned by actual bytes.
It only reads the original DOM, geometry, focus, original input events and actual
reference-handler echo display. Its readonly API has no input or retirement
setter. The existing shared trusted-input DOM1 source and reader remain unchanged.
The real world product route intentionally uses `dispatchEvent`/`el.click()`.
Therefore an untrusted DOM click is retained as an original, never promoted to
trusted input. Qualification requires the preceding original mouseup on the
same actual element birth, its coordinates, the original native dispatch and
its actual completion entry and return in the same original document. Missing,
ambiguous, reused, pending or foreign dispatches fail. Click coordinates alone
cannot qualify this route: the product's HTMLElement.click has zero coordinates.

Main-frame `NSHTTPURLResponse` status/header, current native URL, actual body
response metadata and the separately read original BrowserResources receipt
must all join. A host fetch, resource name, requested ready flag or ACK cannot
provide a consumed response or document completion. Actual verified native
document identities count once across view reconstruction; polls and duplicate
callbacks do not increment document loads.

Actual callback entry/return is recorded inside the original completion body,
including early returns after owner death. Block destruction cannot record a
return. Qt bridge Signal RAII wraps the real original signal emission, preserving
return/exception semantics and nested callbacks. Unreturned evaluations and
signals remain pending after Qt owner death. Complete, bounded metadata fails
closed on clock regression, 4096 events, 32768 detail bytes or a 2 MiB result (writer 3).
The source has no reset or expected-value command.

The source is gated by `OVERTE_E2E_FEATURE_TESTS`, iOS, and the original explicit
test-script/results launch. Native sources are uncompiled. Eight Python cases
exercise original HTTP bytes/receipts with modeled native/DOM envelopes; Node
executes the actual product pointer/key and original reference/observer sources
against a modeled DOM. They establish adapter/source logic only. A complete
19-step normal-input owner, independent actor, image acquisition and actual
Web/native/GPU/VM/pointer quiet finalization remain separate composition work.
No whole Web capability is supplied by this prerequisite.

The source prerequisite is connected to the existing Test provider properties,
nonce-closed probe/fixture command routes and `FeatureObservation.world_web` /
`world_web_dom` AFC factories. Ledger commands are consumed once per nonce; DOM
polling revisits the same native asynchronous request without evaluating it
again. Real codec tests retain the exact returned originals and fixed remote
paths, and reject added expected-state fields before HTTP delivery. The original
probe itself runs in Node to check nonce ownership and pending-to-ready routing.

The controlled BrowserResources pages retain their original DOM and handlers.
A compact fixture stylesheet exposes the actual journey controls within the
world view; ordinary recovery and reference anchors supply real navigations.
The foreign listener adds an actual visible foreign heading. Response metadata
records the actual modified bytes and opaque response ID. Independent video
parity resources remain unchanged. Real socket/receipt regressions and the
original product pointer/key/reference JavaScript pass host checks; actual
WKWebView compilation, layout, input timing and devices remain unverified.

Large original packets are retained in at most four 512 KiB chunks. Each actual
OFS carrier includes its canonical JSON envelope and base64 payload and must
still fit the unchanged 1 MiB OFS bound. Warm pure read rounds reopen and hash
every actual carrier/inode; they may borrow private validated decoded frames
only within the round. Public decode/frame/browser histories are independent
copies. A cached public return cannot mutate the next derived original.

The part reference and its independent Original1/Frame1 envelopes are registered
as `ios-world-web-source-part`, `ios-world-web-source-part-original` and
`ios-world-web-source-part-frame`. The shared original-frame-store wire and
1 MiB per-file limit remain unchanged. Current capacity tests retain a complete
2,406-event modeled native callback original (1,565,701 compact bytes); the four
actual private carrier envelopes remain below 700 KiB each, including base64 and
JSON framing. These are host storage/codec checks, not native or device runs.
