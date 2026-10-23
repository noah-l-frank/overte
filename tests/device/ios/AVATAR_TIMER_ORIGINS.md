# AvatarApp timer origin in source2

The unchanged AvatarApp Script creates a timeout when adding a wearable. Its
actual V8 frames originate in `system/avatarapp.js`, not in
`system/libraries/peopleConnection.js`. The source2 native producer observes
the closed Avatar/People/request module set; requiring the People protocol in
every source2 timer incorrectly rejects this ordinary Avatar action.

The reader correction requires at least one actual closed module and
joins every reported module to the manager's submitted source bytes. Whole
qualification separately requires the independently pinned complete callsite
profile. A valid module with a wrong line can remain module-origin evidence
and still fails that stronger whole assertion. Literal source1 retains its
existing protocol-specific grammar; no old caller chain gains actual V8
provenance.

The original AvatarApp Script runs in Node in the focused regression, with
explicit native engine/snapshot models. The old reader reproduced the failure.
The narrow correction was applied after both other readers released their
source freezes. The actual repository's new positive/negative and existing
source/caller/whole-callsite cases pass (32 tests). An earlier isolated run also
passed the complete ordinary wearable recipe and both independent observers.
Whole Avatar and native/iOS qualification remain separate; this change adds no
advertised capability.
