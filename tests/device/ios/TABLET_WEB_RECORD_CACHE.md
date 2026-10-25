# Tablet immutable record interpretation

`tablet_web_record_cache.py` reuses the committed `AvatarRecordCache` file-
signature/read-membership primitive unchanged. The primitive has no Avatar
DTOs or native semantics. Tablet contributes its own complete key: source root,
binding, run, role, fixture, PID, component, current parser identities/bounds,
exact stored row, index and exact previous original packet.

Only fully returned records without unsafe bytes or readbacks are eligible.
Pending, failed, abandoned, rejected and recovered rows still execute their
full decoder. Each component history independently checks its current WAL,
query uniqueness, raw numbering, capture clocks and every original continuity
join. A cache entry does not discharge a later failed query or produce a new
observation, original, clock or cleanup permission.

Cold reuse requires two complete original decodes with identical actual read
sets, output and private file signatures. Every hit independently checks the
same device/inode/mode/owner/group/link count/size/mtime/ctime and restores actual
read membership. A changed original fails closed. Results are deep copies.
The context resets even after exceptions. Outside an explicit operation scope
the original decoder runs normally. The whole feature selects one fresh cache
per outer operation and preserves it only for nested calls in that operation.

Limits are 512 entries and eight MiB of canonical keys/results. Larger records
or a full cache fall back to the full decoder; native/storage limits stay
unchanged. No shared file, Avatar implementation or native producer changes.

Four host cases pass in 0.547 seconds: actual double byte validation and read
membership/deep copies; a newly rejected raw birth and unchanged no-resend floor;
same-inode rewrite/hardlinks; and default/exception isolation with real new
queries still issued. All 14 earlier Packet cases also pass under selection
(1.398 seconds). Profiling the same retained Actor cleanup original graph
measured 12.250 seconds for the cold full decoder, previously 19.237 seconds;
complete unchanged graph reuse remains 0.017 seconds. These are host decoder
measurements, not native timing or a completed Tablet feature.

The same operation-local primitive also accepts immutable fully returned
auxiliary rows. Their exact kind, parser identities/bounds, original row,
ordinal and previous actual packet form a distinct key. Deferred commands
remain uncached because their authority references another current owner.
Current auxiliary WALs, query uniqueness, raw numbering, clocks, pending and
rejected originals and complete Script membership history are always replayed
outside cached records. Four additional actual-file cases cover read membership,
changed source birth, changed previous packet, same-inode rewrites, current WAL
mutation and real new queries. They pass in 0.462 seconds; 44 existing original/
recovery/authority cases pass under selection in 12.636 seconds.

The real unused-terminal worker profile measured 15,563 auxiliary row decodes
and 177.9 seconds waiting on the actual source lock before the next publication.
The old 128-entry host memo filled at 672,466 bytes, well below its unchanged
eight-MiB budget. The new entry count matches the unchanged underlying private
signature primitive's existing bound. No native, storage, transport, freshness
or operation deadline limit changes. That failed whole run remains unqualified.

After this measured correction the same retained original cleanup graph has
191 entries using 992,193 bytes. Its cold complete decoder takes 9.118 seconds
(previously 12.250 with child records only), with identical output and zero SDK
construction. All eight cache countercases pass in 1.380 seconds and the 44
existing authority/recovery cases pass under the final selection in 13.119
seconds. These measurements do not qualify the still pending whole terminal
path or native execution.

Historical aggregate acquisition rows can also reuse the same bounded
primitive. Live, failed and pending aggregate rows always run their full
decoder. Before every aggregate hit, the actual current parent app-prefix and
each exact current child-index/reference association must agree. Every child
history runs first, including its current WAL, unsafe/rejected/readback rows,
query numbering and native continuity floors. Parent phase/admission following
and native-floor continuation remain outside this interpretation cache.

The aggregate key includes the exact row and previous native packet, full
run/role/root/binding/PID/fixture context, ordered component mapping and actual
parent, child, admission, browser and clock parser identities/bounds. Cold
decoding must leave all parent/child blocked flags unchanged. Immutable file
signatures and actual read membership still use the unchanged common primitive.
The same eight-MiB/512-entry budget applies to all three kinds together.

Seven aggregate countercases cover double decoding and exact read membership,
changed current app/child membership, a same-byte same-inode rewrite, a changed
previous native source or parser, live/failed exclusions, a newly rejected raw
child and forbidden cold-decoder side effects. These and the earlier source,
child/auxiliary-cache and candidate-guard suites pass 32 cases in 25.742 seconds;
216 actual loaded Python sources were unchanged. Native/clock producers remain
explicit boundary models. The earlier four-step paired run still failed its
fresh Actor checkpoint at `clear-text`; this cache alone is not a whole-feature
completion or a new timing claim.

The complete retained Publisher replay with this historical aggregate memo
passes in 104.714 seconds, compared with 107.144 seconds before it. All 2,017
original entries and 259 actual imported sources remain unchanged; SDK
construction, HTTP and ownership writes are forbidden during both profiles.
The small measured difference does not establish the live freshness boundary.

An additional dataflow correction removes an actual duplicate inside one
runtime validation: the original Observer decoder returns its successfully
decoded row/frame privately to the runtime, whose bootstrap/readiness checks
use those exact originals. The public Observer result remains unchanged. No
new cache or persisted authority is involved. Current validation rereads the
exact parent and all nine child WALs after the pure joins and rejects any
change. Historical validation retains the existing complete-root inventory
lease. Three new actual-file/generated-JS cases plus fifteen original source
and historical-inventory cases pass in 19.409 seconds, with 251 loaded Python
sources unchanged. They cover duplicate removal without new native queries,
new pending parent/child responsibility and a failed full decoder; a prior
successful result cannot discharge either failure.

On the same 15-receipt Publisher archive, removing that duplicate reduces the
measured historical profile to 73.140 seconds. Actual source constructors fall
from 37 to 22, parent history traversals from 73 to 43 and child histories from
990 to 585. All 2,017 original entries and 259 actual Python imports remain
unchanged, and SDK construction/HTTP/ownership writes remain forbidden. The
independent read-only review found no additional authority or membership bypass
in this narrow dataflow. A new targeted Common first-four-step/paired-error-end
run is pending; the earlier freshness failure is retained and no whole-feature
or physical timing qualification follows from this historical profile.
