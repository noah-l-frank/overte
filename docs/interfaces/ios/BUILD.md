# Build Overte for iOS

Run build commands from the repository root on macOS. Start with the complete
[host preparation guide](../../ios/HOST_PREPARATION.md) and
[first Xcode run](../../ios/XCODE_FIRST_RUN.md).

The integrated client is the current product path. The smaller bootstrap below
remains a diagnostic for the Apple toolchain; its successful build does not
replace a Full Client IPA. Private build, signing, and Proxmox lab configuration
belongs to the maintainer and is not provided by a source checkout.

## Bootstrap

```bash
./ios/build-ios.sh bootstrap
./ios/build-ios.sh doctor --platform simulator
./ios/build-ios.sh deps --platform simulator
./ios/build-ios.sh configure --platform simulator
./ios/build-ios.sh build --platform simulator
```

The bootstrap deliberately avoids Qt so Xcode, bundle, lifecycle, signing, and
Metal failures remain separate from the Overte migration.

## Integrated client

The integrated client is pinned to Qt 6.11.1. Host tools and target libraries
must match exactly. Configure explicit target and host roots and validate them
as described in [Qt setup](../../ios/QT_SETUP.md). Then resolve dependencies and
configure the opt-in graph:

```bash
./ios/build-ios.sh deps --platform device
./ios/build-ios.sh configure --platform device --client-graph
cmake --build build-ios/device --config Debug --target Overte
```

Do not substitute desktop Qt, a Linux package, or a simulator-only slice for an
iPhoneOS dependency. The port remains experimental. Use [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)
and the actual qualification run for current-artifact status; the old bootstrap
preparation blockers are not a current build result.
