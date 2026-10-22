# Independent Phone Emote actor, version 2

`PhoneEmoteActor` connects the real Run/Role/Source/Namespace/Lifetime components
to the existing separately credentialed `script_observer.py` process. It is an
internal observer owner, not a complete public Emote adapter. No new runner,
automatic process launch, target discovery, session repair or full capability
registration is introduced. Source/native instrumentations remain uncompiled;
all checks here are host simulations, not device acceptance.

## Construction and private configuration

`PhoneAppiumAdapter._emote_actor(selector, run, client=..., image_policy=...)`
requires a reviewed candidate, the controlled Phone app/target and an explicit
separate Client. It reopens the existing parent Run's run/fixture URL, private
artifact root, image extent, marker ROI and admission policy. These are shared
input configuration and expected candidate authority, never copied primary
measurements. It constructs no foreground native source. Role/source acquisition
later independently checks the actual process/candidate/session, submitted code,
configured roots, current world/probe/cache and fresh native/UI originals.

The existing observer config v2 remains readable for Scripts, Authentication and
Graphics. Config v3 keeps those same fields for existing areas and adds Emotes with exactly
`{featureObserverVersion:3,area:"emotes",target,candidateArguments,fixtureUrl,actorToken,durationSeconds,imagePolicy}`.
ImagePolicy is exactly `{source:"world-render-target",marker,subject}`; rectangles
must fit the parent's actual configured extent. The existing CLI still verifies
the candidate arguments, forbids an inherited reader token and disables primary
feature extensions in the actor process. Credentials remain solely in the private
config/Client and are never put in lifecycle evidence or logs. Existing private
file permissions and target-selector redaction apply. Launch is reserved for the
authorized Proxmox laboratory; do not launch device automation on the workstation.

The same loop now calls `run_emote` inside this entry point, waits for the
existing Run and uses only this actor's explicit Client. The configured 30..1800
second monotonic deadline includes the final step; source contention alone may
be retried. Other unknown/missing results remain errors. The primary adapter
does not start the actor process. The enclosing finalizer must eventually verify
actor retirement, retain its originals and remove all owned journals.

## Closed lifecycle ownership

`phone-emote-actor-lifecycle.json` is exactly
`{emoteActorVersion:2,runId,fixtureUrl,artifactRoot,imagePolicy,payload}`.
Payload contains one exact `{phase,binding,pending,last,quiet,dropped,providerRetirement}` record.
Phase is watching, publishing, quiet, drained or retired. Binding is the unchanged
expected Run authority, independently verified by every real role/source factory.
The existing packed 64 KiB metadata bound is unchanged. At most 1024 dropped
publication references are retained; no truncation or higher limit is allowed.

Pending is null or exactly
`{sample,startedMonotonicMs,hostEpochMs,provider,issued}`. Sample is the actual Role
publication `{ticket,actor,actorSequence,capturedEpochMs,facts}`; actor is always
owned-observer. Its five peer facts are projected from this role's new original
native/image observation, never primary observe or an expected scenario state.
Provider is the actual original source phase. StartedMonotonicMs/hostEpochMs are
the original publication acquisition anchors. Issued is durable send intent,
not delivery proof. Pending is persisted/read back before any POST. A slow write
cannot hide an old sample behind frozen external clocks; age includes the
original independent monotonic floor and existing 1.5-second bound.

Last is null or `{sample,receipt}`. Receipt is exactly
`{kind:"journal",receivedEpochMs,body}`. Body is the actual separate fixture
journal entry, containing the original sample fields plus actual sequence and
receivedEpochMs. The receipt proves publication only, not product behavior.
The original product facts must additionally reopen against Role.stored and
its original source/image/motion files. HTTP success with an absent entry is
insufficient. Foreign/changed entries and missing results preserve pending
ownership and prevent retirement. Backend read timestamps never replace the
sample's original capturedEpochMs.

Dropped is a strictly increasing list of `{sequence,ticket,reason}` references to
original role records. Reason is phase-changed, expired-before-send or fixture-retired. These
entries describe obsolete publication intent only; they do not erase the
immutable role original, add actor samples or report successful product effects.
An already-issued missing/unknown result in the same phase is not replayed.

## Phase, namespace and background scheduling

`step()` holds the shared Source lock only while checking parent/role ownership,
acquiring originals, transferring obsolete scopes or acknowledging a namespace.
Publication POST and independent receipt GET happen after releasing that lock.
Every sample is reconstructed from its own original role record before delivery
and acceptance. A lost POST return or final lifecycle write can reopen the
actual backend entry and finish the same historical transfer without another
POST, source acquisition or replacement epoch. An entry not actually present
cannot be guessed from an ACK or expected payload.

