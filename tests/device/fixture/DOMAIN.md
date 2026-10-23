# Controlled E2E domain fixture

`domain.py` owns a private, ephemeral domain-server, one assignment-client
monitor, and repository-owned content and controlled-peer assignments. The
content assignment creates four uniquely named domain entities; the peer
assignment publishes one deterministic moving avatar. The common
`domain-smoke` module requires a real domain connection,
the exact domain UUID returned by `/id`, all four markers for consecutive probe
samples, stable process identity, and foreground state.

Run it only with locally built, trusted executables and keep its output outside
the checkout:

```bash
python3 tests/device/fixture/domain.py \
  --domain-server /absolute/build/domain-server \
  --assignment-client /absolute/build/assignment-client \
  --public-host 192.0.2.10 \
  --output-dir /tmp/overte-domain-fixture \
  --ready-file /tmp/overte-domain-ready.json
```

The ready file supplies `domainUrl`, `domainHost`, `domainId`, and
`requiredMarkers`. Export those values as `OVERTE_E2E_DOMAIN_URL`,
`OVERTE_E2E_DOMAIN_HOST`, `OVERTE_E2E_DOMAIN_ID`, and
`OVERTE_E2E_DOMAIN_MARKERS_JSON` before running `domain-smoke`.

It also supplies `peerScriptUrl`, `peerDisplayName`, and a loopback-only
`controlUrl` plus random `controlToken`. The token exists only in the mode-0600
ready file and is omitted from stdout. `network-fault-recovery` exports those
last two values as `OVERTE_E2E_DOMAIN_CONTROL_URL` and
`OVERTE_E2E_DOMAIN_CONTROL_TOKEN`. Its `offline` and `online` commands affect
only child process groups owned by this fixture instance.

Before each `enter_controlled_domain()` navigation, sessions with those private
control values request `online`. This operation checks the live process stack
and `/id` identity when it is already running, or starts the stopped owned stack
and waits for its assignment content. It does not restart a healthy domain.
`domain-prerequisite.json` records the acknowledged state and generation without
the control token. An unavailable or invalid controller is an infrastructure
error before navigation. The normal pipeline and Jenkins entry points start
the fixture owner automatically before domain suites; a ready file alone does
not replace the live check. Direct external/mock sessions without either control
value retain their existing externally managed lifecycle. Both values must be
provided to enable automatic startup for a direct session.

`domain-recovery` uses the same values plus `OVERTE_E2E_SCENE_URL`. It enters
the domain, returns to the controlled serverless scene, proves that the domain
is disconnected, and re-enters the exact domain without changing the
Interface process identity.

The controller's ready metadata means only that the infrastructure is
reachable and its assignment processes survived warmup. Only the client probe
can prove that the domain handshake completed and the entity server delivered
the assignment-owned markers. Each product adapter advertises
`navigation.enter-domain` only after its own physical acceptance gate.
