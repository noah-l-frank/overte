# Original native Script clock joins

The internal `FeatureObservation.script_fixture_files()` and
`script_execution_observer()` factories now supply separately acquired
`feature-native-observe` clocks over the existing HTTP/AFC route. Both the
pre-command barrier and final capture check use original native epochs from
the same foreground process. Host UTC does not qualify a receipt. Every
private path, request nonce and process guard remains closed and exact.

The shared v1 readers reject a pre-command native request timestamp, stale
capture, regressing clock, late acquisition or lost process before committing
their cursors or engine/effect history. Clock acquisitions share the original
five-second deadline; this change does not increase operation timeouts. An
uncertain storage mutation is sent once, and the existing durable intent
survives until separate original file absence is observed.

Original module, submitted-code and entity-edit timestamps remain unchanged.
A historical module timestamp may legitimately predate this observation;
the current receipt must still be fresh against a separate native clock.

`self_tests/test_ios_script_freshness.py` exercises both factories through
their actual closed HTTP command and AFC path handling, with synthetic native
process/storage boundaries. It checks host-clock skew, stale current-nonce
receipts, foreign/missing clock sources, clock regression/timeout and process
loss. Existing normal-Scripts tests separately verify staged bytes, ignored
stage/release acknowledgments and retained cleanup intent.

These host simulations establish test logic only. Full Scripts coordination,
restart ownership adoption and independent cleanup joins remain incomplete;
no full `feature.scripts.*` capability is registered. Native instrumentation
is uncompiled, and all three clients remain unqualified on devices.
