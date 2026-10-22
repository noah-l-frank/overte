# Normal Audio recipe composition

`PicoAudioRecipe` v1 composes the existing normal Page, Capture, Background and
FinalClose owners in the original shared v16 Audio input order. It selects only
the common verb/input inventory. Assertion rows and requested outcomes never
enter the dispatcher or its child observations. The private bound factory is
`adapter._audio_recipe(target, run, phase_source, source_lock=parent_lock)`.
Call `prepare()` under the original active baseline fixture ticket, then
`act()` with each complete original `feature.audio.act` input packet. The
component returns dispatch metadata and an explicit partial verdict; it does not
implement or expose complete `feature.audio.observe`/cleanup capability.

The 14 ordinary stages are open, mute, rejected Start, unmute, Start/cancel,
Start/automatic completion, Start/mute interruption/unmute, Start/HOME/return,
and final normal X/tablet close. Cycles 2–5 retain the separate original input
and accepted sink PCM before the next native cycle. Completion preserves the
original recording-start ticket, not the later await-completion ticket.

The parent writes its own durable pending child intent before constructing,
archiving or invoking that child. Each full original child journal is stored in
an immutable, numbered private [original chunk](../chat_journey/source_chunks.py),
with run/binding/role scope, raw-size/manifest bounds, actual host timestamp and
both descriptor/path metadata. Each before/after link is ordered and unique;
every next before root equals the preceding original root for that child.
Background originals explicitly bind the capture journal they actually extend.
Capture start, background and final source histories must match their exact
original parent fixture activations. All earlier PCM descriptors, path identities
and hashes remain checked, including during cold background metadata reads.
Missing/orphan chunks and interrupted writers remain unresolved; no archive is
adopted, rewritten, truncated or deleted.

An optional Audio-only Page admission gate prevents a competing Page owner from
taking input while this parent or an orphan original owns the scope. All owners
reuse the same exact `ScriptSourceLock` instance and original source factories.
The normal Qt transport uses the shared `NativeNavigationIO.bind_before_send`
hook: actual finished command → parent CAS → native/OS guards → exact independent
HTTP phase read → validating clocks → original one-time writer. The phase must
still have the same actual instance, birth and complete activation history.
A slow final CAS with frozen fixture/native clocks cannot bypass the advancing
host age limit of 1.5 seconds. No requested mute, frame count, ACK or dispatch
receipt becomes an observed product fact.

Controller streams use the existing Session durable `intent` and reviewed
[`before_publish`](../../openxr_input/BEFORE_PUBLISH.md) APIs. The exact phase is
read outside the session lock. Inside the intent callback only private host CAS
and already captured native/fixture/host anchors are used. Publication performs
only in-memory envelope/owner checks and advancing monotonic age validation;
it performs no filesystem/source/HTTP/SDK/session operation or second CAS.
HOME and return use the original [once-only SDK route](LIFECYCLE_TRANSPORT_ONCE.md)
with another exact phase fence after its actual candidate/process guards.

Lost normal responses reconcile the original child journal, actual native
history and owned neutral stream. An issued parent with no original child
progress, a changed ticket, an uncertain stream cursor or missing original input
remains unavailable. Cold background recovery reads private metadata, phase and
original OS process/foreground sources until foreground is independently observed;
it never reconstructs Qt while hidden. Recovery finishes only the already issued
child. An interrupted final quiet/deferred wait can acquire new read-only originals
with the exact same immutable child fields and retained frame/window prefixes;
it cannot resend X, HOME, a mute toggle or a PCM writer. A later explicit call
for the same current stage can issue its next,
previously unissued child. Completed tickets return metadata through reads and
never replay their input.

Normal close independently restores the original mute/settings/input peak state,
releases the private PCM tap, observes the original page destruction, closes the
tablet, and requires the existing three-second native quiet/deferred retirement
windows. Original QQmlContext, native history, remaining capacity/timer resources,
all original PCM files and all journals remain accurately retained. This is
`partial-complete`, never whole Audio qualification or EngineCleanup retirement.
The exact remaining [original acquisition and cleanup gaps](AUDIO_ORIGINAL_GAPS.md)
are documented separately.

The `audio-normal-recipe-flow` selector runs a complete device-free composition
and interrupted final read-only quiet/deferred recovery.
`audio-normal-recipe-fences` checks recovery, final delivery/publication refusal,
immutable originals and the actual bound factory. SDK/controller/OS/native audio
are declared host seams; these checks execute no device, microphone, loudspeaker,
network peer or service. Native callback behavior remains covered by the existing
separate actual Qt host checks, not invented by the composition fixture.
