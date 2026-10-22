# Phone Emote retirement coordinator, version 1

`PhoneEmoteRetirement` coordinates the completed-setup cleanup path through the
existing run, role, source, input, namespace, lifetime, View and Scene components.
It registers no public capability. Setup/admission abort retirement and the
public Emote facade still remain to be completed; Phone remains at 3/14 complete
areas. Native code is uncompiled and every device remains untested.

## Entry and actual observations

Construct with the real `PhoneEmoteRun`, its held source lock and the original
image policy. The run must have reached `resources-restored`. This path requires
the original baseline, both issued setup resources, both roles' original records,
the primary's completed quiet window and the actor's actual terminal lifecycle.
The actor must have published its own cleanup entry and observed actual fixture
retirement. Do not wait for that actor while holding the source lock.

`finalize()` first validates all original source/input namespaces, role records,
PNG/motion dependencies, failure-ledger entries, completed primary quiet records,
actor quiet/accepted-sample originals, normal cleanup inputs and optional original
background/foreground recovery. It uses the existing parsers and actual private
files. Missing mandatory components, changed candidate, active provider, foreign
controls or unresolved capture/observation/render ownership fail closed.

Scene, View and namespace retirement must transfer their exact originals to the
parent before removing their metadata. Every attempt also acquires new actual
closed Scene/View observations, including original pose/camera/zoom/preferences,
contacts, nodes, Browser drainage and unowned world preservation. The later
[final work observation](EMOTE_LIFETIME.md#final-actual-script-work-observation-version-1)
obtains another real source group and manager-thread work packet. Cached control
values, input ACKs and old completed proofs never become fresh measurements.

## Exact controller and retained records

`phone-emote-retirement.json` contains exactly `emoteRetirementVersion:1`, `runId`,
`fixtureUrl`, `artifactRoot`, `binding`, `imagePolicy`, `runHeader`, `payload`.
`runHeader` is the entire original resources-restored run control, permitting
recovery after its later removal. Actual current candidate/process/session
binding is checked independently. Payload is exactly one record containing
`phase`, `items`, `pending`, `attempts`, `verification`.

Phases are `collecting` and `retiring`. Each item is `{key,original}`, with the
existing compact inode/digest-bound original descriptor. At most 128 records are
retained. Keys are exactly the known `control/<filename>` inventory, `scene`,
`view`, `namespace`, `resources/N`, and `work/N/source|work|complete`, where N is
1..15. Resource records contain `{view,scene}` actual closed observation groups;
work records retain the exact corresponding final-work phase envelope.

The complete 62-name inventory includes all 16 possible input namespaces, both
roles' 16 source namespaces and the known run/resource/role/lifetime/actor/failure/
admission controls. Null snapshots mean original host-control absence only.
Required live components must separately validate; null supplies no native fact.
Unknown `phone-emote-*.json` controls are preserved and prevent success.

A pending record is exactly `{key,value,original}`. The original descriptor moves
planned -> opened -> saved before each corresponding filesystem action. Exact
frozen bytes remain in `value` until their immutable file completes. The existing
`RetirementOriginals(kind="retirement")` file engine enforces exclusive private
files, one link, actual inode, size/hash and canonical bytes. Interrupted writes
resume only the exact owned prefix; they never truncate, replace or invent a
completed observation. Source/input readers still reject this additional kind.
The existing 64 KiB control and 1 MiB original-file limits are unchanged.

## Partial retirement and fresh retry

The controller enters `retiring` only after all control snapshots, child transfers
and a completed actual final-work proof have durable references. Its verification
key names that original work completion. Only then may matching known controls
be removed. Each deletion requires exact original equality and actual subsequent
absence. An ignored delete cannot report success. Missing controls are accepted
only under this retained retirement authority or their exact completed child
transfer, never as an implied successful effect.

Retries can run after some or all child controls and the run control are gone.
Readonly archived contexts revalidate the original files and bindings through
the same component parsers. Actual metadata must still equal its frozen original
or be absent under the retained retiring controller. These contexts forbid normal
input, source/history writes and live public observations. Their only measurement
path uses the existing real closed-source/work readers; no fake metadata store,
expected native result, refreshed timestamp or resurrected input owner is used.
A finished coordinator rejects further measurements through its cached contexts.

Every retry retains a distinct attempt's resource and work originals. Historical
completions remain unchanged. A pending readonly acquisition can be archived and
retried; it cannot be promoted into the next fresh result. The whole call is
bounded to 60 seconds, each component/file operation retains its own bounds,
and final native/provider 1.5-second age floors include deletion and handoff IO
with independent monotonic elapsed-time floors. At most 15 attempts are admitted.

## Durable handoff and current verification scope

Before removing its own controller, the coordinator writes the private immutable
`emote-retirement-handoff-<run>-<attempt>.json` artifact. It contains exactly
`emoteRetirementHandoffVersion:1` and `retirementHeader`, the complete original
controller with every file/inode/hash reference and its last verification key.
This preserves the dependency graph after host-control removal. A failed final
controller removal leaves that controller owned; a later attempt retains its
own new handoff without overwriting the earlier artifact. The handoff's retained
`retiring` header is historical evidence, not a product verdict or proof that
its controller was actually removed. Success additionally requires actual absence
of every known control and the controller itself. General Appium cleanup refuses
any remaining retirement controller even when other journals are absent.

Host coordination cases use real source/role/work/failure parsers, actual private
files and the credentialed loopback fixture. They explicitly double the View/
Scene resource boundary; their native proof internals have separate real-reader
host tests. Cases cover ignored deletion, zero-byte opened originals, exact inode
resume, lost final removal after all child controls disappear, fresh native
reobservation on retry, missing actor authority, changed source files, foreign
controls, forbidden normal input and mixed closed Source/Role failure archives.
Two additional resource-join cases exercise the coordinator's actual View/Scene
call path with real typed native readers and private journals, retaining only an
explicit namespace boundary double. They check new originals on repeated calls
and an actual late retained Browser after a completed old release window.
These establish test logic only and do not qualify product behavior or devices.
