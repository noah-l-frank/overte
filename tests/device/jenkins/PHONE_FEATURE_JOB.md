# Pixel feature job

`overte-pixel6a` is the single parameterized Android Phone job. The renderer in
`phone_job.py` consumes the pure `phone_selection.build_index(catalog_path)`
result. Registered source coverage across fourteen feature areas does not mean
that those areas have passed on a device. The catalog retains its 69 original
module IDs; 35 are tagged for the baseline. These tags select existing tests,
not 35 additional tests or a second test engine. Each selection starts with
`qualification.device = not-qualified-for-this-run`.

The job parameters are:

| Parameter | Values and default |
| --- | --- |
| `EXECUTION` | `plan` (default), `live` |
| `TEST_SCOPE` | `readiness` (default), `baseline`, `feature-area`, `single-test`, `all-features` |
| `FEATURE_AREA` | The fourteen catalog area IDs; `world-navigation` is first/default. Used for `feature-area`. |
| `TEST_CASE` | Catalog module IDs; `domain-enter` is first/default. Used for `single-test`. |
| `FAILURE_POLICY` | `debug-hold` only |

Missing parameter values use those declared defaults. Empty, malformed,
foreign, or injected values fail closed. The UI always submits area and case;
only the dimension relevant to the selected scope determines its lookup key.
There is no area-plus-single-test mode or fallback to a different test.

`RUN_MODE` belongs to the old job interface. Migrate the job properties and
Pipeline together to the parameters above; it is not an alternate execution
engine or an accepted compatibility parameter. Requests carrying obsolete or
foreign fields are rejected. Preserve running historical jobs and their
configuration when deploying the new job.

## Plan execution

Plan is the default and needs no executor, workspace, resource lock, shell,
fixture, or device. Python precomputes every selection, module order, setup
prefix, original timeout, and capability union. The renderer embeds that bounded
public index as SHA256-pinned Base64 chunks. Groovy validates parameter
membership and retrieves one exact key; it does not reconstruct a suite.

An `@NonCPS` publisher writes `archive/selection-plan.json` for the currently
active `overte-pixel6a` build only, using `StandardArtifactManager` and guarded
controller filesystem access. It rejects alternate artifact managers, foreign
builds, symlinks, conflicting files, and failed readback. The same public JSON
appears in the console. Parsed JSON stays inside non-CPS methods; only strings
and ordinary parameter maps cross suspending Pipeline steps. Private deployment
paths, target selectors, and credentials are not included in the public plan.

Both the initial XML job properties and Declarative Pipeline parameters come
from `parameter_choices()`. Updating this job does not mutate other jobs or
running historical builds. The generated Pipeline is a trusted controller
script (`sandbox=false`); deploy it through the official Jenkins CLI with the
normal administrator/script-approval governance. The renderer performs no
Jenkins mutation itself.

## Live binding

The deployment descriptor has exactly these fields:

```json
{
  "controllerRoot": "/owned/jenkins/pixel-feature",
  "controllerManifestSha256": "<64 lowercase hexadecimal characters>",
  "agentLabel": "overte-device-pixel6a",
  "deviceResource": "android-device-01",
  "liveBindings": {
    "bridgeRelativePath": "tools/phone_live.py",
    "bridgeSha256": "<64 lowercase hexadecimal characters>",
    "manifestRelativePath": "deployment.private.json"
  }
}
```

The controller and Proxmox agent have separate copies under that same absolute
root. Live execution allocates `overte-device-pixel6a` only after validating the
live choice, then locks `android-device-01`. A constant Python bootstrap rejects
noncanonical paths, aliases, foreign owners, writable shared inputs, and hash
drift before executing the exact bridge and deployment manifest:

```text
python3 -I -B <bridge> run --manifest <manifest> --manifest-sha256 <pin>
```

Validated enums are passed through `withEnv` as `OVT_PHONE_EXECUTION`,
`OVT_PHONE_SCOPE`, `OVT_PHONE_AREA`, `OVT_PHONE_CASE`, and
`OVT_PHONE_FAILURE_POLICY`. `OVT_PHONE_RUN_NAMESPACE` comes from Jenkins
`JOB_NAME` and `BUILD_NUMBER`. No user value is interpolated into shell code.
The bridge exports only validated public files into the current build slot
`$WORKSPACE/pixel-job-public/$BUILD_NUMBER`; the Pipeline archives only that slot
with symlink following disabled. A parallel read-only watcher verifies the
seal, current job/build identity, exact public artifact-index whitelist,
regular non-aliased files, sizes and hashes. It publishes the exact file list
while the original worker can remain blocked in DebugHold. It never opens
private runtime files or unsanitized log streams. The bridge owns separate private
configuration, SDK, artifact, and fixture namespaces and must preserve the first failed state and complete logs. It must
never convert a failure to a successful skip, clean up automatically, or proceed
to the next test after failure. Exit `77` means an explicitly released failed
hold: the Pipeline remains failed and does not ask for another release. An
unexpected nonzero exit or shell/transport failure enters a separate Jenkins
`input` hold inside the same node and resource lock. Its button, **Leave failed
run and release resource**, requests no private cleanup or recovery and cannot
replace the bridge's original nonce/context checks. Cancellation is never
success. There is no Pipeline post-build cleanup.

Tutorial preparation is measured once per selection, after `launch-smoke`
and before its first subsequent module. Later modules intentionally preserve
their own world transitions. `readiness` selects only `launch-smoke` and has no
tutorial or navigation requirement: it verifies process/foreground readiness,
not a playable world. A launch acknowledgment cannot prove tutorial readiness. Ordinary Phone navigation remains
**focus click → set text → one Return**, followed by fresh independent client
observations. The job renderer does not alter that flow or its authentication,
version, security, or timeout checks.

## Host verification

The admitted deployment pins the client source, harness source, their complete
inventories and declared delta, the installed candidate, adapter inputs, and
fixture configuration separately. `phone_worker.py` calls the original runner;
it does not provide a second journey engine. The native timeline consumer checks
all configured rotation slots, committed index hashes, sequence continuity and
unchanged prefixes before input and around publication. A new unconfigured part
blocks publication with an error while retaining the private originals.

```sh
python3 -B -m unittest discover -s tests/device/jenkins -p 'test_phone_*.py'
git diff --check
```

Renderer tests cover every precomputed lookup, declared-default handling,
invalid parameters, bounded public payloads, matching XML/UI choices,
controller-only plan publication, CPS data boundaries, and execution of the
actual pin-check bootstrap against synthetic local files. A host pass establishes these source and synthetic-boundary contracts only.
It does not claim a Jenkins CPS runtime check, an accepted live fixture, or
physical-device acceptance. Validate the generated
Pipeline through the official Jenkins CLI before deploying it; a plan build
can then verify controller publication without acquiring the Pixel.
