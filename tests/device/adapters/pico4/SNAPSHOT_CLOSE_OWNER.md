# Normal Pico Snapshot Close and checked-control restoration

The private `_snapshot_close_owner` composes the completed primary return-image
owner with the existing `PicoSnapshot`, `PicoNavigation`, `NativeNavigationIO`
and `PicoOpenXrAdapterSession`. It keeps the exact parent source-lock instance,
immutable Cancel/Save/Upload/background/return originals and original PNG identity.
No product button, settings setter, input mechanism or native channel is added.

The separate existing Snapshot preference journal records original mode and
format before capture input. This owner binds those values to the actual checked
normal controls in the original Cancel opening frames. A missing preference
journal, unmatched checked control or replaced parent cannot create a baseline.
For values that changed, ordinary popup and original option controls restore
them. Durable child intents precede every action; the existing final QML hook
records the actual completed command and checks current original sources and
the exact independent fixture phase after the last CAS and native guard.
Only actual subsequent Review values and popup state supply the effect.

Tablet Close uses the original normal controller route. The existing receiver
forwards admission to this owner, while the exact Session sequence remains
owned. Its nonce and next controller sequence are explicitly derived from
the immutable Cancel origin and actual archived Open envelopes. A different
Session cannot replace that original input scope. The Session intent callback performs private host validation/CAS only;
it queries no phase/native/SDK source and never reenters Session. The transport's
final publication hook checks that same persisted envelope and monotonic age
against the already observed native/fixture anchor. Slow preparation cannot
publish input merely because the device clock stopped advancing.

The actual native UI source changes its generation when `_open` changes
(`NavigationUi::observe`, the `_root/_window/_open` comparison).
Consequently the owner pins the original open generation, admits the actually
observed new closed generation and requires that closed generation throughout
quiet. It does not infer Qt page/context death from the generation change.
A hidden Review may remain present; its original values are checked when
present. Original native capture requests, VM history, files, retired upload
objects, script work, account identity, lifecycle return and backend mutation
scope remain independently bound. Three seconds of contiguous quiet span every
original advancing source/host clock, with gaps no greater than 500 ms. V2
reads one original controller answer for every closed sample, preserves it
before assessing it and requires the same neutral DTO throughout the window
and in one final answer. All journals and the original UI/preference records
remain retained.

Unknown QML input is reconciled only by observing its original effect. Once the
popup action is proven, restoration may issue the previously unissued option;
it never resends the popup. A lost controller ACK after actual Session cursor
commit may reconcile through that exact original stream's neutral state and
closed UI. An uncommitted/uncertain Session cursor, ignored command, changed
phase, stale source, replaced PNG or missing original keeps ownership unresolved.
No cold path retries input or creates a new stream to replace an old one.

## Explicit boundary

The record is a normal Close component, not a whole Snapshot verdict. Existing
runs have no pre-input original lease for all thirteen Snapshot settings keys.
The original three-key capture context and checked mode/format values cannot
supply that missing baseline. `completeSettingsBaseline`, `qtObjectsRetired`,
`globalExportExecutorRetired`, `fullSnapshotRecipe` and `deviceAcceptance` stay
false. No old run is retroactively assigned a settings baseline. Future runs
may add a separately reviewed passive original lease before their first input.

New Cancel v3 runs may now opt into the
[passive pre-input lease](SNAPSHOT_SETTINGS_BASELINE.md) and call
`observe_settings()` after normal restoration/Close to record the
[raw thirteen-key result](SNAPSHOT_SETTINGS_CLOSE.md). The checkpoint compares
actual typed originals, never supplies restore values, and does not replace
the later original three-second Close quiet window or change these flags.

The earlier isolated Still harness kept one UI generation through closure; that
was not the production refresh behavior. This composition instead tests the
actual generation transition and retains both existing journals. Neither the
old harness nor this component qualifies Qt destruction or global executor/pool
retirement. Independent actor/challenge/panorama/Share and remaining whole-cleanup
requirements also remain open.

## Host verification and provenance

The tests reuse the complete immutable host lineage described in
[the background guide](SNAPSHOT_BACKGROUND_OWNER.md), plus the original shared
stereo PNG/receipt protocols from [the return-image guide](SNAPSHOT_RETURN_IMAGE.md).
They execute the actual navigation/QML-command validators, original controller
Session, private journals, physical PNG/receipt files and passive cold readers.
GPU/native/JS/Android/SDK producers and virtual device clocks are explicit host
seams. The old fixture omitted its separate preference file; only the test
setup reconstructs that header from its actual archived checked controls.
Production construction cannot create that missing original. The test's private
Session file is seeded only from the archived original Open nonce/cursor; a
separate fresh Session is not substituted for the old stream.

Initial new harness probes used incorrect navigation constructor arguments and
an invalid controlled-scene URL, then a wrong two-command expectation although
both mode and format had changed. Those test-only errors were corrected. A
runner import needed the repository namespace for the existing Session fixture.
Lost OSError and unresolved Session errors are wrapped by the existing source
lock as `NativeUIError`; initial new exception expectations were corrected,
without weakening rejection or changing that lock. The separate private factory
wraps its source rejection as `ValueError`; its added foreign-nonce counter was
corrected to assert that public boundary. Self-review also found that
the first new host setup began a fresh synthetic Session; it was replaced by
the archived original nonce/cursor, and source admission explicitly binds the
original sequence before any new controller publication.

