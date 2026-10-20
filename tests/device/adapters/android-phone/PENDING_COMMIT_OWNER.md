# Phone original pending commit owner

The Phone E2E source registers the typed version-1 owner lazily through the
existing guarded Test interface. It requires the private owned results root,
actual lifecycle source, GUI thread and test-script launch. An existing provider
is never overwritten. The source code is uncompiled and devices are untested.

Fresh roots come from the original active OffscreenUi root/window. Focus uses
the existing native Qt mouse move/press/release route with actual clipping and
weak-object checks; typing uses the existing native IME helper. A background or
missing UI cannot supply a current Scripts field. Exact owned release remains
possible without a visible editor while the original test process is alive.
No QML handler, text property assignment or functional product change is added.

`PhoneAppiumAdapter._pending_owner(selector, intent)` uses the original candidate
APK/install digest, PID/start identity, native clock and one-attempt private
run-as file reads around every exchange. The durable intent callback is required
for mutations; omitting it yields a read-only component. The private source is
`files/overte-e2e/feature-pending-commit-owner.json`. Follow the closed
[shared contract](../../native/PENDING_COMMIT_OWNER.md) for input, fresh effects,
immutable original event history, deadlines and cleanup. Never supply a no-op
intent writer in production orchestration.

All 101 Phone component host tests pass. Four new integration cases exercise
original capture/retirement/release, ignored focus and failed cleanup, changed
candidate/foreign PID and mutation refusal without durable intent. Native and
OS boundaries are synthetic; no Android/Qt event or device ran. No complete
`feature.lifecycle-input.*` capability is registered: actual editor generations,
OS keyboard, world-input/position evidence, restart/recovery orchestration and
full cleanup still need their independent sources and joins.
