# Original owned Chat mixer fixture source v2

The existing opt-in Chat fixture owns one dedicated MessagesMixer assignment
client (`-t 4`). Its authenticated `/v1/messages-mixer-state` endpoint continues
to invoke only that original `MessagesMixer.transition` for offline/online.
It never stops/restarts the whole stack to simulate a mixer-only outage.

When `--feature-chat-receiver` is enabled, `MessagesMixerObservation` is created
at actual stack startup, after the original domain UUID has been read from the
running owned domain-server. It wraps that existing process owner with a fresh
original source instance. The endpoint now returns mixerControlVersion 2,
instance, advancing sequence, actual host capture time, actual domainId, original
stackGeneration, processes, mixer and mixerIdentity, plus runId, offlineFenced
and original command admission/completion history. Mixer retains its existing
mixerProcessVersion 1 running/generation/pending source. It is not a native
connection, delivery or no-replay observation.

The eight fixed other roles are the original domain-server, assignments 0, 1, 3,
5 and 6, domain-script agent and Chat-peer agent. Each is retained as its original
Popen object and qualified against the existing private fixture process owner,
same-user kernel PID/start/boot and executable inode/size/mode/link/timestamps.
They are rechecked before and after the original mixer read. Their original
identities must remain exactly unchanged. No later matching process or display
name replaces one. Mixer identity is separately measured from its actual
original running process; offline requires actual original process absence
through the existing mixer owner, and online gets a different kernel identity.

Only salted identity hashes are exported. No PID, kernel start string, executable
path, environment or owner credential leaves this source. An unavailable other
process, ownership loss, changed executable/start, regressing generation or
capture above 1.5 seconds refuses the entire source. A pending original mixer
intent remains pending. This observation opens no persistent descriptor and
never launches/signals a process itself. Ordinary non-Chat fixture mode retains
the earlier mixer process result.

Seven focused host checks use only owned synthetic stdin workers. They exercise
actual kernel identity/absence and fresh mixer replacement while all other
workers survive, reject a dead original other process and lost ownership, and
execute the original domain mixer_control function against that real existing
owner and source. These tests run no Overte executable, network domain, headset
or device service. The full Chat owner still must persist controller input
before dispatch, never resend uncertain transitions, independently query these
fresh original process observations and join both actual native client domain/
mixer caches, offline echo, restored socket/delivery and three seconds without
replay before claiming the full network operation. All unresolved journals stay.


The Chat command is a closed schema-2 object containing commandId/runId (32
lowercase hex), the actual original controller instance, observedGeneration and
one action (offline/online). The existing transition lock serializes admission,
actual process mutation and source reads. Admission consumes the command ID and
one action for the original controller/run before calling the existing actuator.
Repeated commands/actions, stale generations, another run/controller and an
unfinished callback are refused. An online admission permanently fences any
later offline admission for that controller/run, including a delayed original
HTTP request that arrives after recovery. Online may be admitted first to fence
an offline request whose arrival is uncertain. No ledger or returned ACK is a
process/native success fact: completed/failed records only the actual callback
completion; source.state still measures the kernel owner and actual mixer.
There is no reset/retire/adopt operation for this owner.

The original HTTP handler body is also exercised without opening a server. It
passes the full original command unchanged, rejects old/boolean/extra-field
commands and a wrong token, and returns unavailable for a fenced late offline.
The existing synthetic full-controller test source is updated for schema 2 but
was not executed in this packet. No Overte service or device was run.
