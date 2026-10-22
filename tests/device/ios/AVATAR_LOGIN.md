# Avatar account preparation

`avatar_runtime.py`, `avatar_authority.py` and `avatar_login_owner.py` reuse the
existing candidate qualification, ordinary Login UI, private AFC credential
leases, native account events, protected profile probe, normal account menu
and original preference restoration. They do not enable the Avatar feature
operation triple or certify device behavior.

The whole Avatar run and its two independently provisioned child account runs
have separate identities. Ordinary credentials use the actual child username.
Each role has separate private origin/probe/input/login ownership files. A
read-only authority reader checks both original child-provider timestamps
against the original host request bracket. It preserves provider instance,
child identity and sequence floors; no outer snapshot timestamp is invented.
Provider scopes, supplied domain/session identifiers and credentials remain
input authority, not login or peer observations.

Every login, logout and preference restoration is journaled before its first
ordinary input. Each input retains original UI/native metadata and a separate
native barrier. Actual login/logout event histories establish terminal
transitions. Delivery acknowledgments cannot complete an ignored submit.
Interrupted input remains owned and is never replayed on reconstruction.
Reopening a login runtime with `initial=False` requires its existing validated
role owner and candidate binding; it does not admit an unrelated saved username.

Protected access uses a separate actual native GET with the original child
run, active ticket and `ios-<nonce>` identity. Its response must join a later
passive native account sample. Original native probe inspection and origin
absence establish lease drainage before that read is recorded complete.
An independent actor may separately read the actual private profile-proof route
and join the original provider request to this native response. The primary
adapter credential cannot read that actor-only proof route.

Restoration uses the original account menu and Login controls, clears the
owned saved username, and restores the actual original Remember preference.
Its final original native UI receipt must match the initial preference basis.
Other account preferences and absent/unowned original keys are refused before
input. Credential values are temporary input only and are not journaled.

Host tests use the existing explicitly synthetic Qt/native SDK boundary with a
real temporary loopback HTTPS server, real OAuth/profile replies and proof
routes, real private credential files and file descriptors, and real owner
journals. They include ignored-submit no-resend, original saved-username
admission, remembered-child reconstruction, native protected reads, lease
drainage, historical tampering, ordinary logout and preference restoration.
These are host integration checks; native compilation and device execution
remain unverified.

Full Feature 3/14 still needs the complete Avatar action/observation owner,
independent received/rendered peer effects, actual GPU evidence, materialized
People/model/HTTP callback joins and whole-run product/provider cleanup.
An incomplete input or protected acquisition stays owned; the new login
component does not claim an already completed whole-feature recovery.

The integrated host packet passed 27 explicit no-build tests, including the
existing Authentication journey and preference regression. Documentation,
contract, input-selection, policy and coverage checks also passed. These
results validate adapter logic at the stated SDK seams only.
