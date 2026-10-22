# Original Script-file dialog callbacks

This is a source prerequisite, not a completed feature capability. Native C++
instrumentation is gated by `OVERTE_E2E_FEATURE_TESTS`, iOS and `--testScript`.
It remains uncompiled and has not been exercised on a device.

`IOSScriptDialogObservation.h` observes the actual listener returned to
`Application::loadDialog`, the Application response callback's entry and its
return after the synchronous `ScriptEngines::loadScript` call, and independent
listener destruction. A completed load retains only the returned manager's
original load membership. It retains no QObject, manager, callback or Script
value. The inactive path keeps the original loading behavior.

Each response includes its actual UTF-16 text, code-unit count and hash, plus
the same file-existence decision used by loading. A closed or destroyed picker
alone never proves that its queued Application response has returned. An
absent callback, partial prefix or missing worker exit remains unresolved.

The bounded process ledger keeps all original event timestamps and refuses
overflow or invalid transitions. `feature-ios-script-dialogs` provides a fresh
main-thread read bracket through the existing probe/fixture/AFC transport.
Every nonce is consumed once. The Python reader rejects rewritten prefixes,
retimed responses, foreign processes and ambiguous listener ownership.

The ledger (`ios-script-dialog-ledger`), read envelope (`ios-script-dialogs`)
and acquisition (`ios-script-dialog-acquisition`) each write/read version 1.
The six source tests include actual Node probe/fixture dispatch and existing
FeatureObservation/AFC routing, with synthetic native and SDK responses.

The current Emote marker-owner host regression adds normal Script manager and
file-picker recipes, actual staged marker/companion execution in an isolated
Node VM, exact returned entity ownership, observed original worker terminal
receipts, view restoration and repeated three-second quiet cleanup. It also
checks ignored confirmation, returned cancellation, missing callback/worker
exit, unpainted setup, already-ended setup and lost Stop/Home returns. Native
UI, worker, Web and renderer observations are modeled in those tests. The
whole Emote observer and paired resource retirement remain separate work.
