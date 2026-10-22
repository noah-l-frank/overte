<!--
Copyright 2013-2019 High Fidelity, Inc.
Copyright 2019-2021 Vircadia contributors
Copyright 2021-2025 Overte e.V.
SPDX-License-Identifier: Apache-2.0
-->

# Build Windows

*Inherited toolchain baseline: 2025-08-01; fork guidance reviewed 2026-10-20.*

This guide describes the Windows x64 source build on this hobby fork's `main`
branch. Its commands are checked against the repository profiles; this review
does not constitute a new Windows build qualification. Start with the
[general build guide](BUILD.md) for shared prerequisites and test scope.

Note: We are now using Visual Studio 2022 and Qt 5.15.x.
Select the compiler matching the Conan profiles; an existing toolchain does not
need to be uninstalled merely to prepare a separate build.

**Note: The prerequisites will require about 10 GB of space on your drive. You will also need a system with at least 8GB of main memory.**

## Step 1. Visual Studio & Python 3.x

If you don't have Community or Professional edition of Visual Studio 2022, download [Visual Studio Community 2022](https://visualstudio.microsoft.com/vs/).
While Visual Studio 2019 should still work, we don't support it anymore and might remove workarounds specific to it in the future.

When selecting components, check "Desktop development with C++".

If you do not already have a Python 3.x development environment installed and want to install it with Visual Studio, check "Python Development".
If you already have Visual Studio installed and need to add Python, open the "Add or remove programs" control panel and find the "Microsoft Visual Studio Installer". Select it and click "Modify". In the installer, select "Modify" again, then check "Python Development" and allow the installer to apply the changes.

The older guide recorded a libnode failure with MSVC 14.44.35207 and suggested
14.33.31629. That workaround predates the current Conan profiles, which specify
`compiler.version=194`; it is not a default downgrade step. Match the selected
compiler to [the release profile](tools/conan-profiles/vs-22-release) and inspect
the first actual dependency-build error before applying a recipe-specific fix.

## Step 1a. Alternate Python

