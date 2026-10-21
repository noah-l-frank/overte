# Original Phone touch state, version 1

This passive getter observes actual Phone virtual-pad contact ownership, pending
pinch values and the original input-device channel/button maps. It exposes no
release/setter and makes no claim about another Qt view's private touch state.

The exact request is `{schemaVersion:1,commandId:<32 lowercase hex>,action:
"phone-touch-state-observe"}`. Native admission requires the existing private
results/lifecycle scope, `--testScript`, `OVERTE_E2E_FEATURE_TESTS` and the Phone
interface. The Test, Application and plugin getters execute on their owning GUI/
QObject thread; missing/different-thread plugin observations stay unavailable.
The original production event/update paths and values are not modified.

`Test.phoneTouchObservation` returns the original avatar-render envelope:
`schemaVersion:1`, `requestId`, shared process-birth `instance`, independent
advancing `sequence`, `processId`, `requestedEpochMs`, `capturedEpochMs`, `source`.
Source is exactly `phoneTouchStateVersion:1`, `pluginActive` (actual running
plugin), `eventPointCount`, `moveContact`, `viewContact`, `buttonContacts`,
`unusedContacts`, `axes:[{channel,value}]`, `pressedButtons:[channel]`,
`pendingPinchIn`, `pendingPinchOut`, `lastPinchScale`. Axes retain only actual
entries, with original channel numbers 0..5; no absent entry is fabricated as a
measured zero. Pressed-button entries are the actual channels 0..1. Contact
counts are bounded to 32; malformed/duplicate/nonfinite/over-limit inventories
fail, without truncation. The probe deduplicates and saves the original packet
as `phone-touch-state.json`; missing hooks cannot become empty success.

`NativePhoneTouchState` and the read-only Phone factory reuse original private
candidate/process admission, 51-read/5-second bounds, 1.5-second native freshness
including final guards/copies and monotonic age floors. Historical restore is
bounded to 256 originals and performs no transport or retiming. No launch,
session repair, feature capability or device acceptance is implied.

`released` requires a running plugin, zero event/contact/unused/button counts,
no pressed buttons, only zero-valued actual axis entries, and zero pending/last
pinch. A successful W3C DELETE /actions does not satisfy any of these facts.
The complete owner must obtain current originals after release, join the same
candidate/process and actual SDK session, and check other owned resources.

Eight common host cases and two Phone factory/grammar cases exercise real
reader/probe code with synthetic native boundaries, including retained contacts,
axes/buttons/pinch, ignored/foreign/stale/cursor-reused observations, late guards,
historical replay and missing hooks. Native code is uncompiled; no physical
input or resource retirement has been qualified.
