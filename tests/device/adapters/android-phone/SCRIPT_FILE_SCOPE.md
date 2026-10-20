# Original Script file/source join, version 1

`overte_phone_script_file_scope.join` combines the current private
`PhoneScriptMeasurements.last_sources` with the independent original
`NativeScriptFiles.last_packet`. The Phone factory exposes the latter through
`reader.file_observation()`. Inputs are the run/ticket, original native directory,
fixture URL, actual PID, original source frames, current native epoch, action
barrier and optional previously persisted file cursor. It accepts no expected
state, verb, existence or acknowledgment.

It repeats the existing four-source composition, validates the full original
file envelope and requires the same native birth/PID/run and actual directory.
Present fixtures require `observe`, four actual files and exact controlled bytes;
location presence cannot prove contents. Absent fixtures require the new
[original native location source](../../native/SCRIPT_FIXTURE_LOCATION.md).
Stage/release ACKs, missing/unsupported results, foreign paths/births/runs,
changed/missing bytes and prebarrier/stale/future data fail. All five source
clocks must follow the barrier and agree within 1500 ms. The returned capture
retains their oldest original clock, including an earlier file observation.

The returned private object has `fileScopeVersion:1`, `measurement`, `resources`
and `fileCursor`. Measurement retains the existing six actual Script fields and
native lifecycle. The cursor records only original `instance`, `sequence`,
`capturedEpochMs`, `directory` and `fileScopeVersion:1`; later joins require the
same scope/birth, advancing sequence and nonregressing original clock.
Physical resource aliases are derived from actual observations:

| Alias | Original presence |
| --- | --- |
| `file:script-fixtures` | Present, authenticated native root and four original fixture files |
| `panel:script-manager` | Current passive Script UI open |
| `panel:script-picker` | Current passive picker open |
| `script:owned-script` | Current matching actual engine/service execution |
| `entity:script-effect` | Current actual owned Box, even when its measured tick count is zero |

A removed file root never closes a panel or removes an effect by inference.
Host reservation/cleanup intent is not a physical resource or proof of absence.
Raw paths/IDs/bytes remain private; public aliases contain none of them.

This pure join does not acquire sources, persist provenance or return a full
feature result. The [five-source observation transaction](SCRIPT_OBSERVATION.md) now holds the
shared source lock, persists acquisition uncertainty, restores the four-source
history and retains the original file cursor. It checks factory admission
against the old cursor too; additional queries cannot conceal a rollback. The
full coordinator must freeze normal input/load barriers and wire this transaction
before publishing any full feature result. The four-source transcript intentionally remains separate from this
file cursor; recreating a cursor at each invocation is forbidden. Restart needs
explicit independently proved new-process handoff. Actor facts require separate
original acquisitions and publisher ownership. Cleanup must observe all actual
resources absent and retire original journals; the join never discards them.

Eight additional joined-measurement cases cover actual bytes/resources, original
file clocks, replayed/foreign cursors, stale/prebarrier/ACK-only data, changed or
missing companions, zero-tick actual Box presence and unclosed UI after actual
file release. All forty measurement cases pass on synthetic boundaries. This
is test logic, not a native compilation, product pass or device acceptance.
