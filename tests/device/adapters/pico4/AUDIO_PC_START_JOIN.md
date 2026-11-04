# Independent PC source at the original normal Audio Start

The private `PicoAudioPCStartCoordinator` composes the existing Common16
fourteen-action `PicoAudioRecipe`, an independently credentialed version2 Audio Actor,
and the existing PC recorded-preview producer. It reserves the durable intent,
arms that producer outside both source locks, and requires its actual live
recorder and uncorked receive-monitor route at the finished normal Record
command's delivery fence. It does not replace any normal Pico input.

The canonical private factory is `_audio_pc_start_coordinator(target, run,
primary_phase, actor_phase, peer_configuration, source_lock=...)`. It checks
separate role credentials, the exact original shared SourceLock and Pico PID,
and binds fresh original native, Settings and page readers for the Actor.
The Actor reads these sources independently; it never copies the Primary's
accepted ten-field Audio observations. Original native, Settings and page getter literals, and actual PC CLI stdout
bytes, are retained before UTF8/JSON parsing or schema checks. Existing phase
and OS APIs remain their typed original transports. Long receives and
future waits occur outside both source locks. Lost receive returns resolve by
current original queries; lost Actor publication returns resolve by its exact
fixture GET without reposting the old sample.

## Actual source and lifetime

The additive opt-in `audioPreviewSourceVersion=1` query is produced inside the
existing PC source process. It records the actual provider and client Linux
PID/start/boot, executable signatures and command hashes, plus the actual
`parec` subprocess PID/start/boot and stream generation. It does not invent a
recorder thread or a second capture implementation. Readiness requires the
actual live recorder and current Pulse source-output index, monitor source,
PID route and explicit uncorked state. Acknowledgment or `receivingPreview`
alone cannot authorize Record. The consumer independently checks current
Linux process identity before accepting the source. The consumer and loopback
producer must share the original Linux PID namespace; there is no remote or
PID-namespace fallback.

Both `OVERTE_E2E_RECORDED_PREVIEW_TESTS=1` and
`OVERTE_E2E_PICO_AUDIO_SOURCE_TESTS=1` are required. Existing clients keep the
original preview commands, version1 PC WAV/JSON metadata and status behavior.
The new commands are `receive-preview-owned`, `preview-source` and
`preview-source-retire`. The provider bounds capture owners and query nonces;
it retains failed ownership rather than replaying a capture or releasing an
uncertain process. No PC client, audio server or Domain is started by this
factory or source query.

After automatic native completion, the original cycle3 Start ticket joins the
actual retained input PCM, accepted sink PCM and independent original PC WAV
through the existing digital analyzer. The later completion ticket cannot
substitute for that Start. Final normal HOME, Return and X use the existing
Recipe children. Recorder retirement requires actual process exit/reap,
independently observed old-PID absence, current stream absence, completed
futures and original files. Lost retirement replies resolve by reads. The
final quiet window separately requires at least three seconds on the real
host and every current native and PC clock, with current gaps at most500ms.
All existing source-age, phase, outer-exit, file-stat and ownership checks and
the original120s test bound remain active.

Recorder retirement keeps every original PC WAV/JSON, native input/sink,
capacity/history, Qt context and ownership journal. Replacing a retained file,
including a same-byte Parent replacement at Record delivery, refuses further
input. Product resource history is not reset and there is no hidden restart.
The private Actor version is2; coordinator1 and Recipe2 (reading1/2) retain
their versions. The passive `AudioPCActorOriginals` reader reads old1 and
current2 without creating a live owner or migrating old bytes. Old1 cannot
claim complete original CLI/literal retention.

## Frozen reuse and scope

[The reuse manifest](AUDIO_PC_START_REUSE_20261103.json) pins the inspected
Phone reference `5e8ff8aa19571f5718b982dc47a165b8f22e0dc0`, its six exact
source blobs and the selected independent-role/capture/retirement architecture.
Phone input classes, generated input seams and its Audio restart exception
are not imported. Pico keeps Common16 and its original fourteen normal actions.

