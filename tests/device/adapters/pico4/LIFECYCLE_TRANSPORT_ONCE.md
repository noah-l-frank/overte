# Once-only original OS input

`PicoBoundAdapter._pico_lifecycle_input_once(target, operation, binding,
before_input=callback)` retains the actual target eligibility, candidate,
controlled Debug identity, Pico session, process and foreground guards. The
callback runs after the last guards immediately before the original SDK shell
command. It can refuse publication or perform its own durable intent and final
freshness checks. Its return value is not a receipt or an observed effect.

HOME uses one `input keyevent KEYCODE_HOME`. Resume uses one original
`am start -W -n` with the fixed controlled activity. The helper never retries,
bootstraps a missing process, force-stops, repairs a binding or queries Qt.
An ignored event or lost shell response remains unresolved for the enclosing
owner. Current process and installation checks still run after a dispatched
command, including on a lost response. The enclosing Chat owner retains the
original input intent and independently proves actual OS/Qt/keyboard changes.

Only a facade with an explicitly bound phase fence selects this route. The
existing Graphics path remains unchanged. Actual Pico factory/guard/writer host
checks use explicit synthetic SDK/process/Qt/clock boundaries; device count is
zero. They do not turn a facade invocation into an observed HOME/Resume effect.
