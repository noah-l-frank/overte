# Original Emote source selection, version 2

`select_from_roots` now admits normal Phone startup without replacing any script
or moving Emote into a separate manager. Phone's actual default script includes
`phoneEmote.js` in its shared VM. Selection keeps that VM's top-level assignment/
code separate from the actual compiled included Emote code and native caller.
No platform label, expected input or matching filename supplies measured code.

## Reviewed source tables

The existing immutable [Emote pins](../feature_journeys/emote-source-pins.v1.json)
still identify the three reviewed input/chooser variants. The separate versioned
[Phone manager pin](../feature_journeys/phone-emote-manager-pins.v1.json) identifies
the real Phone default bootstrap: original source path, runtime basename, source
commit, UTF-16LE encoding/length/digest and allowed included profile IDs.

The current manager pin names `scripts/+android_phoneInterface/defaultScripts.js`
at `65b4c7e66d5671c5e7ca3d40da3016222bf0bca2`, with 2,018 code units. Its normal
runtime URL is the configured scripts root plus `defaultScripts.js`; Android's
original file selector supplies the Phone variant's bytes. The selected included
Emote is the reviewed 4,827-unit `phone-one-shot-hide-v1`. The host check verifies
both current source bytes and the immutable manager source commit. Pins are never
regenerated from a target or learned from an unknown runtime response.

Manager-pin JSON has exactly `contractVersion:1` and `managers`. Each of its
closed reviewed entries has exactly `id`, `sourcePath`, `runtimePath`,
`sourceBase`, `encoding`, `codeUnits`, `sha256`, `includedProfiles`. Unknown IDs,
paths, runtime names, malformed versions/lengths/digests and unreviewed included
profile IDs fail. This is review metadata, not measured feature state.

## Actual originals and exact selection

The existing root-before / Script-source / root-after original query and
1.5-second ordering, PID/birth, nonce, configured-root and complete native
membership checks remain mandatory. The selected manager must be actually
running, not stopping/finished, and have exactly its own original physical
assignment under that configured root. Original assignment precedes top-level
submission. Only the original physical key or the existing exact normalized
`file:///~//...` key is recognized; an alias cannot supply an assignment.

For the shared Phone manager, original submitted top-level code must match the
reviewed manager pin. Its complete original V8 compilation inventory must contain
one matching top-level compilation under its physical URL or actual original
normalized key, with compilation following submission. It must independently
contain one matching included Emote compilation at the exact resolved physical
Emote URL, after top-level compilation. The original IDs must differ. Matching
names with unknown bytes, same-name foreign/duplicate compilations, missing or
incomplete inventory and future/reordered source times fail.

Only one actual input owner may remain across the recognized standalone and
shared default-manager contexts. Unknown default code, duplicate managers, an
additional standalone Emote, foreign assignments or multiple active surfaces
cannot be silently ignored. A bare legacy `select` call without original root/
assignment evidence cannot adopt included code.

The private selected descriptor retains the existing `profile`, original manager
`url`, `engineInstance`, top-level `code`, `assignedUrl`, `loadGeneration` and
`assignedEpochMs`. For compiled sources it additionally has original `sourceUrl`
and exact `compilation`. A shared-manager selection also has `managerProfile`
(the reviewed bootstrap pin) and original `managerCompilation`.

`code` always identifies the actual owning top-level VM. `compilation` identifies
the actual included Emote code; the two lengths/digests may intentionally differ.
Native caller v2 must independently match both the manager/code and exact included
compilation. Correct loaded animation from the default script itself, another
same-VM Script ID, unknown origin or legacy manager-only caller fails.

Animation asset paths derive from the original included `sourceUrl`, not the
default manager directory. Actual Phone clips therefore join
`<scripts-root>/system/assets/animations/...`. This is independently checked
against loaded native clip URLs and poses; no URL is returned as a measurement
merely because it appeared in an input or reviewed profile.

## Compatibility, ownership and limits

The existing v1 standalone source-pin schema remains readable. Legacy standalone
observations and caller-v1 histories remain historical inputs to existing joins.
New standalone native packets carrying compilation evidence must prove their
own original top-level compilation too and acquire the compiled descriptor.
Caller v2 cannot qualify a legacy descriptor by ignoring origin; compiled
descriptors cannot use caller v1. Missing new facts have no fallback to a file
reread, platform name or expected animation.

This pure selector owns no product input, timer or UI lease and provides no full
feature result. Actual approved scene/all-manager admission, selected-function
timer/callback lifetime, background/failure recovery, authenticated independent
publication and whole-run retirement remain required. In particular, the current
manager-wide timer-absence helper cannot prove shared-VM Emote retirement while
other normal default scripts keep their own timers; selected work needs original
function/registration provenance. No foreign timer may be cleared to satisfy it.

Host tests compose real root/source/selection, native Rig playback/restore,
ordinary Phone inputs, independent actor effects and original image logic over
explicit synthetic boundaries. They verify test logic only. No native code is
compiled and no product/device qualification is recorded. Complete Phone areas
remain three of fourteen; the full Emote capability stays unavailable.
