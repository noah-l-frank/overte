# Phone original Emote input protocol v1

`_emote_controls(selector,intent,read_only=False)` connects the existing guarded
Phone adapter, `PhoneEmoteIO`, actual tablet visibility and `TokenEmoteUI` to the
normal native Qt channel. See [the exact shared contract](../../native/NORMAL_EMOTE_CONTROLS.md)
for IDs, typed fields, original tokens, source bounds and cleanup ownership.

This is an internal input/observation component, not a full Emote adapter. The
complete independent original Script/Rig/pose/image/actor/cleanup join remains
missing and `feature.emotes.*` is not advertised. Android Phone therefore still
has three of fourteen complete source adapters: Scripts, Authentication and
Graphics. Native instrumentation remains uncompiled and every device untested.

The older Phone source hides the chooser after Play; the reviewed Main parity
source retains it. The input reader measures actual visible UI and does not
change either product behavior. Full tests must retain source-profile identity
and report a real mismatch; UI labels or ACKs cannot override actual Rig history.
