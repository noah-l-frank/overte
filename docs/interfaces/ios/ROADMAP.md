# iPad and iOS roadmap

- **Priority:** NOW, alongside Android Phone and Pico under `CLIENT-PARITY`.
- **Maturity:** iPad personal alpha completed; current-artifact cross-client
  acceptance and wider iPhone coverage remain separate.
- **Status reviewed:** 2026-10-20 against the fork's shared roadmap and live
  milestones. This is not a new device-test result.

## Current milestone

[IOS-P2 — Genuine Cross-Client Feature Parity](https://github.com/noah-l-frank/overte/milestone/6).
The [shared roadmap](https://github.com/noah-l-frank/overte/blob/main/docs/ROADMAP.md)
and [feature contract](https://github.com/noah-l-frank/overte/blob/main/docs/interfaces/FEATURE_PARITY.md)
own product order and the required outcomes. Preserve working iOS behavior
while bringing the useful feature set to parity with Phone and Pico.

## Exit criteria

- The selected shared feature outcomes are usable through normal integrated
  client startup and platform-appropriate controls, as defined by IOS-P2 and
  the shared contract.
- Exact integrated source, producing IPA, signing/installation identity, and
  the required runtime journeys are bound to the same candidate.
- Negative, lifecycle, privacy, and remaining platform limitations are recorded;
  host or simulator success is not substituted for required device evidence.

## Single next action

Qualify the integrated iOS candidate through the regular parent hierarchy and
perform the remaining IOS-P2 acceptance journeys on its exact installed IPA,
recording the first blocking failure and the artifact/source binding.

## Completed baseline

The maintainer completed [IOS-P1 — iPad Personal Alpha](https://github.com/noah-l-frank/overte/milestone/3)
on October 10, 2026. Its eleven acceptance issues are closed. Retain that
historical baseline; it does not reopen IOS-P1 or certify a newer build.

## Execution boundary and non-goals

The maintainer's physical tests use the private Proxmox Jenkins laboratory;
local host tests do not require access to it. Separately authorized manual IPA
installation is distinct from acceptance. Broad iPhone/iPad coverage, App Store
submission, macOS desktop, and Quest work are not implied by this milestone.

## References

- [Development status](DEVELOPMENT_STATUS.md)
- [Testing](TESTING.md)
- [Build and signing](BUILD.md)
- [Touch UI validation](TOUCH_UI.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
