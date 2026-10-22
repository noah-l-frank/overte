# Passive Create entity originals

`IOSCreateEntitiesObservation` combines independent native originals: the actual
`addEntityInternal` return (including null), `deleteEntity` return operands, and
the actual EntityTree map insertion/removal ledger with weak ownership expiry.
All hooks require both E2E+iOS compilation and an actual `--testScript` process.
The read command accepts only schema version, request ID, action and run ID.
No requested UUID, desired result, reset, product setter or queue drain exists.

Each actual Tree has its own birth identity. Reinserting one UUID creates a new
birth. Unknown removals, missing insertion history and bounded ledger overflow
permanently mark the source incomplete. A delete return is never evidence that
an entity disappeared or that its last strong owner died. The host join requires
an original add return from the actual admitted VM and submitted code, the exact
actual Tree birth within that native invocation, an actual later removal, and
independently observed weak expiry. A live replacement with the same UUID keeps
retirement unresolved. Actual null returns are retained separately.

Native packets are bounded to 1 MiB. Native read, API caller, manager assignment,
Tree and weak-destruction clocks/counters remain separate originals. Historical
prefix validation preserves identity and refuses rewrites or revival. No scene
lookup, Script ACK, expected value or delete operand manufactures an add return.

The eight host tests use actual Python object/weak-reference lifetimes with
modeled native DTO producers. They cover retained owners, ignored deletion,
wrong VM/code/UUID, UUID reuse, null returns, unknown removals, overflow and
closed read grammar. Four additional transport tests exercise the actual fixture command validator,
probe Node dispatcher, HTTP/AFC channel and independent native-clock reader.
A 648020-byte original containing 512 births/returns survives the separate
1 MiB source bound; the shared decoder's ordinary 256 KiB default remains
unchanged. Duplicate keys, NaN, wanted-result fields, repeated nonces, missing
originals and changed processes fail closed. These tests do not compile or
execute the native C++ hooks.

```sh
python3 -m unittest ios.self_tests.test_ios_create_entities -q
```

This packet is a prerequisite for the full Create owner. It does not establish
paired cleanup, actual rendered marker absence, or a complete feature capability.
