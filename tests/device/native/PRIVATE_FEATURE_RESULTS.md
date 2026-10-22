# Private native feature-result files

In the dedicated E2E build, `Test.saveObject` treats the closed lowercase
`feature-<words-and-digits>.json` namespace as private observation output.
A newly added observer cannot accidentally use ordinary result-file permissions
because its filename was omitted from an explicit list. Invalid names in this
namespace are refused before fallback. Existing specific aliases and legacy
normal-feature, recorded-preview and world-render handling remain compatible.
This changes no serialized observation schema or functional product path.

The existing writer requires `--testScript`, refuses a destination symlink,
disables direct-write fallback and writes with owner-only read/write permissions.
Original GPU receipt validation remains required for world-render-storage files.
The new namespace admission provides no observation/effect or resource-retirement
verdict and does not make a full native application build qualified.

`contracts/secure-storage/test_private_feature_results.py` compiles the entire
original `TestScriptingInterface::saveObject` body with actual Qt5 filesystem
operations. GPU receipt types are compile-only seams and never executed. Under
an intentionally permissive child-process umask, an unlisted future observation
and existing original filenames produce actual mode0600 regular files with exact
original JSON. The same private names produce no file without `--testScript`;
invalid namespace names and symlinks cannot change their destination. Ordinary
non-feature results remain writable. This is a focused writer check, not a full
application, GPU, Android or device run.
