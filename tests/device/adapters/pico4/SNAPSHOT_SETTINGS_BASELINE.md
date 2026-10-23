# Passive pre-input Pico Snapshot settings baseline

This private component records the actual thirteen Snapshot settings entries and
the actual native format Handle state before the first normal feature input of
a new run. It adds no settings setter, restore operation, product control,
initialization call or dependency creation. Snapshot whole/device acceptance
remains false. Older runs without this original are not upgraded.

## Original native source

The closed key list follows the frozen Phone reference
`3fa8031aa6787af909c6a1701c21536d584c392b`. Its lease cannot be copied as a passive
observer: `_snapshotFormat.isSet()` and `get()` call `maybeInit()`, and the actual
`Setting::Manager::loadSetting()` uses `_settings[key]`, which can insert a
previously absent key. Its restore setters and Phone authority are not selected.

The new `Setting::Manager::featureSnapshotSettingsEntries()` instead reads all
thirteen entries under the existing 25 ms bounded read lock using `contains`
and `value`, retaining presence separately from the actual QVariant. It accepts
unset/invalid, Boolean and string originals; unsupported types, embedded NUL,
oversized values or a blocked lock are unavailable. No normalization repairs a
bad value. The existing original manager instance is retained.

The dedicated Handle accessor reads `_isInitialized`, `_isSet`, `_value` and
`_defaultValue` directly, without `get`, `isSet`, `maybeInit`, registration or a
writer. Its string-only accessor exists only in the dedicated E2E Pico build
and requires `--testScript`. The actual Snapshot getter also requires its
original GUI thread, native review, an existing settings dependency and bounded,
once-unique commands. The Snapshot identity is created with the actual object,
not inferred on the first read. The TSI wrapper retains the existing weak,
bounded observation queue and original lifecycle/HMD/private-directory gates.
The non-Pico getter returns no observation.

The response preserves both the raw entries and cache state, plus the original
`QDataStream::Qt_5_12` QVariant serialization and SHA-256. JSON is diagnostic;
it cannot replace the typed original or become an input value. The source has
no desired settings, expected result, restore payload or writable format field.
The private probe action/file is `feature-pico-snapshot-settings-originals` /
`feature-pico-snapshot-settings-originals.json`; it uses the original source
lock and private result writer. Reader checks include byte bounds before
parsing, original manager/Snapshot births, nonce/sequence continuity and final
native/monotonic age after the last guard. An unavailable read does not become
an original baseline.

## New-run ownership and normal input

Call `_snapshot_settings_baseline(target, run, phase_source, parent=cancel,
source_lock=cancel.lock)` while the new Cancel parent still has no state,
preferences, navigation ownership or original input journal. This factory
attaches one exact lease to that actual parent and lock. The ordinary
`cancel.prepare()` captures the original under the actual baseline phase before
arming the existing capture source or issuing normal input.

Opting in selects private Cancel version 3. Its header pins
`settingsBaselineOriginalSha256`, derived from the original raw receipt,
phase and binding. The source and frame grammar remain the existing version 2
flow. Default runs retain version 2; versions 1 and 2 remain readable, and the
existing explicit v1-to-v2 continuation cannot manufacture this baseline.

Immediately before the first normal controller publication, the existing
parent admission reads the independent settings source again and requires the
exact original typed bytes, entries, cache and native births. It saves the
admission before the parent's final exact phase/clock fence. The existing
Session intent then binds that actual envelope after the parent delivery CAS.
This callback performs only private host validation/CAS and never queries the
SDK, fixture, native source or Session. The parent's original pure publication
age check covers both CAS operations. Late phase advance, changed settings or
slow CAS refuses the original writer without restaging input.

Cold factories reopen the exact lease and its original continuity floor. A v3
parent without that lease, or an orphan original manifest/chunk, is unavailable;
it cannot fall back to a v2 run. An existing parent without a baseline cannot
capture one later, even if it has not yet opened the tablet. The original SHA
survives the ordinary Capture/Cancel/quiet/retire/Still path and its normal
private schema handling. `PicoSnapshotSaveOwner` accepts the original v3 parent
with the same unchanged save grammar. All journals remain retained.

After the first input is bound, `observe()` can record further actual reads and
report whether their exact typed state matches the original. A changed cache
or entry is observed as changed. No method writes the old value back, clears a
Handle, resets initialization or retires an unresolved journal.
`settingsRestored`, `fullSnapshotRecipe` and `deviceAcceptance` remain false.
This is the missing original for future new-run restoration work; capture alone
is not a complete restore/cleanup or whole Snapshot result. Existing Close
records and their explicitly partial settings boundary are not retroactively
requalified.

## Host proof and limits

The Qt harness compiles the complete actual Handle header, original protected
initialization flag, actual raw read/lock, serializer, Snapshot method and TSI
getter body. It uses actual Qt maps, threads and clocks. Missing dependency,
blocked writer, malformed original, foreign thread, duplicate query, runtime
gate, actual initialized-cache change and other-platform getter are checked.
Manager storage/DI, ordinary initialization/write delivery, lifecycle/HMD/UI and
the complete client translation unit are explicit seams. No global settings
writer or product process starts. The original cache read and map are unchanged;
ordinary test setup calls to the existing Handle show that later cache state is
reported separately rather than retroactively substituted for the baseline.

The normal host cases exercise the actual candidate verifier, private Pico
factories, shared lock, normal QML/controller Session, parent/lease CAS, cold
reopen and the normal Capture/Cancel/Still flow. Their SDK, native/VM/GUI,
typed-serialization producer and virtual time are explicit seams. The synthetic
typed bytes in that host producer are not Qt receipts; real Qt serialization is
proved separately in the native harness. No source/header is relabeled as
physical-device evidence. New tests initially exposed a test-only missing-lock
call and a real new-loader cold-read comparison error; both were corrected
before the passing selection.

The disjoint new selections passed 11 cases under unchanged deadlines:
`snapshot-settings-originals` 3.124 s (5 cases),
`snapshot-settings-baseline` 61.083 s (6 cases), coverage 0.059 s, total 64.27 s.
The separate expanded Qt5 check passed in 2.897 s. Use installed real GLM headers
through the compiler's normal include path or `OVERTE_TEST_GLM_INCLUDE`
(`OVERTE_HOST_GLM_INCLUDE` is also recognized). No dependencies are installed.

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<owned-private-tmp> \
  OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=<existing-qt5-root> \
  OVERTE_TEST_GLM_INCLUDE=<existing-glm-include> python3 \
  android/vr/pico/tests/pico4-test-suite.py \
  --test snapshot-settings-originals --test snapshot-settings-baseline \
  --test coverage-matrix --junit <owned-private-report>
```

The unchanged legacy v1-migration/lost-Still continuation also passed in
43.343 s without adding a baseline or changing its old original facts. Final
self-review moved report/receipt processing before the final current-read age
seal; the added frozen-host/native-clock-jump report counter passed with the
normal/cold case in 4.723 s. These are separate checks, not one complete
Snapshot recipe run.
