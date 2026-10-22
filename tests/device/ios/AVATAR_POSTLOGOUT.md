# Original Avatar properties across ordinary logout

The existing passive AvatarState source writes version 3, adding the actual
`sessionPresent` boolean from `!MyAvatar.getSessionUUID().isNull()`. Its UUID
and all model/bookmark/history properties remain original values. Native
instrumentation remains gated by E2E, iOS and `--testScript`.

The reader retains versions 1 and 2 unchanged. Every active `validate`,
`original`, model/bookmark helper and Source/Peer join still requires an actual
nonnull session. Active source groups now accept embedded state versions 2
and 3 through that same strict reader. World and input joins are unchanged.
False with nonnull UUID, true with null UUID, a scalar boolean substitute and
null in a legacy packet are invalid.

Only the closed `avatar_postlogout.restored` property join accepts a version 3
false/null original. It requires actual native account before/after packets,
an original prior owned-account barrier and genuine `logout-complete` causality
for the actual provisioned child. Candidate/process context, native source
birth/cursors, credential generation, endpoint, event prefixes and the account
clock bracket must agree. It checks independently observed loaded geometry,
rig, model/scale/joints and persisted bookmark entries against the actual
baseline. An originally missing empty product bookmark file may become an
empty persisted map after ordinary save/delete; its original bytes remain
unchanged in evidence. No UUID is substituted and no clock is restamped.

This component supplies a historical property proof. Its caller must retain
the source through an owned acquisition and still establish UI/HTTP/timer/entity
lifetimes, current pixels, paired cleanup and account/provider retirement.
It performs no capture, request, input, Domain join or repair and advertises no
whole feature capability.

The packet producer used by new host tests emits version 3 from its first
snapshot. Genuine old producer fixtures remain unchanged. Actual HTTP/AFC
factory transport, active source composition, null refusal and explicit
postlogout proof/counterexamples are covered; native compilation and devices
remain unverified. `ios-avatar-state` writes 3/reads 1,2,3, while the local
`ios-avatar-postlogout` proof writes/reads version 1.
