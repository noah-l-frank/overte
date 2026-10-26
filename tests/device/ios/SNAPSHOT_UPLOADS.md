# Original Snapshot upload observations

Feature 11/14 has a passive original collector for the real uploader, request
tickets, body file, multipart, reply/timer objects and uploader callback stacks.
The Snapshot capability remains closed; the source-complete count remains 5/14.

The shared `JSONCallbackParameters` optional diagnostic holder uses uniform
global E2E+iOS flags. The dedicated test-build flag is private to selected
targets and must not change this value type's layout in other library callers.
The holder contains a callback and atomic health bit. Copies share diagnostics
without copying the callback or owning any QObject/FD. Empty defaults preserve
existing request behavior.

Only the dedicated iOS test target invokes the callback after ordinary real
reply creation and request watching. An empty or throwing observer marks its
diagnostics incomplete; it never changes or cancels the request. Without C++
exception support, invocation is refused and diagnostics remain incomplete.
No CMake definition was changed.

The Snapshot book associates objects and tickets from actual production
operands. QObject destruction is recorded from actual signals. A callback's
explicit stack departure and weak marker are separate observations. Ticket
generations and file identities use lossless decimal strings. Body FD samples
use the original numeric descriptor and actual `fstat`; descriptor reuse or a
changed file is unknown ownership, not absence. Current body-handle absence
requires actual `EBADF`. Expired markers alone never prove callback departure.

The bounded hashes cover actual successful response `readAll` bytes once.
The collector does not read a response twice or reconstruct it from expected
JSON. It reports endpoint paths, origin-host digests and header-presence
booleans without exposing authorization headers or body text. Shared transport
FD/process proof remains explicitly required after these local facts.

The new getter, closed four-field command, probe branch, fixed original filename
and typed AFC reader preserve unavailable/uncertain reads. A consumed nonce
cannot be resent or turned into an empty scope. Native decisions still require
independent actual signal/UI delivery, authenticated backend original bytes,
resource retirement and the unchanged whole Snapshot journey.

The next vertical is original Capture -> normal Upload/Cancel -> these actual
job/file/reply facts, with durable one-send responsibility and independent
backend multipart/story originals. Photos permission/settings recovery,
independent Actor image evidence, primary source-journal retirement and paired
process/SDK finalization remain open. No additional unrelated helper series is
claimed as integration.

## Host validation and limits

`snapshot-uploads-source-resume-20261026-04.log`: 33 selected cases passed in
0.167 seconds: eight new upload source cases and 25 existing Snapshot work,
capture and export cases. New cases use real private files, body descriptors,
actual descriptor reuse and weak Python lifetimes with explicitly modeled Qt
and HTTP producers. They cover retained original identity/tickets, a held FD
after weak death, a departed marker without actual return evidence, observer
failure without changing the modeled send, foreign-run rejection, actual AFC
reader routing and real probe JavaScript nonce/original preservation.

The first selections exposed a replay-key mistake in the new parser and an
existing writer test that assumed the Snapshot block preceded the new Audio
block. The parser and scoped test selection were corrected. Two existing
Snapshot probe tests now pass the identical program via stdin because the
measured 134901-byte source exceeds the per-argument limit.

Native C++ remains uncompiled and unexecuted. The host failure model does not
qualify the real C++ exception boundary. No native compiler, build, device,
installation, laboratory, service or remote operation was used.

The five approved project suites passed in 6.89 seconds: documentation,
documentation contracts, iOS input selection, policy consistency and project
coverage. Contract-version validation, all 829 workspace Markdown checks and
whitespace checks passed.
