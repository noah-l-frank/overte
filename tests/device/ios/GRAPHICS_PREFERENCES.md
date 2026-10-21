# Ordinary iOS Graphics preference ownership

`graphics_preferences.py` owns original preferences and normal generic Qt/UIKit
Graphics input under the existing canonical source lock and scene owner. It
supports the unchanged shared `open`, `close`, `set-resolution`, `set-haze`,
`set-mirrors` and `restore-original` inputs. It advertises no feature capability;
GPU effects and whole-run lifecycle/actor/quiet cleanup remain separate.

The private version-1 `ios-graphics-preferences.json` retains the full candidate,
run, original settings, actual native source birth/cursors/history, ordinary UI
intent receipts, one-send substeps and independently read native/UI proofs.
Input intent is durable before pointer/edit delivery. Reconstruction reads an
already issued substep without sending it again. Scalar effects must match both
the original native settings and original control source, while unrelated
preferences remain unchanged. The actual generic slider range/grid is used;
an original value outside its reproducible grid prevents scalar input.

`graphics_history.py` restores source floors and any present immutable account,
animation and recorded-preview histories without transport, retiming or fresh
results. Account/animation capabilities are not prerequisites for Graphics.
Only the separately clock-bound iOS native reader is admitted. Subsequent reads
must preserve original histories, PID, source birth and advancing cursors.

Cleanup restores only initially measured preferences through the same ordinary
controls, closes owned UI and independently verifies the entire original native
Graphics settings object. A lost restoration return retains its durable issued
step; a replaced source or unrelated setting change prevents a clean result.
Cleanup does not claim native GPU/Web consumer drainage or the final three-second
whole-run quiet window. Metadata retirement remains the outer owner's decision.
The source includes a proposed restart archive for the existing strict iOS
restart-proof contract; the actual restart controller is still unfinished.

The ownership decomposition was reviewed at frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`. Its Phone profile, package/process
identity, clock assumptions and source projection were replaced by the existing
iOS implementations. New decoding also validates untouched original UI receipts
and stored outcome proofs rather than trusting a nonempty proof field.

Nine preference cases, four history cases, six scene cases, seven ordinary
surface cases and twelve bound-clock cases pass (38 selected no-build tests).
They cover nondefault original restoration, real temporary ownership files and
loopback scene responses, ignored/lost input, stale clocks, changed source birth,
failed intent persistence, altered receipts/history and unresolved restoration.
Native settings, UIKit/Qt and GPU boundaries remain synthetic; native sources
remain uncompiled and devices untested. The complete outer Graphics owner is
now integrated; see [the current handoff](GRAPHICS_FINALIZATION.md).
