# Passive current Chat profile source v1

A new application process does not own the previous `ChatProfileOwner`'s saved
variants. Calling its old `inspect` or acquiring a new profile cannot prove
restoration of those original values. `featureChatProfileCurrent` therefore
exposes a separate passive source with no original/adopted/restored result.
The host must independently compare these actual current fingerprints against
the retained old native profile owner and qualify process/candidate/birth.

The exact command is `{schemaVersion:1, commandId:<32 lowercase hex>,
runId:<32 lowercase hex>, action:"feature-chat-profile-current"}`. Extra keys,
expected hashes, caller-supplied original values, mutation operations, foreign
runs and reused native nonces are refused. Native requests are capped at 4096;
unknown/missing sources remain unavailable. The original probe deduplicates its
current command before calling the native getter and preserves the actual
result, including unavailable. It does not manufacture restoration success.

The getter is compiled only with `OVERTE_E2E_FEATURE_TESTS`, requires the actual
`--testScript`/private test-result admission, original native lifecycle and live
original `Setting::Manager` dependency on the same Qt thread. It never creates
that dependency. It reuses the original `ChatProfileOwner` fingerprint helper
and actual `featureChatSnapshot()` barrier: fixed `ArmoredChat-Messages` and
`ArmoredChat-Config` manager-cache variants, original queued writer variants and
independently acquired physical INI/registered-JSON bytes. Physical parsing never
uses a second QSettings object as evidence. Existing original FD/path, format,
canonical JSON, duplicate/alias, ancestor, type, queue and bounded job checks
are unchanged. No ordinary settings/permission/product behavior is modified.

An original closed Chat view is acquired independently before that settings
barrier. Focus/draft/keyboard/page visibility, pending/racing settings jobs,
nonempty messages, missing physical evidence or cache/worker type disagreement
refuse the packet. Actual config changes can be returned as different current
fingerprints; they never become a `restored` claim. Original private variants
never leave the native owner. Only fixed-key fingerprints and original
manager/writer/view identities, sequences and epochs are serialized.

The closed DTO contains `chatProfileCurrentVersion`, `commandId`, `runId`,
`instance`, `sequence`, `processId`, `capturedEpochMs`, `current`, `settings` and
`view`. `current` has exactly the existing native profile fingerprint shape;
`settings` contains manager/writer instances, mutation sequence and actual
epoch; `view` contains original instance, sequence and epoch. There is no saved
`original`, owner token, pathname, raw config/history or success flag.

`NativeChatProfileCurrent.read(run)` preserves both the strict original DTO and
exact acquired UTF-8 bytes/hash. It enforces PID/run/source, manager/writer/view
continuity and the unchanged 1.5-second whole-acquisition freshness bound. Both
returned/cursor copies and raw-byte hashing precede the last original guard and
native/host clock checks. A failure commits neither cursor nor raw originals.
The private Pico `_chat_profile_current(target)` factory uses the existing live
candidate/process guards and actual native writer. It does not open/retire a
receive cache, acquire/restore profile ownership or deliver normal UI input.
Output uses the original private feature-result writer; the explicit alias is
retained for older bases, while integrated builds also admit closed lowercase
`feature-*.json` through the hardened general private writer.

Checks compile the full original Qt5 `SettingManager.cpp`, its actual moc and
worker, original `SettingHelpers.cpp` JSON producer/reader and `SharedLogging.cpp`
with this actual header. INI and registered JSON both prove zero writes by the
passive source, no original owner acquisition, distinct cold manager/writer
identities, actual changed-current facts, physical-history refusal despite empty
live cache and native JSON through the strict Python validator. The closed view
is an explicit native UI seam. Python/Node tests cover original probe behavior,
unknown/birth/PID/run/type/age faults, immutable returned/cursor values, final
copies/guards/clocks and extra caller expectations. Two actual Pico factory
checks preserve the original live verifier/binding logic with synthetic APK and
native IO, including candidate change before native dispatch.

These are host/source proofs. They do not compile the complete Interface/TSI
translation unit, run an Android process/device, establish old-PID ESRCH, compare
new process values to the retained old profile, grant a hermetic AC receipt,
retire a journal or complete Chat. The whole restart/archive owner must still
supply those separate original joins.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_chat_profile_current self_tests.test_chat_profile_native_probe -v
PYTHONDONTWRITEBYTECODE=1 python3 tests/device/contracts/chat/test_chat_profile_current_native.py -v
```
