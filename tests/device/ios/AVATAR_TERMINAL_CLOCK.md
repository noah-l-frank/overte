# Original terminal finish clock

The shared Journey measures `terminal_call('finish')` and rejects elapsed time
at 30 seconds in `tests/device/feature_journeys/engine.py:454–456`. The terminal
codec itself carries no work-budget field. Avatar therefore selects a closed
new 30-second budget only for the typed terminal `finish` operation. Inspect,
seal, ordinary actions and cleanup retain their original 25-second budgets.
An earlier enclosing budget is never replaced or extended.

New finish intents write `avatarTerminalClockVersion: 1` with their actual
original host epoch/monotonic starts and corresponding 30-second deadlines.
An existing `avatarOperationClockVersion: 1` remains byte-identical and keeps
its original 25-second deadline, including after reconstruction. No stored
intent, source timestamp or publication receives a later start.

The entry budget includes final candidate verification and the actual last SDK
guard after request serialization. Expired originals cannot send another Stop
or DELETE. Observation freshness and native/host quiet bounds are unchanged.
