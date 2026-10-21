# Bounded Phone Emote journal namespaces, version 1

The common runner requires at least three advancing samples per checkpoint and
up to 169 ordinary actions during bounded Sit discovery. A complete adapter
must not assume that one 1,024-source journal can hold that run, including inputs
and images. This host-only extension uses the existing source/input owners,
original file engine and source lock. It adds no execution backend, product
input, native capability or complete feature registration.

## Closed namespaces and retained responsibility

`PhoneEmoteSources(...,segment=N)` accepts exactly integer 0–15 (booleans fail).
Zero preserves `phone-emote-<role>-sources.json` and `phone-emote-inputs.json`.
Positive values use `phone-emote-<role>-sources-segment-N.json` and
`phone-emote-inputs-segment-N.json`. `PhoneEmoteInputs` derives its namespace
from its actual source owner. Role/run/candidate/process/artifact-root binding,
source v3 and input v2 packet shapes stay unchanged; the segment is host control
namespace, never a measured device result or public operation argument.

The existing per-journal limits remain 1,024 source records, 256 input records,
64 KiB active metadata and 1 MiB individual original files. At most sixteen
namespaces per role are admitted; this is finite additional retained run
history, not truncation or eviction within a journal. No previous metadata,
original source/input file or image is discarded, overwritten or archived away
when another namespace starts. Original files remain content-addressed with
actual inode/digest checks; reset logical indices cannot overwrite older facts.

The owning full coordinator must select namespaces under the existing lock,
retain the complete role-local archive/index, and freeze a predecessor once
its successor exists. It must not choose a namespace from a caller's requested
outcome, silently skip a hole or forget old responsibility. This coordinator
and authenticated actor namespace lease are still pending.

## Admission and actual continuity

A positive namespace requires the exact immediately preceding source journal
in that role. Its entire original archive is decoded with the actual binding;
it must be ready, nonempty, have no pending write, and its last original native
Rig must be inactive. Missing, foreign, active or interrupted predecessors fail
without creating a successor file. The complete previous metadata remains live.

The actual last frame restores configured-root, Script, native Rig/history and
widget cursors. New source groups must advance actual roots/native evaluation/
widget observations while retaining native birth, selected compiled source,
Script provenance, UI generation and immutable surviving history. Before and
after acquisition, the predecessor metadata, last immutable manifest and actual
last source file are reopened; cached memory cannot hide their deletion,
replacement or a changed predecessor header.

For primary input ownership, the first successor native read must still be
inactive and have exactly the predecessor's animation-call cursor. Even a new
override that already restored before observation is unowned activity and
fails before a new product input. The same check applies when reconstructing
an existing successor, preventing a faulty producer's stored transition from
being adopted. Actor reads instead may observe the primary's new calls after
its ordinary input; their own actual continuation and causality joins remain
mandatory. This does not permit forwarding primary measurements.

## Full owner and cleanup handoff

Rotate only at an independently measured inactive checkpoint, retaining the
previous complete observations through [archive transfer](EMOTE_OBSERVATION.md#complete-original-archive-transfer-version-1).
Normal primary/actor reads must use the parent's explicit current namespace;
an old actor must not continue appending to a frozen predecessor. First source
reads still acquire new facts and obey the existing five-second operation and
1.5-second delivery limits. No timestamp or expected value is substituted.

All namespaces remain unresolved host ownership until the complete owner has
validated their archives and established actual UI/input/native-work/fixture/
image retirement. General teardown rejects every source/input segment filename,
including unknown roles, indices or malformed namespace names. Successful base
teardown cannot turn remaining journals green. This mechanism supplies neither
quiet cleanup nor whole-run retirement; both remain required full-owner work.

Host cases cover three continuous namespaces, retained originals/metadata,
reconstruction, independent role boundaries, missing/active/skipped/invalid
predecessors, post-construction evidence loss, unowned original native calls,
faulty stored transitions, separate input history and incomplete general
cleanup. Native instrumentation is uncompiled; all devices remain unqualified.
