---
last-reviewed: "2026-10-20"
scope: "Dated inventory of the maintainer's private Proxmox laboratory; no device-acceptance claim"
---

# Laboratory status — October 20, 2026

This is a small, dated snapshot of the **maintainer's personal infrastructure**
for this hobby fork. It is not a public service inventory or a contributor setup
guide. The Proxmox Jenkins controller was inspected through `overte-jenkins`
using `who-am-i`, `list-jobs`, and private extraction of safe `get-job` fields.
No build or device action was triggered for this review.

## Observed configuration

| Overte target | Job enabled | Pipeline definition | Timer configured |
| --- | --- | --- | --- |
| Android Phone | Yes | Private inline pipeline | No |
| Pico 4 | Yes | Private inline pipeline | No |
| iPad | Yes | Private inline pipeline | No |

The controller exposes three Overte jobs. Job names, host addresses, agent
paths, credential identifiers, and device selectors remain in the private
configuration. This page deliberately does not provide runnable job-specific
commands or enumerate unrelated personal jobs.

These jobs do not use a Jenkins SCM definition that automatically loads
`tests/device/jenkins/Jenkinsfile`. Inspect each actual inline definition and
its selected source/artifact before planning a run. The checked-in shared
pipeline and migration inventory describe reference contracts, not the live
deployment. An enabled job does not establish a connected device, a successful
scenario, or acceptance of an installed candidate.

## Retirement and historical evidence

The workstation laboratory was retired on October 19, 2026. Its controller,
agents, Appium, and device-connect services must remain disabled. The retained
workstation lab directory is historical; matching paths on a Proxmox agent
do not imply shared files or a current installation receipt.

The [October 7 workstation snapshot](https://github.com/noah-l-frank/overte/blob/286d054f05bbc535d05d8f83dbad3564df41877a/docs/portal/jenkins/status.md)
preserves the earlier job names and August/September results. It describes the
retired installation, not this controller or today's device readiness. Keep
historical browser and transport diagnostics separate from current acceptance.

The shared source reviewed here is fork `main` at
`b5f48d2a842a5cc1655ceb2f69a46bf3c4030429`. Its
[acceptance registry](../../../tests/device/acceptance-evidence.json) contains
no physical acceptance records. This configuration inspection did not test
device connectivity, signing/profile validity, adapter readiness, or the binding
between an installed app and its producing artifact.

## Refresh this snapshot

Use the prepared `overte-jenkins` wrapper to inspect the Proxmox controller and
actual jobs. Read `get-job` output privately and extract only the public
platform, enablement, pipeline type, and timer presence needed for this page.
Do not publish raw XML, console logs, endpoint overrides, or target files.
Use `help` to discover supported CLI operations and keep any build result bound
to its exact source, artifact, selected suite, and cleanup outcome.

Date new observations and state their limits. Recheck the live configuration
before a run; refreshing this page does not qualify an installed application.
