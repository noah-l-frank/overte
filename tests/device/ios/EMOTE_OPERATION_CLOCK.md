# Whole Emote operation work clock

The internal operation scope carries one original host deadline across nested
calls and lock release/reacquisition. It does not supply native timestamps or
effect facts. The coordinator uses 25 seconds for action, 30 for observation,
and 60 for publication, paired cleanup and final archival. Shorter child lock
budgets still apply; nested calls cannot extend the parent deadline. Expiry or
a host clock reversal remains latched for that whole invocation.

The runtime preserves the existing candidate/process checks and adds the work
guard to original source callbacks, SDK calls and the final native input send
callback. The shared context-local transport scope protects actual WebDriver
and native HTTP sends, including channels created by canonical lifecycle code.
Its default is inactive. The guard runs after transport preparation; slow
serialization or a slow W3C lookup cannot authorize a subsequent send or click.
An input already marked issued retains its original ownership after failure.

The canonical installed adapter also enters the same final-transport boundary
before its first candidate check and retains it through its final binding
verification. The early Emote entry guard uses the operation's 25/30/60-second
budget and a pure host-clock callback. Nested operations cannot bypass an outer
deadline or clear a latched failure. Other operation names retain their existing
behavior; this entry guard adds no Emote dispatch or capability by itself.

The host tests exercise the real `NativeUI`, `NativeInput._request` and
`FeatureObservation.send` paths, plus nested call deadlines and context release.
They explicitly verify zero send/click after expiry and rejection after a clock
rewind inside the same operation. No SDK session, compiler or device starts.
These components do not advertise whole Feature 5 capability.
