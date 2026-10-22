# Original Pico controller publication admission

`PicoOpenXrAdapterSession.stage(..., intent=None, before_publish=None)` forwards
an optional final admission callable to the existing original
`AndroidOpenXrTransport.stage(..., before_publish=None)`. The original default
controller path, protocol, profile, target checks, writer order, cursor and ACK
behavior remain unchanged. This is a shared input boundary, not a feature effect
or a Create capability.

The existing `intent(envelope)` callback durably stores the exact original nonce,
sequence, operation, arguments and captured native/host anchors under the session
lock. It must never reenter the session, SDK/ADB, transport, a source guard or an
HTTP phase reader. Select the reviewed original intent/owned-neutral API from
`7dead98566c756bc85035ea9d0515adb2b9f1e5a` when using this addition on an older
source branch; integration already contains that API.

The transport completes its original exclusive-target and protocol/profile
validation, prepares both exact payloads, and invokes
`before_publish(deepcopy(envelope))` immediately before the original command
writer. It invokes the same **pure host validator** again immediately before
`grant.json`, the actual native publication marker, because the first bounded
SDK write can itself take time. Both calls must validate the already durable
original envelope and its advancing monotonic age. They must not write another
intent, acquire a new source, use SDK/HTTP/session APIs, publish input or retry.
Raise to refuse; a callback return value is not an effect or admission receipt.
Callback arguments and external-envelope changes cannot alter the prepared
validated payloads.

A slow pre-write SDK guard can therefore leave zero command/grant writes. A
slow command-file write can leave only an unpublished command, with no new grant
marker. Any failure preserves the caller's original pending intent; the helper
neither retries nor retires it. An ACK, a native neutral receipt or successful
publication still does not prove a voxel, entity, navigation or rendered effect.
Existing independent original effects and lifecycle owners remain required.

The selected device-free original-body tests execute the real session, private
CAS store, original transport validation, serialization and writer code with a
declared SDK subprocess runner. They check unchanged defaults, immutable wire
payloads, malformed profile/callback refusal, and a two-second host advance at
both actual SDK boundaries while native time stays frozen. SDK/session reentry
inside the final validator is an explicit test failure; only one durable intent
is written. These checks run no ADB process, OpenXR runtime or physical device.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m unittest \
  tests.device.self_tests.test_openxr_android_transport \
  tests.device.self_tests.test_pico_openxr_adapter_session
```
