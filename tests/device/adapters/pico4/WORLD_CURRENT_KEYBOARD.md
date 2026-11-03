# Current World keyboard component (private, incomplete)

`PicoWorldWebPrefix.focus_current_keyboard_prefix(call)` continues the actual
next Common16 `focus-type` action in its existing Primary Parent. It creates no
second journey, replacement session, expected-text observer or public capability.
The previous `focus_current()`/CurrentFocusParent1, CurrentRay1 and legacy IME
paths retain their defaults and their existing strict refusal behavior.

The normal path is Focus2 → actual keyboard observation → ordinary
`Session.stage(..., 'input.primary', measured_pose)` → actual accepted-key
observation and Trace1 → fresh independent Document1/focus → owned neutral.
Each Caps/control/character has a separate original intent and stream row.

## Actual native boundary

CurrentKeyboard1 is an additive read-only native/TSI/probe operation,
`pico-world-web / observe-current-keyboard`. The request contains an existing
fresh focus nonce and the original run/owner/root; it contains no requested key,
character, key type, geometry, focus state or desired effect.

The producer observes the actual Keyboard QObject and EntityTree. It returns:

- Complete per-layer key-ID membership (at most 256 keys across 32 layers).
- Full **active-layer** key rows: actual `Key::getKeyString(_capsEnabled)` UTF-16
  units, type, switch target, readiness/pressed/visible state, local ownership,
  entity birth/creation, world-center transform and scaled dimensions. Inactive
  membership does not advertise inactive click geometry or strings.
- Actual raised/enabled/input-target/layer/caps/laser preference, HMD state,
  sensor transform and head position. No setting is repaired or keyboard raised.
- A passive accepted-trigger counter at the actual accepted branch. It joins
  the exact previously observed weak EntityItem birth; an unavailable birth is
  null, never invented. Caps switches layers without emitting a Qt key event.
- The existing Trace recorder's identity for the same live QObject, null until
  that actual object has dispatched a traced key. Reading this accessor creates
  no recorder. This ID is not confused with the Keyboard instance UUID.

The getter has an original pre-queue 1.5-second anchor, bounded existing dispatch
queue, original current-focus/native/weak/editor bookends and post-capture age
checks. A repeated nonce is historical; it does not capture or renew anything.
Native scopes are bounded (32 runs, 128 queries per run, 256 maximal-literal
reservations globally); original command anchors remain bounded at 4096.

All new native collection is gated by Pico and E2E compilation flags and actual
`--testScript` mode. Accepted-key bookkeeping additionally requires a prior
actual CurrentKeyboard observation. Ordinary launches perform no new entity
lookup on a key press. The original product trigger body is byte-identical when
its E2E instrumentation blocks are excluded.

**This packet has not been compiled or executed as native/Qt/Android code.**
Source extraction and Host models do not qualify that boundary or a device.

## Time, original receipts and normal input

The existing native `input.primary` gesture settles for 1200 ms and presses for
800 ms before release. A grant ACK can arrive early. Therefore CurrentFocus1
can already succeed by polling fresh focus after the pulse; the pulse alone
does not make that old path impossible. A late two-second ACK correctly makes
CurrentRay1's final *current* 1.5-second calibration check refuse.

The new Gesture1/Focus2 receipt explicitly keeps fresh-at-publication calibration
as **historical intent** after the ACK. It never relabels it as a current source.
It obtains new focus/DOM originals for the effect, with their own original
1.5-second windows. Every actual publication uses the immutable calibration
anchor, including retention, SDK/session-lock waits and final writer admission.
An expired admission has zero send. Before a new calibration, the existing
owned envelope must pass the same session's passive neutral check.

The original five-second gesture/operation and Trace attempt windows remain.
The whole focus-type call retains one 60-second host anchor. Parent admission
uses its earliest already-persisted input host anchor plus 120 seconds and the
original fixture creation/host epoch plus 120 seconds. Old Parent3 did not
persist a whole-run native start, so this packet does not invent one. Existing
outer Common deadlines remain authoritative. No per-key budget reset occurs.

Character completion requires the actual matching VR-key press, Application,
Native input, JNI, Java-entry/consume and distinct Qt-release/Application-release
originals, plus the independent fresh DOM text/cursor/selection change and actual
owned-stream neutral status. A false release `handled` flag remains false;
release delivery is not a fabricated Java text command. Dispatch, ACK, terminal
Trace or a requested character alone proves none of these effects.

Caps completion requires the actual accepted key/birth, new layer and caps state,
unchanged independent DOM/editor, and the original owned neutral. It does not
invent a Qt event or an accepted trigger-end on a now-inactive old layer.

## Actual Unicode boundary

The installed layout source contains 124 ASCII keys. The first unchanged Common
World text action requests `Overte ä Ω 東京 <runId>`. This component attempts the
actual representable prefix `Overte ` using measured keys and actual Caps changes.
At `ä` it must leave the **same** action `acting`, with
`commonActionComplete=False`. It never appends that Common action as completed
or skips ahead to the later ASCII reply step. An initial unsupported/symbol layer
or mallet preference is an observed refusal; there is no setting/layout repair.

`Keyboard::handleSpecialKey(PASTE)` emits Ctrl+V. The actual Android
`NativeWebViewItem::keyPressEvent` ignores Ctrl/Alt/Meta. A clipboard request,
Qt IME injection, configured Unicode label or legacy IME success cannot replace
ordinary VR input or qualify the missing Unicode step. UTF-16 and standard UTF-8
trace originals retain their existing exact checks and unpaired-surrogate refusal.

## Original storage and failure ownership

The same Parent directory retains all originals through the existing
`ChatSourceChunks` codec: 512 total namespace entries, 512 source fragments,
16 MiB decoded/source billing and physical reservations, 64 KiB headers and the
unchanged 48 KiB packed-child bound. The limits are not renewed per key or source.

