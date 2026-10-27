# Assets ownership of the original marker child

The Assets marker parent reserves its own durable intent before using the
existing normal Script manager and file picker. It uses the explicit Assets
namespace of `CreateMarkerScope`; it does not copy that implementation or
publish a Create observation as an Assets result.

`OwnedAssetsMarker` binds the actual source binding, run, role, fixture URL,
initial ticket, artifact directory device/inode, canonical parent file and
canonical Scope3 child file. Its private runtime factory retains the existing
candidate, installed-code, process, session, source-lock and foreground checks.
Host acquisition callbacks use the actual host clock supplied to Assets runtime;
the native source and native freshness clocks remain independent.

The parent records prepare, rendered admission and cleanup intent before
entering the original child. A completed child return can be adopted from its
original WAL without another Load. Lost Stop delivery stays owned by the child
and is recovered without another Stop. Interrupted setup can move directly into
cleanup; it does not need a new successful setup to become responsible for the
existing work. An original exception remains the primary failure if retaining
the latest child snapshot also fails.

The pure `from_archive` entrypoint requires independently supplied artifact
directory, binding, run, role, URL, ticket, lock and canonical parent store. It
does not follow a directory from an untrusted envelope and does not construct a
live SDK source. It reads the current parent WAL and actual original Scope3
frames, including the existing abandoned-read recovery records and byte
prefixes. This is current ownership replay, not a new live observation or a
generic whole-directory membership certificate.

## Qualification and limits

The native callbacks, Web renderer, Domain and device boundary in the host tests
are declared models. The staged marker JavaScript and existing normal
controllers are the actual source implementation. These tests perform no native
build, device action or service launch.

The first parent codec/factory selection correctly refused a lost foreground
through the installed-code guard; its test initially expected the wrong
exception class. The guard was preserved and the test was corrected to require
the actual installed-code rejection. The final six cases passed in 0.389 seconds.
The final eight small cases passed in 0.441 seconds, including impossible
intermediate-state counterexamples and preservation of the original exception
when the parent retention itself fails. The first two original-child parent
flows passed in 10.424
seconds, including lost completed setup/Stop returns and a pure released-parent
read preserving all retained file bytes and inodes.

The first three direct interrupted-cleanup cases exposed a parent-prefix
mistake: the original child legitimately replaces a full pre-render admission
with its own typed partial-execution cleanup admission. The parent now accepts
only this transition under saved cleanup intent, with the same manager, code,
source URL and marker and the exact retained original frame prefix. The two
changed cases passed in 11.303 seconds. They also reject that same transition
under render intent and reject a changed actual abandoned-read record. The
lost completed render-admission case passed in the original selection. Logs
retain the earlier failures; neither the child nor any freshness/quiet guard
was weakened.

Marker cleanup releases only the original marker, its Script worker, callbacks,
Web context and owned staged files according to the child's existing source and
quiet checks. It provides no Assets Model pixels, entity-specific draw proof,
peer publication, geometry/cache/texture/GPU/OS retirement, full Assets journey
or capability promotion. The Model can remain alive after ordinary deletion.
Actual Assets pixels and the subsequent shared-journey/resource end remain the
next vertical dependencies.

After the strict original-recovery and cleanup-prefix changes, the two original
parent flows plus fifteen canonical runtime regressions passed together in
15.183 seconds. The parent schema is `ios-assets-marker-owner` 1/read 1; the
original explicit Assets Scope3 and its frame/recovery schemas remain unchanged.
