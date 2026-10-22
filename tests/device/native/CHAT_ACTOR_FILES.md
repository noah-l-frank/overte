# Native Chat actor file channel v1

This is E2E-only instrumentation and an actor-host transport, not a complete Chat
adapter. The original private-file header now compiles and executes in the
focused real Qt5/POSIX check described in [peer inputs](CHAT_PEER_INPUT.md);
full Assignment Client linking and real peer reception remain untested.
The host checks below validate transport, ownership and rejection logic only.
The primary normal Chat input/UI/storage adapter, peer stimuli/distance, the remaining native-node/service
composition (the [process actuator](MESSAGES_MIXER_CONTROL.md) now exists) and the
private witness publisher remain required.
No `feature.chat.*` capability is promoted by this component.

## Activation and provenance

Only an `OVERTE_E2E_FEATURE_TESTS` Assignment Client with the explicit, separate
arguments `--testScript --e2eChatActorDir /absolute/private/directory` can create
this channel. The directory must already be a canonical, nonsymlink, same-user
0700 directory for exactly one dedicated fixture Agent. Default builds have no
new option or source. Monitored children inherit both explicit options.

After downloading the actual assignment source, `Agent::executeScript` computes
SHA-256 of the UTF-8 encoding of the actual `_scriptContents`, then configures
its own already-started `MessagesClient` on that object's owner thread. The
hash is never a submitted expected digest. For the existing ASCII peer script
it equals the repository/served-file digest. A future non-ASCII source profile
must qualify the actual decoding rather than assume archive-byte identity.
The actor refuses a pre-existing Chat subscription and owns only its own
secondary subscription to `chat`. The observation channel does not send messages
or mutate the primary client. The separately named fixture
[peer input channel](CHAT_PEER_INPUT.md) uses ordinary script inputs.
Channel subscription is not evidence of
server acknowledgement, peer readiness or message delivery.

The optional existing domain fixture flag `--feature-chat-receiver` stages a
fresh private `runtime/stack-N/chat-peer` directory and adds these native flags
only to the dedicated `overte-e2e-peer` Agent. It writes
`chat-actor-config.json` (0600) in its private output, containing version,
directory, **expected** script/executable digests and the private inherited
process-ownership claim (`ownerToken`, `configHome`). These values are not
printed, placed in a public script or published as measurements. The claim
must be checked against the actual process environment using the existing
`OwnedProcesses.matches` logic. The config is intent, not actor readiness; a
noninstrumented binary or missing native source must fail actor acquisition.
On whole-stack restart this config names the new directory. Existing pinned
readers must reject that replacement and retire/requalify their ownership;
they must never silently relabel it as the previous source.

`fixture.chat_actor_process.LinuxChatActorProcess` qualifies an already-owned
actor PID using the actual Linux executable descriptor and SHA-256, UID,
boot ID, kernel starttime, original private directory and actual opt-in argv.
The mandatory `owned(pid)` callback must independently verify the fixture's
inherited private owner/config environment. Initial metadata supplies only a
candidate PID; metadata, a heartbeat, PID alone or an artifact filename is not
provenance. Construct canonical source/artifact binding only from a reviewed
artifact-to-source manifest plus the measured executable match. The helper
cannot infer the source revision from binary bytes. A failed guard must stop
acquisition. The helper neither discovers nor signals unowned processes.

## Native files and closed protocol

All named files are same-user 0600 regular single-link files. Native and host
retain original directory identity and reject symlinks, replacements, sharing
and in-place changes to immutable source metadata. POSIX native support is
required; unsupported hosts remain unavailable.

* `chat-actor-source.v1.json` is created exclusively by the native actor and held
  open for its fixture lifetime: `{actorVersion:1, instance, processId,
  configuredEpochMs, scriptSha256}`. `instance` is the actual native Chat cache
  birth nonce. The timestamp is the original configuration epoch, **not** a new
  measurement time on each read. A new actor refuses previous source/output
  names. The host pins original inode, nanosecond metadata and content digest.
* `chat-actor-command.v1.json` contains the existing native Chat source v1 request
  with exactly `schemaVersion:1`, a new 32-lowercase-hex `commandId`,
  `action:"feature-chat-observe"`, `operation:"inspect"|"observe"|"retire"`, and
  a 32-lowercase-hex `runId`. It is compact sorted JSON with one final newline,
  at most 2048 bytes. There are no messages, expected states, credentials,
  subscription commands or primary UI mutations. iOS-prefixed command IDs do
  not apply to this separate Linux Assignment Client.
* Every 50 ms the native timer reads a stable original command, remembers its
  ID before executing it, and calls the original `featureChatObservation`.
  An uncertain query is not replayed. That source owns its actual counters,
  epochs, self/mixer identities, receive history, bounded caches and retired
  fences. An unavailable source produces no result, never an empty success.
* `feature-chat-observation.json` is published atomically, at most 131072 bytes:
  `{actorFileVersion:1, commandNode:{device,inode}, resultNode:{device,inode},
  native:<unchanged native Chat source v1 result>}`. Device and inode are
  decimal strings to avoid JSON double precision loss. Both identities come
  from actual native file descriptors; result identity is captured before
  writing that new result file. First publication is exclusive. Replacement
  requires the original previous result descriptor/path to match. The actor
  keeps the newest original descriptor open until replacement or retired-file
  removal. Copying even byte-identical output into a new file fails the host's
  actual-result-inode check. This is private filesystem provenance, not a
  cryptographic signature for untrusted cross-host JSON.

## Host acquisition, errors and cleanup

