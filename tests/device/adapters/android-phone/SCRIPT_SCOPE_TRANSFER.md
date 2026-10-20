# Explicit Script input-scope transfer, version 1

`_script_missing_from_files(selector, run)` transfers an already stopped owned
file-manager journal into missing-URL input ownership without closing/reopening
the actual Script page. It is an internal host transaction, not a product input,
feature acknowledgment or complete capability. Run identity is mandatory; a
foreign run cannot adopt the current staged owner. All source admission uses the
existing-session/read-only path: no Appium session repair, automatic activation,
file stage/release or native UI input occurs during this transfer.

`transfer_file_scope(run, manager, execution, ui)` requires original typed
`NormalScriptManager`, `NativeScriptObservation` and `PhoneScriptFileIO` objects,
the same bound PID/context and unchanged separate staged-file ownership. The
current file journal must own an open manager, no picker/dialog and no unresolved
load. It verifies the original four file bytes and directory/token, a fresh
complete execution/code/load/effect/all-known source, no owned engine/module or
pending known manager, no owned local Box, and independent current service
absence. The original file-source birth must equal the execution-source birth.
The actual passive UI inventory must show an open page, no picker/system request;
source clocks retain the existing freshness limits. Whole transfer is bounded
to 20 seconds, including original reads, guards and private writes.

Only after those observations does one existing private CAS replace schema 3
file input ownership with the strict schema 4 `feature-script-missing` record.
It preserves the binding, original open-UI ownership and actual service instance/
cursor. It starts with no missing-URL source/load intent; the later ordinary
From URL action is separate. The next schema is checked through the existing
strict constructor before writing. Original file owner/token/bytes stay in the
separate existing file journal, without restaging or removal.

Ordinary construction still refuses implicit schema adoption. Every manager
entry that can send input/close UI now checks its exact current private lease
before input. An old retained object cannot close, cancel or reopen the newly
owned scope after transfer. An object that completed close cannot reacquire an
absent lease or close a later owner's UI; repeating its completed close is a
host no-op only while no new owner exists. Full file/missing feature scopes never replay a
manager-open input merely because its ACK was lost or its result is absent;
they can wait for actual UI only. Narrow public foundation behavior is retained.

Before the CAS, failure retains file-mode ownership; after a completed CAS,
failure/lost return retains missing-mode ownership with the original files and
actual UI intact. The stale old object cannot retry it. The full coordinator must
record its transfer phase before calling, inspect the current exact schema on
recovery, and repeat fresh native/UI/file proof before accepting an already
committed transfer. It must not close/reopen the product UI or blindly rewrite
a missing-mode record to make recovery pass. No complete run recovery/cleanup
claim is made by this narrower primitive.

The joined measurement reader also now requires one original native birth across
file, execution and lifecycle sources. A current nonce and matching PID cannot
mix different native sources; the UI retains its separate original UI instance.

Twelve device-free scope cases, three bound factory cases, two retired-lease cases and two one-send open
cases cover unchanged actual UI/files, pending/orphan work, wrong run/birth,
stale objects, missing/changed data, deadline/ownership loss and lost private
writes. All 149 Phone adapter, 32 measurement and 12 scope cases pass. The
existing Phone runtime owner registers the scope group in both modes. SDK/native
boundaries are synthetic; native code is uncompiled and devices untested.
Full durable nineteen-step coordination, independent actor and complete cleanup
remain pending; no full feature capability is promoted.
