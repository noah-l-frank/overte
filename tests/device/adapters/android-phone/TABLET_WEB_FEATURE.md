# Phone tablet browser feature composition

The Phone adapter composes the complete common v17 `tablet-web` journey through
`feature.tablet-web.act|observe|cleanup`. It also supplies every catalogized
foundation: normal `tablet.open|close` and all five existing `web.reference.*`
operations. The unchanged common `tablet-web-video` journey still judges
original encoded video pixels. No video analyzer result, desired text, document
counter, HTTP status or expected state is accepted as an observation.

This is complete source and host composition. Android C++/APK integration and
physical device behavior remain unqualified. No global acceptance count changes.

## Explicit configuration and separate observer

`OVERTE_PHONE_FEATURE_TABLET_WEB=1` enables the complete extension only for an
already candidate-bound controlled debug Phone target. The normal default is
zero. `OVERTE_PHONE_TABLET_WEB_CONFIGURATION` names a private mode-0600 JSON file:

```json
{"tabletWebConfigurationVersion":1,"artifactRoot":"/private/run-artifacts","foreignFixtureUrl":"http://second-controlled-host:port/feature-fixture/v1"}
```

The artifact directory must already satisfy the existing private-directory
boundary and agree with `OVERTE_DEVICE_ARTIFACT_DIR` when supplied. The existing
`OVERTE_PHONE_FEATURE_FIXTURE_CONFIG` still supplies the separately credentialed
adapter reader. Never give the ordinary fixture app that credential.

`script_observer.py` version 3 accepts `area: "tablet-web"`, reconstructs the
original owner configuration and independently acquires native/DOM/Java/HTTP/
service/lifecycle sources with its actor credential. It does not call primary
Observe or receive the primary projection. Version 2 does not gain this area.
All mutating native reservations, inputs and held-callback controls are rejected
by the read-only observer command gate.

## Ordinary input and original evidence

A controlled ordinary fixture application loads through normal Running Scripts
URL entry. Its `WEB TEST` and `INLINE TEST` tiles use the documented
`Tablet.gotoWebScreen` API. The latter reads the public current challenge and
immutable `inline-input.json` from the controlled fixture, then navigates using
its actual `data:text/html;charset=utf-8;base64,...` input. These are application
inputs, not measurements or native grants. The source script deliberately does
not filter foreign-origin echoes; native document authority must enforce that.
Normal Home, tile entry and script Stop retire the actual carrier and service.

The shared pointer/IME seam delivers native pointer, wheel and editor input.
The public normal tablet foundation journals its installed candidate, process,
session and input intent before Open/Close. Lost returns are never replayed;
only fresh original UI absence resolves an uncertain Close. The common tablet
module independently checks its original probe transition.

The existing HTTP-only DOM source remains strict. A separate Phone-only
`feature-phone-tablet-dom-observe` command reads the original document title and
passive trusted clicks/editor/page-received echoes. HTTP views join their actual
consumed response ID to the unchanged server receipt, including the original
404 before restoration and a genuinely new response after Reload. Historical
DOM packets retain their own source timestamps and receipts. Back, reload,
foreign input rejection and resumed view recreation use the same common checks.

Inline observation additionally acquires the actual native
`InlineHtmlDocument` token, revision, issuing-context lifetime, neutral transport,
original source bytes/hash, charset and source-owned injected script URL. The
actual consumed inline input ID joins its original HTTP JSON receipt and byte
hash. That receipt describes delivery of app input, never an HTTP document
status; an inline document has status zero. A DOM label or arbitrary data URL
cannot create or qualify a native lease. Native and separately fenced Java
inventories must match the actual active view and its transport hashes.

One E2E-only hold retains an actual normal Send callback after the unchanged
native bridge gate, including its old document/grant/page, actual origin, raw
payload bytes/hash and copied original weak lease. No packet is invented.
Delivery sends that same original callback through the complete original
`acceptMessage` entry and gate again; a new document/token cannot lend authority to it.
The source independently reports pending state, the original lease's current
state and the actual gate return. Foreign documents/grants are rejected before
a hold, and an accepted retired delivery stays red.

Documented `data:` HTML decoding and native source ownership remain separate:
UTF-8/base64 and percent-encoded HTML are decoded by `InlineHtmlBytes`; unsupported
MIME, invalid base64, oversized input, absent native context, wrong source tuple,
foreign navigation and retired/replaced leases retain the original policy.
The common journey's `parity-inline-v1` fixture specifically uses UTF-8/base64.
No functional product behavior or authority rule is added by this extension.

## Durable retirement and checked scope

The shared hardened browser owner preserves separate primary/actor journals,
source histories and private original PNG ownership. Both roles must complete
their original quiet windows. Every resumed or completed retirement reopens the
actual PNG files and reacquires a new three-second native/Java/service absence
window. Remaining callbacks, native views, Java creations or any previously owned
Java handle prevent retirement, including a late handle whose URL has changed.
Held input resolves only after ordinary carrier retirement. Native tombstones,
service absence and matching host journals are checked before pruning.

Private byte and timeout limits are unchanged. Cleanup retains its first two
and latest original snapshots. A versioned `webPackedSourceVersion: 1` archival
carrier reversibly expands already packed originals before the outer compression,
then reconstructs their exact canonical packs when read. This avoids repeated
compression of immutable inline HTML; it does not replace originals with claimed
absence or remove their hashes, timestamps, candidate binding or PNG ownership.

Twenty-six focused host cases exercise the complete public common journey,
normal foundation, default-off registration, separate actor reconstruction,
actual loopback fixture input and the real ordinary fixture-app handler. They
reject missing title/lease/bytes, borrowed response receipts, accepted retired
messages, lost input replay, changed candidates, late Java handles and changed
original PNGs. Target UI, DOM events, native items and rendered PNGs are explicitly
synthetic. The existing reference-video owner and common video counterexamples
remain applicable to both surfaces.

The actual common Web Java compiles at Java 8 against prepared Android API 34,
AndroidX WebKit 1.12.1 and Core 1.1.0. SDK 36 R8 classfile optimization retains
all 61 C++ JNI lookups/callbacks. The actual C++ provider/command grammar and
native bridge entry/current/origin/gate functions compile directly from
production source and run with Qt6Core, real `InlineHtmlDocument` and `EmbeddedWebPolicy` leases,
and synthetic item/mapping/JNI/transport seams. Foreign grants/documents, real lease
revocation/replacement and unchanged held payloads are checked there. The full
Android C++ translation unit, QML/Android runtime and APK are not compiled or
executed by those checks.

```sh
python3 -m unittest discover -s android/phone/tests/device -p 'test_tablet*.py'
python3 -m unittest discover -s android/phone/tests/device -p test_world_web_feature.py
python3 -m unittest discover -s android/phone/tests/device -p test_web_reference.py
python3 android/phone/tests/world-web-source-contract-test.py --build-dir build/tablet-web-contract
```

Device qualification belongs exclusively in the Proxmox Jenkins laboratory.
This implementation starts no device, observer, installation or lab job. Parent
integration must regenerate the source-bound Emote admission pins once after all
parallel probe changes; this work does not regenerate or learn those pins.
