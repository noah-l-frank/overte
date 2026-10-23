# Original Avatar V8 stack accessor

`ScriptManager::featureAvatarV8Stack()` is a passive C++ accessor to the existing
engine-local `IOSV8ScriptStack` version 1. It requires the E2E/iOS build gates,
the original test-script/results-location gates, the actual manager thread and
that manager's actual V8 engine thread. It delegates to the current-isolate
snapshot and adds no JavaScript API, observation route or compile/evaluate hook.

The unchanged native stack component contains indexed actual V8 frames, script
IDs, line/column, source-URL hashes and hashes/UTF-16 units of the actual compiled
source returned by V8. `firstObservedEpochMs` means first source observation in
that engine; it does not claim compilation time or closure identity.

This packet provides the accessor only. It does not connect the stack to Avatar
timer births, XHR open/response consumption or entity calls. The legacy
`callerChain` helpers remain unchanged. Their parent-wrapper traversal can
repeat the current top frame and cannot establish an exact parent call chain.
Existing legacy originals are not relabelled as actual frame evidence.

Strong Avatar consumers still require separately versioned native receipts,
actual manager/birth association, independent pinned module source and reviewed
call locations, original event/lifetime joins and full cleanup. Snapshot's
separate timer instance and schema remain unchanged. Source-only checks cover
the gates, actual engine/thread association, delegated frame-source seam and
legacy separation. No native compilation or device execution has been performed;
this accessor does not complete or advertise Feature 3/14.
