# Normal Phone account menu, version 1

`_account_menu(selector, intent, run, origin).logout()` uses the existing native
W3C input layer and Phone tablet navigation. It opens the tablet if needed,
returns Home if needed, finds the actual MENU app (at most eight normal tablet
pages), selects File and taps the normal controlled-account Logout row.

The route is source-reviewed in `mobileTabletApps.js`, `TabletMenu.qml`,
`TabletMenuStack.qml`, `TabletMenuView.qml` and `LoginDialog::toggleAction`.
The ordinary menu's existing queued action invokes product logout. The adapter
never calls AccountManager, AccountServices, a QML handler, QAction trigger,
credential storage or a settings setter. It adds no product widget or menu item.
Its input label identifies the controlled fixture account; that label is never
returned as a measured principal or protected-access result.

Before every input, a new original passive native account sample must show the
actual valid controlled principal hash, expected controlled HTTPS endpoint,
active credentials and no pending login/refresh. Native Test/account history,
candidate/PID/start ticks, foreground and the existing SDK session remain pinned.
The real source tree must contain one visible/enabled row in the Phone package;
the W3C reader separately requires actual visible/enabled unique elements.
Qt Android view class names are deliberately not guessed. Unknown/foreign/
ambiguous controls and changed source/account context fail before the tap.

The owner callback receives only `account-menu-<stage>`, the original pre-input
native packet and the closed stage identity. It must persist issued cleanup
intent before allowing the input. The component never retries an uncertain
click. Its whole 20-second budget includes source acquisition, navigation and
the ownership callback; existing UI/source limits remain. An input or private
write failure leaves responsibility with the complete owner.

The result is delivery acknowledgment only. Even actual disappearance of the
Logout row does not prove cleared credentials. The complete Authentication
owner must independently acquire current native credential/history state,
actual protected HTTP401 and separate actor/backend facts. A counterexample
explicitly changes the UI while retaining native login: this component can
acknowledge delivery but supplies no logout verdict. No complete Authentication
capability is advertised by this helper.

Thirteen host cases use synthetic W3C/native boundaries: ordinary tablet/menu/
File/logout, Home/pagination, wrong account/endpoint/pending state, ignored input,
lost guards, private-intent failure/deadline, account replacement, foreign or
ambiguous controls, missing native data, actual factory/session/candidate binding
and the UI-only misleading result. Native producer code and device behavior
remain uncompiled/unqualified. Pico and iOS are unchanged and remain paused.
