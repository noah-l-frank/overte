# Process-scoped Phone account fixture launch, version 1

Authentication needs a real trusted HTTPS account provider. The Phone login UI
has no server editor. The existing product `MetaverseAPI` already supports
`HIFI_METAVERSE_URL`; this packet supplies that process environment only through
the existing shell-permission-protected debug launcher, before Qt initializes.
It changes no saved endpoint, account preference, token, TLS trust or release APK.
It performs no login, logout, refresh or protected request. This is fixture setup,
not a complete Authentication adapter or a function-success receipt.

Enable `OVERTE_PHONE_ACCOUNT_FIXTURE=1` for the entire later lab run, before its
first cold launch, and provide the existing HTTPS
`OVERTE_E2E_FEATURE_FIXTURE_URL=https://<owned origin>/feature-fixture/v1`.
The same source override supplies this origin again on explicit app restarts.
Default-off launch retains the original SDK route. Startup requires a verified
Phone candidate, the existing controlled `android-debug-e2e` target and explicit
`appium:autoLaunch:false`. Other packages/profiles, a changed target/session or
changed installed APK bytes are rejected before input.

`PhoneAppiumAdapter.start_android_e2e` holds the existing SDK admission scope and
dispatches exactly one bounded ordinary Android Activity launch through the
existing ADB transport, with the sole extra
`org.overte.e2e.ACCOUNT_ORIGIN`. Every shell argument is quoted. The origin is
derived from the exact fixture base URL; plain HTTP, userinfo, path components,
query/fragment, percent/alternate encodings, control characters, uppercase
authority, invalid host/port and shell syntax fail before dispatch. A lost
delivery is not retried. The enclosing full restart owner must persist its issued
intent before calling App Launch. Its receipt proves no process or endpoint.

The debug-only `E2eLauncherActivity` independently validates that closed HTTPS
origin and calls `Os.setenv` before returning the target Activity class. Qt then
uses its existing native environment lookup. The normal/release Activity does
not gain an origin input or authority setter. Process death ends this override;
the original stored directory-service choice remains unchanged. No test CA is
installed and no TLS validation is bypassed: the actual provider certificate must
already be trusted by the native candidate. The later full owner must reject
wrong original endpoint identity before releasing private credentials. It must
not silently replace an already-running client's endpoint; a warm process with
a different original endpoint fails admission.

The native per-run origin/probe leases remain separate: those record actual
current Test/native context and private transport ownership, must drain/release
before restart, and must be freshly staged in the proven new context. This
startup environment does not manufacture those leases or adopt their files.

Ten host cases exercise the real adapter dispatch/installed-identity/session
guards with synthetic SDK/ADB boundaries, including ACK-only launch, default-off
behavior, cold App Launch, one-send lost return, wrong candidate/session, changed
installed bytes, malformed origins and IPv4/IPv6/DNS quoting. They execute no
device command. The additional Java URI parser tests are registered as source
test ownership but remain uncompiled/unrun under the current no-build scope.
Native Java/C++ execution, HTTPS/native trust and device qualification remain
untested. The complete Authentication facade, normal logout route, per-role
restart/history and independent protected/UI/backend joins are still pending.
