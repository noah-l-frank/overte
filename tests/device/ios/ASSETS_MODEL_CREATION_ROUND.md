# Assets synchronous original Model dataflow checkpoint

This is not a completed Assets feature or a performance qualification. The
complete capability stays closed, source-complete count 5/14 is unchanged,
native compilation and devices remain untested, and normal removal/image/
Actor/resource/shared-end obligations remain open.

The measured retained graph re-entered Upload decoding for each historical
Parsed frame. The new private path fully reopens the actual Model input
sources and decodes the actual Model once within one `ParsedSources.decode`.
Only that immediate typed creation result is passed to the internal frame
predicate. Raw/logical source parsing and joins still execute for every frame.
No value survives the decoder, a query, CAS or write boundary.

Every use and exit checks current original-reader candidate callbacks, exact
parent WALs/memory, parser/method plus code identities and private directory
dev/inode/mode/uid/link/size/mtime/ctime prefixes. Directory pins protect
consistency; they do not add file membership or prove unseen contents.
Model/Usage/Upload headers and the actual source inputs remain independently
validated. Direct public frame calls and custom frame/Model/parser hooks use
the full public path; incomplete historical contexts and legitimately dirty
in-flight parent state retain that literal path too. A closed round cannot
be reused, and no resource/candidate/clock verdict is cached.

Exact private logs:

- `assets-model-creation-round-positive-first-20261027.log`: PASS1/39.246s
  including original QML/declared native/backend preparation. One full source
  decode invokes the actual Model decoder once; direct public frames still
  perform their full Model validation. Pure assertions forbid state writes
  and retain identical native/input/HTTP command lists.
- `assets-model-creation-round-negative-five-first-20261027.log`:
  PASS5/39.654s. Actual parent file/WAL corruption, memory/parser/frame-hook
  changes and current candidate loss refuse reuse; custom public/private
  hooks retain full validation. Closed rounds and missing/dirty historical
  contexts do not authorize reuse. No query or mutable state write is made
  by the pure assertions.
- `assets-model-creation-round-profile-first-20261027.log`: the first readonly
  diagnostic reconstruction omitted the Model store that the historical
  generic inspector intentionally does not construct. Its optimized arm
  failed with AttributeError before reads. This was corrected only in the
  private harness by explicitly binding the known existing canonical Model
  WAL, not by changing a product/adapter guard or any original.
- `assets-model-creation-round-profile-bound-model-20261027.log`: both exact
  readonly decoders succeed. All 257 private original bytes/dev/inodes/sizes/
  hashes remain identical and forbidden SDK/input/network/write/Popen calls
  remain zero. The local round reduces Upload reads 300→75 and additionally
  reopens actual Model inputs: 26 raw and two logical records. However the guarded local path
  takes 0.573s versus 0.392s for the public full-frame hook path. These are
  diagnostic instrumented timings, not live checkpoint qualification. The
  additional consistency work outweighs the saved reads in this sample;
  there is no demonstrated CPU improvement or basis for a new full removal
  run. Do not remove guards or extend limits to hide this result.
- `assets-model-creation-round-parsed-old-four-20261027.log`: PASS4/84.980s.
  The existing actual body/backend/Model join and generic historical inventory,
  saved logical-original adoption, opened raw-prefix ownership and distinct
  future source bracket after a lost read remain valid. No unchanged full
  removal run was repeated.

The original removal prerequisite's 120s timeout and 257 original files remain
preserved as documented in
[the removal-image handoff](ASSETS_IMAGE_REMOVAL_WIP_RESUME_20261027.md).
The next measurement must isolate memory/directory guard costs and choose a
bounded local dataflow change without weakening the current callbacks,
immutable bytes/inodes, parser identities or parent prefixes. No unchanged
full-flow rerun is authorized by the results above.
