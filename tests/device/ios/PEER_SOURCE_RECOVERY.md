# Interrupted original peer reads

`adapters.original_avatar_peer_recovery.OriginalAvatarPeerRecovery` owns partial
passive acquisitions from the configured `OriginalAvatarPeerSources`. Its
Emote actor and Avatar primary/actor profiles keep their existing source wire
fields, native DTOs, original archive filenames and clocks unchanged.

Call `recover()` before starting another read and `follow(frame)` after the
new completed original is retained. Recovery archives the interrupted raw owner
and every actually opened original file identity, byte count and hash, including
honestly empty or partial files. It clears only pending acquisition ownership
through the normal source CAS. It sends no SDK/HTTP/native request, normal input,
file deletion or duplicate image acquisition. Lost metadata returns adopt the
already committed transition. Altered records, foreign hardlinks and changed
inodes fail closed.

A later read must extend all actually returned native, receive, renderer, World
and phase prefixes. Independent native clocks remain separate. Recovered facts
are never retimed or published as a completed observation. The historical
`archive(value, sources)` and `follow(frame, historical=True)` paths use only
retained private files and do not invoke a live guard or SDK.

The recovery ledger (`original-avatar-peer-recovery`) and abandoned-read record
(`original-avatar-peer-abandoned-read`) both write/read version 1. The generic
source and both existing feature facades retain their current version 1.

Six host tests cover actual private immutable files, partial inode ownership,
prefix contradictions in independently valid completed originals, lost CAS
returns, retained history and configured role separation. Native receiver,
renderer and SDK data are synthetic. This prerequisite establishes no Emote
or Avatar feature capability and performs no native/device execution.
