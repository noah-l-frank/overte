---
last-reviewed: "2026-10-20"
scope: "Maintainer operations through the private Proxmox Jenkins installation"
---

# Run a laboratory test

These instructions are for the maintainer's prepared operator environment;
they do not give contributors access to the private laboratory. Use an enabled
job for the intended platform. Check the [dated status](status.md), then inspect
the actual Proxmox job with `overte-jenkins`. Parameters and inline pipelines can
differ from the checked-in reference templates.

## Prepare one explicit run

Before starting, record:

- the job and the exact source revision being tested;
- the candidate artifact and the verified installed-app binding, where required;
- the suite and all optional suite switches;
- the availability of the physical target and the required fixture/adapter.

Use the current private job's configured resource and credential bindings.
Inspect only the required fields from job XML privately; do not print or share
the full configuration. Device selectors stay in the configured secret binding,
not in public commands or logs. Do not infer live paths or installed-app identity
from the retained workstation lab copy.
The [shared configuration guide](../../../tests/device/jenkins/README.md#job-configuration)
explains which inputs belong outside the repository.

## Start and follow the run

For an authorized test, the wrapper supports explicit public job/suite parameters
and a synchronous result:

```text
overte-jenkins build <job> -p <public-parameter>=<value> ... -s -v
```

Replace the placeholders with the reviewed job and complete intended parameter
set. This is a command shape, not a ready-to-run invocation. Keep private
deployment values in the prepared job configuration and supply every intended
public option explicitly. Available suites are defined by the live job; do not
assume that every suite in the reference Jenkinsfile is exposed there.

`-s` waits and returns the build outcome; `-v` streams the console. Interrupting
`-s` also interrupts the build. Jenkins can queue while its agent or device
resource is occupied. Optional soaks, campaigns, accessibility and upgrade runs
require their own prerequisites and explicit selection.

Prefer this blocking CLI wait. If a build needs separate status polling, check
at ten-minute intervals and continue immediately once completion is observed.
Do not restart an active build merely because it is still running. GitHub check
monitoring has its own shorter watch/poll cadence.

## Follow a known build

```text
overte-jenkins console <job> <build-number> -n 100
overte-jenkins console <job> <build-number> -f
```

Keep the console private until reviewed for publication. Do not share raw job
XML: it can contain private deployment configuration. For a terminal that only
needs to inspect a run, an explicit build number avoids silently following a
different latest build.

## Finish the record

Capture the build number, source/artifact binding, selected suites, result and
cleanup outcome. Inspect the JSON/JUnit evidence rather than reporting only the
Jenkins badge. Continue with [Results and troubleshooting](results.md).
