# Normal feature input foundation

`normal_ui.py` implements source-owned normal W3C click and text input primitives
for the new parity journeys. It uses the existing shared `WebDriver` transport
and a caller-supplied bound native session. It discovers, installs and launches
no targets. This is the first adapter packet; no native adapter advertises a new
feature operation solely because the helper is present.

The owning adapter must keep its original artifact/installed-code checks and
pass its actual process, foreground and candidate-continuity callback. Its
feature-specific implementation supplies reviewed native ID/accessibility-ID
locators; never accept raw locators, XPath, scripts or arbitrary recipes from
test operation arguments. Existing feature contracts still validate every
operation's closed arguments and ACK-only result.

Before input, the helper queries actual W3C `/elements`, requires one unique
reference and checks its actual displayed/enabled booleans. It verifies the
owning application around these reads and each input. Missing or temporarily
hidden controls may be observed again within a bounded monotonic wait. Duplicate
controls and malformed element paths fail. No fixed coordinate, JavaScript
execution, hidden bridge or direct product API fallback is used.

Text replacement uses the actual native element's clear/value commands, supports
Unicode within the providers' UTF-16 limit and rejects embedded control keys.
Mapped special keys from the [WebDriver key table](https://www.w3.org/TR/webdriver/#keyboard-actions)
are also rejected as literal text. `press_enter` submits the actual resolved
field through one explicit native key action. Unmapped private-use glyphs remain
ordinary Unicode. Submitting remains an explicit normal UI action. Input is never automatically
replayed after an uncertain response: an accidental double click or second
submit could alter history or create another object. The ordinary journey then
judges real feature effects through its independent observation.

Transport and continuity errors have closed public diagnostics. Private locators,
selectors, entered text and raw exception details are not included. Session-only
`release_actions` remains callable when the foreground/process guard fails so
owned input can be released. It does not claim to close feature panels or
restore feature state; the feature-specific cleanup still owns that work.

The existing Phone and Pico Android accessibility providers expose real native
nodes and actions; iOS bindings must use the actual exported UIKit/Qt elements.
The shared helper can be reused where a verified native W3C session supplies
those nodes. It does not pretend an absent iOS element or an unexported immersive
Pico control is actionable. Actual per-client flow bindings, configuration,
source/artifact identity and later physical qualification remain pending.

Host tests replace only the native W3C boundary and guard/clock. They cover
normal input, late controls, duplicates, hidden/disabled controls, path injection,
false readiness, changed application state, uncertain mutation responses and
privacy. One case runs the real shared WebDriver over an owned loopback HTTP
endpoint. These are local protocol checks and never device acceptance.
