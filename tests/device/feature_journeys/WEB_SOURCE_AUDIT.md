# Browser source audit and unresolved v9 assumptions

This audit is a prerequisite for complete world/tablet browser adapters. The
existing v9 browser scenarios, carried unchanged into shared v10, are draft
test logic; their source semantics
are not yet qualified. Missing adapters must continue to fail the mandatory area
gates. Do not implement success receipts that conceal the following mismatches.
Native source additions require separate source review, host checks and later
compilation/laboratory qualification. No product or device acceptance is claimed.

## Confirmed local sources

The submitted Phone/Pico native Android WebView uses
`android/common/web/java/org/overte/web/EmbeddedWebView.java`. Its main-frame
`onPageFinished` finishes ordinary documents and authorizes the actual document;
`onReceivedError` covers actual main-frame transport failure, SSL failure has its
own callback, and no HTTP-status error callback maps a 404 document to a native
load error. iOS `ios/web/IOSWebView.mm` likewise permits showable navigation
responses and calls its normal `finished` path after `didFinishNavigation`.
Its navigation failure callbacks are distinct from an HTTP 404 document.

Consequently the current `navigate(missing.html) -> error:not-found -> reload
-> error:none` draft cannot be implemented literally. The fixture permanently
returns a missing resource, and reloading it does not restore availability.
Required correction: serve an actual controlled 404 document, observe actual
main-frame response status/body separately from native load error, restore only
the owned server resource through an explicit fixture actor, verify that this
server input has not changed the current document, then use normal Reload and
observe a new actual successful response/document. Neither requested availability
nor an independent actor's own HTTP GET can stand in for the product's navigation.

The historical generated `reference.html/page-b.html/inline.html` stub only
copies editor text into DOM and emits `{text:...}`. That is not the existing
native parity echo protocol. It lacks ordinary navigation/history/reload controls
and did not establish actual native script delivery. The new
[owned browser resources v1](BROWSER_RESOURCES.md) now replaces those served
stubs using the existing
`fixture/parity/index.html`, `reference.js` and ordinary `client.js` source instead
of introducing another browser test application. The existing reference bridge
accepts only an actual matching script echo, and client.js deliberately does not
filter origin: the native grant, rather than cooperative JavaScript, must block
foreign documents. A foreign negative needs an independently observed normal
send attempt, actual different native frame/document origin and unchanged actual
accepted native/script history; an unchanged counter alone is vacuous.

Android's actual origin-scoped WebMessageListener/document-start bridge and its
main-frame/document-epoch admission gate differ from its editor listener. A
foreign iframe can legitimately lack EventBridge altogether. The attempted
normal click must still be observed; do not inject a bridge or call its handlers
to manufacture a stimulus. A top-level foreign document can instead be used with
explicit ordinary navigation/back steps and actual per-document state. Whichever
profile is selected must measure the real original document/frame/lifetime.

Actual inline tablet HTML is not an HTTP page named `inline.html`.
`TabletProxy::loadHTMLSourceOnTopImpl` creates `NativeInlineHtmlSource` only for a
native source request whose URL begins with `data:`. It owns the exact decoded
bytes/script and a native context-bound document lease; TabletRoot attaches that
opaque carrier to the actual page, suspends it on replacement and retires it on
return. A controlled ordinary fixture app button can use that public source
navigation API with owned data HTML. The adapter must independently observe the
actual native carrier/source/lifetime and original bytes. Visiting the HTTP stub
does not test inline app routing or authority retirement.

Back and foreground form retention also require source qualification against the
actual native view/document history. Android has explicit destroyed-document
recreation and a navigation archive; do not assert Unicode survives an arbitrary
new document because a host reducer retained it. Record actual document epochs,
real current form/focus and source-qualified history/reconstruction behavior.
Any intentional per-backend profile must be closed and bound to the reviewed
source; it must not accept whichever result a broken client happens to return.

## Remaining implementation packet

The owned browser-resource prerequisite now supplies checked original parity
sources, a resource-only second listener and a real 404/restored-200 resource
with separate original HTTP response receipts. It is host-checked fixture logic,
not a correction of the unchanged v10 draft scenario or a product observation.

Before promoting complete browser capabilities, correct the shared breaking
contract and independently witnessed fields, provide the controlled second
origin and real unavailable/recovered document, reuse the original parity page/
echo script with normal controls, and add host counterexamples for an ignored
foreign attempt, a cooperative fake echo, wrong/old document/frame, unchanged 404
reload, requested-only server recovery, recreated document state and fake HTTP
inline routing. Add passive native document/status/DOM/bridge observations and
normal input on Phone first, then Pico and iOS. Preserve existing video/pixel/PCM
foundations and private ownership/cleanup. Until that packet is complete, the
matrix means draft common logic present, complete adapter missing, devices
untested; it does not mean source-correct full browser E2E coverage.
