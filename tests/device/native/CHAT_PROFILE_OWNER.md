# Native private Chat profile owner v1

This E2E-only component owns actual original Chat storage and never supplies a
normal Erase verdict or complete Chat capability. The application/Android hook
is not linked or device-tested. The complete Manager translation unit, actual
QObject metadata, original worker and this entire owner header compile and run
against existing Qt5 on the host. The ChatView provider in that host test is an
explicit seam; it does not prove QML or VR input behavior.

`Test.featureChatProfile` is gated by the dedicated E2E macro, `--testScript`,
the actual result/lifecycle owner and original GUI thread. Its native singleton
keeps a weak pointer to the original Setting::Manager and refuses a replacement
dependency. Its ChatView provider makes a new original native view query with
its own nonce. Capture and restore require the actual closed page, no draft or
editor focus and an independently available hidden keyboard. A restored storage
packet does not establish that normal Erase, page reconstruction or world-input
release occurred.

The closed command contains only schemaVersion, commandId, runId, action
`feature-chat-profile` and operation `acquire`, `inspect` or `restore`. It accepts
no desired settings, original-history payload, expected hashes or retirement.
Each native nonce is consumed once, including failed reads. The original probe
deduplicates its current command before calling the hook, preserving an earlier
result when polling. Results use the original private mode-0600 output writer.
Missing or stale sources remain unavailable. Native birth, sequence, process,
capture, original writer birth and completed-mutation sequence remain measured.

Acquire retains the exact private original key presence and QVariant values in
native memory. History must actually be absent/null or an empty string/list.
Cache and original worker must agree in exact serialized type/value/presence;
their independent physical INI row must also be literally empty. Config is
bounded to a small scalar/map. Only SHA-256 and physical presence/empty markers
leave native memory. This preserves differences such as null QString versus
nonnull empty QString and unset versus present null. Physical serialization is
kept separate: empty QVariantList and null QVariant can have identical bytes.
Qt's worker equality optimization may also preserve a list type when a new
empty string-list compares equal; this mismatch refuses acquisition.

Restore first reacquires fresh original view/cache/worker/file sources. Both
live histories and the physical row must be empty, and original config must
still match in all three independent forms. The native owner records its
restore attempt before admitting one history write. The Manager then takes its
actual write lock without waiting and checks exact current cache variants,
original barrier birth, completed-mutation sequence and absence of other active
mutations. A racing change refuses admission without overwriting that history.
The original valueChanged/keyRemoved path runs after releasing the cache lock,
as in ordinary Manager mutations. Only the saved original history is restored;
config is never set by this operation.

Success requires a new original worker sync and physical read whose cache,
worker and file fingerprints all exactly match the saved originals. No setter
return or ACK supplies that fact. A source timeout after the write leaves the
restore attempt owned, prevents a second restore and retains the actual queued
worker job. Inspect may resolve it only through new actual sources after that
job finishes; it cannot adopt the old timed-out result. Every output continues
to report `owned:true`, including successful restoration. No command clears
this native ownership or the host's independent journals.

The real Qt5 checks exercise each saved empty native type and absence, hidden
versus present view, actual config/history refusal, a physical nonempty row,
changed cache between snapshot and conditional restore, and a deliberately
blocked original worker after the write. That last case restores once, refuses
another restore, and resolves only after fresh actual cache/worker/file reads.
Node runs the original probe dispatch to check deduplication, closed commands,
retained unavailable results and private output routing. These are component
proofs. The full journey still must perform normal Erase, close/reopen to prove
original Script history reconstruction, independently restore peer/service/UI
resources, observe quiet and then verify actual source/callback/file retirement.

The Pico `_chat_profile` factory now binds this channel to its actual installed
candidate/process, original private command/result transport and existing shared
source lock. `OwnedChatProfile` writes each private host intent before transport,
retains complete compressed original results, reconstructs only validated native
cursors and prevents reacquire or restore replay after missing receipts. Only a
new passive inspect can resolve such uncertainty. All nested original capture
times and final guard/storage processing share the 1.5-second freshness bound;
a frozen target clock cannot hide host processing time. No raw original variant
is stored on the host. Pico cleanup retains even a restored profile journal and
reports unresolved ownership after process teardown. Six focused owner/source
cases and two actual Pico-wrapper cases cover these boundaries on synthetic
native/device seams; no physical device or complete Chat verdict is implied.
