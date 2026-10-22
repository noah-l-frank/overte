# Android Phone roadmap

- **Priority:** NOW, alongside iOS and Pico under `CLIENT-PARITY`.
- **Maturity:** Personal alpha completed; current-artifact cross-client
  acceptance remains separate.
- **Status reviewed:** 2026-10-20 against the shared roadmap and live milestones,
  not a new phone-test result.

## Current milestone

[PHONE-P2 — Genuine Cross-Client Feature Parity](https://github.com/noah-l-frank/overte/milestone/4).
The [shared roadmap](https://github.com/noah-l-frank/overte/blob/main/docs/ROADMAP.md)
and [feature contract](https://github.com/noah-l-frank/overte/blob/main/docs/interfaces/FEATURE_PARITY.md)
own product order and required outcomes. Preserve working Phone behavior while
bringing useful features to parity with iOS and Pico.

## Exit criteria

- The selected shared feature outcomes are usable through normal client startup
  and Phone-appropriate controls, as defined by PHONE-P2 and the shared contract.
- Exact integrated source, APK, installation identity, and required phone
  journeys are bound to the same candidate.
- Negative, lifecycle, privacy, and remaining platform limitations are recorded;
  host or emulator success is not substituted for required device evidence.

## Single next action

Qualify the integrated Phone candidate through the regular parent hierarchy and
perform the remaining PHONE-P2 acceptance journeys on its exact installed APK,
recording the first blocking failure and artifact/source binding.

## Completed baseline and later work

The maintainer completed [PHONE-P1 — Personal Alpha](https://github.com/noah-l-frank/overte/milestone/2)
on September 25, 2026. Its eleven acceptance issues are closed. Retain that
historical baseline without treating it as qualification of every newer build.
Broader Adreno/Mali coverage belongs to the later `PHONE-V1` work; it is not a
reason to reopen the completed personal alpha.

## Execution boundary and non-goals

The maintainer's hardware runs use the private Proxmox Jenkins laboratory;
local builds, host contracts, and emulator tests do not require access to it.
The workstation device lab is retired. Broad device coverage, production
portrait qualification, 32-bit support, and store/release support are not
implied by the current parity milestone.

## References

- [Development status](DEVELOPMENT_STATUS.md)
- [Testing](TESTING.md)
- [Build and deployment](BUILD.md)
- [Orientation contract](ORIENTATION.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
- [Retained historical notes](archive/README.md)
