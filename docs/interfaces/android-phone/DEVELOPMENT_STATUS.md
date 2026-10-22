# Android Phone development status

## Current product boundary

The maintainer completed [PHONE-P1](https://github.com/noah-l-frank/overte/milestone/2)
on September 25, 2026. That personal-alpha record covers its named source and
phone, not every later APK. Current work is
[PHONE-P2 cross-client feature parity](https://github.com/noah-l-frank/overte/milestone/4),
under the [shared feature contract](https://github.com/noah-l-frank/overte/blob/main/docs/interfaces/FEATURE_PARITY.md).
Current candidates require their own installation identity and runtime evidence.

## Implemented or host-verified

- independent Phone application and package identity;
- mono 2D renderer and touchscreen input;
- network, audio output, optional microphone, and vibration wiring;
- verified 16-KiB-compatible ARM64 dependency and APK gates;
- separate x86_64 emulator variant;
- device-free behavior, security, packaging, and coverage contracts; and
- store-neutral candidate and emulator-acceptance workflows.

## Later hardware coverage

The later `PHONE-V1` coverage includes Adreno and Mali phones for rendering, touch, audio,
keyboard, lifecycle, deep links, page-size compatibility, sustained performance,
memory, battery, thermals, cutouts, and vendor power behavior. A successful
build, emulator launch, or static contract is not equivalent evidence.

Historical nightly implementation notes are retained under `archive/` and are
not current build or release instructions.
