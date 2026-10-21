# Ordinary Pico Graphics preference ownership

`graphics-journey-preferences` v3 reuses the frozen durable preference transaction
architecture and pins the scene's explicit `pico-stereo-v1` policy. Sources and
hashes are listed in [`FROZEN_REFERENCE.json`](../graphics_journey/FROZEN_REFERENCE.json).
No Phone/iOS source or journal is changed or implicitly migrated.

After the [scene owner](GRAPHICS_SCENE_OWNER.md) establishes actual readiness,
`prepare()` acquires two advancing original native settings/lifecycle packets.
The current generic Qt slider has range 0.1–2.0 and step 0.1. An off-grid original
such as 0.65 fails before preference input because normal input cannot restore
it. Later scalar actions also check the actual current widget range/grid.

`act()` supports the common open/close/resolution/haze/mirrors/restore-original
verbs through the actual Pico token surface and ordinary Home ray. Every step
and input intent is durably reserved before dispatch. Actual native settings
are read separately from widget readback; unrelated preference changes fail.
Repeated tickets and uncertain applied steps acquire new original observations
without repeating an input. Ignored sliders, source birth/cursor changes, failed
intent writes and expired ownership callbacks preserve unresolved records.

Closed-tablet status uses the actual closed navigation snapshot. The input-only
Graphics control wrapper requires an open ready page and is not reused to claim
closed UI. Address dismissal does nothing when there is no address or address
lease; the subsequent tablet close still performs the ordinary Graphics Home
ray before physical close. Foreign address pages remain refused.

`cleanup()` restores only the exact original resolution/haze/mirrors and closes
owned UI, with per-substep source proofs. Partial restoration with a lost applied
scalar receipt does not repeat the scalar. Final native settings must match all
original fields; `retire()` verifies actual journal absence. Operations are
bounded to 30 seconds, histories to 128 tickets/intents, and restoration to five
substeps. `graphics-journey-source-history` v1 restores original native histories
and passive weak UI/QML inventories without sending a new read or input.

These are source/host-verified internal owners. A matching widget/native setting
is not evidence of a rendered effect. Original two-eye images, independent actor,
background/restart, original files and complete native UI/HTTP/Web/capture quiet
retirement are still required by the full Graphics coordinator. This packet
advertises no complete Graphics capability. Native compilation and all devices
remain unverified.
