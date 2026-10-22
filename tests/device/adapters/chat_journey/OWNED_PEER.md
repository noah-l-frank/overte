# Passive original native peer acquisition

`OwnedChatPeer` reads the existing fixture's private `chat-actor-config.json` and
acquires only its already-running Linux actor. It performs no discovery, launch,
signal, subscription, cache mutation, Chat input or state publication. The source
PID and native cache birth come from the original actor-held source file. The
actual executable digest, PID/start/boot identity, original owner environment,
private root and held native source inode are independently checked through the
existing `LinuxChatActorProcess` and `ChatActorFiles` implementations.

The full peer binding uses that actor's original version-2 compiled configure
revision, actual executable hash and kernel process identity. It never copies
the primary APK's revision, artifact or process. Legacy source version 1,
unknown/dirty configured metadata, a changed original config inode, a copied
native source, a foreign executable/owner/script or a changed binding refuse
acquisition. The original private credentials stay inside the host config guard;
they do not become shared Chat facts. Configure metadata keeps its documented
boundary: it is not a hermetic build receipt or toolchain qualification.

`sessionId` is the original native cache birth. `generation:0` explicitly denotes
that this secondary Assignment Client has no primary QML generation; it is not a
sampled GUI fact. The actual connection/domain session and received Chat events
still require new independent native observations. This constructor supplies no
messages, effect, current resources or full peer-journey verdict.

All readers reuse the exact peer `ScriptSourceLock` object. Publication refuses
without that original lock. `_chat_transport` identifies the actual file writer
so the enclosing dispatcher can bind final phase admission after the file
owner's last durable CAS. The reader's own process/source guards remain live.
`admit_capture` performs only an original Inspect and durable source admission;
only the separately fenced `ChatCacheLifetime` can later open or retire its
native cache. Every owner and immutable transcript remains retained.

`close_host` detaches only these host descriptors. It does not stop the actor,
retire a native cache, close native input/receipt files, delete a journal or prove
Qt/process/resource release. The enclosing fixture continues owning the live
host peer. An Android absence observation must never be applied to this Linux
PID. Whole-run restoration, actor input release and final independent evidence
remain separate required owners.

Host checks use real private config files, an owned synthetic stdin worker and
actual Linux kernel/executable/source-FD identity. Their producer rows are
explicit seams. A separate Qt5 original-header test also joins the actual native
source producer to this same passive factory, with its compiler macro declared
as an input seam. No Assignment Client, domain, service, OpenXR runtime or device
is run by these checks. Full Pico Chat remains partial.

`input_close(original_input_owner, distant=original_distant_owner)` creates the
separate [input close owner](PEER_INPUT_CLOSE.md) under this exact peer lock and
actual reader/file transport. It retains the completed close manifest and all
original source chunks in the peer's private host state directory. A held peer
cannot bypass the original distance/restore/motion proof. Closing these input
resources does not retire the observation cache or stop the fixture. The native
input run and release/nonces remain replay tombstones; a different run cannot
reuse this actor's closed input route without an independently owned fixture
restart. No automatic restart or process discovery is supplied here.
