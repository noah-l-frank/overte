# Durable navigation image index

`NavigationSamples` indexes original image attempts for one run, role, installed
process and stage. It reuses `NavigationSampleOwner` and the existing Vulkan
frame owner. It does not send normal UI input, create a process/SDK session,
publish peer observations or advertise the full Worlds capability.

The private `ios-navigation-<role>-<stage>-samples.json` state is version 1 and
uses the existing compressed, bounded original-history format, strict context,
CAS writes and shared source lock. Before constructing or calling an image
owner, it reserves a fresh opaque request UUID. A separate durable `childStarted`
intent precedes capture. A pending attempt prevents another live read. There
are at most 512 attempts; exhaustion is unavailable, not successful empty data.
The final return also checks the original acquisition's 1.5-second host deadline
after archive/index validation. A late result can remain an immutable historical
capture, but cannot be returned as a fresh measurement.

Every completed or marker-pending attempt receives an immutable private
`...-sample-archive.json` record, version 1. It freezes the exact original child
ownership envelope and its digest before the index records its own archive
digest. The original PNG remains the actual owned file, with original inode,
chunks, native clocks and hashes verified by the existing owner. A mutable
child can later accumulate fresh cleanup proofs; that cannot replace its
sealed original. Historical index construction forbids live factories and SDK
ports. Historical archive validation reads original ownership and retained PNG
bytes without minting a new measurement or touching the device.

Every fully archived frame, including a marker-pending frame, enters the
accepted-frame ID set. Subsequent accepted images require original native
observer/history continuity, advancing original navigation/scene history,
advancing same-birth GPU counters, ordered acquisition intervals and immutable
provider/fixture history. Reused frames, counter rollback and source replacement
prevent the index from advancing. Marker-pending originals remain owned and
available privately; a later measurement gets a new request UUID and never
resends a product input.

`changed(request)` selects the immediately preceding successfully observed
original, rather than a caller-chosen convenient baseline. Both images are
revalidated through the original challenge decoder and native scene/GPU joins.
Marker-only changes cannot stand in for changed scene subject pixels. Intermediate
marker-pending originals remain part of source/frame continuity but cannot be
used as valid decoded challenge evidence.

After a lost index return, `recover` can adopt the same sealed child original
without capture, input or retiming. It returns no fresh observation. Only a new
request may supply a later live read. Missing child metadata after the durable
start intent remains unresolved. A reservation proven never started can be
abandoned only when child metadata, frame metadata and owned PNG are all absent.

A partially failed attempt is explicitly drained through its existing child,
preserving partial source packets and native ownership. That abandonment makes
the index terminal (`failed`). No later capture in that index can silently skip
failed-source counters or partially observed frames. A separately admitted
restart/process cohort is required for resumed work. If native ownership or
source correlation cannot be resolved, the pending index remains owned for the
whole failure/OS finalizer; no resource absence or successful cleanup is invented.

This component retains all archives and metadata. It does not establish whole
UI/Web/XHR callback drainage, original-scene restoration, three-second quiet,
process/SDK absence or repeated final cleanup. Those remain responsibilities of
the final Worlds coordinator and independent actor implementation.

Host tests use real private state/PNG files and real loopback scene/phase
sources. Native GPU/UI/process and acquisition clocks are modeled. Tests cover
multiple original requests, marker-pending ownership, canonical B-to-A changed
selection, lost returns, uncertain starts, partial failure, immutable copies,
foreign bindings, reused frames and source/counter replacement. Native code is
uncompiled, devices are untested and physical deadlines are unqualified.
