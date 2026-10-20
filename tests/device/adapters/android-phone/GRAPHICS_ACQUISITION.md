# Phone role-owned original image acquisition

The existing `_world_render_capture` now accepts explicit `role:"primary"|"actor"`,
`read_only:boolean` and `require_trace:boolean`. The actor requires read-only
admission and an already bound SDK session; it cannot bootstrap, repair, install
or launch a client. `require_trace=True` requires the original v2 same-view render
source, with no legacy fallback. These are internal components, not complete
Graphics operations or device acceptance.

`require_frame_view=True` additionally requires trace-v2 recorded-view provenance
and implies `require_trace`. A legacy acquired image/trace cannot substitute for
the actual frame's retained command-generation view.

Each role has its own private original ownership file:
`phone-world-render-owner.json` and `phone-world-render-actor-owner.json`.
Role-bound ownership version 2 has exactly `ownershipVersion:2`, actual `binding`,
`role`, original `capture` command and `receipts` intent list. Input intent is
still durable before native dispatch. A copied primary journal cannot become
actor ownership. The shared constructor retains explicit unscoped version 1 for
legacy components; it cannot silently migrate an old record into a Phone role.
Unrecognized/old/foreign pending records stay retained and prevent green cleanup.

All acquisition orchestration must hold the existing `phone-script-sources.lock`
through original source acquisition and retirement. Separate ownership files do
not make the single private probe channel or GPU acquisition slot parallel.
A future full Graphics owner must preserve each role's independent native/source
cursors and frame history. A new component instance does not reset provenance.

The read-only command grammar now admits only closed original world capture,
owned PNG storage read/release/inspect, native issued-receipt remove/inspect,
passive Graphics UI observe and the existing subject/native getters. No expected
pixels, arbitrary paths, preference setters, Qt activation or value input is
admitted on this channel. `_graphics_controls(...,read_only=True)` provides
passive original UI reads; attempted input still fails its read-only admission.

Android keeps the original guarded app-private transport for receipt reads.
Deletion now uses `NativeWorldReceiptCleanup` through the existing native
`feature-world-render-receipt` hook. The original native issuer must confirm that
the receipt nonce belongs to this retired capture/context and that present file
bytes match its retained original digest. Changed/foreign/symlink files cannot be
deleted as owned originals. A later separately issued native filesystem inspect
must confirm absence; neither release nor remove ACK qualifies. No shell unlink
bypasses these issuer checks in the Phone factory. The original bounded native
receipt-result metadata remains private evidence, with no image byte payload.

Native image memory/callback drainage still precedes receipt removal. Failed
or unissued receipt intents are retained; an unknown issuer cannot be replaced
with a guessed absence. The current v1 native cleanup protocol intentionally
cannot retire a never-issued receipt intent just because no file is visible.
Such uncertainty remains an explicit cleanup failure until original scoped proof
exists. A full source owner must account for that failure path; it may not drop
the journal or infer success from process stop.

The existing whole-cleanup 45-second budget and each native query's five-second
Phone budget remain in force. Native cleanup now checks final context/owner and
clock barriers, including the freshness cost of final guard latency. A clock
rollback cannot be treated as permitted future skew. No original receipt clock
is retimed. Retained journals make interrupted cleanup retryable only in the same
verified original scope; candidate/process/context replacement remains a failure.

General Phone cleanup attempts both role captures under the shared source lock
before base SDK teardown, also attempting the other role and base teardown after
a failure. It then rejects either remaining journal or any failed retirement.
Stopping the app is not evidence that persistent private receipts were removed.

Ten additional Phone cases cover separate actor ownership without repair,
legacy/foreign role rejection, missing required trace, changed receipt bytes,
unissued intent retention, cleanup ordering, both-role attempts, ignored actor
removal and closed read-only grammar. Two shared cases cover clock/context loss
during freshness reads and final guard latency. Actual local files plus explicit
synthetic native/SDK boundaries verify test logic only. Native code is uncompiled;
no device, installation, build or Jenkins run was performed.
