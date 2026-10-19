# Local adapter validation and limits

The implementation is partial; the complete fourteen-area native adapters and
all physical qualification remain open. See
[the matrix and native prerequisites](FEATURE_ADAPTER_IMPLEMENTATION.md).

The main-mono world-render source/chunk packet passes **443** common host cases,
including **28** acquisition/storage reader and original-probe counterexamples,
with zero failures/errors/skips or compiler attempts. The same three original
native compiler cases remain excluded. GPU/backend/frame-hook C++ was reviewed
as source only and remains uncompiled; no frame was rendered or device contacted.
The new memory release inventory is narrower than complete artifact cleanup.
Concrete platform receipt transport, persistent ownership and receipt cleanup
remain prerequisites. No full-area capability is enabled by this validation.

The subsequent durable ownership/native receipt-removal packet passes **463**
common host cases, zero failures/errors/skips or compiler attempts, with the
same three native exclusions. Its acquisition/storage/ownership/receipt group
has **48** cases, including real local unlink/absence and timeout counterexamples.
The ordinary platform factories are validated separately in their own branches.
Native C++ remains uncompiled. Mono-only version 1 explicitly rejects stereo
and unsupported backends; no Pico rendering or iOS installed-code qualification
can be inferred from these host checks.

Version 4 Graphics validation: **388** common host cases pass with zero failures,
errors, skips or compiler attempts; the same three native compiler cases remain
excluded. Its journey group has **39** cases, and four additional Graphics
subject construction cases pass. No rendering or device acceptance is implied.
The subsequent submitted-code packet passes **401** common host cases and
**254** broad iOS component cases, zero failures/errors/skips or compiler
attempts, with the same explicit native exclusions. Focused groups pass **45**
Phone, **18** Pico and **23** iOS source cases, **25** common Script source
cases and **7** source-profile cases on each source tree. Original canonical
iOS binding rejection still passes five cases. These are source/control results
only; native sources remain uncompiled and all devices unqualified.

The normal Graphics input packet passes **414** common host cases and **259**
broad iOS component cases, zero failures/errors/skips or compiler attempts.
Focused groups pass **52** Phone, **23** Pico Script/Audio/Graphics component
cases and **29** iOS Script/Audio/Graphics component cases; the original Pico
binding/navigation/Snapshot group passes **31** cases. The subsequent scroll-
settling/scene-token correction passes **14** common Graphics input cases;
platform follow-up receipts are recorded when complete. Native source remains
uncompiled and no full-area capability or device acceptance is claimed.

Earlier continuation validation before the version 4 Graphics correction (all source only):

* **378** common quick-selection Python/JavaScript cases pass, zero failures,
  errors or skips. Three original Voice compile cases are explicitly omitted;
  the compiler guard observed zero build attempts. This includes version 3 Audio phase/history/PCM counterexamples, corrected
  Script flow, normal file-picker recipe and private fixture-storage, alongside
  actual native effect/module/preview source checks. The common Audio input group has **16** host cases. The shared journey group
  passes **33** cases; the native Script source group passes **19** cases, and
  the atomic Audio history/projection group passes **11** cases.
* Phone's focused real candidate wrapper group passes **44** cases. Pico's
  focused original-observation wrapper group passes **17** cases; its separate
  normal Script group passes **19** cases and the original binding/navigation
  group passes **31** cases. No device is contacted.
* The broad iOS Python component selection passes **253** cases, zero failures,
  errors or skips, with the same 20 native compiler-dependent cases omitted
  and zero build attempts. Its focused source group has **22** cases; the
  canonical installed-code binding group passes five cases including rejection
  of every new internal source reader and file-picker component. The Script
  component group passes **24** cases.
* Contract versions, focused original fixture/probe dispatch tests, and diff
  whitespace checks pass. Native C++ instrumentation remains **uncompiled**.

The current receipts are in the private sibling directory
`overte-shared-feature-journeys-20261019-validation/adapter-continuation`:
`common-no-build.json/.log`, `ios-no-build.json/.log`, and `host_checks.py`.
The reviewed selection script excludes compiler cases before execution and
rejects compiler process launches. Earlier 308/233-case source receipts are
retained separately. Exact selected/omitted IDs are in the JSON/log records.
The focused commands are the existing unittest discovery groups:

```sh
python3 -m unittest discover -s android/phone/tests/device -p test_feature_adapters.py
python3 -m unittest discover -s android/vr/pico/tests/device -p test_feature_observation.py
python3 -m unittest discover -s tests/device/ios/self_tests -p test_ios_feature_observation.py
python3 ios/tests/appium-native-binding-test.py
```

Historical initial adapter packet (superseded counts, retained audit record):

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

That packet's corrected broad iOS selection passed **215 tests, zero failures/errors and
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
