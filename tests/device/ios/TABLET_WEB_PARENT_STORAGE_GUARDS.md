# Aggregate Tablet original-file guards

`TabletWebSourceOwner.history()` and `app_sources()` check the full current
candidate before and after their immutable file traversal. The final check
also runs after an exception. A candidate change immediately after the last
original read cannot qualify the result.

Only the two aggregate `OriginalFrameStore` instances use the scoped storage
guard. Every file retains its actual lock, private parent, device/inode, mode,
link-count, byte-length, SHA and closed-envelope checks and read membership.
Direct reads outside the scope retain the full live guard. The nine child
histories retain their own full entry/exit guards; capture, save and send also
retain their original full live guards, even inside the private read scope.
Historical readers never acquire current SDK authority and cannot mutate.

The actual one-frame/app fixture previously performed 22 live history guard
calls and missed a candidate change after the final parent read. The corrected
path performs 20 calls: 18 child history guards plus the two aggregate guards.
Additional aggregate files require no extra candidate-continuity checks. The
runtime guard here checks local candidate/session/installed records; actual
SDK process observations occur separately in `actual_process()`. This changes no
serialized version, accepted packet limit, native measurement or deadline.

The retained full26 attempt stopped at `clear-text`: the common checkpoint
rejected its second matching Actor observation as older than 1500 ms. Its
original capture and the immediately following cleanup activation differ by
1507 ms; this later activation is not relabeled as the checkpoint clock.
The limit remains 1500 ms. Its 316 frozen sources were unchanged and all 300 actual imports were
declared. The fix has focused private-file, candidate-switch, historical,
capture/write-refusal and existing source/packet regression coverage. The
next targeted run uses the unchanged common first four steps and its actual
paired error cleanup after a controlled refusal before the fifth input.

All native, UIKit and clock producers in these host tests are explicit models.
Native code remains uncompiled and no device or real CPU freshness acceptance
is claimed. Whole Tablet capability remains closed pending the full journey
and canonical integration.