Preparing, acting and intermediate cleanup/resource phases wait without creating
a foreground-only getter. That gate is checked again at delivery and acceptance,
covering a background intent created after measurement while the network was
unlocked. Pending remains owned until actual foreground recovery lets the parent
return to active. The actor never sends Home/activate or replays a background
cycle. Ordinary phase observation requires the exact current actual fixture
stimulus and corresponding prepared/active/resources-restored parent state.

A real source/image acquisition may cross a fixture ticket. The actor retains
that obsolete attempt through [phase retirement v2](EMOTE_ROLE.md#obsolete-actor-image-retirement-version-2),
including actual GPU-buffer/issuer-receipt retirement, before its next read.
Successful old originals whose publication was overtaken remain historical.
Same-phase missing/invalid observations remain errors, not pending success.
A switching parent first transfers obsolete role ownership, then obtains this
actor's own idle source and acknowledges its namespace freeze. It performs no
new playback or primary acknowledgment and does not publish a frozen old frame.
New namespace observations wait for the primary's actual input completion.

## Independent cleanup and terminal handoff

After real input/Scene/View restoration, this actor obtains its own three-second
native/work/UI quiet window. It durably retains the exact Lifetime retirement
packet in quiet before that child journal can be removed. Lost child/callback
returns reuse the same original window without work queries or epoch refresh.
This historical packet is not a claim of current/global callback absence.
The enclosing whole-run finalizer still owes fresh selected-work/native/resource
verification and its own primary quiet proof.

Only then does the actor acquire and publish a fresh cleanup role sample.
Drained requires the same actual cleanup ticket in parent, quiet proof and
acknowledged sample; actual ready role/source state, no pending read, no remaining
actor observation/capture/world ownership, and original window/file replay.
A stale acknowledged cleanup sample stays watching and needs a later fresh
acquisition before this transition. Late final journal IO cannot publish current
drained state. An old baseline peer entry cannot stand in for cleanup. Reconstructing
an already-terminal record reopens original files and rejects unresolved scopes;
it supplies no new product observation or refreshed timestamps.

The actor exits successfully only after the actual fixture retirement described
below and this private terminal handoff. Its lifecycle,
role, source, failure records and original files deliberately remain owned for
whole-run retention. General Phone teardown now explicitly refuses green while
actor, failure or either role journal remains, even if base teardown succeeds.
Remaining complete-facade/whole-run finalization work is mandatory before Emote
capability registration. Device-free tests compose real Python/native packet
validators and credentialed loopback HTTP over explicit synthetic target producers;
View/Scene completion boundaries remain doubled in the Run fixture. They qualify
logic/orchestration only.


## Keep the caller's cleanup observation window alive

The common Engine invokes cleanup twice and then requires at least three fresh
primary/peer observations spanning three seconds. Therefore drained is not a
worker exit condition. While the actual fixture remains active the actor keeps
acquiring new original cleanup role samples and verifying their backend entries.
It reuses its historical quiet proof only as historical work evidence; no epoch
is refreshed and no new current/global work-absence verdict is inferred. The
whole-run finalizer still owes independent fresh native/work/resource checks.

Only an actual original phase packet with active=false, the same provider birth,
complete immutable activation history, and the same cleanup ticket can end the
worker. ProviderRetirement freezes that exact packet. The final actual role
sample must also prove inactive/idle animation, a closed panel and no resources;
old baseline entries cannot substitute for cleanup. A pending extra publication
at retirement is recorded as fixture-retired with its immutable original role
reference. This acknowledges no missing sample and performs no duplicate POST.
Retirement before an accepted cleanup entry and original quiet proof remains an
error. Reconstructing terminal ownership validates the original packet/files and
current retired authority without rewriting the old provider packet or epochs.

A read can be interrupted by the caller's actual DELETE/retirement. Existing
failure-owner/record v7 first retains that passive Source attempt, then its
resource-free cleanup Role attempt, through closed-cleanup failure archives v2.
All complete/partial original/index files and native prefixes remain unchanged;
no new source frame or successful role sequence is created. Only after durable
retention may pending be cleared. Normal active cleanup and normal image phase
retirement keep their existing gates and formats. Unknown/foreign retired
provider data, a missing last cleanup entry, ignored writes and unaccounted
scope/world metadata remain errors. No image/GPU lease can use the new narrow
closed Role format.

Version 1 actor controls remain readable. Their former retired state is
normalized to drained in memory, because v1 contains no provider-retirement
proof. Reconstruction alone does not rewrite the original. A later real
transition writes v2; it must observe actual fixture retirement before claiming
terminal handoff. Observer configuration stays v3, role/source controls and the
shared common journey contract remain unchanged. This corrects composition with
the real caller window; it supplies no complete Emote capability or device
qualification.
