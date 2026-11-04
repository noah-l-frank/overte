# Optional bounded process originals

`AndroidProcessQuery(acquire=...)` accepts one constructor-selected acquisition
callback while retaining its existing PID/header/return-code/stderr parser and
five-second result deadline. `None` preserves the original subprocess path.
`PicoChatRestartIO(process_acquire=...)` forwards the same original callback to
every original prelaunch PID query. Existing callers remain on their old path.
Neither option proves native ESRCH, package ownership, process birth, candidate
identity, kernel absence, physical acoustics or complete feature cleanup.

`BoundedProcessOriginal` supplies the optional collector. Its caller registers
the exact owner and reserves its fixed argument/output/metadata storage before
`capture`. At most129 bytes per stdout/stderr stream are acquired. Byte129
refuses with an explicitly incomplete original prefix. Success requires EOF on
both pipes and actual child exit. The exact bounded bytes, exit, EOF/overflow
state, original error/traceback and uncertain cleanup remain on that same owner.
The collector terminates only its own Popen after failure and attempts bounded
wait/pipe/selector cleanup. The original failure is never replaced by an archival
callback failure. It invokes the supplied retention callback before the PID
parser or final currentness check. Failed/used owners cannot acquire again.

The callback must durably retain originals and keep acquired objects/resource
charges on an unknown return. The generic collector has no independent budget
or archive and does not authorize dropping old storage. A caller must account
for retained argument strings, encoding scratch, both bounded buffers/result
copies, metadata and original exception/traceback lifetime. Audio's prospective
same-bank source and complete restart cleanup remain separate unfinished work.
A callback or cleanup timeout cannot become a successful absence receipt.

Host checks use actual owned Python stdout/stderr pipes and the existing declared
Android/SDK boundary. They cover128/129-byte output, stderr, real timeout partial
bytes, first-error/traceback custody, callback failure, no retry, the original
present/absent PID ABI, ignored Stop, invalid PID and unchanged original input
cursor. The existing PID and restart regression cases remain applicable.
No test invokes ADB, a device, a build, an audio service or physical capture.
