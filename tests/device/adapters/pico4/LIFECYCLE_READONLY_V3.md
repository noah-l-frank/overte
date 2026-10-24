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
adds a conservative128 completed-sample bound; its512 child parts,16MiB
unpacked-container and logical raw budgets, original file64KiB and all existing codec
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
84019 unpacked container bytes and185042 logical original bytes. **85 owner triples
+17 readonly triples =102 actual physical triples**: the earlier102 total was
not reduced or relabeled. The new source retains honest ownership and separate
finite histories. The original owner reload succeeds with its exact last
cursor after all readonly queries. Diagnostic originals and counters remain
retained from construction.

Byte-accounting clarification: `ChatSourceChunks.raw_bytes` is the unpacked
transcript-container budget, not the sum of stored JSON files. A subsequent
read-only measurement of the unchanged `lifecycle-editor-z3l5t02u` originals
finds **119,083 actual stored bytes in 69 files**, including the manifest root
and all 68 children. The original 84,019 container bytes and 185,042 logical
original bytes remain different quantities. Detailed sizes are retained in
`lifecycle-historical-stored-file-sizes.json`; no original was rewritten or
observed again. New diagnostics name all three byte quantities explicitly.
The 512-child, 16 MiB container/logical-raw and 64 KiB individual-file limits
remain unchanged; an aggregate stored-byte measurement does not create a new
protocol budget.

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
selector or catalog-count change is required. The subsequent canonical factory
test below closes the previously explicit factory-runtime gap; it does not
close the independent Actor, image or full-operation gaps.

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

## Canonical factory runtime evidence

`test_lifecycle_readonly_factory.LifecycleReadOnlyFactoryTests` executes the
actual private `_lifecycle_observation_readonly_begin` in the canonical Pico
namespace. It uses the existing Restore/BeforeInputs fixture at its original
pre-Create boundary. The original factory, source-lock/path checks and fixed
app-file transports execute. Native Qt/physics/process and ADB app-file I/O
remain explicitly modeled; no device is accessed. The factory performs no
Script inventory query, input or native observation during construction.

The positive then makes one real Source3 `read`: separate gesture, drive and
UI readers acquire new originals, followed by Pending and NativeFeature.
The same World remains at two frames, its saved cursors and journal unchanged;
the readonly source retains one sample and its complete originals. An actual
World reload still succeeds. The second case supplies a foreign process
identity to the same canonical factory and proves refusal before any source
query or input.

Both cases passed **2/0.371 s**, `lifecycle-readonly-factory.log`, under full
13481-file source SHA
`76f57744b67b7f788ff7610622a72b12b3d0ec792d2e3092a68d30edc3482f78`,
identical before/after. Their retained roots are `tmpe307wtpt` and `tmpycshkbnu`
in the evidence directory above. The initial run, recorded separately in
`lifecycle-readonly-factory-order-red.log`, failed after 0.242 s solely because
the test predicted UI before gesture/drive. The assertion now follows the
unchanged actual acquisition order; no runtime method or source was changed.

The two cases join the existing `lifecycle-primary-baseline` wrapper (8 to 10
cases), keeping its existing 120 s limit and selector. There is no new registry
contract, capability, selector or catalog-count entry. The full-operation
composition plan is [documented separately](LIFECYCLE_COORDINATOR_PLAN.md).


## Root integrated verification

Root selects9ed04d33ea/642be960ed/1bf4c371a6 as89800250e3/ece5c43769/
dee08ce63d. Existing baseline10 cases39.318s, legacy observation7/51.815s
and coverage10/0.091s pass91.22s. All13,545 source hashes match before/after.
The actual canonical factory and foreign-process refusal run in this selection.

Actual integrated bill:85 owner triples+17 readonly triples=102,68 child
parts/69 files including root,84,003 uncompressed transcript-container bytes,
185,008 logical original bytes and119,101 actual stored JSON bytes. These
three byte quantities are distinct and stay reported separately. Original
World128, successorProcess2..64, readonly128 and container512child/16MiBraw/
64KiBfile limits retain their actual individual scopes. Whole16-action, Actor,
images, new-process cleanup source handoff and final file/resource/Host closure
remain unqualified.
