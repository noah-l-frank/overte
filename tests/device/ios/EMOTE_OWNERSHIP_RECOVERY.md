# Emote local ownership recovery

`IOSEmoteSources` and configured `OriginalAvatarPeerSources` accept an explicit
`ownership_only=True` constructor mode for already existing private owners.
This mode performs guarded local CAS, original-file validation and recovery of
interrupted passive reads. It has no SDK/runtime/reader attachment. It cannot
read a current source, send native input, create a new original or manifest,
append a qualified frame or increase its revision. It is mutually exclusive
with historical mode and never toggles a historical object into a live one.

The only changing source CAS removes the exact pending owner after the actual
recovery journal has retained the hashed abandoned original, matching the
original prior owner and unchanged target owner. Clearing an unjournaled
pending read fails. Original partial files, immutable frames, source histories
and identities remain intact. No normalized current effect or native cleanup
fact is established by this mode.

Inactive-run finalization can use this narrow ownership transition when the
other role's SDK is already gone. The caller still checks its own actual SDK,
process and fixture binding through a real read-only continuity guard; actual
native resource and pointer retirement require separate fresh originals and a
validated quiet interval. Fixture retirement permits publication/metadata
responsibility to end and never replaces product cleanup.

Four mode tests cover both source types using real private files, together with
31 existing source/peer/recovery compatibility tests. Native and SDK producers
remain modeled; this is not device acceptance. No whole Feature 5 capability
is enabled by this internal constructor option.
