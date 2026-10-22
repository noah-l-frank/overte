---
last-reviewed: "2026-10-20"
scope: "Maintainer's private Proxmox Jenkins laboratory; operator overview"
---

# Jenkins laboratory

This hobby fork's maintainer uses a **private Jenkins laboratory on Proxmox**
for tests on their own devices. It is personal infrastructure, not a public
testing service or a setup that contributors are expected to reproduce.
Source builds and [host tests](../testing/local-tests.md) can run independently
of it. The repository provides portable harness and pipeline contracts, while
deployment, credentials, agents, and devices are managed privately.

Since October 19, 2026, the maintainer's hardware/device tests use this Proxmox
laboratory. The former workstation laboratory is retired. Do not restart its
controller, agents, Appium, or device-connect services, or use direct local
device automation as a fallback. Diagnose an unavailable Proxmox service there.
This does not retire local source builds, host unit tests, or separately
authorized manual IPA installation.

Use this path:

1. Check [dated laboratory status](status.md) and choose the platform job.
2. Follow [Run a laboratory test](run-tests.md) to select the installed candidate
   and the intended suite.
3. Read [Results and troubleshooting](results.md) for the outcome and evidence.

## Access the existing installation

On the maintainer's prepared operator workstation, `overte-jenkins` wraps the
official Jenkins CLI, selects the Proxmox controller, and supplies authentication
from protected configuration. It rejects local or alternate endpoint overrides.
The endpoint and deployment details are intentionally not published here.

```bash
overte-jenkins who-am-i
overte-jenkins list-jobs
overte-jenkins help build
overte-jenkins help console
```

The wrapper is a private operator tool. A fresh clone does not install it,
grant access, or configure a laboratory. Use it for supported inspection and
operations rather than raw Jenkins HTTP requests. The available commands depend
on installed Jenkins/plugins; inspect `help` before assuming a command exists.
The old workstation lab directory is a historical copy, not the live Proxmox
filesystem. Inspect the actual job and agent through the CLI; do not use stale
local receipts as installed-build evidence.

## Components and ownership

| Component | Owner and role |
| --- | --- |
| Jenkins job | Chooses a source branch or exact revision and the external deployment parameters. |
| Checked-in shared pipeline | Defines portable input, locking, execution, and publication contracts; it is not proof of the live job's implementation. |
| Device runner | Reserves a target, applies timeouts, produces JSON/JUnit, and cleans up. |
| Platform adapter | Translates advertised capabilities into Appium, ADB, desktop, or platform-owned operations. |
| Controlled fixture and in-client probe | Provide deterministic content and observed effects inside Overte. |
| Acceptance policy and registry | Distinguish implemented scenarios from registered physical acceptance. |

The [shared pipeline guide](../../../tests/device/jenkins/README.md) owns the
checked-in reference implementation. Current private jobs can use separately
configured inline pipelines; inspect their actual definition before assuming
they load the repository's Jenkinsfile. The
[device harness](../../../tests/device/README.md) owns scenarios and capability
semantics.

## Platform paths

- **Android Phone:** product source and adapter integration belong to `android-phone`.
- **Pico:** product source and adapter integration belong to `android-vr-pico`.
- **iPad/iPhone:** product source and adapter integration belong to `apple-ios`;
  signed Overte and WebDriverAgent artifacts and installation evidence are
  separate prerequisites. See the [shared iOS handoff](../../../tests/device/ios/README.md).
- **Desktop:** the common desktop adapters and product source belong to `main`;
  a checked-in adapter does not establish an enabled private laboratory job.

Agents, resource names, credential identifiers, device selectors, signing data,
and populated target files stay in the private laboratory configuration.