Private World ledger2 preserves exact UTF-8 bytes/extent/SHA. A raw source record
has an explicit `literalCodecVersion: 1 / utf8-base64-inline` discriminator when
the actual existing packed codec fits. Otherwise deterministic 16384-byte
base64 fragments retain the complete literal. Selection uses the exact encoded
size, not a caught generic failure. Worst-case capacity for 131072 bytes, metadata,
9 children, header/CAS overlap and decoded/physical totals precedes every actual
send/getter and is charged to its original age fence. Native wire semantic caps
remain 65536 bytes; a retained oversized reply still refuses.

Only byte-identical, strictly typed already-captured focus originals reuse an
immutable reference. Reuse re-reads the actual retained record and all original
Parent/file proofs. Every new request nonce, raw return and request/raw association
is still separately retained. No cached freshness, decoded verdict, owner or clock
is restored. Historical storage1, fragmented2 and explicitly tagged inline2 remain
readable through passive `historical_literal`/`historical_original`; reading a
partial `reading` header does not make it ready or recreate its producer.

Document1/Input1 optional retention/capacity hooks retain their actual request and
raw bytes before parsing/type/size refusal. Their default `None` behavior remains.
Consumption1 similarly adds only an optional original-anchor capacity admission.
An elapsed preflight permits neither a late native writer nor a late raw getter.

Only this new keyboard owner uses a callback-free host retention transaction.
Complete Parent byte/payload and full file-byte/OFD/stamp inventories bracket
the transaction. Intermediate checks retain fresh complete namespace and all
eight physical fields, the original directory OFD, the main Parent bytes, and
the ledger's actual prepared file OFD/full bytes/CAS. Only actual prepared child
writes and that ledger header can change the expected set. The final full
inventory must match before the owner remembers it. Source acquisition,
capacity callbacks, Native clocks, SDK guards and input/publication entry refuse
reentry before external work; the transaction ends before any such work.

Every namespace enumeration explicitly rewinds the same verified directory OFD.
On the tested filesystem, an atomic replacement can otherwise be absent from a
subsequent `listdir(fd)` even when its reported offset is zero. The positive test
observes actual header inode replacements and repeated original-OFD rewinds.
Foreign children, changed/replaced old children, a replaced prepared child,
lost CAS and an actually recycled directory FD all refuse. Uncertain handles
remain strongly retained; no foreign descriptor is force-closed.

The current OS file transport has no bounded-read API. Replies over the explicit
131072-byte durable-literal bound leave an actual unresolved raw object in the
host owner and durable extent/SHA/overrun metadata, then fail. This is not a claim
that an unbounded return was fully durably archived. Lost writes/returns, failed
CAS, foreign inode/OFD, missing source and uncertain ownership retain their
namespace and original handles/data; there is no resend, truncation, adoption,
forced descriptor close or generic-cleanup escape.

## Qualification and remaining work

The no-build tests execute real Python Parent/Session/factory functions, loopback
HTTP where needed, prototype normal-controller compilation/consumption, immutable
files, codec and kernel descriptor checks. Native Keyboard/Qt/JNI/Java/DOM/XR
producers in those tests are explicit models. The factory-function fixture does
not qualify complete production candidate admission.

The first continuous attempt reached actual modeled focus, Caps, `O`, Caps-off
and `v`, then hit its unchanged outer 120-second limit. After measured storage
changes, the next attempt reached `Over`; `t` remained published/unresolved at
the same 120-second limit. It had already exceeded the actual 60-second call
budget. Both remain RED, with original files and source manifests retained.
The changed attempt made 6283 full-directory pin reads, taking 76.77 seconds
inclusively. Storage method gains and negative checks do not qualify a complete
normal prefix or extend any deadline.

After the new host retention transaction, all 52 selected reader/codec/ownership
and negative join checks passed in 4.713 seconds. Their 221 loaded or explicitly
declared sources retained exact SHA and eight-field physical identity. A storage
method replay of the same 89 original callback DTOs changed 12.774 to 8.783
seconds while producing identical complete header/child bytes and schema:
136 children, 98 records, 835495 decoded bytes and 365638 physical bytes. It
reduced full pin calls from 1449 to 269. This measures host storage only.
The existing Node probe owning case separately passed after adding the four
keyboard exact/missing/throw/foreign-source dispatcher cases; its original eight
Trace cases remain. This executes the original JavaScript branch with the native
getter explicitly modeled, not a native producer.

The one changed continuous attempt remained RED at its original outer limit
(120.223 seconds); all 226 loaded/declared sources stayed unchanged. It completed
modeled `Overt` at 110.984 seconds; the next `e` remained calibrated without a
new gesture publication. Its ledger remains `reading`, with 319 children,
248 records and no pending record. The last gesture intent is durably present,
but its Parent reference attachment and host close did not finish. The watchdog
raised `SystemExit(143)` *inside* the final pin digest computation, before the
comparison completed; this is no evidence of a digest mismatch or completed
ownership release. A passive audit verified all 389 retained original file
SHA/stamps, every child digest and the final historical record with actual OFD
closure (FD 4 to 4), without recreating the producer. The actual 60-second call
limit was already exceeded; the modeled source clocks and final unreached real
wall-time assertion do not qualify that limit. The run made 3977 full pin calls
(55.302 seconds inclusively). There is no unchanged retry or deadline increase.

Full `Overte ` timing qualification, all Unicode/Common steps, independent Actor,
stereo/pixels, original global cursors/typed returns and final resource/quiet
retirement remain separate open boundaries. A terminal Trace does not retire its
native receiver. Completing host archive close does not retire keyboard entities,
native query maps, web documents, scripts, services or a peer.
