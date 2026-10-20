# Physical iOS installed-code binding v1

`--native-binding --physical-candidate-metadata ...` now composes the original
physical candidate consumer, original Appium physical/WDA attestation, native
DVT process plugin and actual CFBundle file measurement. This is implemented
host-tested adapter logic. The native worker is uncompiled, the process plugin
is uninstalled/inactive, and no physical client is qualified. Complete
`feature.<area>.act/observe/cleanup` capabilities remain absent.

## Inputs and ordering

Keep the [physical candidate inputs](PHYSICAL_CANDIDATE.md) independently frozen:
final signed physical IPA, original General terminal metadata/sidecar/all four
tiers, original identity record, frozen normalized inputs, original SBOM pair
and immutable published reader roots. The existing verifier still requires its
official SBOM validators. Missing local releases/dependencies are hard failures;
this change adds no installation or network fallback.

An original kernel-metadata inventory of the artifact root surrounds full
candidate preflight before the canonical base is constructed. It rejects
symlinks, hard-linked regular files, nonordinary nodes, relative/aliased roots,
more than 50,000 nodes or depth above 64. Directory records detect additions and
removals. Original device/inode/mode/link-count/size/mtime/ctime are guarded
during native input; metadata is never converted to a measured content hash.
Full source/input/evidence/candidate verification repeats before and after each
public description or invocation. Changes, including a same-byte restoration
with changed original kernel metadata, prevent a successful result.

Only a physical `ios-documents` E2E target with both original artifact-mode
fields equal to `personal-team-preinstalled` is accepted. Its bundle ID must
match the selected final IPA. The original preinstalled receipt retains
`cryptographicByteBinding:false`; this code does not rewrite that receipt into
code proof. The new native measurement supplies a separate association.
`app.install` and `app.upgrade` are rejected before native I/O and omitted from
capabilities. The original session/device/WDA/OS-version/team checks remain in
place. No adapter path installs a candidate as a side effect of this binding.

The new `IOSNativeMixin` composes with the exact base class provided by the
canonical entrypoint, including when it is executed as `__main__`. It preserves
the independent component entrypoint. The legacy simulator consumer remains a
refusal path and cannot claim installed physical identity.

## Actual sources and private journal

Before controlled launch, require the original plugin's closed source-info v1:
`source:dvt-bundle-pid-xcuitest-state`, native observer instance,
`available:true`, `cleanupPending:false`, and the locked Appium 3.7.0,
XCUITest 12.8.0, RemoteXPC 5.15.3 versions. Missing commands or poisoned/pending
leases fail. The [process plugin](process_plugin/README.md) still requires
separate immutable Proxmox runtime packaging/activation; no active runtime was
changed. Source-info alone is neither code identity nor device acceptance.

`installed-code-binding.json` uses the existing private ownership store, with
closed `bindingVersion,phase,scope,source,process,observation,previousInstance`.
The current host journal writer is version 2; readers explicitly support
versions 1 and 2. A v2 `preparing` record freezes the original validated SDK
process-source metadata before any launch. Its process/byte observation remain
null until actual binding. Ordinary `bind()` still requires the original
in-memory launch owner and now requires that exact persisted SDK source before
and after the independently measured installed bundle. A retired source must
remain independently absent and unchanged before a new preparing intent can
replace it. Missing/unavailable/pending SDK sources cannot create launch intent.

Existing v1 bound/retiring/retired owners retain their original verification
and cleanup readers; no bytes, source or completion result is synthesized.
A v1 preparing owner has no original prelaunch source and remains unqualified:
it cannot be auto-migrated, adopted, rebound or used to replay launch. A fresh
CLI still cannot bind any abandoned preparing owner. Explicit physical restart
recovery remains a separate pending implementation; version 2 supplies its
necessary original provenance without enabling recovery by itself.

Scope is exact source SHA, original archive SHA, actual Appium session,
generation and current target fingerprint. The original session state and
fingerprint are rechecked around every source read. An existing owner whose
session disappeared or changed is rejected before creating another session.
No raw device selector, original path or pairing data is exported.

The state transitions are:

- `preparing`: durable intent before the existing single controlled launch.
  A fresh CLI cannot adopt an interrupted launch. Initial source availability
  is checked before launching, then its original instance is checked again.
- `bound`: original OS bundle/PID/foreground, original plugin instance and
  nonce-bound native bundle observation agree. The seven measured bundle fields
  must equal the independently hashed final IPA contents, including resources,
  scripts, Info.plist, executable, signatures and provisioning bytes. Expected
  hashes are never passed to the native measurement command.
- `retiring`: durable intent before normal Stop or explicit native abort.
  A termination acknowledgment cannot complete this state.
- `retired`: the original OS source separately observed process absence, with
  no outstanding plugin lease. Only then may a controlled new launch begin.
  PID reuse is allowed only with a different original native bundle instance.

Every ready byte verification requires a new nonce, higher original sequence,
nonregressing capture time, unchanged original instance/preparation time and a
separately acquired native clock/PID within the existing freshness window.
The source and OS process are independently checked before and after transfer.
The emitted `executionIdentity` retains the existing four-field Common shape;
source/archive association is returned only after these actual measurements.
There are no sampled expectation fields or cached-success fallback.

Background queries check the actual same OS PID and source without pretending
to read suspended JavaScript. `app.foreground` remains a state query. Normal
`app.launch` performs the existing controlled reactivation and requires a new
foreground bundle observation afterward. Unexpected restarts, including a
permission operation that silently replaces the process, fail this binding.
A future full permission-restart coordinator needs explicit original-process
retirement and new-process measurements; it must not relax these checks.

Cleanup remains possible without candidate inputs. Original component cleanup
is attempted, then original process/session teardown always runs. The journal
is discarded only after successful teardown and independently absent original
session state. Failed teardown, ignored cleanup and unresolved component owners
remain failures with retained private intent.

## Bounds and remaining integration

The original preflight subprocess has a 90-second ceiling; controlled initial
probe waiting retains its 20-second ceiling; native initial bundle measurement
retains 100 seconds/1001 reads and its separate clock acquisition. Later native
reads retain original source bounds. None of those ceilings is automatically
added to the runner's current 30-second describe or 60-second normal-operation
timeout. A qualified bounded bootstrap/deadline integration is still needed
before the slowest valid first-hash path can execute through the standard
runner. Existing outer timeouts continue to fail rather than accepting partial
identity. No global CI workflow or timeout protection was changed.

The 21 new host counterexamples exercise the actual ownership/gate/mixin/
HTTP/AFC logic with explicitly synthetic native/OS byte sources. They cover
missing/foreign bytes, ignored stop, stale frames/nonces, source/PID/session/
generation changes, background/resume, confirmed retirement/relaunch, artifact
replacement, input changes and failed cleanup. The physical consumer's eight
separate cases still exercise the original runtime/identity/General CLI with
injected immutable-package/official-format boundaries. These checks establish
adapter logic only, not native compilation, installation, signing acceptance,
physical-device behavior or complete feature-area adapters.