The disjoint selections retain the unchanged 120 s group deadline:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<owned-private-tmp> python3 \
  android/vr/pico/tests/pico4-test-suite.py \
  --test snapshot-close-owner --test snapshot-close-recovery \
  --test snapshot-close-fences --test snapshot-close-statuses --test coverage-matrix \
  --junit <owned-private-report>
```

The latest fixed Phone reference reviewed for original admission/bookends was
`3fa8031aa6787af909c6a1701c21536d584c392b`. Its constructor-history design is not
copied as Pico authority. Its thirteen-key settings lease also confirms why the
three original capture-context keys are insufficient; no Phone restore setter,
SDK authority or touch route is used here.

The V1 source originally passed eight host-component cases in disjoint owning
selections; its status semantics are superseded by the V2 correction below:
`snapshot-close-owner` 88.885 s (3 cases, final v5),
`snapshot-close-recovery` 112.803 s (2 cases, v4), and
`snapshot-close-fences` 114.831 s (3 cases, v4). Coverage passed in 0.059 s.
The only change between v4 and v5 was the private factory counter's public
exception expectation; source was unchanged. All per-group deadlines stayed
120 s. Four selected repository checks passed in 3.30 s. No complete Snapshot
recipe prefix, compiler, native product process, device, renderer or service was
run for this Close packet. The earlier separate warm prefix and current
component originals must not be described as one whole acceptance result.

## V2 original status correction

The V1 implementation used `require_owned_neutral`, which can poll past an
actual active answer. Its host fixture also assigned a new `updatedEpochMs`
when reading status. The actual `Protocol::publishStatus` in
`E2eInputProtocol.cpp` publishes that field at a state transition; it is not a
sampling clock. Consequently the V1 host result was not a proof of the actual
status behavior. V1 records remain strictly validated historical data and are
read-only. They cannot produce `continuousOriginalNeutral` or resume input;
there is no migration that adds missing actual answers.

V2 uses the unchanged `PicoOpenXrAdapterSession.observe_owned_status` and test
from reviewed `d01c48041bca48bd400d40f796b54849ef9a4c89`. The local dependency-only
`0b4db57a58` must not be selected back into root. That helper validates the exact
original process/nonce/cursor and returns exactly one original transport answer.
It neither polls for neutral nor changes the Session cursor or native input.
The complete returned JSON value is stored in the existing immutable chunk
mechanism under `snapshot-close-statuses.json` before UI/frame acquisition or
neutral validation. Every answer has its own sequence even when its bytes are
identical. Original envelope, host observation time, private scope, manifest,
full file signatures and strict JSON graph remain bound. Active, unknown and
unlinked answers remain visible after cold construction, including when later
frame acquisition fails. A missing owner header cannot adopt retained original
manifests as a new owner. Orphan status manifests/chunks block base cleanup.

A qualifying V2 window references every consecutive status original from its
first frame through the final one-read answer. No intermediate answer can be
filtered out or omitted by skipping a reference. Each answer must be neutral
for the exact owned stream and byte-equivalent to the first DTO, including its
unchanged actual transition epoch. That event must follow the original
pre-controller frame; it is never retimed and is not required to advance over
three seconds. The existing actual frame and host clocks still span at least
three seconds at the same 250 ms sampling cadence and maximum 500 ms gap.
Controller status reads have the same 96-entry bound as the existing owner
frame bound; no timeout, frame cap, cadence or acceptance requirement is raised.
An active or unknown returned value is retained before rejection. A new quiet
attempt, if otherwise authorized, must establish a new complete actual window.
Historical completion never erases later unresolved originals.

The V2 host producer keeps the original transition epoch constant. Dedicated
counterexamples return a held answer between neutral samples at that exact
same epoch, then an unknown answer, and fail frame acquisition after a further
actual answer. Each original remains unchanged and no extra controller command
is delivered. Cold V1 reading performs no status query or input and rewrites
neither the old header nor its parent originals. These remain host/native/SDK
seams, not physical OpenXR evidence. Whole Snapshot, settings restoration and
global resource-retirement boundaries above remain unchanged.

V2 verification passed the four owning groups plus coverage in 361.64 s:
normal/factory 88.515 s (3 cases), recovery 80.433 s (2 cases), fences 92.763 s
(3 cases), and initial status/legacy 99.868 s (2 cases). Final self-review added
a pre-read capacity check: once all 96 original-answer slots are full, another
SDK response must not be requested if it cannot be retained. The status group
then passed all 3 cases in 97.686 s, including a genuinely full private store
with 96 immutable files, the actual Session helper and an unchanged transport
read counter/cursor at refusal. Its held sample uses the actual active enabled
flag. Coverage passed in 0.061 s. Existing deadlines, cadence and bounds remain
unchanged. The shared helper's unchanged single-read test and the normal V2
constant-event-clock case also passed together in 53.569 s.

Four selected repository checks passed in 3.93 s; the contract registry and
documentation/diff checks also passed. No compiler, native product run, device
operation or service was started for V2.


New runs can now opt into the separate [passive pre-input baseline](SNAPSHOT_SETTINGS_BASELINE.md).
It supplies original thirteen-key/cache data and an actual first-input binding;
it does not restore values, upgrade old runs or qualify this whole cleanup.
