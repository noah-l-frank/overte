# Original owned Chat mixer fixture source v1

The existing opt-in Chat fixture owns one dedicated MessagesMixer assignment
client (`-t 4`). Its authenticated `/v1/messages-mixer-state` endpoint continues
to invoke only that original `MessagesMixer.transition` for offline/online.
It never stops/restarts the whole stack to simulate a mixer-only outage.

When `--feature-chat-receiver` is enabled, `MessagesMixerObservation` is created
at actual stack startup, after the original domain UUID has been read from the
running owned domain-server. It wraps that existing process owner with a fresh
original source instance. The endpoint now returns mixerControlVersion 1,
instance, advancing sequence, actual host capture time, actual domainId, original
stackGeneration, processes, mixer and mixerIdentity. Mixer retains its existing
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

Three focused host checks use only owned synthetic stdin workers. They exercise
actual kernel identity/absence and fresh mixer replacement while all other
workers survive, reject a dead original other process and lost ownership, and
execute the original domain mixer_control function against that real existing
owner and source. These tests run no Overte executable, network domain, headset
or device service. The full Chat owner still must persist controller input
before dispatch, never resend uncertain transitions, independently query these
fresh original process observations and join both actual native client domain/
mixer caches, offline echo, restored socket/delivery and three seconds without
replay before claiming the full network operation. All unresolved journals stay.