The actual Android permission boundary remains the existing controlled-debug
AppOps/dumpsys foundation. No synthetic normal-VR permission action is added.
A PC digital playout monitor can receive network microphone traffic; it does
not prove Pico physical speaker playback or acoustic microphone acceptance.
`fullAudioQualified` and physical acoustic qualification remain false. Complete
Common16 cleanup and the whole independent device campaign remain open.

## Literal admission and append lifetime

`AudioRawArchive` reserves worst-case literal parts, the complete receipt and
index/root metadata, every concurrently pending return and the existing PC
producer's bounded temporary PCM/WAV allocation before any corresponding
Native/Settings send, getter or PC CLI dispatch. One combined512-part and16MiB
bill includes all existing Recipe parts. Fixed root/index files count their
actual bytes; retained PC WAV/JSON and host PCM count their actual stored bytes.
No second budget domain is created for raw storage.

The journal uses its own bounded source lock. It never holds that lock across
a receive or waits on the Primary lock to retain a returned worker response.
The original Primary SourceLock still binds every normal input/source owner.
A separate index receipt records each original command, read ID, original
clock, exact UTF8/bytes/None kind, range and full literal hash. Repeated equal
responses retain their distinct read receipts. All current source/phase clocks,
source-age checks, original120s test bound and quiet500ms/three-second checks
remain unchanged.

An open part retains an actual `O_APPEND` descriptor and its kernel alias.
Before and after every append it verifies the entire prior prefix, hash,
current full physical signature, path, directory and original OFD. Each literal
and durable receipt are fsynced before its parser is invoked. Parts never
exceed64KiB. A completed part closes only after its actual OFD pair verifies,
then uses the existing `ClosedOriginalFile` checks with its final full stamp.
Open ranges are versioned originals; they are not represented as immutable
closed-file stamps.

Fresh Actor/role/header checks gate new source admission before and after its
reservation. An already issued response can still be retained when later
admission fails, including a late lost Actor header or credential. New quota
refusal fences new reads/sends without consuming an earlier issued response's
reservation. A parser/history expansion refusal keeps its sealed literal and
fences new work. If the raw root/OFD itself becomes unreliable, an issued
return stays explicitly unconfirmed in bounded owner memory; partial files and
unknown CAS remain owned. This is not a durable receipt, a recoverable live
owner, or a cleanup success. No retry, truncation, cold adoption or forced
foreign-descriptor close occurs.

The passive reader reports pending writes, unknown index files, unconfirmed
tail bytes and foreign open-part nodes separately. It never promotes those
bytes to a confirmed source or opens a new normal input path.

## Owning host checks

Three disjoint wrappers select the same existing full flow, its independent
host-clock quiet counter, and the source/input/storage/factory counters. Their
AST catalog requires exact complete coverage once:

```text
python3 android/vr/pico/tests/device/test_audio_pc_start.py -v
python3 android/vr/pico/tests/device/test_audio_pc_start_fences.py -v
python3 android/vr/pico/tests/device/test_audio_pc_start_quiet.py -v
```

The tests execute real source/owner/file/CLI/OFD logic and owned stdin Python
worker births/exits. Native/Qt/OpenXR, PC media/Pulse, readiness and target clocks
are explicit models. No compiler, capture program, audio service, network
server or device is activated. Synthetic audio is not physical acceptance.

The raw cases include actual262144-byte native noise and1MiB PC stdout noise
and NUL, parser refusal, zero getter/send on exhausted admission, complete
parallel receipt metadata reservation, late header loss after an actual CLI
return, preserved earlier-issued returns after later quota refusal, partial
append, a foreign write during append, lost receipt CAS, same-node recycled
writer OFD, fork, changed inode and missing root. The normal Record counters
inject at the actual finished command CAS, preserving issued ownership and
zero normal Record delivery. The old1 history reader retains its original
bytes and cannot claim the new literal guarantee.

