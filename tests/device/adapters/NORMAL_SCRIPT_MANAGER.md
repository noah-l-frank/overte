# Normal script-manager adapter packet

`normal_script_manager.py` drives the existing five `scripts.*` operations. It
does not implement or advertise the larger `feature.scripts.*` v1 contract.
`android_script_ui.py` binds ordinary Phone screen-space Tablet input. No direct
`ScriptDiscoveryService.loadOneScript`/`stopScript`, probe mutation or arbitrary
UI recipe is used for actions. The independent existing `scripts_journey.py`
still decides actual execution, companion loading, new instances and silence.

The existing app-private client command channel accepts the read-only command
`{schemaVersion:1, commandId:<32hex>, action:"normal-feature-observe",
includeAvatarEntities:false}`. It samples once per new command ID into the
separate private diagnostic, `normal-feature-observation.json`:

```json
{"schemaVersion":1,"requestId":"<actual command ID>","instance":"<probe UUID without punctuation>",
 "sampleSequence":1,"sampleEpochMs":1234,"complete":true,
 "scripts":[{"url":"<actual native URL>","path":"<actual native path>"}]}
```

`scripts` is the complete actual `ScriptDiscoveryService.getRunning()` result
projected to URL/path, bounded to 128 entries. Read failure or overflow produces
`complete:false`, never a successful empty list. No expected state, test input,
event count or feature verdict enters the diagnostic. It is private input-row
identity data; do not copy it into public artifacts. The existing execution
journal is a separate observer and remains mandatory. A diagnostic alone does
not prove that a script executed. The probe shipped in the later candidate must
include this new producer. An old installed probe cannot enable these operations.
No periodic service/entity query is added to unrelated journeys. Repeating a
request never manufactures a new capture or sequence.

Readers require complete bounded original JSON, unique keys/URLs, a source
sequence advancing past the previous read, the current request ID, an unchanged probe instance, and a
native sample age from -250 to 1500 ms against a separately read target clock.
They wait at most five seconds/51 reads for advancement and never refresh the
sample timestamp themselves. The owning adapter verifies candidate bytes,
process start identity, foreground, target fingerprint and native session.

Normal input opens the native Tablet, Home/app pagination and `app.scripts`.
`scriptFromUrl` opens the source-reviewed `TabletQueryDialog`; it currently has
no field objectName. A unique native EditText is permitted only when its actual
`Script URL` label and `Open and Run Script` title are exported. The source is
entered, independently read back, then submitted exactly once through OK.
Tests require the English UI locale. An absent or ambiguous modal is a failure;
there is no coordinate, JavaScript, direct-load or alternate source fallback.
This source entry calls `loadScriptURLDialog`, which currently loads the script
without `askToLoadScript` consent. The adapter does not invent a consent step.
The full feature journey's consent cancellation/rejection remains unimplemented.

Restart/Stop match the exact actual URL in the native service list, reproduce
the UI's basename sort and verify the real adjacent Label/Restart/Stop trio in
the current native tree. Duplicate basenames or non-ASCII ordering are refused.
The native list is reread unchanged before the input, and the UI is checked
again at dispatch. Unrelated same-named scripts cannot be adopted. An uncertain
mutation is never replayed. Stop waits for the exact URL to disappear; the
common journey separately observes three seconds without execution events.

`normal_feature_state.py` retains cleanup intent in a versioned, atomically
replaced, current-user 0600 regular file. It rejects aliases, hardlinks,
duplicate keys, foreign context and changed concurrent state. Capture the
original source/artifact, process identity, target fingerprint and Appium
session/generation. Save panel/dialog/load intent **before** input. An existing
Tablet or source cannot become owned. Repeat Stop after actual disappearance is
idempotent; a subsequently appearing source cannot be stopped after ownership
was retired. Close verifies modal/tablet absence and releases owned inputs.
It refuses success while a source might still run. Failed cleanup retains the
sidecar. The script ownership schema is v2, with a closed `sourceKind` of
`scripts` or `create-observer`; a source owned by one cannot be adopted by the
other. App-wide process stop does not prove removal from persisted Running
Scripts; do not discard unresolved source intent merely because the app stopped.

Host self-tests replace only the native boundary and clocks; they execute the
real flow, original probe diagnostic body and private-file implementation.
These checks qualify control logic only. No Phone/Pico/iOS product feature,
physical input path or real installed candidate has been qualified here.
