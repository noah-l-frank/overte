# Overte Server Console

The Server Console is an Electron application that manages local Overte
processes. Its JavaScript host runtime and locked npm dependencies are separate
from the `libnode` embedded in the native client.

## Run locally

Use the Node.js 22 host-tool baseline in [BUILD.md](../BUILD.md). From the
repository root:

```bash
cd server-console
npm ci
npm test
npm start
```

`npm ci` installs the committed dependency graph, including the Electron runtime.
The console needs builds of Interface, domain-server, and assignment-client in
`build` beside `server-console`. With a multi-configuration native build,
`npm start` selects Debug binaries. Use `npm run local-release` for Release,
or `npm run local-release-no-debug` for Release without console debugging.
These commands launch the application; `npm test` uses Node's test runner.

For dependency verification without launching Electron, CI uses
`npm ci --ignore-scripts --no-fund --no-audit`, `npm audit --audit-level=low`,
`npm test`, and the packager's version entry point. This checks dependency and
console behavior, not an interactive GUI session or a complete installer.

## Packaging

The CMake target `packaged-server-console` builds the selected native components
and bundles the console for its platform. The actual target definitions and
configuration-dependent output live in [CMakeLists.txt](CMakeLists.txt).
Follow [INSTALLER.md](../INSTALLER.md) for desktop packaging. This hobby fork's
console and local builds do not require the maintainer's private Proxmox lab.
