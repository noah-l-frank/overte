# JavaScript API documentation generation

Use the pinned Node.js 22.23.3 host-tool baseline in [BUILD.md](../../BUILD.md)
and this directory's committed npm lockfile. A global JSDoc installation is not needed.
From the repository root:

```bash
cd tools/jsdoc
npm ci --ignore-scripts --no-fund --no-audit
node node_modules/jsdoc/jsdoc.js root.js -c config.json -d ../../build/jsdoc
```

The HTML entry point is `build/jsdoc/index.html` relative to the repository
root. Keeping generated output under `build` avoids rewriting the retained
`tools/jsdoc/out` tree or mixing API output with the Sphinx developer portal.
The CMake `jsdoc` target has its own output directory; see
[`CMakeLists.txt`](CMakeLists.txt).

`config.json` selects the repository's template and plugins. To increase the
Node heap for a large generation, put the option on the local invocation,
rather than editing a global npm executable:

```bash
node --max-old-space-size=2048 node_modules/jsdoc/jsdoc.js \
  root.js -c config.json -d ../../build/jsdoc
```

The bounded dependency verification used by CI additionally audits all npm
severities and generates documentation into a temporary directory. Its entry
point is documented in [project testing](../../tests/PROJECT_TESTING.md#host-prerequisites).

The optional Grav export retains `pretty`'s HTML function and `rimraf.sync`
cleanup APIs with current dependency consumers. Scoped overrides select
`js-beautify` 2.0.3 beneath `pretty` and patched `glob` 14.0.3 beneath both
consumers; EditorConfig also uses patched `minimatch` 11.0.4. Their former glob
versions rely on matcher internals removed in patched `minimatch`, so overriding
only the matcher is incompatible. JSDoc's
version and template APIs stay unchanged. The dependency graph requires Node.js
22.22.2 or newer within the supported Node.js 22 series. Verify HTML formatting,
wildcard matching, cleanup, and actual documentation generation after updates.

## Historical Grav export

`gravPrep.js` retains an optional export for the former `hifi-grav` and
`hifi-grav-content` layout. It is separate from the current Sphinx portal and
has not been qualified as a current documentation publication path. Inspect
its source and expected `out` layout before adapting that older workflow.