Earlier original archives remain separate. Actor1's successful87.237s full
flow and85.065s quiet counter were prior source evidence with an identified
large-literal/CLI pre-parser gap. A later Actor2 full flow passed117.813s on a
prior guard revision; two following full/quiet checks reached the original120s
bound while overlapping and remain RED. They are not adopted or resumed.
The current source passes all46 selected cases: the final short wrapper
passes44/11.804s, the full normal/Actor/PC flow passes1/110.777s and the separate
frozen-host quiet counter passes1/108.580s. Full and quiet run sequentially,
each under the unchanged120s bound; they retain109 loaded source hashes and
eight-field physical signatures unchanged. The short wrapper retains233.
These are host model results, not a physical performance or device claim.

Each complete prefix preserves461 actual raw read/dispatch receipts, including
34 independent observations from each native/Settings/page source and every
actual PC source/status/domain/file/receive/retire response. All five receive
operations retain original actual-worker lineage and their WAV/JSON pairs.
The full case ends with27 literal parts plus376 Actor and66 Recipe history
parts:469/512 total. Its531 retained files occupy3777501 bytes; raw literals
account for1729137 bytes. Fixed metadata roots and retained PCM/WAV bytes stay
in the aggregate storage bill. The quiet counter retains the same469 parts
and531 files,3777807 bytes, and refuses completion when native and PC clocks
advance3000ms while the independent host remains frozen. No original is deleted
to fit a limit.

Current proof directories end in `labinpu1`, `2jy7pl7s` and `9c90f9bp` under
`/home/user/.local/state/overte-pico-navigation-g1-check-20261103-`. Their exact
loaded-source manifests are retained with the original outputs. The shared
binding file was independently updated by other features; the factory's own
method bytes remain identical to the original Audio factory packet. The final
short proof records actual whole-file SHA
`5f2ffc4d41259dfb4b1aff61f756e48bf1da3bbda05d8890f1eac9736811e68e`
and Audio factory method SHA
`cb285a27c54a252fa3ef710f13189e13d83ad327e026e44d2d9ff16318e118bb`.
No prior partial run is presented as current completion.

The unchanged legacy/default selection also passes26/81.260s with all94 loaded
source hashes and physical signatures unchanged: ten prior digital joins, the
complete normal fourteen-action default and fifteen shared Voice cases. Its
private proof directory ends in `fmj4d1nd`; no compatibility test substitutes
for the new Actor2 original-source proofs.

## Root integration and strict historical version admission

Root review reproduced two passive-reader counterexamples: an unknown range
index version was accepted from a fully resealed historical root, and boolean
`read:false` aliased literal0. Both were RED before correction. The historical
reader now admits only the exact version1 index envelope and bounded integer
indices, and requires exact range-reference keys and an integer read cursor.
Rejected construction closes qualified original handles; uncertain original
pairs remain strongly retained. No live source, input or migration is granted.

The current disjoint inventory is48 cases: one unchanged normal full cycle,
one unchanged quiet counter and46 short fences. Root's current short selector
passes46/5.151s with233 loaded source SHA/eight-field identities unchanged;
this includes both passive-reader corrections and the actual canonical Audio
factory. The recorded110.777s full and108.580s quiet remain valid for their
unchanged loaded sources; the passive reader is outside those scopes.

Root's short selector uses shared binding whole-file SHA
`9de8e305101fc964981750810214f54de119782ab5834f4f104aaf31b6cba500`;
the Audio factory's method is unchanged. Separate later Create/Emote methods
carry their own qualification. The actual Voice CLI help/parser entry also
exits0 and lists the new opt-in commands; no PC/audio service is started.


## Optional original PID acquisition prerequisite

The [bounded process-original collector](../BOUNDED_PROCESS_ORIGINAL.md) can be
selected through the existing restart transport before construction. Its actual
host pipe and unchanged PID-parser tests preserve literal failures and original
cursor/no-replay behavior. The default transport remains unchanged. This is a
prerequisite only: the complete Audio cleanup owner, cold global-budget/source
composition, new independent roles and physical acoustic evidence remain open.
No additional complete feature capability is advertised.
