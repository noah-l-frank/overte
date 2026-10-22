# Original normal-input reception and interruption recovery

The gated `IOSNormalInputObservation` is one passive ledger with an explicitly
closed profile enum. Only `Avatar` is enabled. It records ordinary Avatar and
People commands, plus shared Home/page commands while an actual Avatar/People
root is present. Login and private credential controls are excluded. Future
control profiles must extend this same closed source deliberately.

An original received event retains the inner command UUID and full command,
actual control ID/root/component, outer transport UUID and native clocks. A
separate returned event stores the original receipt only after the actual
normal `edit` function returns. These records say what input was received and
returned; they establish no loaded model, account effect, consent or rendered
pixel. A command rejected after sequence consumption is never inferred to have
succeeded merely because that sequence advanced.

`feature-ios-avatar-inputs` reads the source through the existing gated Test
getter, fixed AFC file and all-consumed-nonce probe. The packet writes generic
`iosNormalInputsVersion: 1`, closed `profile: avatar`, and actual process clock
domain. Native history is bounded; exhaustion makes `complete` false rather
than dropping events or resetting its birth. Such a packet cannot resolve an
unknown input. Neither can an absent, merely received, rejected, duplicated,
foreign, rewritten or mismatched original command/receipt.

`IOSAvatarInputReads` persists each passive query before transport, writes its
matching original native DTO unchanged into an immutable private file, and
retains acquisition clocks separately. Interrupted queries are never resent.
Reconstruction adopts a fully completed saved read or archives the partial
query and any planned/opened/saved original before a distinct future query.
Actual partial writer inode, bytes and hash stay owned. Every valid returned
native prefix, including abandoned reads, must extend unchanged into future
reads. No transport or live guard is needed by the historical decoder.
If the native DTO returned but its writer never reached a saved original,
the retained planned/opened file cannot be cleared by another query. That
case stays unavailable with its original responsibility; this component does
not manufacture continuity from an incomplete file.

Resolving an exact returned receipt updates only the existing saved input
owner. It does not authorize repeating the recipe. Recipe continuation needs
a separately validated program counter, its original deadline and genuinely
fresh controls for the first remaining step. Cleanup still requires actual
pointer drainage, root lifetime, script/timer/HTTP drainage, pixels and paired
retirement originals.

Twenty-one host tests cover actual normal input transport/private journals and
files, exact UUID recovery with no repeated edit, query storage before send,
lost native return, distinct later nonce, lost completed metadata return,
retained partial inode/replacement refusal, source-prefix reset, final-save
deadline and input-owner regressions. Actual FixtureState/probe/FeatureObserver
AFC routes and both fresh Python import orders are exercised. Native Qt/ledger
producers are explicit synthetic seams; native compilation and devices remain
unverified. This component advertises no whole Avatar capability.

Contracts `ios-normal-inputs`, `ios-avatar-inputs-acquisition`,
`ios-avatar-input-reads` and `ios-avatar-input-read-record` write/read version 1.
