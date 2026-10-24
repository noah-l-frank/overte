# Rooted Emote terminal persistence and read-only replay

The explicit internal `IOSEmoteRuntime._emote_rooted_feature` factory selects
coordinator version two. `_emote_rooted_terminal` binds its actual Primary and
Actor flows to `IOSEmoteTerminal`. The existing configuration and ordinary
`_emote_feature` factory retain their version-one behavior. Complete Emote
capability admission remains closed; no public terminal dispatch is admitted.

The default terminal factory reopens the actual version-two Actor feature
metadata under Actor -> Primary locking. It preserves that Actor's separate
artifact root and image policy rather than deriving either from Primary
settings. Missing, foreign-run/role/fixture, legacy or malformed metadata and
shared role roots prevent construction. It creates no SDK or replacement
owner. Construction under an existing Primary lease is rejected before an
Actor lock is acquired. Explicit paired owners retain the same distinct-root
and actual shared-Primary-lock requirements.

The internal controller accepts the shared version-one terminal arguments.
Inspect and seal retain the unchanged thirty-second whole-call limit. It
acquires the Actor source lock and then the same actual Primary lock object.
Both current flows must have cleaned and retain their role-specific scene
retirement. Current Scope, Source, Peer, Sample, Observer, file, entity, pointer
and Primary input metadata must match the selected cleanup originals. The
latest current five-component snapshot must match the actual last live record.
Unresolved local acquisition or changed component responsibility prevents
inspection. The additional
[current recovery/scene/publication guard](EMOTE_ROOTED_RESPONSIBILITY.md)
now checks the named interrupted-read histories, rooted scene ordering and
Actor publisher originals before journal persistence. The
[paired carrier inventory and current GPU join](EMOTE_ROOTED_INVENTORY.md)
now cover actual read membership and reject unknown responsibility before any
terminal journal write. Final frozen ownership archival remains required.

`IOSEmoteTerminalJournal` persists inspect references and the derived
[window description](EMOTE_TERMINAL_WINDOW.md) in the Primary SDK directory:
`ios-emote-primary-<run>-terminal.json`. Before file creation it stages the exact
qualified proof in private CAS metadata. The existing `OriginalFrameStore`
then retains one inode-bound proof in the artifact root, using the
`emote-terminal` input namespace and `iosEmoteTerminalProof` header. No limits
are enlarged. Metadata/Frame/Original versions are registered separately as
version one. The operation clock is checked at every persistence guard,
including after pure qualification and before creating an original.

Recovery before any file intent can save the exact staged proof. After a
recorded opened/saved birth it can adopt only the same fully written file,
with its original device, inode, length, hash and header. A planned-only birth
or an incomplete opened file retains responsibility and is never recreated.
Loss of a metadata commit return poisons that writer and requires a new owner.
Every public seal return, including a repeat, requalifies the retained proof
against the actual original role graphs and Actor HTTP publications. File-only
recovery alone supplies no public feature verdict and sends no input.

`IOSEmoteTerminalReplay` checks the actual sealed metadata and proof file, then
reopens both stored role journals with their actual source locks. It rederives
the complete paired window and independent Actor publication join. It has no
runtime, SDK, native reader, clock renewal or input method. Merely matching a
stored digest cannot establish a native fact.

Finish currently raises `EmoteObservationPending` before opening a live
component. Whole current-WAL/recovery/scene-order archival, exactly one normal
Stop per role, independent OS absence for at least three seconds, separate
SDK DELETE/GET-404 owners and canonical/worker end recovery remain required.
The original terminal journal is not itself process-death authority.

## Host evidence and limits

The full three-pair window integration passed in 1453.631 seconds with all
2688 captured source files unchanged. Both original roots were retained at
construction and contain 1439 files. This exercises the actual Python, normal
JS/W3C, source files, PNG, independent UDP peer and loopback HTTP paths. It does
not exercise this new controller or the complete Emote journey.

On the previous complete three-pair originals, persistence plus injected loss
of the actual saved-file return passed in 129.186 seconds. Reconstruction
adopted the same file inode and fully requalified the original proof. All 1439
prior files retained their exact identities and bytes; exactly two owned
terminal outputs were added. Subsequent SDK-free replay and five invalid
metadata/file-identity cases passed in 88.615 seconds, leaving all 1441 files
unchanged. The private window proof measured 22240 bytes before adding the
seal and frame envelopes.

The new local-component join passed for both roles in 227.871 seconds over the
same actual current metadata/originals, without modifying those 1441 files.
Its SDK/candidate guards and component factories were explicit models. This
duration fails the controller's unchanged thirty-second whole-call bound and
does not qualify the operation. Further performance work remains necessary.

Fast tests use real source locks, private files and CAS, with modeled paired
measurements and SDK boundaries. They cover file-return/metadata-return loss,
incomplete and unknown births, forbidden replay, phase/context/file-identity
rejection and deadline expiry before inspection or seal persistence. They do
not replace the actual-original tests above. Native, SDK, Qt, GPU and acquisition
clocks in the connected tests are models. Native compilation and devices remain
unexecuted; Emotes remains partial.

After integration, all fifteen targeted no-build controller/journal tests pass
in 0.446 seconds. The five project suites pass in 6.83 seconds; contract-version
and whitespace checks pass. No build, compiler, device, simulator, installation
or laboratory operation ran.

After correcting the default Actor-root selection, eighteen targeted host
cases pass in 0.555 seconds, including distinct stored roots/policies,
missing/foreign metadata and rejection before reversed lock acquisition.
