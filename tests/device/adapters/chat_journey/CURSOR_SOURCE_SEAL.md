# Complete warm global Chat source graph seals

`ChatCursorSourceSeal` version 1 is an explicit source extension alongside the
unchanged legacy `ChatSourceSeal` version 1. It reuses that implementation's
original physical passes, admitted chunk identities, isolated full loads,
immutable original stamps, final source/native-clock fences, post-lock age
checks and historical receipt. It does not duplicate the common journey or
introduce another observation protocol.

Its exact warm owner is either a primary `ChatObservationCursor` or an
independent `ChatObservationPublisher`. The cursor must contain original
initial, active and cleanup owners. The graph includes the cursor, publisher
when applicable, every stage's observation and sample owners, and their actual
compiled-script predecessor objects. Identical objects are retained once; two
different owners of the same path are refused. Every root and immutable chunk
remains original and is physically verified. Exact cached JSON types are
checked across the graph, including old stages and compiled-source frames.

The seal binds one guard to every stage's observation. It binds the primary
cursor's query guard, or the actor publisher's additional query guard while
preserving the publisher's original ownership of its cursor guard. Query
permission is separate from read-only physical control: a completed source
can be checked historically without granting another query or accessing an old
PID. Failed or cold seals cannot be adopted. A sealed-looking file whose final
native-clock or actual lock-exit checks did not return cannot qualify receipt.

The original legacy seal record/schema and ownership path remain unchanged.
Pico has a separate private factory and fixed stores for the global extension.
Those roots and rootless chunks keep generic cleanup closed. The factory
checks binding, exact independent/primary owner types and fixed cursor paths.
Premature initial-stage sealing is refused. A complete Pico factory positive
through all original global stages is still part of the enclosing composition
work; the current factory tests cover refusal and retained originals.

The graph proof does not stop a process, close IPC, retire a journal or close
an independent publisher's host descriptors. Existing legacy baseline/archive
code cannot silently adopt this new source family. A later explicit join must
compare the actual externally consumed global cursor rows, seal this complete
graph, include every root/chunk in its archive, and verify actual release.
No public capability, cold RPC owner or stereo evidence is admitted here.

`self_tests.test_chat_cursor_source_seal` covers original primary and actor
graphs, repeated physical receipts without native re-query, unchanged actor
guard ownership, old-stage type mutation and frozen-host/native jumps after
the final seal CAS. Initial/Open and actual cache retirement owners execute.
The remaining 24 input rows and native/V8/widget/network/clock producers are
explicit seams; these tests do not qualify those 24 product effects or a full
external journey. Physical originals are retained on failure.
