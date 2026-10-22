# Original world attempt and normal X route join

The private `_lifecycle_x_join(target, run)` factory combines the actual
`PicoLifecycleWorld` and `PicoLifecycleBack` owners in one candidate/process/run.
It uses the shared `PicoScriptJourney` source lock, plus the existing Back owner's
separate input journal lock. All real Lifecycle UI/Drive/Gesture factories also
bind the same target-specific shared source-lock domain. World and X pass the
exact same instance, permitting bounded nested acquisition without another
flock on its own held inode. Lock order is always shared source then Back
journal; busy independent readers send no query. Unbound readers exist only
for explicit host/native boundary tests. Its own journal and its original X owner's journal
live beside the original world journal. The prior standalone Back primitive
keeps its own existing ownership scope.

Before the first possible X press, the join freezes the real current Create
identity that received the first consumed world gesture. The original Back
owner now accepts an optional exact identity guard before reserving or sending
its normal physical X input. A replaced Create page cannot inherit that input.
The join reserves its own transaction before invoking Back. An interrupted
reservation never causes another press; reconstruction only reconciles an
existing original Back journal. A missing journal stays unavailable.

The Back owner's complete existing historical validator is factored into the
pure `validate_history()` helper. Live loading and the join both use that same
validator. Original private Back frames/envelope/neutral/quiet are preserved,
not an ACK or hand-authored success summary. The real world/UI histories must
contain the join's exact before/after original packets. Their actual source
instance, editor identities and advancing cursors must bracket the original
Back packet history. The current UI must independently show Home, no original
field/page, no focused editor and the real released VR keyboard.

A surviving original QQmlContext remains `retainedContext=true` and
`editorRetired=false`. The join neither deletes that QObject nor changes its
original flags. `worldAttempts` remains the original consumed count, and current
held input/displacement still comes from the independent avatar source. A later
second ordinary world gesture remains a distinct original input; it does not
rewrite the completed X history.

`pico-lifecycle-x-join:1` is a partial source/owner contract. The ordinary X route,
original movement and local quiet compose here; the full editor/typing,
background/pending-stale, peer/image/restore and final OS-proven owner retirement
still require their own closure. All three journals remain preserved. Device-free
checks execute the actual owners/session/readers over explicitly declared UI,
OpenXR-status and physics boundaries. No hardware run is claimed.
