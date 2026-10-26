# Unretired Audio responsibility before ordinary session operations

The partial [page and recording owner](AUDIO_PAGE_CYCLES.md) can close the
tablet and retire its [PCM lease](AUDIO_PCM_LEASE.md). Those steps do not prove
that native callback, source, page or settings ownership has ended. Until that
complete protocol exists, any `ios-audio-` carrier beside the installed session
blocks ordinary describe, invoke and cleanup, and generic component cleanup.
The barrier runs before candidate, SDK, session creation or process input. It
does not acquire sources, interpret malformed files as absence, remove carriers
or turn an unfinished operation into successful cleanup.

The existing Audio runtime writes an immutable version-one scope marker before
entering its input session or creating Audio evidence. The marker retains the
exact binding, run and canonical artifact directory, including an external
directory. Losing an operation journal therefore cannot hide that registered
responsibility. A different run or root cannot replace the marker. Legacy
external artifacts whose owner and scope metadata were both lost cannot be
discovered by this local-directory barrier; it performs no global scan.

Seven focused cases exercise empty readonly inspection, malformed/partial
carriers, external scope retention, incompatible reentry, the actual runtime
factory, ordinary admission and unchanged owner-free cleanup. Together with
the eighteen installed-adapter cases, all 25 pass. Private files, locks,
factory construction and entry decorators run; SDK/native process boundaries
are explicit host models. No hardware or native compilation is qualified.

There is deliberately no Audio marker removal API yet. Original complete
source/callback/settings retirement and process/SDK end must own that change;
page visibility, zero recording buffers and input ACKs cannot supply it. The
whole Audio capability remains closed.
