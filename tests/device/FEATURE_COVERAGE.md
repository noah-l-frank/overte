# Fourteen-area feature coverage

Source audit base: `7636452f2124029798948aafae70ecff5c5fa7d0`. The historical
coverage summary was checked against the actual source modules before extending
them. No existing worktree, product source, frozen build, global workflow or
acceptance evidence was changed.

Every row means **test logic exists · adapter missing · untested on devices**.
These are implementation statuses, not complete product-feature acceptance.
The later [local adapter packet audit](FEATURE_ADAPTER_IMPLEMENTATION.md)
records narrower foundation implementations and concrete native blockers; no
complete new area triple has been enabled by that work.
Existing adapters may cover portions of the reused foundations; none is claimed
to implement the new complete area contract.

| Area | Existing common modules retained | Added shared user flows | Required additional evidence | Status |
| --- | --- | --- | --- | --- |
| world-navigation | `domain-enter`, `domain-roundtrip`, `places-navigation`, `look`, `move`, `input-neutral`, `collision`, `jump`, `fly`, `scene-reload` | Bookmark CRUD and restart durability; directory/search, failed navigation, recovery. | changed, image, peer | Logic present; adapter missing; device untested |
| authentication | No prior feature journey | Invalid login, cancel, delayed stale completion, successful login, restart, logout and revocation. | peer | Logic present; adapter missing; device untested |
| avatar-people | `multi-user` | Avatar URL/bookmark, scale, wearable, invalid URL, mutual contact consent/cancel/reject/removal. | changed, image, peer | Logic present; adapter missing; device untested |
| create | `create-management`, `entity-sync`, `world-interaction` | Model/texture/voxel import/edit, original export, cancellation and rez permission denial/recovery. | changed, file, image, peer | Logic present; adapter missing; device untested |
| emotes | No prior feature journey | Ten real Emote choices, all three actually observed Sit variants, override/cancel and resume. | changed, image, peer | Logic present; adapter missing; device untested |
| world-web | `world-web-video` | Real text/bridge, foreign origin rejection, navigation/Back, 404/reload and background resume. | changed, image, peer | Logic present; adapter missing; device untested |
| graphics | `render-health` | Preset cancel, actual render scale/shadow graph, mirror, apply/restart durability and restore. | changed, image | Logic present; adapter missing; device untested |
| audio | `audio-controls`, `permission-recovery`, `sound-playback`, `voice-roundtrip` | Recording permission, cancel, save, preview/stop, mute, background silence and discard. | audio, file, peer, silence | Logic present; adapter missing; device untested |
| chat | `text-input` | Unicode send/receive, keyboard Back, filter, history reopen, offline failure and exactly-once retry. | peer | Logic present; adapter missing; device untested |
| snapshots | `snapshot-output-parity` | Cancel/permission denial, original capture/share bytes, share cancel, upload failure/retry and resume. | file, image, peer | Logic present; adapter missing; device untested |
| scripts | `scripts-management`, `scripted-entity` | Local/folder companions, consent cancel/reject/accept, application restart, stop and 404. | peer | Logic present; adapter missing; device untested |
| assets | `asset-load` | Upload cancel, browse, companion mappings, rename, bake, Add to World and original resolved bytes, permission denial, delete and 404. | changed, file, image, peer | Logic present; adapter missing; device untested |
| lifecycle-input | `lifecycle-under-load`, `tablet-input-isolation`, `text-input` | Create/Chat/Scripts editor focus, Back, world-input isolation, resume, context replacement and stale input. | changed, image, peer | Logic present; adapter missing; device untested |
| tablet-web | `tablet-web-video`, `tablet` | Same browser flows plus ordinary inline app routing and input ownership. | changed, image, peer | Logic present; adapter missing; device untested |

All areas also require fresh product samples, independent baseline/cleanup
observations, native lifecycle counters and empty owned-resource inventories
after cleanup. `image` means actual current challenge-bearing pixels; `changed`
also requires changed feature-subject pixels; `audio`/`silence` inspect PCM;
`file` inspects original bytes; `peer` reads the independent actor journal.
Existing modules retain their additional image, PCM, process and file checks.

The [machine matrix](feature_journeys/coverage.v1.json), [journey guide](FEATURE_JOURNEYS.md)
and [adapter handoff](FEATURE_ADAPTER_HANDOFF.md) record the exact contracts.
All rows currently depend on real product transports and independently measuring
target observers. That dependency belongs to the later adapter implementation
phase; absent capabilities, missing observations and missing prerequisites fail
closed. No row is blocked from device-free test-logic implementation.

The aggregate `feature-journeys` suite includes the union of the existing modules
above, one mandatory capability gate per area, and all fourteen extensions.
Individual `feature-<area>` suites include only their own foundation and extension.
Long stability campaigns, upgrade/install paths and unrelated accessibility suites
retain their existing separate owners and are outside this local no-device scope.
