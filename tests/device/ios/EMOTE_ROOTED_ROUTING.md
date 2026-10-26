# Explicit rooted Emote routing

Current readiness work and remaining actual-source blockers are recorded in
[the source handoff](EMOTE_REMAINING_SOURCE.md). Complete admission remains closed.

The installed adapter reads configuration versions 1 through 6. Version 6 adds
the exact `emoteCoordinatorVersion` field: integer `2` when `emotes` is selected,
otherwise `null`. Versions 1 through 5 keep their literal previous field sets.
Emote settings retain the explicit Primary artifact/image policy and Actor
target. Version 6 selects the rooted role coordinator for action, observation,
cleanup and terminal operations. Older configurations retain their old reader.
The complete Emote capability remains closed.

The terminal entry owns one 30-second operation budget, including controller
construction, durable pending retries, polling and final verification. Pending
finish polls occur outside both source locks and continue the same issued
process/SDK owners. A failed or backward deadline cannot be renewed by a retry.
Inspect and seal do not consume a pending result as successful end readiness.

Canonical post-finish verification requires a physically present complete typed
end journal. It then reopens the actual paired role, source, native, image,
inactive phase, process, OS, SDK and metadata CAS graph. Both current candidate
and target scopes must still match. A public result, bare complete marker or
partial end journal is insufficient. Replaying a complete end recreates neither
SDK and sends no normal input.

Canonical session cleanup detects rooted responsibility before legacy cleanup
or ordinary SDK teardown. Only explicit rooted configuration, one owned run and
its complete typed end allow cleanup to report success. A bounded passive
bootstrap reads the exact retained Primary feature configuration from actual
archive copies under both existing source locks and unchanged inventories.
Configuration copies authorize no process or resource absence. The separate
complete verifier must still qualify every original. Missing locks, changed
copies, changed configured root/policy and unfinished rooted ownership fail
closed. Ordinary unfinished ownership cannot fall through to a generic DELETE.

The independent worker reads literal configuration versions 1 and 2. Version 2
additionally requires `primaryArtifactRoot` and `primaryImagePolicy`, distinct
from its own root. It explicitly selects the rooted Actor. An actual sealed
control journal pauses further live publication; an inactive fixture alone
does not finish the worker. Only full historical replay of the paired complete
typed end permits successful exit. Existing durable failure evidence remains a
failure after eventual cleanup. Version 1 keeps its previous shape and path.

The focused no-build selection passes 55 cases: 22 new routing, worker,
scheduling, deadline and retained-configuration cases, plus 33 existing
admission, configuration, API, worker and controller regressions. The first
38-case selection completed in 1.600 seconds; the separate 17-case bootstrap
and controller selection completed in 0.374 seconds. Routing authorization and
end readiness are explicitly modeled in their focused scheduling cases; archive
bootstrap creation uses an explicitly modeled effect qualifier. These tests do
not qualify the models, the full common journey or device/native execution.

`emote_common_journey_fixture.py` drives the unchanged common `Journey` and its
28 Emote rows over fresh pinned JS callbacks, normal W3C/token input, independent
UDP/HTTP publication and PNG originals. It supplies only declared native, WDA,
OS and candidate-preflight producers. Typed terminal authorization and canonical
installed-source Stop gates remain actual. The full scenario, its timing and
end must pass before complete area admission can be enabled. A bounded profiling
attempt or a passing Waving-only path is not that qualification.
