# Original V8 Script compilation identities, version 1

This E2E-only extension observes actual V8 compilation at the application's
`ScriptEngineV8::evaluate(QString,...)` and `ScriptProgramV8Wrapper::compile`
entry points. It addresses an actual Phone startup prerequisite: the normal
`scripts/+android_phoneInterface/defaultScripts.js` evaluates `phoneEmote.js`
with `Script.include`, so Emote has no separate top-level ScriptManager.

The existing top-level submitted-code identity remains unchanged and cannot
stand in for included code. No default script is moved to another manager,
stopped, replaced or reconfigured. No animation, timer, input or functional
product behavior is changed. Native additions remain uncompiled.

## Native provenance and limits

Immediately after a successful actual V8 Compile and before Run, the hook reads
the original V8 UnboundScript ID and original compiled resource name. It copies
the actual V8 source string's UTF-16 code units and computes their little-endian
SHA256 under the manager's existing native observation owner. This records what
V8 received after the existing UTF-8 conversion; requested text, a disk reread,
pre-conversion QString or guessed include URL cannot replace those bytes.

Script IDs are scoped to the actual manager/isolate, not globally unique across
clients or managers. Separate same-name compilations retain separate IDs and
actual code hashes. A repeated cached original ID with identical name/code keeps
its first original timestamp. Reuse with different name/code invalidates the
inventory. Records never evict or retime older entries. A wrong owner thread,
invalid source/name, backwards compilation clock or more than 256 original IDs
makes completeness explicitly false. Metadata retains no V8/Script/QObject
strong reference and does not prevent normal code/resource collection.

The hooks are guarded by `OVERTE_E2E_FEATURE_TESTS` and active `--testScript`.
They do not add a command or setter. They reuse `feature-script-observe` and its
actual main-native birth/PID, request/sequence/time/size/privacy checks.

Compilation is **not** execution or call provenance. Syntax-only compilation may
appear here. These two hooks do not enumerate V8's internal eval/Function or
native prototype compilations. `complete` means no lost records at these
instrumented entry points, not a complete JS heap or code-security attestation.
Actual native caller/function-origin and selected timer/callback observation
must independently join an original Script ID before included code can qualify
Emote effects or cleanup. Unknown/unobserved origins must remain unavailable.

## Exact wire extension

The original Script observation source gains `compiledSourceVersion:1`. When
present, every original public engine row additionally has exactly `compiled`.
Its complete value is:

```json
{"compiledSourcesVersion":1,"complete":true,"compilations":[]}
```

An incomplete value has exactly `compiledSourcesVersion:1, complete:false` and
no truncated compilation list. Complete lists have at most 256 rows, sorted by
strictly increasing `scriptId`. Each row has exactly:

| Field | Original source and bound |
| --- | --- |
| `scriptId` | Original positive V8 ID, at most 2,147,483,647 |
| `resourceName` | Original V8 name, 0–4,096 characters, no control characters |
| `encoding` | `utf-16le-code-units` |
| `codeUnits` | Actual V8 source length, 0–4,194,304 |
| `sha256` | Actual UTF-16LE digest; empty code has the actual empty digest |
| `compiledEpochMs` | Original positive native compilation clock, no later than packet capture |

Empty code and an empty original name remain observable; they do not identify
an Emote implementation. A filename hash or matching resource name is not enough.
Manager assignment/top-level code, actual configured root, compiled source ID/
bytes and actual caller/function source must remain distinct observations.

## Reader and historical compatibility

`native_script_compilations.validate` accepts only the exact complete/incomplete
schema. `accept` requires completeness, independently validates each row and
requires every old ID/name/hash/size/time to remain unchanged. Added original
IDs are permitted; missing, relabelled, reordered, duplicate or retimed records
fail. Script ID namespaces stay independent across actual manager instances.

The original `NativeScriptObservation` parses this optional extension without
changing legacy packet structure. Once observed in a reader, the extension is
mandatory even for a later empty engine inventory. Per-manager original rows
remain immutable through normal live reads and historical replay. Incomplete
inventories cannot advance source provenance. Replay restores the downgrade
guard without a native query or refreshed timestamp. Legacy source packets remain
readable, but cannot supply the newly required included-code facts.

The existing 256 KiB Script response and private file bounds remain unchanged;
oversized/partial evidence fails. This extends native provenance only. Pico
selects this shared observation and its reader from the pinned Phone commit;
it does not yet select Phone's Emote caller/work/role/input bindings. Those
joins, actual Pico entrypoint/normal VR input, stereo avatar images, independent
actor and whole-run cleanup remain required. Complete Pico areas remain three
of fourteen. See [Pico reuse provenance](../adapters/pico4/EMOTE_SHARED_REUSE.md).
Host tests use synthetic packets and inspect guarded native hook placement;
they do not compile V8/native code or establish product/device success.
