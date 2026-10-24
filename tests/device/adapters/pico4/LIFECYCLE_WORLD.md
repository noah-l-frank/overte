# Owned ordinary world input and original neutral quiet

`_lifecycle_world(target, run)` binds `PicoLifecycleWorld` to the actual candidate,
process identity and input session. Its private journal lives alongside the
existing Script journey and uses exactly `PicoScriptJourney`'s stable
`script-sources.lock`, shared with other native source owners. The journal
contract is `pico-lifecycle-world-owner:2`, reading versions 1 and 2; no new
full feature capability is advertised.

Only a newly created owner selects v2's complete canonical XZ/Base64 JSON
payload. An admitted existing v1 owner retains its original zlib/Base64 codec,
version and permitted operations; reading never migrates or rewrites it.
The World limit remains 128 original composite frames; the complete payload
still has a 16-MiB raw limit, 48-KiB Base64 limit and existing 64-KiB private
file limit. The v2 decoder has a 16-MiB LZMA memory ceiling and limits output
to the declared raw size plus one. It verifies exact length, hash, canonical
JSON, stream completion and absence of trailing/concatenated data. Duplicate
JSON keys, noncanonical bytes, metadata/type aliases and codec/version relabels
are refused. All source, clock, inventory and physical CAS checks remain.
Historical process snapshots use the original World version when encoding
their exact original payload again; no process/source claim comes from a codec.

The disjoint seven codec and three actual-owner cases passed in 0.478 s. A
fresh original v1 producer remained v1/zlib after cold read and actual further
input/release/reconciliation; neither read nor continuation migrated it. A new
v2 owner and its original cold history/process snapshot remained byte-exact.
The existing thirteen World and fourteen process-retirement cases passed in
21.783 s. The existing close cap counter then passed in 12.058 s with 128
distinct UI/gesture/drive query IDs in the same authoritative journal. Its
complete v2 payload is 1,192,193 raw bytes and 46,912 Base64 bytes in a
47,463-byte private file. Closure refused before another query or X stream.
All journals remain owned; this is not a complete Lifecycle qualification.

The normal Pico runner exposes `lifecycle-world-codec` (the ten disjoint codec
and legacy-owner cases) and `lifecycle-close-owner` (the five close cases,
including the original 128-frame counter), each under the existing 120-second
limit. The old World/process groups remain unchanged and are not duplicated
in either new selector. Both selectors map to existing input/tablet coverage
risks. This branch's actual catalog grows from 226 to 228; integration must
add exactly two to its own current count rather than copy that older baseline.

`prepare()` freezes independently acquired original UI, gesture and avatar
packets before an editor is opened. The actual axes must be known neutral, the
avatar grounded/still with valid tracking and no effective input, and no editor
or keyboard may own focus. Original raw JSON/SHA and cursors remain private.

`world_input()` delivers one ordinary bounded forward controller operation
through the existing OpenXR session. It persists the exact original envelope
before the first possible transport write. The first operation requires actual
Create focus and the real VR keyboard; a subsequent operation requires no
current editor/focus/keyboard, an actually closed owned tablet, and the previous
observed neutral quiet window. Reaching Home via the first normal X is distinct
from closing the tablet before post-editor movement.
The existing two-second lease at strength0.2 does not change native watchdogs.
The original input ID/nonce/sequence must join an original actual `started`
event and intercepted-query vector receipt after this owner's frozen native
barrier. Keepalives and requested/ACK counts never contribute to `worldAttempts`.
Extra foreign starts fail closed. Current effective held input and all three
feet displacement components come from the separate actual avatar source; an
independent peer and changed world image remain required by the whole journey.

`release()` uses the exact session process/nonce/cursor and a separate original
current native status check. It persists release intent before removing the
owned grant. The session/cursor journal remains intact. Lost responses may only
be reconciled through reads; uncertain grants/newer cursors cannot be adopted or
released. Removing a grant and reading native neutral do not prove the effect.
The independent client history must show actual known neutral publication, and
the avatar source must show three seconds of original 3D stability on both native
and host clocks. Movement/gaps reset the window. Monotonic final freshness also
covers parsing, persistence and guards when the device wall clock freezes.
The final result also rechecks the native clock after its last process guard
and after result construction. A late native-clock jump cannot escape by
freezing the host clock; pre-transport intent callbacks remain host-only.

The owner remains partial. Its journal is deliberately preserved even after
quiet; base teardown cannot retire it. Full Lifecycle still needs normal editor
opening/typing, the X join, background/resume, original pending/stale dispatch,
independent observer evidence, position/settings/scene restore and final actual
process-owned resource retirement. A retained original QQmlContext remains
alive until separate real owner-process absence proves its lifetime ended;
normal page disappearance does not rewrite its original weak flags.

Device-free tests execute the real owner, three strict readers, private CAS
storage, source lock and input session over explicit native/physics/transport
boundaries. They cover blocked input versus motion, original attempts, lost
responses, failed persistence, foreign sources/cursors, grant uncertainty,
neutral without client publication and a moving release window. No devices,
OpenXR sessions or complete native client runs are represented by these tests.
