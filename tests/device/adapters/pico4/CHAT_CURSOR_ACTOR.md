# Original independent Chat observer producer

`PicoChatCursorActor` version 3 runs only through the existing independently
provisioned Pico `feature_observer.py` entrypoint. Observer configuration version
3 adds `area=chat` and the exact private `peerConfig` file. Existing version 1
and 2 configurations keep their existing routes. No target discovery, product
process launch, installation, repair or controller input is added.

The producer waits for the original prepared Parent and passively acquires its
own `PicoChatWitness`, `OwnedChatPeer`, native readers and OS lock objects. The
legacy witness must have no publications or existing journal. Its original
initial and active sample owners supply the new global cursor and publisher;
the producer never publishes through the old witness. The normal completed
input journal authorizes stage selection. Cleanup uses a new final-absence
sample owner with the exact original code reader and lock instances.

The producer's fixed private `chat-cursor-actor-owner-*` root records a new
original instance, actual `/proc/self` PID/start/boot identity, bindings and
the two actual captured peer-directory/executable descriptor pairs. It pins
its physical root stamp, canonical cached value and pair descriptions across
each CAS. A cold root or rootless child is retained. It never becomes a fresh
producer by loading a ready-looking file.

The separate fixed `chat-cursor-actor-stop-*` command contains exactly:

```json
{
  "picoChatCursorActorStopVersion": 1,
  "commandId": "<32 lowercase hex>",
  "instance": "<the original producer instance>",
  "runId": "<the original run>",
  "afterSequence": 3,
  "ticket": "<the actual current cleanup publication ticket>"
}
```

`afterSequence` is the actual current global publication sequence, not a phase
count or caller offset. The producer accepts one original command only while
the Parent is `caches-retired`, the current stage is cleanup, and every actual
publication/query transaction has fully completed. It pins the command's exact
physical stamp and original bytes through stop, seal and closure. A mismatch,
lost CAS, failed original lock exit or unknown command quarantines the warm
producer without publication replay or command replacement.

Actor version 3 additionally accepts Stop version 2. It replaces
`afterSequence` with `consumedSequence`, `consumedPayloadSha256` and
`cleanupConsumptionSha256`. The requested sequence must name an actual
publisher payload with its exact digest; every later original publication
must have the same actual cleanup ticket. Those later rows remain intact in
the complete source seal and returned graph. There is no caller offset,
truncation, replay or synthetic publication. Stop version 1 still requires
the exact current sequence. The cleanup-consumption digest is request metadata;
the Parent must separately join it to the actual externally consumed common
cleanup bytes. Supplying that digest alone proves no consumption.

Before any foreground/native query, `publish()` checks original host metadata,
Parent admission and captured descriptor ownership. A pending Parent input is
an expected wait, including HOME/background input. Completed-phase admission
is checked again while holding both original source locks, before unchanged
script/native/peer guards. Genuine unacquired lock contention is retryable only
if neither publisher nor cursor changed or failed. An actual query, failed
lock exit or uncertain transaction quarantines the Actor.

Each successful core publisher return produces a version 1
`returnedPublication` certificate in the original Actor root: actual sequence,
publisher-row digest, current publisher/cursor root digests and original
physical stamps, and actual ticket. Its CAS and outer source-lock exit are
inside the same original 1.5-second freshness bound; clocks after release do
not query foreground state. This certificate binds the completed core return,
not native truth or final process closure. A late CAS/lock failure can leave
a ready-looking disk certificate while quarantining the warm Actor. A future
remote common consumer must gate the original same-phase publication and
freshness independently; the certificate alone cannot authorize a next input.

After the durable `stop-issued` intent, the Actor constructs and runs its own
`ChatCursorSourceSeal`. It preserves the full returned original graph receipt.
After `host-close-issued`, it calls the actual `OriginalDescriptor.close` for
both captured pairs, then detaches the original witness wrappers and verifies
every original pair is closed with no lost/recycled half. The final durable
`host-closed` result has scope `original-independent-chat-host-handles`. It
retains the command, original source roots/chunks, seal and owner result for
the Parent's later complete archival. Best-effort `detach()` alone cannot
produce this result.

Version 2 adds fixed private `chat-cursor-actor-return-*` and
`chat-cursor-actor-consumption-*` stores. All four fixed stores must be empty,
with no rootless chunks, before acquisition. Ordinary generic application
cleanup retains both new stores and their orphan chunks. The Stop command
uses its own explicit version; its version does not follow the producer version.
Legacy producer version 1 roots remain historical/retained only and never gain
return qualification. The public observer configuration remains version 3.

