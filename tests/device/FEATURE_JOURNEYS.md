# Shared feature journeys

All fourteen areas have common user-flow logic, controlled input data, versioned
read/action contracts and device-free counterexamples. **Test logic exists;
product adapters are missing; these flows are untested on devices.** Simulation
proves assertions and failure handling only. No physical acceptance is registered.

Start with the [coverage matrix](FEATURE_COVERAGE.md) and the
[adapter handoff](FEATURE_ADAPTER_HANDOFF.md). The implementation extends the
existing catalog → `OverteSession` → adapter → target automation architecture.
It uses the existing runner, capability registry, process locks, JSON/JUnit,
timeouts, artifact audit and acceptance policy. No second runner is introduced.

`feature-<area>` composes existing modules with one new common feature extension.
`feature-journeys` composes their union. Existing navigation, entity editing,
Web-video, original Snapshot decoding, Scripts lifecycle, voice and locomotion
assertions retain their owners. The existing Create journey now observes live
empty entity state before stopping its diagnostic. Scripts cleanup establishes
three seconds of independent execution silence and does not stop a source when
no owned load was attempted.

The source of truth for actions and checkpoints is
[`feature_journeys/scenarios.py`](feature_journeys/scenarios.py). Runtime validation
is in [`contract.py`](feature_journeys/contract.py), execution in
[`engine.py`](feature_journeys/engine.py), and byte inspection in
[`evidence.py`](feature_journeys/evidence.py). The checked
[adapter inventory](feature_journeys/adapter-contract.v18.json) contains input
vocabularies, observation field types and independent witness fields. Its v18
contract is registered in `contract-versions.json`; breaking changes require a
new version and explicit compatibility policy for still-supported producers.

In v17 active Emotes additionally require an original
[native motion file](feature_journeys/EMOTE_MOTION.md). Three real moving native
frames over the measured-duration-based window qualify brief one-shot clips;
reports distinguish this from repeated public RPC sampling. Images, independent
facts, freshness and complete cleanup remain mandatory.

## Contract v18: complete per-feature retirement

The successful module performs both normal cleanup calls and the unchanged
three-second independent quiet checkpoint while the original fixture/peer is
still live. It then closes its original fixture run and invokes the same
`feature.<area>.cleanup` operation once more, with contractVersion 18 and the
same runId. No new transport verb, test runner or target selection is introduced.
The final call must finish original actor termination, native/file absence and
owned measurement-journal retirement before the module succeeds. A later
feature must not invalidate an earlier feature's world/PID-bound originals.

Adapters distinguish the live and retired phases through fresh independent
original provider observations. Neither a local cleaned flag nor the caller's
cleanup request proves closure or absence. The Phone dispatcher only selects
its existing strict owner finalizer; that finalizer still verifies its retained
provider, actor, native and file evidence and recovers interrupted retirement.
A cleanup acknowledgment by itself is never sufficient. Finalization must not
restart the application; the module retains its independently read process
identity and foreground guards. Audio retains its one documented normal cleanup
restart before fixture closure; no second restart is allowed afterwards.

Failure during the original journey remains a failure even if retirement
succeeds. Failed closure/retirement remains red and retains unresolved owners.
An unused owner is not created after preparation failure. Historical v17
inventory/coverage files remain unchanged for source history; v17 observations
are not accepted by the v18 runner. Recompile/propagate the common contract and
implement this cleanup lifecycle before enabling a platform's v18 capability.
Finish any existing v17 run and its retained retirement with its original matching owner before selecting v18; journals are never rewritten or deleted to manufacture compatibility. There is no physical-evidence migration or acceptance promotion.

## Device-free verification

From the repository root:

```bash
python3 -m unittest discover -s tests/device/self_tests -p test_feature_journeys.py -v
python3 -m unittest discover -s tests/device/self_tests -p test_create_management.py -v
python3 -m unittest discover -s tests/device/self_tests -p test_scripts_management.py -v
python3 tests/device/feature_journeys/server.py --check
python3 tests/device/validate_contract_versions.py
python3 tests/device/validate_policy.py --policy tests/device/acceptance-policy.json --catalog tests/device/catalog.json
```

The new self-tests are selected by `run_control_plane_tests.py --profile quick`
and full self-test discovery. The complete quick profile also contains existing
native compiler checks; those were excluded from this local no-build task.
See `FEATURE_JOURNEYS_VALIDATION.md` for exact performed checks and limits.

Inspect registration without discovery or device access:

```bash
python3 tests/device/run.py --adapter-manifest tests/device/adapters/mock/adapter.json \
  --catalog tests/device/catalog.json --suite feature-journeys --list
```

Each new suite has a capability gate with an empty `requires` list so it always
runs. It checks the union of the selected area's existing and new capabilities.
Missing mandatory capability produces infrastructure exit 75 even when the
caller omitted `--require-complete`. It cannot become a green partial run.
Real acceptance must run through the Proxmox Jenkins laboratory using the
official CLI, and continue to use `--require-complete` as well. The retired
workstation device laboratory is not an execution option. The stock
mock deliberately does not advertise the new feature capabilities: direct
boundary-model simulations are not adapter implementation or product evidence.

## Controlled inputs

[`fixtures.py`](feature_journeys/fixtures.py) generates fresh per-run text, image
cards, Web pages, a distinct texture, a wearable, an executing script with a
relative companion, PCM, controlled entity-JSON picker input and a private
export assertion reference. The reference is never served as a product export. It reuses the hash-pinned
[glTF/OBJ companions](fixture/parity/companions/manifest.json). Additional avatar
resources remain in their original repository locations and are hash-pinned by
[`resource-pins.v1.json`](feature_journeys/resource-pins.v1.json); licenses and
attribution are unchanged. No assets are downloaded.

The local fixture coordinator serves owned resources and journals independent
actor observations. It does not implement metaverse authentication, an asset
server, a native capture transport or a product peer. Those existing product
services must be provisioned in an isolated owned environment and connected by
the independent target observers during the adapter phase. An absent actor or
service fails observation rather than silently substituting fixture values.
This is an explicit execution dependency for every row, not a device pass.

Execution profiles require the private feature fixture URL, reader token and
image policy, plus the prerequisites of the reused modules. Domain-backed
recipes also require the existing controlled domain fixture. Planning reports
missing inputs before discovery. Avatar/People, Create, Emotes, Audio, Chat and Assets enter the controlled
domain so peer replication and server permissions remain connected. Other
extensions use the controlled serverless scene. They must run in an isolated test profile with the documented
baseline; an unexpected account, object, mapping, setting or panel blocks work
before ownership-dependent actions are enabled.

Version 4 Graphics uses [measured original preferences](feature_journeys/CONTRACT_MIGRATION.md)
and the versioned [Graphics subject](feature_journeys/GRAPHICS_SUBJECT.md). These
are common test/fixture contracts; native rendering and full adapters remain
unqualified and mandatory capability gates remain closed.

Snapshot contract v9 pins the actual independently measured OS Save backend and
authorization, requires original pending-cancel history and separately acquired
Save/receiver/upload bytes, and records source-specific non-applicable rows
explicitly. All common flows and the complete area capability remain mandatory.
See [the exact source policy](feature_journeys/SNAPSHOT_SOURCE.md); synthetic
profiles do not establish a qualified OS/settings/chooser or cleanup actor.
