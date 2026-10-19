# Native account-origin fixture ownership, version 1

This source provisions and removes only the E2E protected-probe configuration.
It never changes the product metaverse/auth URL, native TLS trust, login state or
credentials. Native C++ is uncompiled; no client/device has qualified it. The
existing default-off feature flag, explicit testScript/private results launch
and healthy lifecycle source gate the Test API.

## Scope and closed input

The original native `feature-native-observe` envelope supplies the actual
32-hex Test `instance`. It is distinct from AccountManager's account instance.
Every origin command must name that current original instance. Old commands
cannot become valid after native process/source replacement; copied metadata,
PID coincidence or a claimed fixture URL cannot rebind this ownership.

The existing Android private or iOS HTTP/AFC command channel accepts exactly
schemaVersion=1, commandId, action=feature-account-origin,
operation=stage|observe|release, runId, ownerToken and instance. Only stage also
has origin. IDs are 32-hex, with ios- prefix only on iOS commandId; ownerToken is
a fresh private random 64-hex value. No file path, credential, desired product
state or assertion field is accepted. The source refuses a foreign instance,
unknown field, malformed nonce or unsupported operation. Tokens remain private
input/journal/native metadata; original result inventories never echo them.

Origin is a canonical ASCII HTTPS origin, at most 1024 characters, with a host,
optional valid nonzero port, and no userinfo (including empty userinfo), path,
root slash, query or fragment. Host readers require lower-case authority. Native
QUrl strict/canonical parsing is authoritative. TLS/hostname trust must already
be established through the unchanged product policy. This source installs
nothing and provides no insecure transport fallback.

## Exclusive original files

The native results root must be canonical, current-owner 0700. The first native
request pins the actual root path/device/inode for this source lifetime; a later
replacement is an error. Only these two reserved direct filenames are touched:

* `feature-account-origin.v1.json`: sorted compact JSON followed by one newline,
  exactly schemaVersion=1, runId and origin. It is the original configuration
  read by the protected-account probe, not a product preference.
* `.feature-account-origin-owner.v1.json`: original ownership metadata containing
  schemaVersion=1, runId, ownerToken, actual Test instance and original config
  SHA256. It is not OAuth authority or an independently measured product result.

Stage requires both names absent and no retired owner scope. Native openat with
O_EXCL/O_NOFOLLOW creates original regular single-link 0600 files, preserving
native ownership before config creation and fsyncing original files/root. It
never overwrites or adopts existing files, including manually provisioned ones.
Other existing private results metadata is left untouched. Only the reviewed
Unix ownership semantics are implemented; unsupported filesystems fail closed.

The native source retains actual created device/inode identities and the bytes
whose write calls actually succeeded. Fresh original-file reads validate current
UID/mode/link count, bounded size, path/inode and bytes. Matching path names or
even copied valid manifest/config bytes in different inodes cannot establish
ownership. Source observations hash/base64 the actual read config bytes and hash
actual owner bytes; they never fill measured data from the requested origin.

A stage ACK proves no content. The host first persists a process/candidate/
session/generation-bound intent, dispatches stage once, then requests a distinct
fresh observe. It validates original canonical config bytes, actual owned file
presence and an unretired scope. The returned origin is decoded from that actual
readback after comparison with controlled fixture inputs. Ignored input, missing
files, wrong bytes or malformed ownership retain the host journal and fail.

## Cleanup, partial writes and late commands

Release retires the actual run/owner scope before deleting anything. This also
retires an intent whose stage command never arrived. A delayed original stage
or a new stage nonce for that retired owner cannot recreate configuration. Native
process replacement has a different instance, so old stage commands remain
invalid there too. At most 256 owner retirements and 65536 command identities are
retained in one native source lifetime; new stages reserve capacity for cleanup.
Repeated exact commands retain their original response and never repeat writes.
Uncertain mutations must not be retried as if they had not happened.

Deletion requires original native creation identity and an independent actual-
byte reread matching that source's recorded successful write bytes. This permits
cleanup of its own zero/partial write, including interrupted manifest/config
creation, while refusing altered, shared, linked or replaced files. A copied
manifest and a matching requested filename are insufficient. If filesystem or
process failure prevents that ownership proof, preserve the journal and report
incomplete cleanup; stopping the process is no evidence of file removal.

A release ACK still proves no absence. A separate new observe must report
originExists=false, ownerExists=false, zero original sizes and retired=true for
the same native context/run/owner. Only then can host ownership be discarded.
An empty directory without native retirement cannot make cleanup green, because
a late stage could still arrive. Source metadata/retirement history is retained
private run evidence, not active configuration or account authority.

The fixed result `feature-account-origin-result.json` has originVersion=1,
commandId, instance, runId, operation, processId, sequence, requestedEpochMs,
capturedEpochMs and source. Stage/release source is exactly performed=true.
Observe source is exactly originExists, ownerExists, originBytes, originSha256,
originBase64, ownerBytes, ownerSha256 and retired. It exposes no owner token,
private filename, username, password or OAuth token. Both hashes cover actual
original bytes; absent files have zero bytes and the empty-byte hash.

Readers retain existing original JSON bounds, current process/source/nonce
checks, monotonic five-second/51-read acquisition and native time ordering.
iOS never compares a host wall clock with native capture time. Each mutation is
dispatched once. Retries acquire only original result bytes. Complete stage and
release each include a separately bounded operation and independent observe.

## Restart and platform integration

This fixture ownership is deliberately native-context scoped. Clean network
probe copies/replies first, then these origin files **before** an intentional
product restart. Restage in the independently verified new native context;
fixture-file staging does not alter the account's ordinary saved login state.
Never copy an old binding into a new process or silently adopt its files. An
unexpected process replacement preserves unresolved ownership. The complete
Authentication restart coordinator remains missing.

The common Test API, both existing command channels, fixture validation, typed
reader and persisted owner now exist. Phone/Pico and the unbound iOS component
now acquire the actual native Test instance through their existing guards,
connect the original file transport and persist this independent scope. Their
adapter-wide cleanup drains probes first, then origin files before base teardown,
and preserves unresolved ownership. Canonical iOS explicitly rejects this
factory; installed-code binding remains unavailable. Actual trusted native origin
setup, ordinary login/cancel/UI/error observations, verified restart and complete
independent actor composition still gate the full Authentication capabilities.

## Device-free checks

The guarded common selection passes 550 cases, including seventeen origin and
nineteen protected-probe cases, with no failures/errors/skips, compiler attempts
or devices. The account source/origin/probe group has 48 focused cases. Explicit
synthetic native boundaries create/read/remove real private temporary files;
the actual JavaScript dispatch also runs. Ignored stage, ACK-only files, no-op
cleanup, missing retirement, partial writes, changed bytes/inodes, foreign
contexts, cross-acquisition native clock regression and retained journals are
covered. These checks validate host/test logic and the boundary model; they do
not execute or qualify native POSIX/Qt code or product authentication.
