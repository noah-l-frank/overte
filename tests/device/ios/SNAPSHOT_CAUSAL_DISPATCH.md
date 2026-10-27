# Original Snapshot callback and queued dispatch source

This diagnostic source observes the actual `Window.shareSnapshot` native call,
the current original Combined XHR DONE/responseText context, the metadata lease
carried by the actual Application/Snapshot queues, and the existing native
uploader's original ID. It runs no input, Script handler or network request.
The existing HTTP1 and Upload-source2 schemas, public product signatures,
callbacks, source clocks and limits remain unchanged.

## Native boundary

The existing `ScriptManager::FeatureNativeCallScope` captures the actual
manager membership, submitted main code, Combined evaluation originals and
full V8 stack for the existing `shareSnapshot` native method. It accepts no
adapter-supplied manager, source, effect or caller identity. The added method
metadata is limited by the existing E2E/iOS/dedicated-build guards.

`XMLHttpRequestClass` retains a scoped thread-local identity for the actual
currently executing callback. Nested callbacks and timeouts shadow/restore
that context. The read-only HTTP ledger helper returns only the existing
created/sent/finished/DONE-enter/text-read events while that exact callback is
still active. It allocates no replacement event and changes no HTTP wire.
Missing, released, non-DONE or unrelated contexts remain absent.

`IOSSnapshotCausalDispatch` holds copied metadata and weak references to its
own diagnostic leases. A lease retains no ScriptEngine, QObject, uploader,
callback, network reply or product resource. The existing Window call creates
it; the actual Application lambda and optional Snapshot thread hop carry it.
Scoped thread-local values restore the prior diagnostic context on exit. The
existing uploader constructor associates the exact ID returned by the
existing Upload observer. Queue cancellation/destruction, entered/left scopes
and final lease destruction stay separate observed facts. No association or
successful native effect is invented when a queue never creates an uploader.

The native ledger preserves up to 64 original calls and 16 actual hops per call.
The existing native bracket's 250000-byte source bound, overall 262144-byte
reader, original clocks, counter limits and once-only acquisition mechanism
are unchanged. Caller/queue records use actual process epoch; HTTP and getter
monotonic counters retain their own origins. Interface hooks and the new
ledger are inactive outside the existing three E2E/iOS/dedicated-build guards.
The new ledger locks event mutation before its original read bracket begins;
returned event epochs therefore precede `clockBefore` without retiming. This
lock ordering was corrected during source review and remains native-uncompiled.
All native changes remain uncompiled and unexecuted.

The fixed read-only `feature-ios-snapshot-causal-dispatch` command/getter/probe/
fixture/AFC route takes only schema, nonce, action and run. Its version1 source
and acquisition tags are explicit. Probe nonces are consumed before the
getter, including missing/throwing getters, and cannot be reissued on polling.

## Host decoding and qualified evidence

The host codec retains factual unknown caller/context values. Admission
additionally requires the independently observed Script root, all four
reviewed UTF-16 sources, original main code, complete actual indexed V8 frames
and their submitted-code continuity. The separate HTTP join reads and matches
the exact existing original event IDs and event bytes; it never manufactures
an HTTP envelope or refreshes an old timestamp. Call/hop/job identity and
completed prefixes cannot change. An incomplete source cannot heal under the
same birth, and an expired lease cannot resurrect. Weak expiry before the
diagnostic destructor has acquired the ledger lock remains factual uncertainty.

The first focused selection failed at its first decoder case in 8.152 seconds:
the codec treated the existing filename regex string as a compiled regex.
Only the application was corrected to `re.fullmatch`. The failed log remains
`.ios-host-tmp/snapshot-causal-dispatch-resume-20261027-codec01.log`.

The corrected eight cases passed in 7.930 seconds in
`.ios-host-tmp/snapshot-causal-dispatch-resume-20261027-codec02.log`. One fresh
normal Capture/Upload flow executes the actual repository Script/request.js,
responseText GET and Window call/return in Node. The model observes that
actual invocation before the native upload constructor creates its own ID;
it does not copy a requested expected result into the source. Original PNG,
protected HTTP serialization and existing native-upload models execute through
the existing fixture. Counterexamples cover unknown/foreign compiled caller,
wrong independent root, event/HTTP identity mutation, foreign PID/run/clock,
rewritten hop/job/caller prefix, failure healing and lease resurrection.

Four new fixed getter/probe/AFC cases plus four old Combined HTTP1 transport
cases passed in 0.602 seconds in
`.ios-host-tmp/snapshot-causal-dispatch-resume-20261027-transport03.log`.
The new empty native producer is independently constructed; emptiness is only
an original fact and is not returned as an Upload/branch/quiet outcome. Actual
Node probe execution preserves originals and once-only nonces. PID, candidate,
foreground and size failures do not repeat dispatch or recreate a session.

The additional held-lease case passed in 8.052 seconds in
`.ios-host-tmp/snapshot-causal-dispatch-resume-20261027-lease04.log`. A real
Python diagnostic object remains strongly held after the normal upload; drain
stays false. After actual release, its weak/destructor callback records the
original departure and every saved hop is returned. A later source original
passes continuity and drain without changing the earlier original or replaying
Upload. This run overlapped the already-live modeled Assets History3 flow
(session 84859), which imposed CPU/file-I/O load. It is observed acquisition/
logic behavior under load, not an isolated timing benchmark. Original operation
and acquisition bounds remained unchanged.

The seven existing Script boundary cases with optional tracing disabled passed
in 0.222 seconds in
`.ios-host-tmp/snapshot-causal-dispatch-resume-20261027-legacy05.log`.

Native/V8/Qt/SDK boundaries and queues in these fixtures are declared models.
The real Node callback/Window boundary, Python weak diagnostic object, PNG,
protected body bytes and host files do not establish installed iOS execution.

At HEAD `e5724d2402` plus this packet and unrelated unqualified agent WIP,
the five approved documentation/contracts, iOS input selection, policy and
coverage suites passed in 6.72 seconds. Contract versions, all 862 workspace
Markdown files and whitespace checks also passed. Their separate originals
use the `snapshot-causal-dispatch-resume-20261027-` prefix with
`project06.log`, `versions06.log`, `documentation06.log` and
`whitespace06.log`. These source checks do not qualify the other agents'
unfinished Chat7, Assets or Tablet scenario changes, or the native code here.

## Parent integration

The standalone source packet does not admit a live Upload/Backend branch.
The explicit [Upload4/Backend4 composition](SNAPSHOT_FRONTEND_BRANCH.md) adds
durable original query/raw/frame ownership, the same Capture manager/root and
compiled V8 history, a separately reviewed full normal Window callsite, the
exact HTTP callback/backend/native job join and diagnostic lease/scope drain.
Its qualification and remaining limits are recorded separately. Lost
dispatch/query/result and opened file prefixes remain owned without normal
input resend or retiming. Default HTTP-consumer3 retains its branch obligation;
no stronger result is inferred by this standalone codec.

Rendered review, independent Actor/scene agreement, failed/recovered whole
composition and complete source/main/SDK/witness endings remain separate
mandatory obligations. Feature 11 stays partial and capability-closed. No
compiler, build, device, simulator or laboratory was run.