`adapters.chat_actor_files.ChatActorFiles` takes the private directory,
`PrivateFeatureState`, existing normal-feature binding, independently expected
script hash, mandatory actual-process guard and mandatory actual-FD-release
callback. Use the Linux helper's `guard`/`released` for that host. Explicit
`component_only=True` permits synthetic component contexts, which do not qualify
product acceptance. Its `send` and `read` attach directly to the existing
`NativeChatObservation`; pair and own that reader through `OwnedChatCapture`
and `IndependentChatReceiver`, not through a submitted primary sample.

Before first query, refuse foreign command/result files. Persist query intent
before filesystem mutation; verify the actual original command inode and bytes
before replacing an owned command. Persist the original published command node.
If publication or its journal update is uncertain, retain pending intent and
refuse replay/adoption. Complete known journals can reconnect to the same
original actor. They cannot adopt changed source, PID, process start, executable,
script, root or run. Keep unresolved intent for enclosing fixture recovery.

Every read verifies the actual root/source/process, actual native ownership of
the original source FD, file privacy/stability,
closed envelope and actual result node. A current reply must name the exact
original command node, run/operation/nonce, native birth instance and actual PID.
Require that the actual native process still holds the original current result
FD, then validate original source time/history with the existing Chat parser.
Even a copied envelope edited to name its new inode cannot satisfy this check. The host
never changes a native time, event, identity, text or counter. While a new query
is pending, only the byte-identical **previously acquired original** response
may be returned with its original nonce; the reader ignores it. Foreign, copied,
malformed, missing-after-acquisition or changed replies fail. Native queries use
the existing five-second reader deadline; receiver sampling retains its tighter
1.5-second total bound. External process ownership must remain valid throughout.

`reconcile_pending(original_request)` is an explicit read-only recovery of an
already processed original transaction. It never writes or republishes a
command, unlinks a source or labels an old result with a new nonce. The supplied
request must exactly match the durable pending record. Actual current command
bytes/inode must match the native result's command node; the result must still
be held by the original live PID/start-qualified actor. Native Chat v3 and its
original first Open/Retire mutation ID are mandatory for mutation recovery.
Absent, old, copied, unheld, changed, legacy or foreign-nonce results retain the
pending record. Normal `send` still refuses pending publications.

After repeated original-file and clock checks, the helper consumes only that
original pending publication into the same existing v1 transport journal shape.
A lost acknowledgement of this local update may leave the genuine transaction
consumed; the next parent operation must query passively, never resend the old
mutation. Final copying, persistence, source/FD guards and actual native/host
clocks remain inside 1.5 seconds. Older v1/v2 Chat packets remain readable by the
ordinary transport but cannot qualify this recovery. No durable-layout or wire
version changed. The whole cache owner separately verifies its original nonce
and obtains new independent passive retirement observations.

Retire the peer cache with its existing owner and independent empty/fenced
inspections first. `close()` requires the latest fresh original inspect/retire
to show the actual retired, absent, empty scope. It journals closing intent and
removes only its original command/result. It then requires actual kernel FD
inventory to prove that the native timer closed the original unlinked result
within 1.5 seconds. File absence or an unlink ACK is insufficient. A failed
release retains the journal and can reconnect/retry the actual release check.
A partial deletion before its journal update remains unresolved; do not guess
ownership or report cleanup success. `detach()` closes only the host handle and
makes no cleanup claim.

Global root/source/executable handles belong to the enclosing actor fixture,
not an individual run. Reuse requires the same qualified actor and a new run;
whole-fixture teardown must stop only that owned actor, verify its process/FD
absence and remove only owned baseline files. This transport alone does not
prove full feature cleanup or MessagesMixer/peer availability.

## Local verification

The existing quick control-plane registration includes 26 real-private-file
cases, seven Linux kernel cases against temporary synthetic Python workers and
four existing domain-controller checks (including the opt-in path). They cover
original native-reader composition, unchanged stale originals, ignored queries,
missing results, copied files before first acquisition (including rewritten inode claims),
unheld source metadata, foreign source/nonce/
command inode/PID, modes/symlinks/hardlinks, failed intent and uncertain writes,
known journal recovery, active/false retirement, actual open unlinked descriptors,
wrong executable digest, lost owner/start/process/root, peer-only argv, private
config and fresh restart directories. All pass. These Python cases start no native Agent, domain product,
compiler, build, device or Jenkins job. The separately compiled native timer/file producer
has since received the focused Qt5/POSIX header check linked above; complete
native integration and laboratory qualification remain required.

The additional actual Qt5 proof is
[`test_chat_actor_pending_native.py`](../contracts/chat/test_chat_actor_pending_native.py).
It compiles the complete original ChatActorFiles/ChatObservation/DomainSession
headers into a private owned stdin worker (not Overte, Assignment Client or a
service). The existing original Linux guard qualifies its actual executable,
PID/start/boot/argv/root and kernel open-file inventory. Genuine C++ observation
files pass through the Python transport and whole-cache lifetime owner after
lost Observe AND Retire publication acknowledgements. The worker records one
Observe and one Retire, then new passive Inspect results establish the actual
cache fence. Native result-FD absence after unlink is separately checked through
that live original process. Capture/lifetime journals remain retained. Constant
network/NodeList/assigned-script inputs are explicit seams; this proves neither
an actual Agent/network peer nor full Chat/process/resource closure.

Prepared Qt5 check from `tests/device/contracts/chat` (use the existing Qt5
pkg-config/library environment):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_chat_actor_pending_native -v
```
