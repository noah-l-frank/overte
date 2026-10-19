# Local adapter validation and limits

The implementation is partial; the complete fourteen-area native adapters and
all physical qualification remain open. See
[the matrix and native prerequisites](FEATURE_ADAPTER_IMPLEMENTATION.md).

Validated locally:

* **261** quick common Python tests pass, with zero failures/errors/skips, including
  the new native flow tests. The selection has
  three explicitly excluded pre-existing compiler cases in `test_voice_roundtrip`.
* Phone's real candidate-bound wrapper: **43 original + 13 new tests pass**. Original installed-identity/native input
  tests and the new `test_feature_adapters.py`. The new group is registered in
  the existing Phone runtime runner. W3C/ADB/time boundaries and candidate bytes
  are explicit host fixtures, not an APK execution.
* Pico's real candidate-bound wrapper: original **31** native binding/navigation/
  Snapshot tests; new **seven** native-feature reader tests; existing suite-runner
  and coverage checks. The new group passes through the actual existing Pico
  suite selector as `feature-observation`, with zero skipped selected groups.
* iOS's new eight reader tests, original five canonical binding tests, and the
  existing broad Python component selection excluding native compile cases.
  The canonical installed-code/session/invocation rejection is retained.
* Contract-version, policy/catalog and fixture-orchestrator validation; original
  probe JavaScript syntax; whitespace/diff checks. No required device result is
  replaced by these host checks.

An initial expanded iOS selection ran 234 tests successfully, but two existing
Snapshot self-test classes compiled the original native host reader in their
`setUpClass` helpers. This was an execution mistake and **violated the user's
no-build constraint**. The two temporary SDK build directories were removed by
the original test teardown. No application build, code signing, installation,
device access, Jenkins execution or existing frozen build modification occurred.
That initial result is labelled `ios-initial-mixed-host`, with two native host
compilations and `noBuildScopeRespected:false`; it must not be cited as a no-build
validation receipt.

The corrected broad iOS selection passes **215 tests, zero failures/errors and
zero skips**. It explicitly excludes the acoustic native compile test and all
19 tests in the two native Snapshot classes. A process audit hook rejects direct
compiler launches before execution; it observed zero blocked build attempts.
The exact excluded test IDs are retained in its local JSON receipt. Native
compile checks are omitted from this run, not silently marked passed.

The private local validation directory is
`overte-shared-feature-journeys-20261019-validation/adapter-phase`, beside the
worktrees. It retains the reviewed host-selection script, logs, selected/omitted
case lists and JSON summaries, including the initial mixed-run correction.
Platform packet documents contain direct focused commands for review. The
existing complete platform runners may also contain native compiler jobs; do
not invoke them wholesale under a no-build instruction.

All results here establish control logic only. No native feature acceptance,
physical form factor, keyboard delivery, real frame/PCM/file output, real
account/domain/peer success, install association or complete cleanup on a device
has been qualified. Incomplete full-area capabilities remain unadvertised and
the mandatory common gates fail closed. Later device work must run exclusively
through the Proxmox Jenkins laboratory and the official CLI.
