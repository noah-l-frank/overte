# Historical retirement prefixes

An original retirement proof records the exact Source, marker-entity, file and
pointer owner prefixes that qualified that acquisition. A subsequent passive
acquisition appends new immutable originals. It does not invalidate the older
proof or change its original timestamp, native counters, bytes or SHA.

`OriginalMarkerEntities.archive`, `IOSEmoteFileReceipts.archive` and
`IOSEmotePointers.archive` are explicitly historical and read only. They replay
every referenced original, its digest and closed grammar, native/host ordering
and accepted partial-source floors. They do not require absence of the next
original file: a later live prefix may legitimately own it. An archive cannot
save, capture, resolve, abandon or directly retain new ownership.

Live constructors retain the next-file orphan checks. Rolling live metadata
back to an older prefix while a later original exists is refused. An altered
referenced original is refused in both modes. No DTO, original file name,
version, resource-closure predicate or freshness requirement changes.

Host tests append actual private originals, re-read the earlier prefix, reject
archive writes and prove that both live rollback/orphan detection and original
byte/digest validation remain effective. Native source producers are modeled;
this is not device qualification.
