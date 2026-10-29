# Callback Emote literal key packets

The explicit Callback Archive2 path now reads key packets through their
existing literal raw/frame decoder. It avoids the additional packet-result
memo in the historical round. The default `None` policy and legacy readers
keep their previous behavior. The receipt-result memo remains guarded by its
complete inventories.

Both paths retain the same owner-lock and parser admission. The literal path
checks the original owner/raw namespace and raw-store guard before and after
decoding. Each packet reopens its actual bytes and validates its original
hash, inode and query; parser replacements execute instead of returning an
older packet result. Every complete archive still requires its unchanged
full entry and exit inventory. An intermediate literal value is not archive
authority; a persistent unknown file refuses the enclosing archive return.

The implementation is in [the existing round](adapters/emote_archive_round.py)
and [the callback archive](adapters/emote_callback_archive.py).
No wire version, registry entry, acquisition limit or deadline changes.

## Host verification and measured scope

Thirty checks passed: eleven literal-packet cases, twelve existing key-round
cases and seven existing archive-round cases. They cover mutation, replacement
inodes, original read membership, independent return values, parser changes,
foreign locks, invalid boundaries and complete exit inventories. The runs
retained 159 original files in 31 genuine temporary roots. All 8,134
source/launcher pins remained unchanged; no owned processes or fixture threads
remained.

The same supported complete Primary Live2 archive was then decoded from the
same 735 retained files and two saved snapshots, with the byte-identical
profiling runner and unchanged 60-second limit. It returned in 35.879206403
seconds versus 52.907479342 seconds before the change, approximately 32% less
in this profiled comparison. Round guard calls fell from 3,274 to 956 because
literal packet reads no longer claim a packet-memo hit. Required receipt and
whole-round inventories remain. This is a single diagnostic comparison with
profiling overhead, not a general performance qualification.

The changed-source diagnostic retained all 100 prior cohorts and 35,728
files, with 8,149 source/launcher pins unchanged. Its local packet is
`.ios-host-tmp/emote-complete-live735-literal-packet-qualified-readonly-profile-preparation-20261029`.
The earlier profiling result and the Window735 timeout remain untouched.

Whole paired Window, terminal, process/SDK end and public Emote acceptance
remain open. The changed Window flow has not yet been qualified. Native/SDK,
Qt and GPU sources in fixtures remain declared host models; no native build
or device execution was performed. Complete areas remain 5/14.
