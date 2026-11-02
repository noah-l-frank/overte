# Private World consumption readout

The existing Trace1 WIP recorder now has a private route through the existing
Test API, probe and strict Python reader. This continues the
[reviewed source proposal](WORLD_CURRENT_CONSUMPTION_PROPOSAL.md); it does not
complete the World feature, advertise a capability or register the private
wire. The native/Java recorder and new C++ route remain uncompiled in this
resume packet. Its original production-body owning checks are still required.

## Existing route and ownership

`Test.featurePicoWorldCurrentConsumption` creates the same native query anchor
before queued dispatch and uses a dedicated instance of the existing bounded
`AudioSettingsQueue`. The original test-launch/lifecycle/results-directory and
settled-queue gates remain in force. It calls the one provider already installed
by `NativeWebViewItem` in the Pico build. The probe sends both private operations
to that getter and saves the actual returned packet to
`feature-world-current-consumption.json`. Missing, throwing or foreign getters
produce an empty unavailable original, with no substitute result or old Browser
operation. The bounded queue implementation is reused unchanged.

`PicoWorldCurrentConsumption` accepts the existing CurrentInput reader and
existing owner transport, source lock, lifetime guard and required original
retention callback. Arm resolves that reader's actual warm focus original,
including its complete nested current-document original. The callback receives
the exact request before sending and every acquired raw response before parsing,
even if the response is malformed, foreign or unusable. The owner must persist
those records under its existing journal/source-chunk limits. The new reader
does not introduce another store or take cleanup authority from the Parent.

An uncertain send/read/parse/exit/correlation failure leaves the issued reader
failed. It cannot replace the arm or resend the query. Successful reads advance
only the actual next frame cursor, original source sequence and high-water mark.
One outstanding query uses one nonce and at most31 raw reads within1.5s;
the Host sends it once. Complete validation, copying, event correlation and
real outer-lock exit count against that original query. The fixed5s attempt
also charges cumulative Host monotonic time from arm, so frozen native and
epoch clocks cannot renew it. The warm focus lease is additionally checked
through arm completion. Subsequent historical trace frames do not become a new
focus or input lease.

## What the reader establishes

The closed packet grammar ties native bookends and original finish to the
retained focus item/source/instance, process, run, owner and fixture. Per-kind
raw DTOs retain actual Keyboard, Application, Native, JNI and Java data.
The native-input DTO includes `accepted`, which the preserved WIP actually
records after returning from the original event handler. The proposal's earlier
field list omitted that field; this packet reconciles the list explicitly.

Exact UTF-16 big-endian units and standard UTF-8 bytes remain distinct. Malformed
surrogates cannot qualify through matching replacement bytes; those raw units
can be retained only in encoding-unavailable evidence. Java entry and dispatch
must match the actual prior JNI event ID, origin, scope and full encoded command.
Their own original clocks cannot borrow a fresh native callback-collection
clock. Native keys, default ASCII VR keys and separate Unicode Qt IME origins
remain separate. An ignored release remains an ignored release. An accepted
Native event or Java dispatch is not proof of JavaScript execution or field
effect; that still requires a new independent document/editor original.

## Verification and remaining boundary

The focused Python tests execute the real reader and a complete original probe
dispatcher in Node. Native frames, Qt/Android, keyboard events and Java callbacks
are explicit producer models. They do not establish compiled native behavior,
JNI behavior, a normal controller key or a device result. No compiler, Java
compiler, application build or device test runs in this packet.

The owning command is:

```text
PYTHONDONTWRITEBYTECODE=1 python3 android/vr/pico/tests/device/test_world_current_consumption_reader.py -v
```

It covers the readout chain, exact command/raw grammars, native-key versus IME
data, supplementary Unicode versus Modified UTF-8, malformed surrogates,
unavailable originals, stale/foreign scope, forward cursor and event joins,
source-sequence replay, raw-before-refusal retention, uncertain-send ownership,
same-nonce bounded polling, stale focus, held locks, real outer exit, original
clock skew, slow correlation, cumulative frozen-clock attempt expiry and old
Java originals under fresh collection clocks. The Node part executes eight
actual-dispatch/missing/throwing/foreign-getter cases for both operations.

The initial2026-11-02 owning run passes16 tests in0.619s, including those eight Node
cases. The unchanged CurrentInput and CurrentDocument Python reader groups
pass16/0.819s and9/0.035s respectively; Node probe syntax and scoped whitespace
checks also pass. The13 named source, test and document files retain identical
SHA-256 and physical signatures during these checks. Other agents' concurrent
feature files are not claimed frozen. Original requests, raw model frames,
logs and the exact named-source manifest are retained in
`/home/user/.local/state/overte-pico-world-consumption-owning-20261102-usd7hpw4`.
The earlier11-case and15-case runs remain separate historical evidence rather
than being relabeled as that16-case run.

Root review identified a pre-send gap: the request-retention callback, lock
admission or lifetime guard could exceed the original query/focus lease and
still send an arm before the post-read refusal. A real new counter fails all
three delayed cases before the fix (1 test/0.032s,3 failures). The fixed reader
checks the original query elapsed/epoch and existing arm bound immediately
before dispatch, and rechecks the original warm focus under the same held lock
for arm. It acquires no new source or renewed anchor. All three cases then
pass with zero sends and retained issued/failed/request ownership
(1 test/0.026s). The full affected reader passes17 tests in0.668s; unchanged
legacy reader suites were not repeated for this correction. Red and green
originals remain respectively in
`/home/user/.local/state/pico-trace-presend-red-20261102-ok9__7xa` and
`/home/user/.local/state/pico-trace-presend-green-20261102-xbxgjewn`.

Next, run the original native/Java recorder owning checks when compiler work is
authorized, including original weak death/late callback/thread and once-only
product-dispatch counters. Then compose this reader with the existing same
Parent focus stage and real normal keyboard input, retain a new independent
DOM/editor effect, and preserve unresolved ownership on failure. The stock
keyboard's arbitrary-Unicode source gap, complete stereo/Actor composition,
native resource/receiver closure and final retirement remain open. No completed
feature or device count changes.

Root review additionally reproduced a late epoch-clock read before dispatch:
the old ordering sampled host monotonic time first, then spent two modeled
seconds reading the epoch clock and still sent one arm. That counter genuinely
failed before the fix. Both dispatch and final publication now sample monotonic
time after the epoch read, so that work counts against the original bound.
The17-case owning reader remains green, and the delayed dispatch sends nothing.
The unique Root logs are `trace-clock-presend-red.log` and
`trace-reader-root-final.log` under
`/home/user/.local/state/overte-pico-browser-png-projection-20261102-mconlui2`.