If you do not wish to use the Python installation bundled with Visual Studio,
download the installer from [Python](https://www.python.org/downloads/). Use
the Python version in [the general build guide](BUILD.md) so repository tooling
and the native build share a compatible environment.

## Step 2. Python Dependencies

Use a Python version satisfying [BUILD.md](BUILD.md), with a dedicated environment
from the repository root. These Python helper packages need no administrator shell:

```bat
python -m venv build\python-env
build\python-env\Scripts\activate
python -m pip install distro setuptools html5lib
```

## Step 3. Installing Conan

Download and install Conan from the [Conan website](https://conan.io/downloads).
Next, add the Overte remote to Conan:
```bash
conan remote add overte https://artifactory.overte.org/artifactory/api/conan/overte
```
We also need to generate a default Conan profile:
```
conan profile detect
```

## Step 4. Installing CMake

Download and install a CMake version satisfying
[the general build guide](BUILD.md); the modern build requires 3.24 or newer.

Download the file named cmake-[version]-windows-x86_64.msi Installer from the [CMake Website](https://cmake.org/download/). During installation, make sure to check "Add CMake to system PATH for all users" when prompted.

## Step 5. Create conan environment variable

In the next step, you will use conan to install the dependencies required to build Overte. By default, conan will build and install the dependencies in `<username>/.conan2`.
Some build tools still encounter Windows path-length limitations, especially
when building Qt WebEngine from source. Choose a short, writable Conan home
such as `C:\Conan2` rather than relying on every tool supporting long paths.

To create this variable:
* Navigate to 'Edit the System Environment Variables' Through the Start menu.
* Click on 'Environment Variables'
* Select 'New'
* Set "Variable name" to `CONAN_HOME`
* Set "Variable value" to any directory that you have control over. For example `C:\Conan2`.

*Make sure that you copy the contents of your old `.conan2` folder over, or that you add the remote from step 2 again.*

## Step 6. (Optional) Node.JS and NPM

Use the Node.js 22 reference version in [BUILD.md](BUILD.md), with its matching npm.
This is required to build the server-console and jsdoc, and for JavaScript console autocompletion.

## Step 7. Running CMake to Generate Build Files

These instructions only apply to Visual Studio 2022.

### Automatic

There is a batch file to automatically run the commands below for ease of use.

`winprepareVS22.bat`

### Manual

Run the Command Prompt from Start and run the following commands:

```bash
cd "%OVERTE_DIR%"
conan install . -b missing -pr=tools/conan-profiles/vs-22-release -of build
conan install . -b missing -pr=tools/conan-profiles/vs-22-debug -of build
cmake --preset conan-default
```

Where `%OVERTE_DIR%` is the directory for the Overte repository.

Note: After running Conan it is recommended to run `conan cache clean "*" -sbd` to clean the build folders created by Conan, saving disk space.

## Step 8. Making a Build

Open `%OVERTE_DIR%\build\overte.sln` using Visual Studio.

Change the Solution Configuration (menu ribbon under the menu bar, next to the green play button) from "Debug" to "Release" for best performance.

Run from the menu bar `Build > Build Solution`.

## Step 9. Testing Interface

Create another environment variable (see Step #3)
* Set "Variable name": `_NO_DEBUG_HEAP`
* Set "Variable value": `1`

Restart Visual Studio again.

In Visual Studio, right-click "interface" under the Apps folder in Solution Explorer and select "Set as Startup Project". Run from the menu bar `Debug > Start Debugging`.

Now, you should have a full build of Overte and be able to run the Interface using Visual Studio.

Note: You can also run Interface by launching it from command line or File Explorer from `%OVERTE_DIR%\build\interface\Release\interface.exe`

# Troubleshooting

For a failure after Step #7, retain the first causal error and check the selected
compiler, Conan profile, and CMake cache. Preserve local changes and existing
worktrees. Use a separate build directory for a clean comparison; regenerate
Conan files into that directory and point CMake at its toolchain.

The source repository for this fork is
[`noah-l-frank/overte`](https://github.com/noah-l-frank/overte), branch `main`.
Re-cloning upstream is not a repair procedure for this fork's build.

## CMake gives you the same error message repeatedly after the build fails

Remove `CMakeCache.txt` found in the `%OVERTE_DIR%\build` directory.

## MSVC bugs
MSVC is apparently a buggy mess, and almost every version has *something* broken in it.

Available MSVC versions can be found here: https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-community?view=vs-2022
Just search for `Microsoft.VisualStudio.Component.VC.14.` using your internet browser search.

### `EtcLib.lib(EtcImage.obj) : error LNK2019: unresolved external symbol __std_init_once_link_alternate_names_and_abort`
This is a bug in MSVC 14.31.31103. Solution is to upgrade or downgrade from that specific version.

The issue if fixed in MSVC 14.32.31326. Install a probably working version using:
`.\VisualStudioSetup.exe modify --installPath "C:\Program Files\Microsoft Visual Studio\2022\Community" --add Microsoft.VisualStudio.Component.VC.14.33.17.3.x86.x64`
Notice how the relevant component has been added to the "Single components" section on the right.
Make sure to reload your environment (by restarting your terminal for example), otherwise the new compiler version won't be found.

### `v8_compiler.lib(v8_pch.obj) : error LNK2019: unresolved external symbol "protected: static class v8::internal::Handle<class v8::internal::NameDictionary> ?`
This is a bug in MSVC 14.44.35207. Solution is to upgrade or downgrade from that specific version.

Currently (2025-06-28), this is the latest version, so we need to downgrade to an older version.
A probably working version is MSVC 14.33.17.3, which can be installed using:
`.\VisualStudioSetup.exe modify --installPath "C:\Program Files\Microsoft Visual Studio\2022\Community" --add Microsoft.VisualStudio.Component.VC.14.33.17.3.x86.x64`
Notice how the relevant component has been added to the "Single components" section on the right.
Make sure to reload your environment (by restarting your terminal for example), otherwise the new compiler version won't be found.

### `draco.lib(point_cloud.obj) : error LNK2019: unresolved external symbol "__std_find_trivial_4"`
This is a bug in MSVC 14.32.31326. Solution is to upgrade or downgrade from that specific version.

Install a probably working version using:
`.\VisualStudioSetup.exe modify --installPath "C:\Program Files\Microsoft Visual Studio\2022\Community" --add Microsoft.VisualStudio.Component.VC.14.33.17.3.x86.x64`
Notice how the relevant component has been added to the "Single components" section on the right.
Make sure to reload your environment (by restarting your terminal for example), otherwise the new compiler version won't be found.

### Removing specific MSVC versions

To remove a version, replace `--add` with `--remove`.
E.g. `.\VisualStudioSetup.exe modify --installPath "C:\Program Files\Microsoft Visual Studio\2022\Community" --remove Microsoft.VisualStudio.Component.VC.14.31.17.1.x86.x64`
Don't uninstall or manually delete the latest version! This will make your build tools unable to find Visual Studio.
Instead, just install whatever compiler version you need. The last installed version will be given priority.
If you don't know the version number Visual Studio uses to select MSVC versions, just open the `VisualStudioSetup.exe` directly,
press "modify", and deselect it from the "Single components" section on the right. The tooltips help determining what is what.

### `"atlbase.h": No such file or directory`

*Sometimes* the build process requires ATL support.
To fix this, install "C++ vXX.XX (...) ATL (...)" replacing XX.XX with the first two numbers that you used to install an specific MSVC version above using the `VisualStudioSetup.exe`. E.g. "C++ v14.32 (...) ATL (...)".

### `warning : cannot resolve item 'api-ms-win-(...)-l1-1-0.dll'`

You may be able to ignore this warning. My assumption is that the MSVC version used is incompatible with the currently installed Windows SDK,
and Overte will just use the newer SDK during runtime.
