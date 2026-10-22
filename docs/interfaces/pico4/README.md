# Overte for Pico 4

> [!CAUTION]
> This is an AI-assisted experimental port. It may be incomplete,
> insufficiently tested, insecure, or unsuitable for valuable accounts and
> production use. Review the current status before installing or distributing
> the application.

This is a personal hobby port. Local compilation and device-free tests are
separate from the maintainer's private build runners and Proxmox Jenkins lab;
contributors are not expected to reproduce or access that infrastructure.

## Current status

The Pico 4 port has a Linux command-line build with explicit source dependency
bindings, an install/deploy path, device-free regression tests, and separate
release-candidate and headset-acceptance workflows. It remains experimental and
does not have complete worn-headset, security, privacy, comfort, or store
acceptance evidence.

The maintainer completed [the Pico personal alpha](https://github.com/noah-l-frank/overte/milestone/1)
on September 27, 2026. Current [PICO-P2](https://github.com/noah-l-frank/overte/milestone/5)
work addresses cross-client parity and exact-candidate acceptance; the historical
alpha does not establish production readiness or acceptance of a newer APK.

## Support matrix

| Area | Current configuration |
| --- | --- |
| Build host | 64-bit Linux; Fedora, Debian/Ubuntu, Arch, and openSUSE bootstrap paths |
| Target | Pico 4 |
| Target architecture | ARM64 |
| Virtual target | No emulator acceptance path |
| Physical target | Authorized USB-connected Pico 4 |

## Quick start

```bash
cd android/vr/pico
./build.sh doctor
./build.sh bootstrap
```

The bootstrap may request administrator access and Android SDK license
acceptance. `doctor` is the read-only entry point.
Before building, supply the revision-bound source inputs in
[BUILD.md](BUILD.md); bootstrap alone does not produce or qualify them.

## Output, installation, and launch

The debug APK is written below
`android/vr/pico/apps/picoInterface/build/outputs/apk/debug/` relative to the
repository root. For the maintainer's devices, installation and hardware tests
run through the prepared `overte-jenkins` wrapper and private Proxmox jobs.
The workstation lab is retired. See [Testing](TESTING.md) and the
[shared operator guide](https://github.com/noah-l-frank/overte/blob/main/docs/portal/jenkins/index.md).
The build helper's `install`/`deploy` commands remain agent-side implementation
references, not a local workstation fallback.

## Known limitations

- The current consumer requires a complete, explicitly supplied source graph;
  historical prebuilt Android packages cannot replace it.
- Device-free tests do not prove OpenXR, controller, rendering, audio, thermal,
  or comfort behavior on a worn headset.
- Store and direct-distribution requirements remain partly portal-dependent.
- Release publication is limited to a verified draft candidate and an explicitly
  approved device-acceptance handoff.

## Documentation

- [Roadmap and current milestone](ROADMAP.md)
- [Complete build guide](BUILD.md)
- [Testing](TESTING.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
- [Continuous integration](CI.md)
- [Development status](DEVELOPMENT_STATUS.md)
- [Developer artifacts](RELEASE.md)
