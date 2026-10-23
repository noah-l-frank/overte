# Consumed private Chat cleanup baseline and archive join v1

`ChatCleanupBaseline` binds the exact fresh primary cleanup observation and
independent cleanup publisher to the unchanged common
`Journey.wait('cleanup-restored-baseline', ..., duration=3.0)` checker. It
requires independent clients, compiled-code owners and correctly paired source
locks/bindings. Expected baseline facts remain exclusively in the checker;
they never enter a source request or publisher payload.

Every iteration acquires a new actual actor publication, a separate primary
source bundle, and the original independently received journal endpoint. The
received current-ticket entries must match every corresponding original actor
payload exactly. A stale snapshot or POST ACK cannot substitute for received
actor facts. The common checker enforces resources, lifecycle continuity,
advancing cursors and its existing three-second/20-second/81-attempt bounds.
No bound is increased. Native/host freshness includes both roles, journal I/O,
copies and original lock-exit costs; a fresh phase response cannot retime older
native facts.

The root records `chatCleanupBaselineVersion`, `runId`, `fixtureUrl`,
`binding`, `peerBinding`, `primaryObservation`, `actorPublisher`, `sourceSeals`,
`phase`, `stage` and `chunks`, followed only on successful measurement by
`common` and `sealSha256`. Immutable chunks preserve each actual common sample
and its `primaryObservationSha256` and `actorPublicationSha256`. The original
native source/observation/publisher files remain separate. After the common
baseline, actor sealing completes under the actor's own locks; only then is
the primary sealed under the parent's locks. Different lock objects at the
same flock inode are never nested.

The final complete CAS, copies, physical receipt checks and final original
clocks must actually return before this warm owner is completed. Any unknown
failure quarantines both exact bound source seals, retaining every original
without requery, resend, adoption or retirement. An existing complete-looking
root is not a cold receipt. Historical `receipt()` verifies the actual received
warm result, unchanged root stamp, complete physical chunks and cached rows on
an isolated reader that cannot replace admitted identities. It performs no
old-PID native guard reentry or new target query.

Pico's private `measure_cleanup_baseline(independent_witness, after_epoch)`
works only after the original caches-retired stage, while the original process
and diagnostic peer channel remain live. It constructs the primary owner and
both seals from the fixed factories, releases the parent's actual locks before
the independent actor factory, and consumes the warm receipt before returning.
It does not restart, close IPC or finalize host descriptors.

`PicoChatArchivePlan.add_cleanup_baseline()` admits only this exact warm parent
graph and received receipt. It explicitly adds the common root/chunks, both
seal roots and every original observation/publisher/sample/compiled-code root
and chunk. Actual captured catalog root stamps and aggregate chunk stamps must
equal the previously received seal stamps. A same-byte replacement between
receipt and catalog capture is refused. The existing pre-stop directory
inventory still rejects every extra or unresolved file. No path discovery can
adopt a ready-looking source.

Two optional v4 archive metadata fields identify this additional trace:
`chatCleanupBaselineSha256` and `chatCleanupSourceSeals`. The Pico archive
reader requires a complete correctly typed pair with two distinct seal hashes
when either appears. Legacy v1-v4 archives without these fields retain their
original scope; no baseline/seal proof is invented or retroactively attached.
The generic cold archive reader verifies sealed bytes, not current target
state or semantic whole-feature acceptance. This packet does not upgrade the
earlier 860.797-second archive/host result or rerun a complete archive.

Focused validation:

- Three baseline cases passed in 76.556 seconds: actual common checker followed
  by both seals, stale receiver journal rejection, and frozen-host native jump
  after the final complete CAS.
- Full explicit catalog inclusion and the parent/actor factory lock boundary
  passed in 68.683 seconds. A follow-up removed a constructor-only guard reset
  from the projected fixture: fresh callbacks are now created directly.
- That corrected parent case, same-byte replacement after seal reception and
  the actual Pico orphan guard passed in 63.471 seconds. The independent lock
  check uses genuine different flock owners at the same original inodes.
- Actual Pico optional-metadata admission passed in 2.348 seconds, with its
  archive-byte verifier explicitly mocked for that narrow parser check.

Native/V8/widget/clock and consumed-input metadata producers are explicit
seams. Only baseline and first Open run ordinary controls in the compiled
fixture; it does not qualify the remaining 24 target effects. Pico parent/
adapter identity projection is explicit in the composition tests; actual Pico
factories have their separate owned Linux stdin-worker checks. No product app,
AC, network service, device, OpenXR runtime or full archive run occurs here.

Public operation/cold-RPC cursor/lifetime and actual stereo qualification remain
closed. This private checker is not evidence that the external common module
received its own final cleanup baseline. That module currently observes for
three seconds after its two cleanup calls and then closes the fixture. A
future explicit finalization join must preserve those fresh observations and
PID continuity, then finalize before fixture closure; neither PID forgiveness
nor a longer RPC deadline is supplied here.
