# Explicit private whole-feature configuration

The existing `OVERTE_IOS_FEATURE_ADAPTER_CONFIG` file now writes
`iosFeatureAdapterVersion: 5` and reads literal versions 1 through 5. Readers
never add new fields or rewrite retained legacy bytes. The common configuration
still selects private fixture credentials through `fixtureConfig`.

Version 5 retains the existing `graphics`, `create` and `emotes` fields and
requires these additional nullable fields. A selected area requires its own
closed settings object; every unselected area's settings must be `null`.

| Area | Private settings field | Original existing settings contract |
| --- | --- | --- |
| `world-navigation` | `worldNavigation` | Explicit private artifact root |
| `avatar-people` | `avatarPeople` | Private image policy and independent Actor selector; optional separate authority reader |
| `world-web` | `worldWeb` | Private image policy, independent Actor selector and distinct controlled origins |
| `tablet-web` | `tabletWeb` | Private native-screen policy, original existing physical binding/setup packet and distinct origins |

These settings create no SDK, issue no native query, obtain no new permission
and supply no measured feature effect. Existing settings validators retain
their original process/image/origin restrictions. The Tablet setup packet must
later pass actual existing-session admission; configuration alone supplies no
freshness or execution identity.

The operation vocabulary now reserves the existing common terminal protocol
for these four held-resource areas. Scripts, Authentication, Graphics and Create
retain their existing operation triples. The independent complete-area gate
continues to admit only those four source-complete adapters. Configuring any
partial area fails before operation dispatch; parsing new settings cannot
advertise a complete feature capability.

Sixteen no-build host cases pass: all four actual whole-settings validators,
literal legacy-file preservation, missing/unselected/unknown fields, partial
capability refusal, and existing Script/Create/Emote admission regressions.
The native setup packet is an explicit host model.

Worlds now routes its existing whole owner through canonical installed-adapter
Act/Observe/Cleanup and common terminal Inspect/Seal/Finish. The original
30-second work guard includes runtime construction and final verification.
After Finish, the narrow actual original-end reader replaces live SDK binding
verification. A synthetic public End cannot satisfy that reader. Generic SDK
cleanup first checks Worlds ownership: unfinished/orphan carriers, including
originals in a separate configured artifact root, prevent another Stop or SDK
deletion. Only the actual retained completed graph can return cleaned there;
this reader has no live finalization branch. Graphics retains teardown routing
with version-5 configuration as well.

Fifteen additional focused host cases cover actual installed dispatch with
effect spies, forged Finish refusal, actual generic orphan fencing, original
transport deadlines, strict whole configuration and Graphics teardown routing.
These spies establish routing and fences only. Full fifteen-step Worlds
terminal/cleanup integration, partial-preparation retirement and each area's
final qualification remain open. Complete admission still excludes all four
new areas. Native compilation and devices remain untested.
