# Fail closed when a Material clone loses diagnostic scopes

The Texture5 native source previously made only the unpublished clone's local
health false if copying its diagnostic callbacks threw. A failed allocation
can leave that clone with an empty scope vector. If an independent caller then
replaces its map, the original registry cannot observe the new group through
those lost scopes. Death of the old map/source groups must not authorize a
complete original inventory while the hidden replacement remains alive.

The gated Graphics implementation now owns one process-long atomic failure
bit, independent of callback allocation or registration. There is no reset.
The copy catch calls the existing incomplete helper, which sets the bit before
attempting any callback, even when the vector is empty. Registration also
refuses already failed global health. The native main-thread origin snapshot
reads only the static atomic getter and permanently makes its existing
`complete` field false. No Material object or mutex is entered from the
registry lock. A compile-time lock-free requirement forbids replacing this
health read with an implicit lock.

The change retains the existing iOS/feature-test gates and runtime
`--testScript` admission. It changes no product copy, setter, texture operation,
normal input, parser, queue, cleanup or ownership behavior. No new strong owner,
callback pointer or Graphics-to-Networking dependency is introduced. The wire
remains History5; this only strengthens its conservative completeness failure.

Three explicit native-boundary host cases pass3/0.031s in
`assets-texture-clone-failure-three-first-20261027.log`, without an isolated
timing claim. A real Python `MemoryError` loses the modeled scopes, then real
Python weak references show old groups dead while a replacement Source remains
alive. The actual host reader retains the new incomplete original and refuses
texture-owner absence; it does not substitute its earlier good packet. Failure
before the first query remains visible after a later legitimate publication.
A successful clone keeps original groups alive without inventing failure.

The five approved no-build project suites pass5/7.34s
(`assets-texture-clone-failure-final-common-20261027.log`), with unchanged
contract versions, all883 workspace Markdown files and whitespace checks green.
These shared checks supply no native compilation or scenario expansion.

These tests specify the boundary's fail-closed expectation and run the actual
host codecs; they do not execute C++ allocation failure or its atomic. The
native correction has not been compiled or run. The earlier225.251s connected
host pass used the preceding native source snapshot and cannot retrospectively
qualify this change. No unchanged whole journey is repeated for this native
exception-only correction. Decoder/destructor/GPU/resource completion and
owner retirement remain unavailable; Assets and the overall5/14 count are
unchanged.
