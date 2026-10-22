# Overte for Android phones

> [!CAUTION]
> This is an AI-assisted experimental port. It has not completed the device
> coverage, security review, performance validation, or release testing required
> for production use. Review the source before using valuable accounts or
> distributing the application.

## Current status

The `phoneInterface` module packages Overte's mono 2D renderer and touchscreen
input as the independent `io.github.noah_be.overte.phone` application. Its Java
namespace remains `org.overte.phone`; these are distinct identifiers. It targets 64-bit
Android phones running Android 8/API 26 or newer and targets API 36. Both Phone Activities currently request `landscape`; portrait
is not a declared supported mode of this manifest. See [Orientation contract](ORIENTATION.md). 32-bit devices, broad
GPU compatibility, and store publication are outside the current milestone.

The maintainer completed [the Phone personal alpha](https://github.com/noah-l-frank/overte/milestone/2)
on September 25, 2026. Current [PHONE-P2](https://github.com/noah-l-frank/overte/milestone/4)
work addresses cross-client parity and exact-candidate acceptance. Broader
Adreno/Mali coverage remains later `PHONE-V1` work, not an unfinished PHONE-P1.

This is a personal hobby port. Build runners, signing/release setup, and the
Proxmox Jenkins device laboratory belong to the maintainer; contributors do not
need access to them for local builds, host checks, or emulator tests.

## Support matrix

| Area | Current configuration |
| --- | --- |
| Build host | 64-bit Linux |
| Target OS | Android API 26 minimum, API 36 target |
| Production architecture | ARM64 with verified 16 KiB-compatible dependencies |
| Emulator | x86_64 AVD, API 35 default |
| Physical target | Named personal-alpha phone; wider Adreno/Mali coverage remains later work |

## Normal developer setup

Run from `android/phone/`:

```bash
cd android/phone
./build.sh doctor
./build.sh setup --download
```

This restores checksum-verified shared and Phone-specific dependencies and
builds the debug APK. The multi-hour dependency producer path is maintainer work
and is documented separately in [BUILD.md](BUILD.md).

## Emulator tests

```bash
cd android/phone
./phone-emulator-test.sh doctor
./phone-emulator-test.sh all
```

The emulator build is x86_64 and cannot be confused with the ARM64 production
APK.

## Output, installation, and launch

The debug APK is
`android/phone/apps/phoneInterface/build/outputs/apk/debug/phoneInterface-debug.apk`.
The commands below describe installation on a separately prepared agent.
The maintainer's hardware operations use private Proxmox Jenkins jobs; the
retired workstation lab is not a fallback. See [Testing](TESTING.md).
For an independent authorized lab, the helper's deployment command is:

```bash
cd android/phone
ANDROID_SERIAL=<serial> ./build.sh deploy
```

## Known limitations

- Normal APKs are ARM64-only and require the dedicated verified 16-KiB graph.
- A successful emulator run does not prove graphics, audio, lifecycle, page-size,
  thermal, or vendor behavior on a physical phone.
- Microphone denial is supported, but privacy and security review is incomplete.
- These commands produce developer builds; distribution follows the separate
  [release procedure](RELEASE.md).

Validate every active Phone documentation command and the orientation wording
without building or starting an emulator:

```bash
python3 docs/interfaces/android-phone/check-documentation-contract.py
python3 docs/interfaces/android-phone/check-documentation-contract.py --self-test
```

## Documentation

- [Roadmap and current milestone](ROADMAP.md)
- [Complete build guide](BUILD.md)
- [Testing](TESTING.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
- [Continuous integration](CI.md)
- [Development status](DEVELOPMENT_STATUS.md)
- [Orientation contract](ORIENTATION.md)
- [Developer artifacts](RELEASE.md)
