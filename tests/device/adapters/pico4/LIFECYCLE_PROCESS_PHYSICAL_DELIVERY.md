# Original Process file ownership at final delivery

The actual warm G1 handoff must keep the original Process journal identity,
not only its JSON value/hash. A same-bytes final-root replacement previously
passed `final_delivery()` after a real modeled Process retirement. The actual
counter was **RED1/5.432s**, source
`4863ea4dd3c0ac39eb427e356e14fc30c6b42ec24db5b21849d205dcf52b1180`,
`lifecycle-process-physical-red.log`, originals`lifecycle-world-0zgquoev`.
It expected refusal; the old adapter incorrectly returned success.

`LifecycleProcessFile` now holds the original private parent and file using
the existing `OriginalDescriptor` kernel/OFD primitive. Guards compare parent
node/mode/owner, exact current file/path identity, complete bytes and full
device/inode/mode/uid/link/size/mtime/ctime signature. The source's pathname and
descriptor objects cannot be silently replaced. `F_DUPFD_QUERY` distinguishes
a recycled descriptor of the same file from its original open description;
unknown ownership fails closed, never inode-only close or adoption.

Every own save preserves the existing canonical JSON/newline bytes and limits.
It opens and holds the **actual prepared candidate OFD before atomic replace**,
checks the previous original before publication, publishes relative to the
actual held directory FD, fsyncs file/directory and
advances the pin only to that exact candidate. The retired old owned OFDs close
only through their original kernel aliases. A lost publication keeps unknown
files/handles; it does not select a new pathname as authority. Normal held cost
is two FD pairs (directory/current file), with retired pairs closed on each
successful save. Uncertain pairs remain for actual host-process finalization.

The Process memo retains the same physical owner/file/stamp as its successful
save. `final_delivery()` checks them before external guards and again after
all reader guards, before its last original native/monotonic clocks. The
existing actual outer restart lock exit is inside that final delivery. There
are no new Native/UI queries or renewed sample timestamps. Wire versions1/2,
formats, encoders, state fields, old weak flags, native ABI and original bounds
remain unchanged. Cold file reading does not create a warm final-delivery memo.

`close_host()` closes only verified owned handles; it deletes no journal or
temporary and reports false for uncertain/recycled descriptors. This supplies
neither complete Lifecycle cleanup nor foreign-FD release. Canonical generic
cleanup admission also retains Process/restart roots and
`lifecycle-process-owner.json.pending-*` orphan responsibility independently
of the World root.

## Fresh evidence

Evidence directory:
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.
All actual host files and original inner exceptions are retained. Native/OS/
Qt/physics producers remain explicit models; filesystem and OFD operations
execute on the host. No client/device, ADB command or compiler ran.

- Same original counter after fix: **GREEN1/5.888s**,
  `lifecycle-process-physical-fixed.log`, source
  `aeb5cb43250d1394a20ed6a546f3fb6af1d1a1904cbe8226e55b4db6da1d82ae`,
  originals`lifecycle-world-covvc6f9`.
- Six disjoint owning cases: **GREEN6/11.434s**,
  `lifecycle-process-physical-owning.log`: real outer-exit replacement, final
  reader-guard replacement, exact own writer/old-handle retirement, same-bytes
  directory replacement, deterministically recycled same-file FD (foreign
  replacement stays open), and actual canonical orphan/root/input guard.
- Existing V1/V2 final-save/report/guard/outer-exit fences plus cold codec and
  actual connected/disconnected domain compatibility: **GREEN11/29.877s**,
  `lifecycle-process-physical-legacy.log`.

The latter two use the unchanged full source
`4af495ee21ca540f40799c16a27bd801f3c56ba79cd2ac3e6e68edfcb74f5448`.
The checkout also contains explicitly unfinished Ops3 source during those
narrow tests; that WIP is excluded from this physical-file commit. No Ops3
runtime or sixteen-action result is claimed from these checks.

After anchoring publication to the held directory FD, the actual root
replacement plus three direct writer/parent/recycled-FD cases passed
**GREEN4/5.790s**, `lifecycle-process-physical-directory-publish.log`, source
`f5bca853e6492708ef13581e8805766511712aad1049e9f86d793230bb8ee926`.
After that change, static coverage12, registry, discovery18, diff and all four
repository suites passed again (2.80s),
`lifecycle-process-physical-final-checks-directory.log`. There is no
sixteen-action repeat. The final edit only records these completed checks.

Seven additive cases join the existing `lifecycle-process-finalization`
selector:18 total with its existing11 cases, same120s. Two ControlPlane
patterns are added, no selector/risk-row count or registry/wire change. The
packet is separate from pending Ops3/G1 implementation and depends only on
the existing Process-v1/v2/finalization chain (current branch includes
`571192b9a8368b5f99621c70e6f53370b4836f39`). All broader public/Actor/image/
resource/file/archive/host-finalization boundaries remain open.
