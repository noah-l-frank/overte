# Independent Photos companion code admission

This internal packet admits the selected standalone Photos companion's actual
installed byte forest. It does not save/read/delete a Photos asset, launch an
application, create a WDA session, install a build or enable Snapshot capability.
The selected companion must already have its own bound physical SDK session,
with the real driver bundle identifier matching its selected final artifact.
The Overte application's separate binding remains the enclosing flow's
responsibility, including explicitly guarded background continuity during a
later companion handoff.

## Source and artifact

`snapshot_companion_artifact.py` reads the unchanged selected final IPA without
extracting or executing it. It requires one independently named Payload app,
the dedicated `photos` role/version and file-sharing declaration. It preserves
signature, provisioning and every other original app byte in the canonical
`bundle_identity.root_digest` calculation. The product reader still accepts
only `Payload/Overte.app` with its original product contract. Companion paths
are bounded ASCII, the same narrower naming profile in native and archive
readers. Links, competing apps, ambiguous names and changed archive identity
fail closed.

`CompanionIdentity.m` defaults to the explicitly selected standalone E2E Photos
target. Its separately selected compile-time Share archive profile has distinct
roles, DTO keys, controls and filenames, and no Photos permission dependency;
see [Share admission](SNAPSHOT_SHARE_ADMISSION.md). No runtime-selected profile
or source translation is accepted. The actual `NSBundle` root and actual process executable
must agree. A background native collector hashes every real regular file,
retaining actual kernel inode/size/mtime/ctime records and directory membership
guards. Later reads perform a complete stat-only recursive census using real
no-follow directory descriptors. Every current entry must be in the exact
cached forest, every cached entry must be reached, and each opened directory
and parent-relative name is checked again after its descendants. The root is
checked before and after the complete census. Only that complete unchanged
forest can reuse its original byte hashes. Initial collection is bounded to 90 seconds, 20,000 nodes, 2 GiB
total and 1 GiB per file. Subsequent native queries retain the 1.5-second bound.
Only aggregate hashes/counts, role/bundle identity, source birth, PID and real
native clocks leave the collector. Provisioning and account-bearing bytes are
hashed; their raw data and filesystem paths are never included in observations.

The normal identity panel appears first in the companion's existing vertical
layout so code admission is reachable without navigating past the Photos
editor. It accepts only a fresh nonce; its buttons select `identity` or `clock`.
The native observer rejects additional query keys, repeated nonces and query
overflow. There is no expected hash, requested file path, expected identity or
success input. The independent clock action does not call Photos or use the
Overte process's clock. Pending/unavailable collection cannot admit code.

## Ownership and original transfer

`IOSSnapshotCompanionRuntime` consumes an already retained session state and
selected artifact scope. Every process read goes through that session's actual
`overteProcessSourceInfo`/`overteProcessInfo` plugin route, whose driver bundle
must match. The owner never substitutes a companion bundle into the Overte
session. The original plugin instance, SDK versions, process, session,
generation, target fingerprint and selected archive digest remain fixed.
The selected original IPA's actual no-follow regular-file identity is pinned
before/after archive decoding and rechecked around every process/input guard.
Mutation or replacement fails before normal input; the runtime does not hash
the whole archive again for every SDK request.

`IOSSnapshotCompanionOwner` uses the actual Script source OS lock and CAS state.
It journals each normal field Clear, nonce Value and button Click intent before
its only delivery. Unknown field returns are resolved only through actual
field text. Unknown button returns recover only the original nonce-bound AFC
output. Inputs are never replayed. A failed/ignored input keeps responsibility.
Native queries occur as clock → identity → independent clock. Their original
UTC/monotonic order and common source birth/PID are preserved, bounded to 1.5
seconds; neither host time nor an old cached result becomes a native clock.
The 25-second host operation budget remains in force.

The actual AFC JSON bytes are retained unchanged inside immutable private
original carriers, with OS scope and fixture originals. These files use the
common 1 MiB limit, exact inode/digest checks and a separate census namespace.
Saved-original/final-CAS loss recovers those same bytes without another click;
partial original writes retain unresolved responsibility. Unknown sibling
frames, changed process/source/session, foreign native PID/birth, stale nonce,
changed prepared identity or byte mismatch cannot yield admission. A pending
identity group remains unqualified after its closing clock is retained and
returns the typed pending signal. A later call starts an entirely new nonce
group; old replies, input intents and original bytes are never promoted or
rewritten. Re-admission performs a new native query group. Pure archive validation reads the actual
selected IPA and immutable originals without constructing a native/SDK source.

## Qualification limits

`SnapshotCompanionAdmissionTests` connects normal W3C field/button requests,
explicit native/OS models, actual independent installed-directory bytes,
original AFC files, real CAS and locking. Negative cases include ignored/lost
inputs, changed executable/signature/provisioning bytes, stale AFC output,
foreign process/source birth/session, invalid clocks, pending collection and
orphan originals. `SnapshotCompanionArtifactTests` verifies role separation
and that the existing Overte artifact reader remains strict.

The ZIP fixtures are structural signed-like models. They do not verify an Apple
signature or prove a real signed IPA, SDK, UIKit layout, Objective-C compilation,
installation, device or laboratory result. Normal Photos permission/scroll UI,
the owned original resource read and deletion, destination quiet, companion
private-file/process retirement, original Overte restoration, independent
witness and paired finalization remain open. Share archive/appex code and
extension process admission require their own later source; ordinary app
identity cannot substitute for an extension. Results keep Photos outcome,
companion cleanup and whole-feature obligations explicit.

The final explicit host selection passes 17 cases in 3.263 seconds. These use
a structural selected IPA, a separately populated installed app directory,
actual native-result/AFC/private files and CAS, with declared UIKit/SDK/OS
producers. They cover candidate mutation/inode replacement, source/PID/session
changes, ignored/lost normal input, stale AFC files, pending hash recovery in
a fresh nonce group, and original inode/byte preservation. The native stat-only
complete-forest census was reviewed, including unknown entries and directory
rechecks. Native compilation, signing trust, actual installation and device
behavior remain unverified.
