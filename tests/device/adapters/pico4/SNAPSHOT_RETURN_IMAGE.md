# Original Pico Snapshot return image

The private `_snapshot_return_image` factory composes the completed original
Snapshot background parent with the existing `OwnedWorldRenderCapture`, original
stereo/used-camera reader, `GraphicsOriginals` PNG writer and actual complete
memory/receipt retirement. It does not add a render channel or product control.
The exact parent source-lock instance is retained. The existing shared Graphics
role capture owners are already excluded by other Pico render publishers; no
Snapshot-specific owner can silently overlap that original fixed source channel.

The background parent, its immutable Upload/Save/Cancel ancestors, original
process/candidate and actual native lifecycle return remain bound throughout.
Cold construction reads only host originals. OS foreground is checked before
constructing a live capture reader. A fresh Snapshot/VM/UI/file/account/backend
frame precedes acquisition, and its durable child intent precedes the actual
native render query. An exact independent phase fence follows that CAS. The
original reader then requires a new actual submitted stereo frame and original
used-camera uniforms. It reads the original PNG from native storage and validates
both eyes. No callback ACK, requested pixel value, half-width Snapshot still,
Phone mono source or uploaded backend PNG supplies those pixels.

Fresh Snapshot/lifecycle bookends after acquisition bind the same current
process, context, capture history, files, account and backend mutation scope.
Native render timestamps lie between those original frames. The complete PNG is
written exclusively to the existing private host artifact directory, with
planned/opened/saved intents and original file identity. The Snapshot record also
pins the complete device/inode/mode/UID/GID/link/size/mtime/ctime stamp of the
saved host PNG. Own header, strict JSON graph and physical PNG signatures are
checked again after the final native callback, so a late mutation cannot escape
through an otherwise fresh clock seal. The shared original
retirement performs actual memory release followed by independent zero-memory
inspection, complete native receipt removal and a separate actual absence query.
Only then may it discard the temporary shared capture owner. The Snapshot image,
its original proof and all enclosing Snapshot journals remain owned.

A lost/unknown acquisition cannot be resent after cold reconstruction. A saved
original may finish its own retirement. An uncertain release/remove does not
become permission to repeat that mutation; the common retirement helper permits
only its proven read-only continuation. An ignored release, remaining callback,
missing receipt or replaced host image leaves original ownership unresolved.
Cold validation rechecks the original PNG, strict stereo/camera grammar,
Snapshot bookends and complete request-bound retirement proof.

The selected dependency is the unchanged shared
`original_stereo_retirement.py` from fixed root
`71faaacaa40a351a1387d0cd7fe979af939fb470`. The local dependency-only commit
`d6676f4799` must not be selected back into root. The world-render, storage,
receipt, GraphicsOriginals and proof-validator files were byte-identical to
fixed root `f023b2d681a1c3581baae5be5a7f860e0e7324cc` during review. The
Snapshot factory uses the existing generic role-scoped factory unchanged.

## Qualification boundary

`originalStereoReturnPng` means newly acquired original two-eye bytes after the
proven return, together with actual temporary capture retirement. It does not
mean the Snapshot scene challenge/marker, panorama/cubemap fidelity, independent
actor role, final Close, complete settings restoration, backend story removal or
global Export executor retirement are qualified. `sceneChallengeVerified`,
`fullSnapshotRecipe` and `deviceAcceptance` remain false. A completed cold record
is historical evidence and never a new screenshot or fresh product observation.
The separate TLS reader can reacquire the original uploaded PNG after return;
that is backend preservation and is not substituted here for VR return pixels.

The disjoint `snapshot-return-image` and `snapshot-return-fences` selections use
real private PNG/receipt files and the original shared native protocols. GPU,
rendering, Android/native source producers and virtual device time are explicit
host seams. The retained normal background parent fixture has the provenance
and limitations in [the background guide](SNAPSHOT_BACKGROUND_OWNER.md). The
actual private Pico factory is exercised with the original shared transport
options and lock. The tests cover normal capture/retirement, unchanged parent,
passive cold reads, duplicated eye descriptors, foreign Snapshot generation,
foreign retirement request, same-byte host inode replacement, lost acquisition,
ignored release and a phase change after durable intent but before the native
query. No renderer, compiler, headset, service or physical input is run here.

## Verification

The final disjoint selection passed all 6 component cases under unchanged 120 s
per-group limits: `snapshot-return-image` 43.766 s (3 cases),
`snapshot-return-fences` 51.296 s (3 cases), coverage 0.060 s, total 95.122 s.
The first added foreign-generation counterexample used the wrong exception
expectation: the existing navigation validator already rejected it. Its exact
`NavigationError` expectation was corrected; source rejection was unchanged.
A later self-review added the final own-header/graph/PNG stamps and their late
callback counterexamples before the final passing selection.

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<owned-private-tmp> python3 \
  android/vr/pico/tests/pico4-test-suite.py \
  --test snapshot-return-image --test snapshot-return-fences \
  --test coverage-matrix --junit <owned-private-report>
```

The newer fixed Phone reference
`3fa8031aa6787af909c6a1701c21536d584c392b`,
`overte_phone_snapshots_constructor_history.py`, was reviewed as an original
admission/bookend design. This owner retains its existing explicit Pico source
lock, strict JSON and physical originals. It does not copy the Phone passive
scope, SDK authority, touch transport, history-pass optimization or facade.
