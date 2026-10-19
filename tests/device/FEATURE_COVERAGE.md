# Fourteen-area feature coverage

Source audit base: `7636452f2124029798948aafae70ecff5c5fa7d0`. The historical
coverage summary was checked against the actual source modules before extending
them. The original common packet changed only its own test worktree. The later
authorized continuation adds E2E-only instrumentation to native sources; other
sessions, frozen builds, global workflows and acceptance evidence stay unchanged.

Every row means **test logic exists · adapter missing · untested on devices**.
These are implementation statuses, not complete product-feature acceptance.
The [source compatibility review](FEATURE_SOURCE_COMPATIBILITY.md) identifies
remaining platform Emote prerequisites. Version 5 corrects ordinary override/chooser semantics, adds nine automatic completions and a separate early-restoration check. Version 4 corrects Graphics to immediate settings and independently measured original preferences. Version 2 corrected Scripts to the real file-bundle picker; version 3 corrected
Audio to automatic in-memory capture/play/drain/completion;
its adapter input/observer join is still incomplete. Host logic is present; it is not yet a qualified
product workflow. No complete area adapter is advertised.
The later [local adapter packet audit](FEATURE_ADAPTER_IMPLEMENTATION.md)
records narrower foundation implementations and concrete native blockers; no
complete new area triple has been enabled by that work.
The [controlled HTTPS account backend](feature_journeys/ACCOUNT_PROVIDER.md) now
supplies real owned grants/profile access and delayed-response/revocation controls;
native Authentication observation/input and complete adapter composition remain open.
Existing adapters may cover portions of the reused foundations; none is claimed
to implement the new complete area contract.

| Area | Existing common modules retained | Added shared user flows | Required additional evidence | Status |
| --- | --- | --- | --- | --- |
| world-navigation | `domain-enter`, `domain-roundtrip`, `places-navigation`, `look`, `move`, `input-neutral`, `collision`, `jump`, `fly`, `scene-reload` | Bookmark CRUD and restart durability; directory/search, failed navigation, recovery. | changed, image, peer | Logic present; adapter missing; device untested |
| authentication | No prior feature journey | Invalid login, cancel, delayed stale completion, successful login, restart, logout and revocation. | peer | Logic present; adapter missing; device untested |
| avatar-people | `multi-user` | Avatar URL/bookmark, scale, wearable, invalid URL, mutual contact consent/cancel/reject/removal. | changed, image, peer | Logic present; adapter missing; device untested |
| create | `create-management`, `entity-sync`, `world-interaction` | Model/texture/voxel import/edit, original export, cancellation and rez permission denial/recovery. | changed, file, image, peer | Logic present; adapter missing; device untested |
| emotes | No prior feature journey | Ten actual native overrides, nine automatic completions, all observed Sit variants, chooser lifetime, early restoration and resume. | changed, image, peer | Logic present; adapter missing; device untested |
| world-web | `world-web-video` | Real text/bridge, foreign origin rejection, navigation/Back, 404/reload and background resume. | changed, image, peer | Logic present; adapter missing; device untested |
| graphics | `render-health` | Immediate resolution/Haze/Mirrors, actual completed-frame/pass effects, close/restart durability and measured original restoration. | changed, image | Logic present; adapter missing; device untested |
| audio | `audio-controls`, `permission-recovery`, `sound-playback`, `voice-roundtrip` | Automatic memory capture/play/drain/completion, real cancel, muted rejection/cancel and background cancellation; OS permissions remain in the composed foundation. | audio, file, peer, silence | Logic present; adapter missing; device untested |
| chat | `text-input` | Unicode send/receive, keyboard Back, filter, history reopen, offline failure and exactly-once retry. | peer | Logic present; adapter missing; device untested |
| snapshots | `snapshot-output-parity` | Cancel/permission denial, original capture/share bytes, share cancel, upload failure/retry and resume. | file, image, peer | Logic present; adapter missing; device untested |
| scripts | `scripts-management`, `scripted-entity` | File-bundle picker cancel/accept, actual relative companion execution, application restart, stop and URL failure; separate existing entity-script consent. | peer | Logic present; adapter missing; device untested |
| assets | `asset-load` | Upload cancel, browse, companion mappings, rename, bake, Add to World and original resolved bytes, permission denial, delete and 404. | changed, file, image, peer | Logic present; adapter missing; device untested |
| lifecycle-input | `lifecycle-under-load`, `tablet-input-isolation`, `text-input` | Create/Chat/Scripts editor focus, Back, world-input isolation, resume, context replacement and stale input. | changed, image, peer | Logic present; adapter missing; device untested |
| tablet-web | `tablet-web-video`, `tablet` | Same browser flows plus ordinary inline app routing and input ownership. | changed, image, peer | Logic present; adapter missing; device untested |

All areas also require fresh product samples, independent baseline/cleanup
observations, native lifecycle counters and empty owned-resource inventories
after cleanup. `image` means actual current challenge-bearing pixels; `changed`
also requires changed feature-subject pixels; `audio`/`silence` inspect PCM;
`file` inspects original bytes; `peer` reads the independent actor journal.
Existing modules retain their additional image, PCM, process and file checks.

The [machine matrix](feature_journeys/coverage.v5.json), [journey guide](FEATURE_JOURNEYS.md)
and [adapter handoff](FEATURE_ADAPTER_HANDOFF.md) record the exact contracts.
All rows currently depend on real product transports and independently measuring
target observers. That dependency belongs to the later adapter implementation
phase; absent capabilities, missing observations and missing prerequisites fail
closed. The source-contract corrections above are open implementation work too.

The aggregate `feature-journeys` suite includes the union of the existing modules
above, one mandatory capability gate per area, and all fourteen extensions.
Individual `feature-<area>` suites include only their own foundation and extension.
Long stability campaigns, upgrade/install paths and unrelated accessibility suites
retain their existing separate owners and are outside this local no-device scope.
