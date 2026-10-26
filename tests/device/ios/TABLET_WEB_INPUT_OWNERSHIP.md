# Ordinary Tablet input ownership

`TabletWebInputs` owns a real `TabletWebPackets` DOM source and an existing
SDK session under the actual Script source lock at the exact source root
`script-feature-sources.lock`. A held unrelated lock is rejected before creating
the input journal. Every action first records
its ticket, label and exact expected source-record index. It acquires and
retains a new actual DOM original before computing normal W3C input. The
original native view, document/element birth, geometry and request are retained.
No JavaScript setter, DOM click, Script setter or SDK session creation is used.

Touch uses the original visible element's projected integer UIKit point and
one normal W3C touch action. Text uses the actual active WDA element only after
its native type, visible/enabled state, rectangle, accessibility label and value
agree with the original controlled DOM field and actual WK first-responder
subtree. Secure/unrelated native fields fail before their value is read. Clear
and Unicode value are separate issued/returned requests. Historical decoding
requires the exact optional-clear then optional-text sequence, each at most
once, and the same closed text/control/length/WebDriver-key grammar as live input. Input acknowledgments
supply no trusted DOM event, bridge effect or cleanup fact.

After a successful nonempty-field Clear, live input reacquires the actual active
UIKit element before issuing the remaining Text request. The element reference
must still be the original one; type, visibility, enabled state, label and
rectangle are checked again before its actual current value is read. That
independent value must be empty. A Clear ACK cannot supply it. A changed or
secure field, ignored Clear or unknown Clear return sends no new Text and
never repeats Clear. The original DOM owner/hash and native/host acquisition
deadlines remain unchanged. This live guard changes no Input1 record grammar;
historical input metadata supplies no new current field/effect proof.

Each request is durably issued before transmission; the canonical SDK transport
guard remains active across slow preparation/journal/process reads. The entire
source age is limited by its original host epoch/monotonic acquisition start,
without a new deadline after writing intent. Unknown touch delivery attempts
one owned release; an expired transport budget sends neither touch nor release,
while retaining any attempted request intents as unresolved responsibility.
Release acknowledgement alone never qualifies actual UIKit/Qt contact death.

For an already attempted touch, release intent/return transitions use the
confirmed original pending touch, its exact native ownership and binding, the
original still-held source lock and original private journal CAS. They do not
require a new candidate/PID/foreground admission and do not acquire product
facts. The original SDK method/session prefix and endpoint are pinned through
`finally`; endpoint changes are refused rather than redirected. Ordinary input
still requires current admission. The unchanged final transport freshness guard
also applies to release, so expiry before the touch sends neither POST nor
DELETE. Unknown DELETE stays journaled and cannot be resent by reconstruction;
a returned release supplies no UIKit weak death or native quiet proof.

After a returned action, a separately owned immutable input record retains its
exact source descriptor and actual request transcript. The small parent journal
stores descriptors instead of repeatedly embedding large DOM packets. Repeated
same-ticket actions read the original record and send nothing again. Failed or
unknown actions remain owned and block further input; separate current native
and terminal OS proof is required by the final coordinator. An unknown source
query is never resent by rebuilding this owner.

Planned/opened/saved record transitions preserve interrupted original files.
An actual complete opened/saved record may be reconstructed after a lost write
return; an empty/partial opened inode remains present and cannot be replayed or
promoted to complete. `historical=True` requires an already historical DOM
source and existing journal. It creates no SDK/reader and prohibits all input,
archive, recovery and journal writes. Actual byte/hash/inode and source-prefix
validation still apply; historical decoding is not current product evidence.

Current version-1 keys: `ios-tablet-web-inputs`, `ios-tablet-web-input`,
`ios-tablet-web-input-frame`, `ios-tablet-web-input-original` and
`ios-tablet-web-native-input`. These prerequisites do not advertise whole
Feature 7 capability. Host tests execute generated page JavaScript and normal
W3C request boundaries with local private files; native UIKit remains uncompiled
and no device/session action was performed.
