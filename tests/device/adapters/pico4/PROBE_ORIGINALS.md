# Pico probe original transport

`PicoProbeOriginals` uses the actual `AndroidAdapter.read_probe_snapshot` method
and its existing JSON, freshness, sequence and retry policy. An optional raw
reader applies only to Pico; the default SDK path and Phone path stay intact.
The feature owner must supply the same original candidate/Session/source guard,
clock and existing `AudioRawArchive`. This transport grants no live ownership
from a historical original or decoded expected-state object.

Each actual read reserves existing bounded raw capacity before `exec-out`. One
five-second anchor starts before the SDK call and includes every retry, guard,
reservation and returned-byte check. It never renews the caller's outer clock.
The fixed read-only script selects only the existing private probe file, rejects
symbolic links and multiple hardlinks, checks app ownership, and transfers at
most262145 file bytes. A fresh nonce frames actual before/after full stat values.
Only an exact complete regular0600 original up to262144 bytes reaches UTF8 and
the SDK parser. No missing tail or whole-file digest is invented.

Every obtained bounded wire return is durably retained before framing, UTF8,
JSON or candidate validation, including empty, malformed, oversize-prefix,
partial-timeout and late returns. Unknown delivery and unresolved raw capacity
remain owned; there is no retry after reader failure. Non-byte or unexpectedly
unbounded returns remain strongly retained in `UNCONFIRMED_RETURNS` and refuse.
Duplicate object keys and nonfinite JSON values refuse even if the SDK's ordinary
parser accepts them. Original SDK/binary getter substitution and nested reads
refuse before another query. Error text excludes target selectors and contents.

Twenty host cases use the canonical SDK and execute the verbatim shell script
against owned actual temporary files through an explicit `run-as` transport
facade. They include distinct literal retries, real symlink/hardlink/mode
refusals, capacity-before-query and clock-before-query cases. Together with34
unchanged mock-ADB SDK regressions they pass54/42.758s;54 loaded repository
sources keep SHA256 and all eight physical signature fields unchanged. Logs,
raw originals and source receipts remain under the private owning run
`overte-pico-resume-integration-20261102-24qkewqw`, label
`pico-probe-originals-final-20261103`. This is host transport qualification,
without an ADB server, device, compiler or laboratory execution.

The same Navigation C pre-input lease still needs explicit integration of this
reader and whole namespace accounting. The native producer, device behavior,
independent changed scenes, complete whole journey and final resource/host
retirement remain unqualified. No source-complete area is added.
