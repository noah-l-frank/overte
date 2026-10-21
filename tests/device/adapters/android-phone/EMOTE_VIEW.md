# Owned ordinary Phone Emote view, version 1

`PhoneEmoteView` prepares and restores the controlled domain's avatar view using
the existing normal tablet/Settings/View-menu surface. It never loads a
serverless scene, sets a camera/avatar/setting through a test getter, or enables
a complete Emote capability. Controlled marker/content ownership, current Rig/
input/image/actor joins and whole-feature retirement remain separate work.

## Preconditions and original sources

The caller holds `phone-script-sources.lock`, supplies the existing Emotes
`PhaseFixtureReader`, and an existing candidate/process-bound read-only runtime.
Preparation accepts only active baseline; cleanup/retirement accept active
cleanup. Each step obtains fresh original configuration, avatar/render and
[touch](../../native/PHONE_TOUCH_STATE.md) packets between two original fixture
phase queries. Both phase histories must match. Original Model/Rig/Geometry,
loaded-source and [actual bundled resource bytes](../../native/PHONE_AVATAR_CONFIGURATION.md)
are independently joined; custom, missing or changed avatars fail closed.

The controlled fixture must start with the bundled default mannequin and the
normal default perspective boom: First Person at 0.5, or Look At/Selfie at 1.5.
Other original zoom profiles are refused before any input: ordinary menu cycling
can restore these exact native defaults. An existing foreign tablet is refused.
All steps preserve original feet within 1 cm, orientation within 0.001 and model
scale within 0.0001; an unexpected gesture movement does not become an assumed
new baseline. The enclosing controlled-domain owner must validate original
world/domain/content/Script membership and exclude foreign occluders or motion.
This view owner alone does not prove that the world is controlled.

## Normal input and interruption

The existing Graphics surface now exposes its shared normal `open_settings`
path, also used by its unchanged Graphics page opener. Emote view extends only
General preferences recognition: the actual Save/Cancel IDs must both be present.
It uses normal `settings.general`, the unique visible enabled checkable checkbox
`Enable two-finger perspective zoom`, and normal `GeneralPreferencesSave`.
Actual native saved preference, independently read afterward, must agree; a
checked editor or Save ACK cannot supply that fact. General/tablet/menu leases
are persisted before opening input and retired only after actual UI absence.

Normal View selects Selfie and independently observes its actual native mode.
After dismissing owned panels, at most six distinct W3C pinch gestures expand
the actual measured boom to [3,12]. Each has two touch sources, eight 80-ms moves,
an initial 100-ms hold and explicit pointer-up. The first contact stays at
(0.55,0.35); the second moves from (0.65,0.35) to (0.73,0.35), as fractions of the
original viewport. This keeps the first look-region contact stationary. Window
extent must be at least 240x240 and at most 16384. Driver support and actual
layout/gesture delivery are unqualified until laboratory testing; absent zoom
or unexpected avatar movement fails. Every pinch finally releases this owned
W3C session, then requires independent actual native contact/axis retirement.

Each high-level step persists `issued` before constructing/delivering input.
Every normal subinput persists its actual subject/widget and current matching
fixture-phase original first. A reconstructed issued step only re-observes its
actual result; it never repeats that gesture/button chain. Later distinct
steps may proceed after a proven effect. A lost camera return retains its panel
leases and is followed by a separate owned dismissal. Unknown/partial failed
steps stay red and may enter cleanup under the new cleanup ticket.

## Restoration and ownership

Cleanup first releases the owned SDK input session and independently observes
native drainage, then dismisses only owned General/tablet/menu UI. Normal First
Person resets actual boom to 0.5; selecting the original camera restores its
native default. Normal General checkbox/Save restores the original saved pinch
setting. A final separate original acquisition verifies original camera/view
position, orientation, projection, loaded identity, pose, boom and setting, all
contacts released and all own UI leases retired. A repeated cleaned call obtains
new facts and sends no camera/preference input. Ignored restoration stays red.

The private journal `phone-emote-view.json` is exactly `emoteViewVersion:1`,
`runId`, `fixtureUrl`, `binding`, `payload` (the existing bounded packed codec).
The decoded record is `phase`, `original`, `current`, `leases`, `actions`,
`active`. Phases are reserved/preparing/active/restoring/restored. Snapshot fields
are `configuration`, `avatar`, `touch`, `phaseBefore`, `phaseAfter`. Leases are
boolean tablet/address/menu/general. At most 24 unique closed step kinds and
96 subinput records per step are accepted. Each step is exactly `kind`, `phase`
(issued/observed), `intents`, `before`, `after`. Intent is exactly `stage`,
`control`, `subject`, `graphics` (original widget packet or null), `fixturePhase`.
Snapshots retain full original source identities/times; no retiming or implicit
journal migration is allowed. Failed writes latch the live owner; reconstruction
uses only the durable original. Foreign CAS replacements stay untouched.

`retire(retain)` obtains another fresh restored snapshot and requires the
parent's callback to durably retain that exact proof in its own bound journal
before child removal. False/failed retention leaves child responsibility. A lost
removal return can leave the proof with the parent; a missing child alone never
reconstructs success. General Appium cleanup refuses any remaining view journal,
including unknown/partial metadata. The full parent must still retire every
other fixture/source/input/image/actor resource before declaring cleanup.

The whole method is bounded to 60 seconds, each combined source acquisition to
5 seconds and source/phase freshness to 1.5 seconds, including final durable
writes/copies/guards and a monotonic age floor. Frozen wall clocks do not hide
late delivery. Nineteen Phone host cases exercise real UI recipes/readers and
private filesystem journals over explicit synthetic boundaries, including ignored
input, lost returns, phase races, altered evidence, late delivery and incomplete
cleanup. They establish test logic only. Native additions are uncompiled; the
complete Phone area count remains 3/14 and all devices remain unqualified.