After actual successful warm `host-closed` receipt, `publish_return()` passes
its unchanged literal original root bytes and physical stamp to the neutral
[observer return transport](../OBSERVER_RETURN.md). Its typed family is
`pico-chat-cursor-actor`; its original request is exactly the one original Stop
command ID. No expected feature state or caller completion flag is passed.
A lost host-close CAS cannot publish a return, even if its disk root looks
closed. The producer's historical return guard verifies original roots,
command, source seal and already closed original descriptor pairs, without
native guard reentry or new source queries.

The real loop keeps this same Actor alive after return publication, under its
unchanged original duration bound. It cannot publish or stop again. Only after
independently reading the Parent's fresh actual host identity/nonce and echoing
the original consumption bytes through the neutral sender does it write
`parent-consumed`, recheck original historical ownership and return normally.
Missing consumption reaches the original deadline; it cannot become a normal
exit or trigger another publication. Lost consumption or owner CAS remains
uncertain, retains originals and has no replay path. The returned historical
host-close payload stays unchanged while the separate current Actor owner root
advances to `parent-consumed`; its old stamp is not represented as a new physical
current root. The immutable transport chunks preserve those original bytes.

This is the producer side of the process boundary. The Parent still needs
originally live acquisition of this exact reviewed host PID/start/executable,
typed admission of all original Chat graph bytes and seals, fresh consumption
through the neutral receiver, and actual kernel absence after termination.
The neutral transport supplies no graph or whole-feature verdict. The local
v1 cleanup consumer still requires live Actor objects in its own host process;
it cannot adopt these files as those objects. A separate explicit remote
consumption join is needed. The existing full archive diagnostic and in-process
Actor scheduling seam do not qualify this boundary. Public Chat capability
remains disabled.

The Stop2/source extension passed five grammar/type cases in 0.001 seconds,
then six serial source cases in 38.332 seconds: all extra real same-phase
queries remain in the seal/remote graph; pending-input and lock races make no
foreground query; actual outer lock-exit failure and a native epoch jump after
the final owner CAS quarantine without replay; the existing final-guard jump
and two-process typed-return positive remain green. These use the same explicit
native/Parent/input fixture seams below, not a device or whole common journey.

The five `self_tests.test_pico_chat_cursor_actor` cases execute the actual stage
selection, repeated publisher, full source seal and original Linux descriptor
closing bodies. Native producers, Parent provenance, the remaining 24 input
rows and initial object injection are explicit seams. Separate actual Pico
factory coverage passively acquires its own already-owned stdin peer and
checks captured pairs, cold refusal and host-only detach without changing the
durable publishing intent. Ten small observer tests preserve legacy routes,
validate the private v3 configuration and exercise the real loop routing and
deadline with model owners. No product App, AssignmentClient, device or
independent observer entrypoint process is launched by these tests.

The first six-case source/factory run completed in 32.609 seconds: all five
source cases passed, and the factory test failed because it expected the
internal error instead of the existing private factory wrapper's `ValueError`.
Only that test expectation was corrected. The two actual factory/retention
cases and ten observer cases then passed together, 12/12 in 5.435 seconds.
Those timings describe host checks, not native/device performance or a whole
feature result.

For version 2, the existing actual seal/descriptor positive case additionally
publishes the literal original host-close root and starts a second owned Python
stdin Parent. That process independently reads the real immutable return chunks,
checks the typed terminal root and writes a fresh actual host identity/nonce.
The original Actor consumes it through the actual neutral sender, reaches
`parent-consumed`, and performs no native guard/query. Native/Parent graph
provenance and that small Parent's full graph admission remain explicit seams;
the neutral receiver's separate two-process tests qualify original host/kernel
return. This positive passed 1/1 in 13.818 seconds and, after adding the final
rootless owner/Stop chunk checks, 1/1 in 13.574 seconds. The lost host-CAS refusal and
two actual fixed-factory/rootless-chunk cases passed 3/3 in 20.000 seconds.
The small routing tests additionally cover passive nonce waiting until the
original deadline and strict refusal to qualify legacy version 1 metadata;
all 12 small routing cases passed in 0.272 seconds.
No complete observer entrypoint, product process or device was run.
