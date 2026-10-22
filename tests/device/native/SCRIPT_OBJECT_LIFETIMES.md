# Original Script object lifetime source v1

The Pico private `feature-script-object-lifetimes-observe` query accepts exactly
`schemaVersion:1`, a new32-hex `commandId` and `action`. It has no desired URL,
manager, run, result, stop/quit/delete option or permission to pump product events.
The actual original ScriptManager constructor registers its own existing load
membership instance with its actual engine QObject; `runInThread` records the
actual newly allocated worker. Direct Qt destroyed signals record each separate
object death. `disconnectNonEssentialSignals` reattaches only the same original
manager observer after its normal disconnect; existing product shutdown wiring
is unchanged. Registration never holds strong references to product objects.

All additions require `OVERTE_E2E_FEATURE_TESTS`, the Pico build and the existing
`--testScript` runtime gate. Phone/iOS bindings are unchanged. Future Phone
reconciliation can reuse the source/strict reader after reviewing its own
registration/getter gates. The frozen Phone references inspected for this work
had no equivalent original Manager/engine/worker QObject-death source.

The TestScriptingInterface getter calls the out-of-line
`ScriptManager::featureObjectLifetimes` in the owning library. It does not create
another application-side header-local registry across the DSO boundary. The
source includes complete sorted original rows, permanent tombstones, source
epoch and an exact mutation revision. Shared-holder expiry, running-table or
membership absence and a stopped-but-alive QThread cannot substitute for death.
The source is bounded to128 original object triples per process, without reset,
eviction or a successful truncated inventory. Overflow, identity collision,
unknown reconnect/worker, duplicate death, clock regression or incomplete hook
registration makes the source unavailable. These process-wide metadata rows
outlive product objects; they are not a feature-owned live VM or worker.

The original native getter consumes at most4096 distinct queries, each once,
with the existing billion-sequence bound. Its32-hex native instance, PID,
request/capture/source clocks, all rows and their immutable original death/birth
times reach the private `feature-script-object-lifetimes.json` through the
existing probe/saveObject route. A missing native getter produces unavailable
metadata with no invented empty source. Existing private file modes remain.

`NativeScriptObjectLifetimes` validates the closed original grammar, exact
revision, all tombstone transitions and source/PID/cursor continuity after cold
restore. Both return copies and the final guard precede actual host/native clock
checks in the original1.5-second age budget. Failed acquisition does not advance
its cursor. The Pico factory binds the existing canonical Script source lock;
every query/read guard requires that same held lock. No target input is sent.

This source is not the complete browser retirement proof. The enclosing owner
must independently pin the manager from actual assigned URL, submitted and V8
compiled bytes before stopping it; retain full original histories; exclude
duplicate or later loads; then join fresh actual all-three death with native,
Java/renderer, HTTP, service, phase, capture and both independent roles across
the required continuous quiet window and final archive. `destroyed()` requires
an explicitly selected existing original manager; an unknown ID is unavailable.
The private Tablet Web finalize() still refuses and retains ownership until
that complete join exists. No complete capability is advertised.

Host tests compile the actual registry, native getter and original complete
disconnect method in real Qt. Original weak-holder expiry, deferred QObject
deletion, separately retained engine, stopped live worker, reconnect identity,
overflow and malformed/repeated requests are exercised. Manager/engine are
declared QObject producer seams: the full ScriptManager/V8/Android translation
units, application/APK and devices are not compiled or qualified by this test.
Protocol, actual probe-branch and Pico factory counterexamples additionally
reject stale final copies/guards/clocks, missing/resurrected/retimed originals,
forged revisions and outside-lock acquisition.
