# Troubleshoot the iOS port

## The host check fails

For the device-free host contracts in [TESTING.md](TESTING.md), Linux and macOS
are supported; start with the failing command and its listed prerequisites.
A Linux host check does not need Xcode. Native iOS configure/build and simulator
commands require the macOS/Xcode environment in [BUILD.md](BUILD.md); for those,
check the selected Xcode, SDK, CMake, Python, Conan, and matching Qt roots.

## Qt validation fails

Set `OVERTE_IOS_QT_ROOT` to the iOS target installation and
`OVERTE_IOS_QT_HOST_ROOT` to the matching macOS host tools. Do not allow a
Homebrew desktop Qt to enter through an incidental `CMAKE_PREFIX_PATH`. See
[`docs/ios/QT_SETUP.md`](../../ios/QT_SETUP.md).

## Configure or build fails

Match the earliest causal error to `ios/first-run-triage.json`. Record the exact
command, source revision, target, Xcode/SDK versions, and smallest relevant CMake
cache excerpt. Later linker errors are not actionable while an earlier recipe or
compile phase is failing.

## A simulator or device crashes

Retain the crash report, bounded console excerpt, screenshot, and reproduction
sequence. Remove tokens, signing material, usernames, full deep links, and
absolute home paths before sharing evidence.
