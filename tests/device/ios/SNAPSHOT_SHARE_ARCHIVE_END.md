# Snapshot Share Archive process and SDK retirement

Feature 11/14 has an Archive-only end coordinator after completed original
Share transfer, run-file cleanup, admission seal, source inventory and seven
global-source unlinks. The complete Snapshot capability stays closed and the
source-complete count remains 5/14.

The coordinator pins the original Archive admission, IPA, SDK state and their
first local file identities before Stop. Its process anchor remains the first
positive Archive PID from that admission. A normal bundle-scoped terminate
input is journaled before its one dispatch. An uncertain return never permits
another Stop or an anchor change to a later process.

The existing process-retirement owner receives one closed Archive profile:
only primary stage zero is admitted. Existing profiles and default filenames
are preserved. The repository Node source independently measures original
numeric-PID absence and bundle absence; its actual connection closure and
cleanup state must qualify. Original Node and separately sampled host clocks
must span at least three seconds. Process exit or a command acknowledgement
alone does not qualify retirement.

The main app retains its original PID and SDK responsibility. Its original
process source is checked before one normal activation when necessary, then a
fresh OS observation requires the main app in foreground. This does not claim
that its previous page or settings have been restored.

A fresh original process quiet window precedes the Archive SDK DELETE intent.
Only one DELETE is permitted. Actual GET of that exact old session must return
a typed HTTP 404 before the original local SDK pointer is conditionally
discarded. A successful DELETE acknowledgement with the session still present
leaves responsibility open. Lost responses recover the original journal and
query the same old session without resending Stop or DELETE. Original source
histories and capture bytes remain retained.

The runtime entrypoint obtains the original pair of source locks and reopens
Share history without constructing a live Archive client context. This allows
recovery after the helper has stopped or its SDK session has disappeared.
Historical proof reads only retained original files and performs no SDK call
or journal write.

Main-app page/settings restoration, primary process and SDK retirement,
authenticated upload, independent Actor image evidence, failed-capture
cleanup and the complete outer Snapshot journey remain open. Native companion
source is uncompiled and the repository process plugin remains uninstalled.
No build, device, installation, laboratory, service or remote operation was
used.

## Host validation

`share-archive-end-owner-resume-20261026-01.log`: the first complete Archive end
case passed in 90.928 seconds. It runs original Share and actual host source
file retirement, real Node/host quiet, one modeled normal Stop and one SDK
DELETE, actual old-session 404, exact local pointer CAS, main OS foreground
return, repeated entry and pure historical replay. The original main PNG
remains present. The production operation budget is unchanged.

`share-archive-end-context-resume-20261026-02.log`: six new context cases and
three unchanged Share factory cases passed in 11.712 seconds. They cover the
original PID anchor after Stop, independent quiet clocks, strict profile
namespace, a new live PID, original numeric-PID presence despite bundle absence,
held Node sockets and same-byte SDK/IPA inode replacement. The generic process
retirement owner's eleven cases passed in 0.775 seconds in
`share-archive-end-generic-resume-20261026-01.log`.

`share-archive-end-owner-resume-20261026-02.log` first passed lost-Stop recovery,
then stopped on the lost-DELETE case's exception-type mismatch. The original
privacy-safe typed non-404 transport uncertainty is now propagated unchanged;
no response body is exposed and the issued journal remains unresolved.
`share-archive-end-owner-resume-20261026-03.log` passed both lost-DELETE recovery
and ignored-DELETE acknowledgement in 161.556 seconds. The former requires
fresh actual 404 before CAS; the latter leaves the SDK and local responsibility
owned and rejects a second DELETE.

The fixtures run the repository Node observer with fake DVT and real host
sockets, descriptors and clocks. UIKit, device OS behavior and native source
execution remain explicit model boundaries; these are host results only.

The five approved project suites passed in 6.66 seconds: documentation,
documentation contracts, iOS input selection, policy consistency and project
coverage. Contract-version validation, all 822 workspace Markdown checks and
whitespace checks passed.
