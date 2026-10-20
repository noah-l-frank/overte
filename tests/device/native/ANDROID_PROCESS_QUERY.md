# Original Android PID selection, version 1

`adapters/android_process_query.py` is a bounded read-only pre-launch source.
The existing general `AdbTransport.process_state` uses unchecked `pidof` output;
an empty string can also follow a failed command. New restart logic must not
use that empty fallback as a complete absence observation.

`AndroidProcessQuery(transport, package, guard).read(target, old_pid)` executes
one original selected ADB command, preserving the configured transport prefix
(including its dedicated server port):

```
adb [configured options] -s <selected-target> exec-out run-as <reviewed-package> /system/bin/ps -p <old-pid> -o PID
```

The exact command uses a fixed absolute tool and fields, positive signed-32-bit
PID and a closed dotted package identifier. There is no shell script, signal,
file write, installation, user text or alternate target discovery. `run-as`
uses the existing debuggable application's UID; this is a prerequisite source,
not an alternative to installed-candidate/debug-channel guards. The adapter
must supply its original selected target and revalidate the same candidate and
target both before and after the native command.

The required native tool ABI is ASCII, newline-terminated output containing
exactly the whitespace-trimmed header `PID`, followed by either one positive PID
line equal to the queried PID, or no data row. A found PID requires original
exit code zero. A complete header-only selection accepts native exit code zero
or one. Any stderr, other exit code, empty/partial/missing output, non-ASCII,
wrong header, blank row, wrong/duplicate/multiple PID or output over 128 bytes
is unavailable proof. Unsupported Android/tool ABI must fail; it cannot be
substituted with guessed absence. Actual device ABI remains unqualified.

The whole query, both original candidate guards and final monotonic validation
have a five-second bound. Initial guard time is deducted from the subprocess
timeout. There is one invocation, no retry, and no cached result or receipt file.
Timeouts, execution errors, candidate loss or clock regression raise the same
privacy-safe error; raw stderr/selectors never become public diagnostics.

Return exactly `processQueryVersion:1`, `queryProcessId`, `complete:true`,
`processIds` and `nativeReturnCode`. `queryProcessId` is the original query;
`processIds` comes only from original PID output, never from an expected result.
A found/reused PID conservatively blocks launch even if it may now belong to
another process. An empty complete selection is an OS precondition only. The
Script handoff still requires [original new-process kernel ESRCH](PROCESS_PRESENCE.md),
a distinct qualified new process/native birth, unchanged originals and stable
independent execution/UI absence. No full feature capability is advertised.

Six host cases replace only subprocess/candidate/clock boundaries. They verify
exact argument routing, original positive/empty return codes, all malformed and
missing/error outputs, permission/transport/timeout failures, initial/final
candidate loss and deadlines, wrong PID and closed target/package grammar.
No ADB executable, device or native tool is run by these checks.
