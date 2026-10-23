# Script UI original root ownership

The iOS E2E `ScriptUiInventory` writer emits version 2 only with the actual
`--testScript` and `--testResultsLocation` flags. Other runtime/platform paths
retain literal version 1. Readers preserve versions 1 and 2; version 1 supplies
no original root identity or lifetime evidence.

Version 2 retains the original manager/picker status and adds an exact aligned
`rootMembership` plus `IOSScriptUiRootOwnership1`. Each identity is assigned on
the first observation of the actual whole-walk `QQuickItem` operand, and its
`QPointer` does not retain the QObject. Hidden/detached roots remain alive while
their actual weak operand remains alive. `firstObserved*` is observation time,
not allocation time. `weakExpiredObserved*` is the time nullness was observed,
not completion of a destructor, queued callback or OS process.

The ledger is main-thread-only, except for an atomic sticky failure flag. It
retains at most 64 identities and emits at most 16 KiB of compact JSON. Overflow,
unknown operands, missing startup flags and incomplete whole walks cannot prove
absence. No history reset, product mutation, callback drain or root purge occurs.
The containing original native UI receipt supplies run, nonce, process and
candidate provenance. Its native-clock bracket also bounds this source.

Host tests use actual Python weak references to modeled Qt operands, plus the
production inventory decoder and historical v1 fixtures. They do not execute
the native header, compile iOS, or establish physical Qt/device qualification.

The existing NativeInput HTTP/AFC transport tests also decode both literal v1
and freshly emitted v2 model packets through the production reader. A foreign
process or an old nested root clock is rejected against the original parent
observation; parent freshness alone cannot qualify the nested source.
