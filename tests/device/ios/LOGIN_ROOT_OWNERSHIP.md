# Observed Login root ownership

The optional native UI `loginRootOwnership` component is independent of Login
control metadata version 2. It records only the actual LoginDialog root operand
from the existing bounded whole-tree UI walk, its exact original QML component,
an observed identity, first-observed clocks and a retained QPointer. Tablet,
Overlay and desktop-style Login components have their own closed kinds.
`firstObserved` is never an allocation or component-birth claim.

The existing passive Script root ledger has a separate closed Login profile,
instance, schema and clock domain. Its Script default and original manager /
picker version-1 bytes remain unchanged. The Login profile is compiled only for
iOS E2E builds and requires the existing `--testScript` and results-location
gates. It adds no JavaScript API, property setter, login operation, QObject
parent, destruction action or credential observer.

The getter surveys hidden roots before hit-testing and retains previously seen
operands even after visual detachment. The normal Login menu entry is not a Dialog operand and cannot admit a root.
Original current Dialog control tokens map to
these exact observed identities. The component contains no text, credential,
text length, credential hash or requested cleanup verdict. Incomplete walks and
unavailable getters do not prove empty ownership. Roots never seen by the
getter remain unknown; this is not global QObject creation history.

`login_root_ownership.admitted` requires a positive actual current control token
and its matching root. `follow` preserves that identity after hidden controls
have disappeared. A live cached root stays held; only actual original weak
expiry or separately qualified OS process death can end it. Those sources do
not replace callback, keyboard, pixel, account or whole-feature retirement.
The success terminal descriptor must still retain every actual outstanding
Login root until its actual endpoint. No successful-login ACK implies weak
expiry.

The retained Login operand map has a hard bound of 64. Overflow permanently
marks its whole-walk result incomplete; removing expired entries cannot turn
that lost history back into a complete empty inventory. The original weak-root
ledger has its own unchanged 64-entry history bound.

Host tests call the actual repository validators and NativeInput implementation.
They include actual host weak-reference retention/expiry, default Script-source
compatibility and cross-profile rejection. Genuine loopback HTTP POST and
unchanged AFC JSON bytes cover optional-component/legacy receipts and nested
PID, clock and secret-field rejection. Native roots remain an explicitly modeled
boundary. No native build or device run is claimed.
