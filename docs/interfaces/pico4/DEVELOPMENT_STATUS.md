# Pico 4 development status

## Current product boundary

The maintainer completed [PICO-P1](https://github.com/noah-l-frank/overte/milestone/1)
on September 27, 2026. That personal-alpha record covers its named source and
headset, not all later APKs. Current work is
[PICO-P2 cross-client feature parity](https://github.com/noah-l-frank/overte/milestone/5),
under the [shared feature contract](https://github.com/noah-l-frank/overte/blob/main/docs/interfaces/FEATURE_PARITY.md).
The maintainer's real-target tests use the private Proxmox Jenkins laboratory.

## Implemented or host-verified

- Linux build consumer with explicit source bindings and toolchain bootstrap;
- dedicated Pico package, OpenXR boundary, and ARM64 APK validation;
- device-free lifecycle, WebView, microphone, input, packaging, and power
  contracts;
- draft release-candidate provenance, SBOM, checksum, and signing gates; and
- separately authorized physical-device handoff.

## Current-artifact and broader device evidence

Worn-headset validation remains authoritative for rendering, controllers,
interaction, audio, microphone routing, lifecycle, thermals, sustained power,
world loading, and comfort. Store requirements remain external until verified
by an authorized release owner.

Historical nightly implementation notes are retained under `archive/` and are
not current build or acceptance instructions.
