# Explicit raw literal profiles

`AudioRawArchive` keeps its original 1 MiB per-read default. An explicitly
selected `literal_limit=4*MAX_LITERAL` also requires the original caller scope
`maximumLiteralBytes=4*MAX_LITERAL`. Mismatched, unsupported, boolean and float
profiles refuse before opening files. The exact initial profile tuple and scope
hash stay pinned throughout the warm owner; mutating both public/private limit
fields cannot enlarge an existing namespace.

This enables the Assets source's existing 4 MiB bounded acquisition to use the
same raw ranges without four invented read tokens. It does not itself connect
the Assets upload owner or authorize any broader acquisition. Audio raw root,
range and index grammars stay at version1. Existing Audio, Navigation, Lifecycle
and SDK probe callers retain their existing scope bytes and 1 MiB limit.

The compound 512-part, 512-read and 16 MiB retained/decoded-byte bounds, maximum
4096-byte command metadata, side-byte allowance, original clocks and reservation
receipts are unchanged. A 4 MiB reservation accounts for65 possible parts before
any getter; actual exact4 MiB bytes occupy64 ranges. The 16 MiB bound measures
protocol retained/decoded bytes and copy extents, not Python process RSS or all
transient Unicode allocations. Each enclosing typed owner must still account
for its own sources and simultaneous copies before acquisition.

Ten explicit host cases pass0.648s (0.674s including loaded-source verification),
39 loaded sources with unchanged SHA256/eight-field physical signatures. They
include actual4 MiB incompressible binary originals, original paired OFDs,
range/index readback and sealing; explicit scope admission and anti-resealing;
and unchanged part, command, side-byte and16 MiB refusal before any getter.
The earlier42-case frozen scope (eight initial profile cases,14 existing raw
cases and20 actual SDK probe cases) passes1.671s/56 stable loaded sources. These
are separate qualified scopes, not a claimed current aggregate. Originals and
receipts remain privately retained in the owning integration area, labels
`raw-literal-profile-first-20261103` and
`raw-literal-profile-budget-20261103`.

Catalog group `raw-literal-profile` selects the ten cases. No source-complete
feature, compiled native producer or device acceptance is added.
