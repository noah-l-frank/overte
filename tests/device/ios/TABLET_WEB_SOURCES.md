# Native tablet source and inline-carrier prerequisites

`IOSTabletSourcesObservation.h` passively records the actual native
`TabletProxy::loadHTMLSourceOnTopImpl` source input, native root birth and original
QML invocation return. The return means invocation only; it supplies no loaded
page, HTTP status, DOM, bridge outcome or document counter. No new source or root
can be introduced by an observation query.

An inline input belongs only to the same actual native root as an earlier owned
fixture HTTP source. Its actual decoded original HTML must contain that run's
owner metadata; the exact native URL bytes, decoded bytes, charset and hashes are
retained. Metadata alone supplies no authority or effect: full original input
bytes, actual native opaque descriptor/token, document/context binding, document
completion and bridge/pixel originals must still join independently.

Actual `NativeInlineHtmlSource` births and bindings retain weak native owner,
page and context references, actual bind/retire callback-return receipts and an unchanged `InlineHtmlDocument` copy. The copy
owns immutable payload bytes and a weak revocation lifetime; it cannot prolong
the source authority. Native revocation, retire entry after its actual retired
flag, QObject destruction and queried weak liveness remain separate originals.
A retire flag, document-current=false or weak death without the actual method return cannot qualify full source retirement.

The native source header is gated by both iOS and `OVERTE_E2E_FEATURE_TESTS`,
then actual nonempty test-script/results arguments. Hooks add no source ownership
outside that gate. iOS libraries are statically linked by `cmake/init.cmake`, so
the shared header's inline native ledger belongs to the one application graph.
There is no reset. Birth/history rewrites, resurrection, clock rollback and
incomplete/overflow histories fail closed. Private source/descriptor bytes stay
in the original native packet; they are not public feature projection fields.

The separate v1 source DTO has a closed run/fixture query and its own action/file.
The Python reader reuses only the already reviewed bounded guarded Web transport
base, overriding action, grammar and the explicit existing 2 MiB bound. It never
converts WorldWeb DTOs into Tablet observations. Original native clocks stay
separate from host/AFC timestamps. Four initial host tests qualify this pure
reader and transport logic. Native hooks, actual shared JS/fixture/AFC routes and
all 26 whole Tablet-Web checkpoints require separate integration and checks.
The native additions are uncompiled and devices remain untested.
