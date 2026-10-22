# Passive animation inventory and Emote readiness, version 1

This E2E-only source observes existing `AnimationCache` resources on their actual
GUI owner thread. It neither instantiates a cache nor calls `getAnimation`,
`getResource`, `prefetch`, refresh or loading methods. It accepts no requested
URL, name, expected digest or result. The original registry method compiles and executes with real Qt5 weak owners
and locks, with explicit resource-loading/row seams. Full AnimationCache and
application native compilation remain unverified; devices remain unqualified.
Complete Pico Emotes remains unavailable.

## Query and original packet

The command has exactly `schemaVersion:1`, fresh `commandId` (32 lowercase hex;
the shared decoder also supports the explicit `ios-` protocol), and
`action:"feature-animation-inventory-observe"`. The GUI-marshalled
`Test.featureAnimationInventory` requires the existing test-results location,
live native lifecycle and `--testScript` admission. `isSet<AnimationCache>` must
precede `get`: observing must not instantiate a cache. The probe deduplicates
the request and saves `feature-animation-inventory.json`; a missing hook remains
unavailable. Pico `_animation_inventory_observer(target)` uses existing original
file transport and candidate/session/PID guards without repair.

The exact packet is `animationInventoryVersion:1`, `commandId`, native birth
`instance`, increasing `sequence` (1–1,000,000,000), actual `processId`, original
`requestedEpochMs`, `capturedEpochMs`, and `source`. A complete source has:

| Field | Actual meaning |
| --- | --- |
| `complete:true` | Entire bounded registry inspected, unchanged weak map and live/expired states |
| `registrySlots` | Actual weak registration slots, 0–1,024 |
| `expiredSlots` | Actual slots whose resource owner had expired |
| `resources` | Unique live animation objects, 0–256, sorted by resource UUID |

Each exact resource row has `resourceInstance` (32 lowercase hex), `urlSha256`
(actual `getURL().toString().toUtf8()` digest), actual boolean `loaded`/`failed`,
positive `registrySlots` for that object, and `model` (the original
[parsed data record](ANIMATION_SOURCE.md), or null). Duplicate registrations
increment a single object's count. Live plus expired slots must equal the
complete registry count. Unknown parsed provenance stays unknown when loaded.

Native acquisition copies weak owners under the registry read lock, examines
temporary strong references outside that lock, requires each actual GUI owner
thread, then rechecks the weak map and every live/expired state. Weak equality
includes the control block; reused addresses cannot impersonate old entries.
Temporary strong references never escape acquisition. More than 1,024 URL keys/
slots or 256 objects, changed registry, wrong thread or incoherent repeated object
yields exactly `source:{complete:false}`, never a truncated or guessed inventory.
Global resource URLs are hashed to avoid exposing unrelated private URLs.

## Strict reader and readiness join

`NativeAnimationInventory.read(after_sequence)` sends one query, uses at most
51 file reads at 100 ms intervals, and has a five-second monotonic bound.
Device age and final identity/copy/guard work must fit 1.5 seconds; a frozen
external clock cannot hide latency. Birth, PID, nonce, counters and original
timing must agree. Failure does not replace the last accepted snapshot/maps.
Model metadata and resource URL identities remain immutable across temporarily
absent rows in that reader, with 1,024 identities per map and no eviction.
`restore(original)` restores only that historical cursor/snapshot. Whole-run
reconstruction must retain and validate all original transitions separately;
one latest snapshot cannot establish omitted history or fresh facts.

`emote_animation_readiness.ready(group,pid,epoch)` requires exactly
`rootsBefore`, `script`, `inventory`, `rootsAfter`. Independent configured-root
reads bracket the actual compiled Emote source and cache query. PID/native birth
agree, Script capture precedes cache request, and cache capture precedes the
final root request. The complete group fits the existing 1.5-second window.
The original physical compiled source resolves its fixed animation directory.
Each of twelve actual URL hashes must have exactly one original live resource,
loaded/not failed, with known model, full parser, actual URL digest and fixed
byte pins. Multiple different objects at a needed URL are ambiguous; duplicate
slots for one object remain allowed. Empty/missing/pending/failed/unknown entries
and wrong bytes at the right URL fail. Unrelated resources need not disappear.

The returned private proof is `emoteAnimationReadinessVersion:1`, complete
original `group`, and twelve `{name,resource}` rows. Names resolve through the
observed source directory; resources are original measured rows. This proves
neither input, playback, pose, pixels nor peer delivery.

## Owning adapter handoff and cleanup

The full Pico coordinator must acquire the group under the existing Script
source lock, enforce a whole-operation monotonic deadline, join current fixture
phase/run/candidate/session, durably retain original transitions and require
actual readiness before Emote input. Any loading poll must use a separately
classified loading condition; invalid evidence and failed resources must not
be repaired or retried. This owning admission/recovery composition remains
pending; the component advertises no complete capability.

No file lease, timer, contact, entity or network request is created. Private
getter output follows existing probe artifact retention/teardown. The enclosing
run must still retire captures, UI/input ownership, fixtures, source journals
and its authenticated actor. Hardware-free factory/JS/cache/content
counterexamples establish test logic only, not native compilation or behavior.

## Pico selection and compiler finding

The reviewed fixed Phone commit is
`abb7f6b60d97daf17752aadf94e2b5df099bb7ba`; its live worktree is untouched.
The common Python reader and readiness join are selected exactly. Only guarded
observation methods/declarations are selected from AnimationCache: the Pico
functional full-FBX parser remains unchanged. Original ScriptManager load and
resolve paths expand normalized file aliases to actual configured physical URLs;
the join uses the original assigned source, never a guessed animation URL.
The actual Pico separate Emote VM and unrelated bootstrap are covered together.

The first Qt5 compile found the selected local C++ name `slots` conflicts with
Qt's keyword macro. Renaming that observation counter to `slotCount` fixes the
E2E source and retains Qt keywords. No build flag or functional parser is changed.
The compiler check extracts the actual registry method, with real nested weak
maps, expired owners, registry mutation, duplicate slots, object/thread/type
refusals and bounds; resource loading and Animation row values are explicit
seams. This is not full application or model-parser compilation.

The native getter retains up to 4,096 consumed original query nonces, including
unavailable acquisitions. Reusing a native nonce fails; the probe suppresses its
current duplicate poll so it cannot overwrite an original successful response.
The output is explicitly admitted only to the existing private E2E result area.
No public whole Emote capability is enabled by cache readiness.
