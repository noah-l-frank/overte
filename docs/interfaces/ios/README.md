# Overte for iPhone and iPad

> [!CAUTION]
> This is an AI-assisted experimental port. It is incomplete and has not
> completed the security, privacy, performance, and physical-device acceptance
> required for production use. Review the current status before using valuable
> accounts or distributing an application.

## Current status

The product path is the integrated Qt/Overte Interface on `apple-ios`. The
maintainer completed the [iPad personal-alpha milestone](https://github.com/noah-l-frank/overte/milestone/3)
on October 10, 2026. That is evidence for its recorded iPad source/artifact,
not acceptance of every later IPA or broad iPhone support. Current work follows
[IOS-P2 cross-client feature parity](https://github.com/noah-l-frank/overte/milestone/6)
and the [shared feature contract](https://github.com/noah-l-frank/overte/blob/main/docs/interfaces/FEATURE_PARITY.md).

The smaller UIKit/Metal bootstrap remains a separate toolchain and simulator
diagnostic. It resolves places but does not implement the full domain protocol;
its limitations must not be presented as the integrated client's current status.
See [Development status](DEVELOPMENT_STATUS.md) for the distinction.

This is a personal hobby port. Build hosts, signing, Sideloadly configuration,
and the Proxmox Jenkins laboratory are the maintainer's private infrastructure,
not services or access supplied to contributors. Local host contracts do not
require that setup.

## Support matrix

| Area | Current configuration |
| --- | --- |
| Build host | macOS with Xcode 26 or newer |
| Target OS | iOS 17 deployment target |
| Architecture | arm64 simulator and arm64 device profiles |
| Virtual target | Simulator profiles; bootstrap diagnostics and separately selected Full Client paths |
| Physical target | iPad personal-alpha evidence; current-artifact acceptance and wider iPhone coverage remain separate |

Linux can run repository contracts but cannot establish an iOS build, launch,
signing result, or native ABI compatibility.

## Bootstrap diagnostic path

```bash
./ios/build-ios.sh bootstrap
./ios/build-ios.sh doctor --platform simulator
./ios/build-ios.sh build --platform simulator
./ios/build-ios.sh test --platform simulator
```

This path keeps `OVERTE_IOS_BOOTSTRAP_ONLY=ON` and prevents unfinished desktop
dependencies and dynamic plug-ins from entering the build.

## Integrated-client development path

The integrated client requires audited iOS Qt and Conan packages. Follow
[BUILD.md](BUILD.md) and opt into the client graph only in a separate build
directory. A configured or compiled target is not device acceptance.

## Output, installation, and launch

Simulator builds are unsigned. Device builds can produce an unsigned IPA for
inspection or a developer-signed app when an explicit team and bundle ID are
provided. Build scripts never install an app implicitly. A developer may either
package a locally signed build on a Mac or verify an unsigned CI artifact before
using the separately authorized Sideloadly signing and installation path. See
[Developer artifacts](RELEASE.md) for the local installation boundary.

## Known limitations

- The bootstrap resolves places but does not send Overte domain protocol packets.
- Current cross-client parity and exact-artifact acceptance remain open in
  IOS-P2; historical preparation blockers are not a live status inventory.
- Physical iPhone and iPad acceptance evidence remains external.
- App Store submission is not part of the current milestone.

## Documentation

- [Roadmap and current milestone](ROADMAP.md)
- [Complete build guide](BUILD.md)
- [Testing](TESTING.md)
- [Touch UI architecture and validation](TOUCH_UI.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
- [Continuous integration](CI.md)
- [Development status](DEVELOPMENT_STATUS.md)
- [Developer artifacts](RELEASE.md)
