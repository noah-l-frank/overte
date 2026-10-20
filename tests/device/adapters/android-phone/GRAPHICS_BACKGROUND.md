# Original Phone Graphics background/activation v1

`PhoneGraphicsBackground` owns one ordinary `background-resume` input on the
existing process/session. It composes Home/activation, independent actual OS app
state and fresh native lifecycle/preferences. It supplies input receipts only:
original GPU/image persistence and complete feature coordination remain separate.
Explicit process restart is not implemented by this component. No full Graphics
capability is enabled; native instrumentation is uncompiled and devices untested.

## Inputs, sources and durable recovery

Construct with the existing prepared `PhoneGraphicsPreferences` and held shared
source lock. The private CAS `phone-graphics-background.json` v1 pins actual run,
fixture URL, candidate/session/process, exact v16 action arguments, original
pre-input native packet, actual OS background observation and final native packet.
The UI must be closed and no owned UI lease may remain before Home is delivered.

Action phases are `background-issued`, `background-observed`, `foreground-issued`,
`observed`. Each input intent is durable before delivery through the existing
normal `lifecycle.background`/`app.launch` operations under existing-session input
admission. Home is sent once. Only an independently observed backgrounded,
still-running original process permits the one owned activation. Activation
is sent once; an uncertain return cannot be redelivered on reconstruction.
The same ticket/arguments may recover only through new original observations.
Changed ticket/arguments, unknown status or a replaced process remain errors.

`_graphics_lifecycle_status(selector,binding)` uses the existing session without
native foreground-only guards or SDK repair. It independently verifies installed
candidate, target fingerprint, exact session/generation and original PID/start
identity. Actual original OS app-state reads must agree around the independent
process observation. States 2/3/4 require the original running process; status 4
is actual foreground. Missing, inconsistent or changed observations fail closed.
The returned binding is built from these actual observations. No source is
manufactured from an input acknowledgment or requested state.

Background readiness is bounded to 51 original OS acquisitions and five seconds.
The full operation has a 30-second budget including durable callbacks. A backward
clock or changed scene/preference/background CAS record fails. While backgrounded,
foreground-only native/UI guards correctly remain unavailable and are not called
to authorize activation. Existing-session OS/candidate/process observations remain
mandatory. After actual foreground, a new independently acquired native packet
must preserve process/source birth and all actual Graphics preferences, increment
background/activation counters and preserve the launch counter. OS success without
those native changes cannot qualify. Original cursors/history persist through
the preference source owner; neither source clock nor packet is retimed.

## Retirement and remaining work

Repeated completed actions reacquire original terminal proof without normal input.
`retire()` requires completed activation, stable actual foreground, the original
process and fresh advancing native/counter proof. No UI lease or incomplete
preference action may remain. It then discards the exact CAS record and separately
proves actual absence. Ignored removal stays red. This retires background metadata
only and may precede the later explicit process restart: it does not reset the
changed preferences that restart must test. Original preference/scene restoration
and whole-run retirement remain separately mandatory. General Phone cleanup
refuses a retained background journal.

Fourteen focused host cases exercise normal persisted preferences, ignored Home,
lost Home/activation responses, missing native events, ignored activation, foreign
process status, missing OS observations, open UI rejection, repeated/conflicting
tickets, pre-input storage failure, unrelated preference change, ignored metadata
removal and metadata retirement before restart without preference reset. Two
actual Phone wrapper cases verify background OS reads without native foreground
access/repair and reject changed process/install/session or inconsistent OS reads.
A separate wrapper counterexample prevents forgotten background ownership from
becoming green cleanup. These are synthetic SDK/native host checks only.
