# Continuing the same original peer input owner

Host ChatPeerInput v4 retains the complete original receipt bytes, native packet,
command/result inode identities, immutable timestamps, request epoch and original
command for every consumed transaction. Its bounded compressed ledger supports
the distant-peer polling history without dropping any input. Native receipts
remain versions 1/2/3 and mean consumption only; actual position, network arrival
and accepted model/storage remain separate original sources.

A fresh RPC process may reconstruct this same original owner only when every
record is consumed and every historical receipt validates against its original
command, run, process, native birth and advancing sequence. The actual current
command and native-held receipt must still have the exact original bytes,
private descriptor identities and stamps. The original kernel/script/file owner
must remain live, unchanged and open. Reconstruction reads only these originals,
performs no command, changes no journal and never returns historical data as a
fresh measurement. An unused v4 owner also reconstructs only while both actual
input files remain absent.

A reconstructed owner can admit the next different fixed operation under the
same original rules. It cannot send the same channel/textKey again, repeat a
hold/restore/release, resume an uncertain transaction, recreate a missing file or
adopt old v1/v2/v3 host journals. Those owners and unresolved journals remain.
Only the existing distinct restoration path is allowed after uncertainty in its
original live owner. Historical consumption never proves a requested effect.

The final live result is copied before the final actor/file guard and actual
native wall-clock read. A frozen host clock cannot hide a late native-clock
jump during that guard. Focused tests execute original fixture JS and actual
private host files on explicit synthetic native seams, including 200 complete
v3 receipt transactions, passive reconstruction, the next distinct operation,
uncertain/old/rewritten histories, original file replacement and source loss.
No device, service or complete Chat capability is qualified by this component.
