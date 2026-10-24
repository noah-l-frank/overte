# Fresh readonly Lifecycle triples (private source v3)

Source v3 separates actual observation acquisition from the mutating World
history. `World.current()` is acquire+append; `World.acquire()` is the existing
complete fresh UI/gesture/drive acquisition without append. No source contract
requires readonly polls to enter the World action journal. The original limits
are distinct: World128, actual new-PID Process.frames2…64, and existing original
containers512 parts/16MiB/64KiB per private file. There is no invented universal
128 across those independent histories. All physical acquisition totals are
still reported.

`LifecycleReadOnlyAcquisition` reuses the exact original `World.acquire`,
`originals`, `now` and freshness grammar, with actual separate readonly readers
for the same PID/instances/run and exact source lock. It has no state journal,
attempt array, save or input method. Reusing the mutating World's reader
objects would corrupt their `.previous` floors, so it is explicitly rejected.
The actual owner readers remain pinned to their last saved owner frame and
continue loading/acting normally after readonly samples.

`readonly_before_inputs` and the private
`_lifecycle_observation_readonly_begin` factory select v3 explicitly. The
registry reads1/2/3; existing v1/v2 entrypoints preserve their exact writers and
World-index semantics. No old journal is adopted, migrated or rewritten.

## Complete original admission

V3 retains its complete **new** World triple in the existing Primary bundles
before Pending/NativeFeature acquisition. The record has `worldBundle` and
`worldOwnerContinuity`; it has no fictional `worldFrameIndex`. The latter
metadata binds the actual old owner journal/frame as a continuity floor, not
as a current readonly sample. Current triples are joined against both that
actual owner floor and the prior literal readonly triple. Live readonly
cursors must match their complete stored literals before another query.
Unknown instance, generation, sequence/event prefix, PID, scope or original
bytes refuse. An originally returned foreign triple is retained before refusal.

The existing complete Pending readonly/owner joins, original CAS/FS guards,
actual call exit, native clocks and Host age checks remain. The readonly source
adds a conservative128 completed-sample bound; its512 physical parts,16MiB
physical and logical raw budgets, original file64KiB and all existing codec
limits remain unchanged. The owner World128 continues counting its actual
action/quiet acquisitions; no second mutating same-generation World is created.

## Actual integrated and counter evidence

Evidence directory:
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.
The four new cases passed **4/14.651s**, `lifecycle-readonly-v3.log`, full13479-file
source SHA
`07efefb1ecc81f481ab2ec9e070bcc1c8eb4f69fe6ebf45124951818149a1a19`
identical before/after:

- actual unchanged OverteSession/Journey.wait baseline/Back consumer and
  existing owner prefix: `lifecycle-editor-z3l5t02u`;
- foreign native generation, complete bad triple retained before any Pending
  or Feature query: `lifecycle-editor-lwyl1l8w`;
- landed final CAS plus Native+2000ms at fixed Host time refuses success:
  `lifecycle-editor-pxa5nzlo`;
- changed readonly cursor refuses before any next getter/send:
  `lifecycle-editor-nmtj3c1h`.

| Actual integrated stage | Mutating World frames |
| --- | ---: |
| Before baseline | 2 |
| After actual readonly baseline3 | 2 |
| After original first-four-action prefix | 19 |
| After actual readonly Back ≥3s wait | 19 |
| After original remaining Pending prefix | 85 |

There are17 distinct fresh readonly triples and results,68 physical parts,
84019 physical raw bytes and185042 logical original bytes. **85 owner triples
+17 readonly triples =102 actual physical triples**: the earlier102 total was
not reduced or relabeled. The new source retains honest ownership and separate
finite histories. The original owner reload succeeds with its exact last
cursor after all readonly queries. Diagnostic originals and counters remain
retained from construction.

Relevant unchanged v1/v2 cases passed **2/25.203s**,
`lifecycle-readonly-legacy.log`, the same full source SHA: legacy shared-reader
floor/advancement (`lifecycle-editor-ahku6teg`) and the original v2 Session/Back
World2→5→22→36→102 path (`lifecycle-editor-84vwemv_`). No Restore/Restart or Whole
was repeated. All native/Qt/OS/physics boundaries remain explicit model seams;
these results do not qualify devices, Actor, images or a complete common flow.

## Review delta and remaining work

Depends on `c824b48e3b292fa2c85727e16cd94338a96e0bde`. One existing registry
entry moves to3/reads1,2,3. Four disjoint new tests join the existing baseline
Pico wrapper (4→8), unchanged120s; one control-plane pattern is added. No new
selector or catalog-count change is required. A separate canonical new-factory
test remains open; the integrated test exercises the actual source class,
existing session contract, shared consumer and real owner/storage paths.

Public capability remains disabled. The next coordinator bill must preserve
all16 original actions, actual per-checkpoint primary/Actor advances and3s
windows, plus Restore and actual process replacement under their existing
separate caps. This source change is a new acquisition path, never permission
to erase prior originals, reuse old samples or omit required queries.

Final lightweight checks: shared discovery finds4 readonly cases and the
existing Pico baseline wrapper8, without duplicated inherited original cases.
Registry is coherent; Coverage10/0.038s maps14/14 risks. The repository suites
`documentation-contracts`, `project-coverage`, `documentation` and
`source-layout` passed in2.63s; `git diff --check` passed. No functional case was
repeated for these registration checks.
