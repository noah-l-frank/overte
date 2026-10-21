# Original Graphics background and activation v1

The neutral [`GraphicsBackground`](../graphics_journey/lifecycle.py) adapts the
frozen normal lifecycle transaction architecture to the actual Pico Android
backend. It records durable intent before normal `lifecycle.background` and
controlled `app.launch`. The existing backend may send another Home key only
after independently observing that a prior acknowledged key did not background
the same process; a lost operation result is never redispatched by this owner.

Pico reads the original installed candidate, current kernel PID/start identity,
existing OpenXR host binding and actual foreground package around each status.
Missing foreground, a changed candidate/process or an unavailable controlled
probe cannot become a background result or trigger bootstrap. No Appium
`appState` value is fabricated. The status binding identifies the existing
owner scope; the original GUI bridge is reacquired and checked after actual
activation through the normal guarded feature runtime.

Completion requires independently acquired native counters showing a background
and activation, unchanged process birth/launch count and unchanged actual
Graphics settings. Input acknowledgment establishes no rendering persistence;
fresh stereo observations from both roles remain separate requirements. The
whole operation is bounded to thirty seconds and the background status wait to
five seconds/fifty-one reads. Issued Home/activation intent survives ignored
inputs and lost replies without resending either operation.

## Recovery without a foreground-only guard

An uncertain applied Home can leave the process in the background. Ordinary
scene construction deliberately requires a foreground native source and cannot
be used to recover that state. The explicit recovery loader instead validates
the preserved scene/preferences/background archives while holding the same
source lock. It creates no live owner or successful guard from those archives.
Actual current process/foreground checks admit only the remaining original
activation. After actual foreground is observed, the loader reconstructs the
real guarded scene/preferences owners and checks their exact unchanged records,
binding and fresh native counters. A lost applied activation can therefore be
completed by observation; an ignored uncertain activation remains unresolved.
Changed owner files prevent recovery dispatch. The pure archive API retains
original epochs and accepts no current clock/guard.

Host counterexamples cover both lost replies, both ignored operations,
unexpected native launches, changed preferences, missing/replaced OS sources,
process replacement during a foreground query, old archive validation and
changed owner records. They exercise actual durable owners at synthetic native,
UI and OS boundaries. Native compilation and all physical input/rendering/timing
and device qualification remain unverified. No complete Graphics capability or
public operation is registered; the [normal restart owner](GRAPHICS_RESTART.md) is now source-implemented;
independent actor/full feature dispatch and combined resource quiet retirement
remain required.
