# Avatar ordinary-input recipe recovery

Avatar actions and actor consent retain an optional `operationClock` component
inside their existing version 1 call records. Its
`avatarOperationClockVersion: 1` schema stores the original host UTC and
monotonic start and the corresponding 25-second deadlines. Reconstruction
preserves these timestamps. An interrupted legacy call without this component
cannot resume. Completed legacy records remain readable.

Each ordinary Qt input has a durable intent before transport. When an input
return is lost, the owner first acquires the original native input ledger through
`IOSAvatarInputReads`. Only an exact received-and-returned command, control,
root, outer UUID and receipt can settle that input. A received event alone,
rejection, incomplete ledger, changed command or ambiguous UIKit dispatch leaves
the operation owned. Settling input delivery proves no Avatar feature effect.

`AvatarRecipeUI` interprets the immutable, observed event prefix as a program
counter for the original recipe. This historical section calls neither the SDK
nor the input callbacks and creates no commands. A different branch cannot
consume the prefix. At the first remaining step the recipe captures the actual
current control source and checks process, source and root continuity before
admitting a new input. Entirely historical recipes also require this current
join. The original operation deadline is checked during historical planning,
fresh acquisition, new input and completion; it is never renewed on restart.
The deadline is also checked after intent storage, after the internal second
current Qt capture, and immediately before the native HTTP send after process
continuity and request serialization. UIKit open/close uses a private copy of
the normal UI helper whose continuity callback brackets the original candidate
check with deadline checks, including after element resolution. A slow durable
save, current-state read, candidate check or element lookup cannot authorize a
late input. The shared caller's UI object is not modified.

Consent additionally retains the exact incoming invitation UUID. Both a fresh
response and reconstruction must match that UUID and peer. Closing a terminal
dialog requires the same original invitation and the expected accepted or
declined phase. A newer invitation or terminal for the same peer cannot replace
the owned invitation.

Host regressions lose the return after each of the four actual URL recipe
inputs and each of the three actor response/terminal/table inputs. They use
ordinary input transport with independently produced native ledger originals,
private source files and real owner reconstruction. They also reject changed
current roots or QML sources, a different recipe branch, received-only commands,
expired or absent original deadlines and a replaced terminal UUID. These are
host source checks; native instrumentation remains uncompiled and the complete
paired Avatar cleanup journey is a separate integration requirement.
