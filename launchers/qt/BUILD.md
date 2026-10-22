# Historical Qt launcher build guide

This directory contains an inherited standalone launcher, separate from the
Overte Interface and the active Android/iOS products. Its older Visual Studio,
CMake, Qt, packaging, and service assumptions are not the current fork's
application build procedure. The directory's own CMake files retain those
legacy project requirements; changing them requires a separate source review.

The original commands are preserved in the [historical launcher guide](https://github.com/noah-l-frank/overte/blob/b5f48d2a842a5cc1655ceb2f69a46bf3c4030429/launchers/qt/BUILD.md).
Use [BUILD.md](../../BUILD.md) for the current shared client/server build and
[the platform index](../../docs/interfaces/README.md) for Phone, Pico, and iOS.
This hobby fork does not supply the former launcher's private service or release
configuration.
