# Original UIKit keyboard and responder observations

This passive source supplements the ordinary [Back input](LIFECYCLE_BACK_INPUT.md)
and retained Qt input-event owner. It supplies no complete Lifecycle capability.
It is independent of QML `keyboardRaised`, Qt input-method visibility, product
geometry resets and input acknowledgements.

The existing ARC-enabled `IOSTouchUiMetrics.mm` forwards original UIKit keyboard
notifications to a dedicated E2E-only observer. Registration requires the actual
test-script launch, GUI thread and existing dedicated iOS E2E definitions. The
typed Qt provider preserves any existing application property and holds its real
metrics owner weakly. Missing registration or a dead owner is unavailable, never
an empty keyboard inventory. Production notification and input behavior is
unchanged; no keyboard/focus setter or extra notification observer is added.

Original notification entries preserve kind, native clocks, local/unknown
attribution, the actual current key-window identity, geometry digest and native
frame intersection. Invalid or absent frame data remains explicitly unknown.
Current independent window/responder observations walk the original application
windows with bounded view ancestry/census, use actual `isFirstResponder` reads,
and retain weak object birth and positive observed expiry. No field text,
selection, key content, accessibility value or object description is read.

The pure projection requires a complete live source, active application and one
visible active key window. Its geometry and identity must match the latest
original local notification. Settled `did-hide` proves hidden; valid actual
`did-show`/`did-change-frame` geometry proves current intersection or absence.
Initial silence, will-notifications, foreign/unknown local attribution, changed
window/geometry, partial inventory and background state cannot produce absence.
The returned native responder is not relabeled as a specific Qt editor or its
focus. Lifecycle must independently join its actual QML context/field source.

`feature-ios-keyboard` has the closed schema-one request
`schemaVersion,commandId,action,runId`, without expected state, requested text or
mutation. The original probe consumes each nonce once. The Test getter requires
the existing private test-results/lifecycle guards and the registered typed
provider. Its result uses the existing compact, atomic private writer/AFC path.
Unknown delivery never authorizes reissuing a read. The native source retains
its last exact nonce result without refreshing its clocks; old nonce reuse and
native capacity exhaustion fail closed.

`FeatureObservation.keyboard` reuses the existing bounded HTTP/AFC source reader,
separate independently acquired native clock and unchanged 1.5-second original
acquisition deadline. The canonical `_keyboard_source` factory uses the current
existing installed Script runtime/session/bundle/source gate; it does not create
or launch an SDK/app session. The unbound adapter refuses this factory. The two
new literal contracts are `ios-keyboard:1` and `ios-keyboard-acquisition:1`.
Other source/command versions and complete capability admission are unchanged.

Host entry points are
`ios.self_tests.test_ios_keyboard_source.KeyboardSourceTests` and
`ios.self_tests.test_ios_keyboard_runtime.KeyboardRuntimeTests`.
They model native/Qt/SDK/installed-byte producers explicitly, while exercising
the actual pure reader, canonical gates and HTTP/AFC codecs. They cannot qualify
the native implementation, notification attribution, hardware/floating keyboard
behavior, actual responder mapping, device timing or an iOS product result.
No compiler or device is used. Initial unknown state still needs an independently
observed settled original before a full Lifecycle baseline can qualify.

The first coordinated host selection passes all eleven pure source/history
cases as part of 69 cases in 24.144 seconds. Three further canonical keyboard
factory/HTTP/AFC cases pass in 0.119 seconds, including changed candidate,
replaced process and lost foreground refusal without another launch/session.
The first factory attempt correctly rejected a fixture clock producer with the
wrong PID; that producer was corrected without relaxing the actual source gate.
