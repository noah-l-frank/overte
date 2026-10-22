# Retained original Chat actor IPC closure v1

`ChatActorFiles.close(retain=True)` closes only the original observation
command/result pair after actual native retirement of its run-owned Chat cache.
It preserves the complete original private actor-files journal, including the
original source, process binding, last consumed command and native result
stamp/digest. The optional host API does not change the native envelope/journal
schema. The legacy default still discards its resolved component journal after
successful original release; it gains no whole-feature qualification.

The closing intent precedes either unlink. Original command bytes/stamp and
result bytes/stamp must still match the acquired originals. The command is
checked again before its removal. A bound actual cleanup fence marks before the
closing CAS and rechecks the original run/ticket/full phase immediately before
each unlink. If a path is missing/replaced or the phase changes partway through,
the original closing journal remains unresolved; no replacement file is adopted.

Neither unlink, an empty namespace, a native ACK nor a reported closed flag is
descriptor release. The actual bound original actor `released(original_node)`
kernel inventory must prove the original result handle absent, twice around the
final checks. In the complete owned peer factory this callback must remain the
actual original `LinuxChatActorProcess.released` method. The actor-files process
guard and process owner callback must also remain original; replacing one with a
caller-supplied success function refuses peer qualification.

Retained-result copying precedes the last original path/source/guard and clock
checks. One unchanged 1.5-second native/host window includes that successful
kernel observation, copy, guards and original host directory-descriptor closure.
A frozen host clock cannot conceal a native jump, and a frozen native clock
cannot conceal a slow copy or guard. The strict owned peer factory requires the
actual original kernel OFD witness before closing its host descriptor. An
uncertain/recycled descriptor is retained, never closed as an owned handle.

The enclosing whole-feature owner must still join two original cache lifetimes,
two independent cache-absence sources, peer input closure, original profile
restoration, process/QML finalization and a dedicated immutable evidence archive.
The retained root deliberately prevents generic cleanup from becoming green.
Baseline fixture SOURCE/process ownership is retained. This API neither stops a
fixture nor qualifies a missing Assignment Client build receipt.

Five focused cases passed in 1.461 seconds: retained success with actual private
files/descriptors, retained native-handle leak despite unlink, current cleanup
change after closing CAS, slow final copies under either frozen clock, and the
legacy default close. The separate actual owned-worker callback replacement
countercase passed in 0.103 seconds. Native cache/protocol rows in these component
tests are explicit synthetic producer seams; the original file parser, OS
inodes/descriptors/OFD witness, private journal, phase reader, owner and guards
execute. No Assignment Client, native compiler, service or device ran.

The complete affected file-transport and owned-peer groups subsequently passed
38 cases in 3.714 seconds with resource warnings treated as errors.
