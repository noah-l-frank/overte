# Phone normal account input, version 1

This internal source-bound input component does not advertise the three full
feature.authentication operations. Common journey contract v6 and account
provider v2 remain mandatory for eventual composition. See the shared
[normal-login source/recipe contract](../../native/NORMAL_LOGIN_CONTROLS.md).
The native source is uncompiled and no app/device has executed it.

The existing private channel carries exactly schemaVersion:1, commandId (fresh
32-hex), action:"phone-login-ui" and request. Request is the closed observe or
normal-input object in the shared contract. Actual Test.phoneLoginUi returns
original NormalControlUi metadata with loginControlsVersion:1 and
privateCommandReaderVersion:1. The latter is mandatory: a narrower legacy reader
that can cache credential JSON is not admitted, even if it exports login controls.
The host pins processId to the independently verified actual PID/start context,
fresh device epoch barriers, original UI instance/generation, advancing sequence,
nonregressing monotonic source time and native account/endpoint state. Responses
are private phone-login-ui.json files, read at most 51 times within five seconds.
Missing/foreign/stale or untyped source fails before native input.

The native handler reads the actual passive AccountManager observation on its
owner thread before observing/revalidating Qt control tokens. Actual normal
window pointer, focus and IME/Return events enter the existing login flow. No
QML handler or AccountManager login/logout method is invoked as test input.
The fixture username must be e2e-<owned-run>; password is the actual private
bounded printable-ASCII fixture input. Domains, foreign native endpoint,
existing authority, pending requests, closing/disabled or stale controls cannot
receive credential entry. Source changes between read and delivery invalidate
the original control token. Cancel remains possible during a pending request.
UI/native pending may differ transiently; the component observes both and never
repairs the product or infers a network abort from closing the view.

## Cache, private-file and cleanup boundary

Feature-enabled Phone polling uses Test.phoneReadFeatureCommand(), a read-only
native method over the fixed android-control-command.json file in the existing
private test root. It accepts only an original same-user 0700 directory and
0600 single-link regular input, no symlinks or path/file replacements across the
read. Input is at most 16384 bytes. Qt validates actual JSON grammar; a bounded
member-name scan rejects duplicate/escaped duplicate keys and depth above 128.
Valid existing numeric/Unicode spellings remain accepted. No path is supplied
by a script or command. Missing/non-Unix/private-file support is unavailable;
there is no permissive filesystem fallback. The method never changes product
settings, native authority or trust and keeps no input history.

This prevents credential JSON from entering Script.require's CommonJS source/
module cache. Non-feature sources retain their existing polling behavior; the
mandatory source marker prevents this input component from admitting them.
The JavaScript dispatcher deletes the transient request.text property in finally,
including invalid input, native failure and unavailable hooks. It saves only
native closed delivery/source metadata and never echoes text or raw exceptions.

After every attempted credential replacement, including a lost input receipt,
PhoneLoginIO sends a fresh read-only observe request. The existing atomic private
writer independently reads back the exact replacement bytes. A fresh original
native response is additionally required. This retires the on-disk secret command
without replaying uncertain input. If binding, replacement or original readback
fails, the operation fails and its caller's durable intent must remain. The
component cannot safely clear a foreign/new process's files. A later full owner
must recover/remove only its original command scope and verify absence before
claiming full cleanup. Native memory erasure or secure-storage logout is not
inferred from a transport replacement.

The caller must persist scoped intent before **each** actual input. It receives
only original metadata, closed verb and control ID, never username/password.
No full run journal/coordinator is created or silently discarded by this
primitive. Full cleanup still needs ordinary owned view close, independently
measured anonymous protected profile, actual fixture revocation, native probe/
origin drain and all owned file absence. Intentional restart additionally needs
new installed-code/process/source binding and real lifecycle/persistence facts.
Neither a view ACK nor these host checks qualifies any of those behaviors.
