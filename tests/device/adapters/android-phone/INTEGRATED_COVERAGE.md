# Combined Android Phone coverage and focused repairs

Combined source `0a7de4299f4bb97e99c844288e6381efd973df0f` has a matching full
debug E2E APK, version code **15**, SHA-256
`43ed8f0ad7e9e5fe4beaa7c39833441f42979ff209181eaf00e4ec933df41248`.
Actual native compilation, native/resource/Probe/Dex provenance and installed
identity were verified. All **14 areas** have source composition inherited from
the [historical source/host scope](SOURCE_STATUS.md#historical-integration-and-host-evidence).
Those earlier scoped host results were not all rerun on the combined build.
Shared journey logic and Android Phone adapter source are present for every area.
Runtime capability availability and device acceptance remain separate observations.

The table below preserves the historical build 3 campaign scope. Later focused
repairs are recorded separately below; a resolved prerequisite does not change
an original result.

Jenkins **build 3 is RED: 7 PASS, 5 FAIL, 57 ERROR**, with no aggregate skips.
All 14 full feature journeys returned ERROR; only the Scripts mandatory gate
passed. No complete feature area receives device acceptance. This Phone result
qualifies no Pico, iOS or other client.

| Area | Shared logic / Phone adapter source | Mandatory gate | Full journey | Build 3 limitation |
| --- | --- | --- | --- | --- |
| Worlds / Navigation | Present / Present | ERROR | ERROR | Owned navigation directory and source-bound image policy missing; no native domain READY. |
| Authentication | Present / Present | ERROR | ERROR | Trusted HTTPS account owner/configuration missing. |
| Avatar / Contacts | Present / Present | ERROR | ERROR | Second independent ARM64 Phone with same APK and HTTPS account missing. |
| Create | Present / Present | ERROR | ERROR | Native permission/AC/picker configuration missing. |
| Emotes | Present / Present | ERROR | ERROR | Original image/adapter and domain/admission prerequisites missing. |
| World Web | Present / Present | ERROR | ERROR | No original gate/journey summaries or target logs; journey setup results missing. Source-bound image policy absent in preparation. |
| Tablet Web | Present / Present | ERROR | ERROR | No original gate/journey summaries or target logs; journey setup results missing. Active-container image policy absent in preparation. |
| Graphics | Present / Present | ERROR | ERROR | Original adapter/source-bound GPU image policy missing. |
| Audio | Present / Present | ERROR | ERROR | Original audio configuration and independent compatible PC voice peer missing; no native domain READY. |
| Chat | Present / Present | ERROR | ERROR | Source-matched independent chat receiver/AC missing. |
| Snapshots | Present / Present | ERROR | ERROR | Trusted HTTPS account/upload and original Snapshot policy missing. |
| Scripts | Present / Present | PASS | ERROR | Gate passed; original journey itself returned ERROR 75 after 5.905 s. Aggregate also records observer-required-forced-cleanup; no passing journey. |
| Assets | Present / Present | ERROR | ERROR | Source-matched native asset AC/worker and permission owner missing. |
| Lifecycle / Input | Present / Present | ERROR | ERROR | Original adapter/source-bound image policy and native domain prerequisites missing. |

The 49 retained target `module.log` digests establish only that the original
runner reached logging after `Popen.communicate`, including its timeout path.
The 65 original summaries preserve setup, target and infrastructure statuses.
Neither count establishes 69 device journeys. Four Web gate/journey targets
have no original summary or target-log proof. Nested setup failures and original
skips remain visible even when an aggregate observer error is reported.

The 37 preparation ERROR rows are separate from the 57 actual campaign ERROR
targets. The native domain never reached READY: an assignment client ended with
`std::bad_alloc`; its cause remains unknown. Missing geometry, HTTPS/account,
independent peer and native-worker inputs were not invented. Default-off source
flags and mandatory capability, source, freshness and cleanup gates remain strict.

See the [machine-readable matrix](integrated-coverage.v1.json),
[all 69 actual target statuses](integrated-campaign-results.v1.json),
[the exact preparation gaps](integrated-preparation-errors.v1.json),
[the failure and cleanup handoff](INTEGRATED_FAILURES.md), and
[the integration campaign provenance](INTEGRATED_CAMPAIGN.md).


## Focused repair state, 2026-10-24

All fourteen areas still have shared journey logic and Phone adapter source;
complete device acceptance remains **0/14**. Later focused evidence does not
qualify another client or replace the original campaign above.

- Tablet core: build 6 PASS, 204.195 seconds under its registered 300-second
  module budget. This is one core journey, not complete Tablet Web acceptance.
- Controlled Scene foundation: build 9 PASS, 64.132 seconds; six entities and
  one stable sample. Full Worlds / Navigation acceptance remains open.
- Native backend: the argument-lifetime source fix allowed the separately
  built, source-bound domain fixture to reach READY. Before/after ownership
  verification also passed in build 17. This resolves the earlier native
  preparation blocker, not the Phone connection failure.
- Single `domain-enter`: build 17 used harness `75ee0a49ec4b` with the unchanged
  installed client/APK above. Required launch passed (40.426 seconds); domain
  entry returned ERROR (130.727 seconds) after its outer 90-second adapter
  operation timed out. A normal Go HTTP click was acknowledged at 73.371 seconds
  into that operation; this does not prove that the button was activated. The
  address field remained present in the next actual lookup. The fresh
  post-error probe still showed a disconnected local-file scene, with no
  controlled-domain markers. No connection or feature PASS is claimed.

Future device runs select one independent target at a time, with only its
required setup. The current `domain-enter` failure must be fixed and confirmed
PASS before another independent target is started. Source-only counterexamples
and preparations do not constitute device acceptance.

Build 17 public summary SHA-256: `378a0c330854670db4e0778f0ed6bf5a85ecc6afee36c24dba94bde4924be17c`.
