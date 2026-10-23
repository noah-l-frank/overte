# Durable Tablet source observer

`TabletWebSourceOwner` composes the nine actual independent Tablet readers:
sources, trace, DOM, buttons, UIKit input, native disposition, Web closures,
native Script emissions and held-inline callbacks. Every component retains its
own action, command nonce, PID, source birth, original clock, cumulative history,
raw byte segments and query/record ownership. Source acquisition requires the
actual held `script-feature-sources.lock` in that same private root.

Acquisition writer 2 reads literal acquisition versions 1 and 2. Version 2
also embeds the actual current CLI admission before the first native query,
binding its host PID and host-before endpoint. Later acquisition admissions
must retain the immutable native process/installation and monotone original
bundle-observation prefix; a new CLI PID does not rewrite the bootstrap.
Legacy source-only callers may retain the literal acquisition-1 grammar; that
legacy record does not supply a new current-CLI admission.

The parent journals acquisition intent before native reads and each child
association before that child's send. Its immutable acquisition file binds the
exact original child record references, browser snapshot, app-admission prefix,
host worker PID, actual input-phase originals and native before/after packets.
The host/native brackets are independently measured and bounded to 1.5 seconds;
native source times are not replaced with host times. Header copies, child host
intervals and phase source lifetimes must agree with the exact saved originals.
Final file writes cannot restart the original freshness deadline.

Each child stores matching privacy-qualified native bytes before cross-source
interpretation. A lost query leaves all already returned children and the
unreturned child responsibility owned. The parent cannot resume or resend that
acquisition. Accepted native clock boundaries remain unchanged; an exception
before a boundary returns leaves a failed acquisition, not a fresh snapshot.
A failed or unresolved parent/child/app owner blocks another live acquisition.
Source-owner writer 2 reads literal owner versions 1 and 2. A narrow
`reconcile_unanswered(reader)` freezes the unchanged failed parent in its
immutable acquisition file before reading the old child's issued nonce. It
accepts only a typed, privacy-safe, semantically valid actual old response;
missing, rejected, unsafe, partial and unresolved native-clock originals stay
owned and blocking. The child keeps its failed status and original failure
endpoint, plus separately timed original readback spans. The explicit parent
association binds that exact failed child/query/index and actual raw floor.
Neither failed original is a successful frame or page fact. Only a separate
later complete acquisition can produce current facts; historical frame indexing
counts successful frames without discarding the intervening failed originals.
Native callback/product retirement still needs independently acquired quiet
and final OS originals; passive response recovery does not retire those holds.

Parent/app files use the existing immutable `OriginalFrameStore`. Actual
planned/opened/saved descriptors and partial prefix hashes are retained. A
complete opened file after a lost flush is adopted from its original bytes and
inode, without another write or native query. An incomplete prefix or hardlink
remains blocked and owned. `historical=True` creates no state and forbids native
reads, app registration, recovery and all writes.

`tablet_web_history` validates the complete typed source prefixes and original
app admissions, including manager/code/module/membership and file-source
continuity. Each past document retains its own last actual active frame.
Later navigation or close cannot retime it, erase its real sends/receives, or
substitute a new DOM for it. All fifteen Tablet facts are derived from those
originals. Page absence additionally requires current native disposition and
actual UIKit detachment/no responder. Detached but cached-alive owners remain
alive in the evidence and are never called weakly retired.

`TabletWebObserver` acquires the sources and uses a separate historical decoder
for the unchanged `PhaseWitnessPublisher`. A publication binds the immutable
acquisition reference, physical binding, run/role, original worker PID, actual
ticket, original clock bracket and fully revalidated facts. The actor publishes
its own queries; it receives no normalized Primary feature state. Unknown POSTs
can only be reconciled from the existing journal, not resent. App-scope/file
responsibilities and actual native view, callback, carrier and input-object
holds remain explicit public resources. Host worker, query and private evidence
ownership is tracked privately rather than advertised as a product listener.
The explicit `TabletWebDOMDisposition` reader accepts the native terminal
`unavailable` packet as an original disposition, not as a ready DOM or proof of
absence. History still requires genuine current State/Trace/UIKit closure. The
existing ready-only DOM reader remains strict and unchanged.
A genuine pre-app baseline can have no resources: both observers start before
the first ordinary open stages the app Script/files. App registration does not
retroactively change that original baseline. Once acquired, app scopes remain
public responsibilities until a separate retirement owner proves their closure.
Unowned, already-ended UIKit contacts may leave cached event/touch objects;
those objects are not claimed as feature-owned. Active unowned contacts, pending
unowned dispatches and responder focus at baseline are rejected independently.

The whole-feature runtime must separately retain genuine same-physical SDK
admission and prove a distinct observer worker. This source component alone
does not establish candidate identity, create a session, issue product input,
obtain page pixels, stop the application or delete an SDK. The actor owns its
reader/query/files/worker responsibilities; the later Primary finalizer owns
the single ordinary Stop and SDK deletion for their shared physical session.
Both observers still require independent original terminal OS observations.

Host tests execute the generated app/reference/DOM JavaScript, actual private
durability files and unchanged phase/publication journals. Native/UIKit/SDK
transport boundaries are explicit models. They cover the nine-source positive
flow, full fact replay, current native close retaining old counts, lost query
and flush returns, partial inodes/hardlinks, actual source/clock/phase mismatches,
wrong locks and once-only publication using the real historical decoder.
Native code remains uncompiled and unexecuted. Runtime worker/action/image and
paired terminal finalization integration is still incomplete; Feature 7 is not
advertised complete by this packet.
