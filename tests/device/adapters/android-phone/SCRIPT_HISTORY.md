# Durable original Script source history, version 1

`_script_durable_measurements(selector, run, fixture_url, role=...)` wraps the
existing joined reader with private cross-invocation provenance. Roles are the
closed `primary` and `actor` vocabulary, with separate private files. Both use
existing-session/read-only admission. The actor role is an independent source
reader prerequisite; this factory has no publisher secret and does not itself
implement the independently running publisher.

The exact versioned envelope contains `schemaVersion:1`,
`sourceKind:"phone-script-history"`, original `binding`, `runId`, `role`,
`directory`, `fixtureUrl`, `phase`, `revision` and `transcript`. Binding retains
the existing original APK digest/revision, PID/start time, SDK session,
generation and target fingerprint. Typed equality matters: a JSON boolean
cannot replace a numeric generation/version. Foreign targets, processes, roles,
runs, directories and fixture origins are refused without adoption or reset.

The transcript contains only original metadata acquired by the execution, UI,
independent Script service and lifecycle sources. Each frame retains its actual
request IDs, sequences, native births, original acquisition clocks, ticket and
barrier. No desired verb, expected state, cached verdict, media, credential or
publisher token is stored. The result returned to the caller remains the live
joined measurement; historical frames are never returned as fresh evidence.

On reconstruction, pure validators replay original frames with their original
clocks. They invoke no transport callbacks or product inputs. Script execution
uses the same pure transition as its live reader, retaining retired engine and
manager identities, immutable submitted code/module/load prefixes and effect
absence. UI birth/generation/cursors/elapsed/input sequence, service birth/cursor,
original lifecycle counters and optional native voice/animation/account prefixes
are restored too. Invalid replay leaves execution-reader restoration atomic.
The next acquisition still needs four new original requests and advancing source
cursors; stored history cannot rescue an ignored or missing current result.

Factory admission and each whole acquisition use the same stable private
`phone-script-sources.lock` inode for both roles. POSIX nonblocking `flock`
excludes other processes, with a five-second host wait inside the reader's
20-second whole-call budget. A blocked acquisition sends no source request and
writes no pending intent. Mode/owner/type/link/inode checks reject unsafe locks;
exception/process death releases OS ownership. The lock file is never unlinked.
The full coordinator must use this same lock for its normal inputs, restart and
cleanup; this reader alone cannot serialize those not-yet-composed operations.

Before any new source request, one existing `PrivateFeatureState` CAS records
`phase:"reading"` and advances the revision. Only a wholly successful fresh join
and persisted original transcript can return to `ready`. Whole acquisition,
including guards, compression and private writes, is limited to 20 seconds;
individual getter/runner limits remain in effect. Rewound original source or
host acquisition clocks fail. Failures preserve existing input/file responsibility.
A pending acquisition blocks the same object and all reconstructed objects; it
cannot be cleared or retried into a green run. Independent cleanup must inspect
fresh sources and retain this unresolved record until complete cleanup is proved.

A lost final persistence return may have left a complete `ready` transcript.
That call still fails. A reconstructed object can validate that exact committed
prefix and perform a separate fresh read. It neither repeats product input nor
relabels the stored result current. Stale objects cannot overwrite a later
invocation's transcript. General Phone cleanup still runs base teardown, then
refuses success while either history remains; process stop is no history cleanup.
There is deliberately no unconditional discard/reset method.

Storage keeps the existing private-parent, mode-0600, no-symlink, single-link,
atomic replace and **64 KiB file cap** unchanged. Canonical JSON metadata is
compressed as zlib/base64 with original uncompressed length and SHA-256. Limits
are 512 complete frames, 16 MiB decoded metadata and 48 KiB encoded payload.
Capacity exhaustion fails; old frames are never truncated. Decode rejects
oversized output, bombs, trailing/concatenated/truncated streams, altered digests,
noncanonical base64/JSON, duplicate keys, nonfinite numbers and unknown fields.
Raw paths and IDs remain private and must never enter public artifacts.

The existing mandatory Phone runtime owner registers `test_script_history.py`
in both modes. Thirty-four host-only cases exercise fresh reconstruction,
ignored/partial sources, retained retired identities/absence, rewritten modules/
callbacks, original clock/cursor/birth/generation rollback, role separation,
foreign bindings, stale objects, lost/failed private writes, full deadlines and
bounded decode/capacity, private source locking, cross-process exclusion and
unsafe/replaced lock rejection. Four Phone factory cases check actual binding and general
cleanup refusal. Boundaries are synthetic; no native compilation or devices run.

The full nineteen-step coordinator still needs baseline before staging, explicit
restart history handoff, frozen action/load barriers, original HTTP404 join,
serialized independent publisher acquisition and complete verified cleanup.
This component requires already staged fixtures and a single original process;
it never implicitly accepts a new restart birth or deletes the old transcript.
No complete `feature.scripts.*` capability or device acceptance is promoted.
