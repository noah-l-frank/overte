# Original Chat phase admission at input publication

`ChatPhaseFence` version 1 creates a separate `PhaseFixtureReader` over the
original owned fixture Client and its existing non-Qt clock. It reads no UI,
keyboard, native Chat cache, product ACK or requested effect. Each admission
requires the original run, fixture instance/birth, active ticket and complete
unchanged activation prefix from the dispatcher intent. Fresh request nonces
and monotone source sequences are retained; packets never become new inputs.

`mark()` captures actual native/host clocks and an original HTTP frame before
the child intent CAS. `check()` obtains a new original frame after the final
CAS at actual publication. It checks the original anchor before and after the
query, final copy and host guard. A native clock jump under a frozen host clock,
rollback, slow CAS, changed/retired phase or stale response permanently refuses
this fence. A later fresh response cannot reset an unknown input's admission.
The dispatcher retains these original packets in its immutable proof chunks.

Actual checks occur at Pico navigation command writes, the Chat native-source
writer, peer command-file link/replace, mixer HTTP open, background native
ownership commands and the normal OS input route. Every normal Type part and
controller Open has its own original intent marker. The normal QML callback and
separate before-controller/host-only intent pair use the generic owned
`NativeNavigationIO` hooks. Original OS HOME/Resume uses the once-only guarded
SDK route, with its last phase admission after the candidate/process guards. The dispatcher requires
the same concrete child owners, role objects and source locks; a source gate
cannot stand in for an input owner or a remotely observed effect.

The original controller session's locked callback cannot call HTTP, ADB or any
session/guard method. That route therefore checks its fresh original phase
before the lock, then persists the actual locked original envelope and checks
host elapsed age before and after that CAS. The original clocks are sampled
outside the lock. The callback is not an independent native clock sample or
proof of input application/neutrality; those remain separate original sources.

Denial retains the child and parent intents and their actual journals. It does
not claim foreground restoration, peer/mixer restoration, timer retirement,
native process absence or complete cleanup. Original owned recovery remains
separate authority; an expired stimulus cannot be relabeled as recovery or
replayed. No device, service, Agent, actual network or OpenXR runtime is run by
the focused host checks. Full Chat qualification still requires the remaining
Pico factory and whole-run cleanup/retirement composition.
