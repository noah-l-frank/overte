# Combined two-prefix quiet acquisition preparation

Combined JourneyFiles cleanup now reserves its four existing query owners before
the first animated manifest acquisition: animated manifest, still-PNG manifest,
file-work and owned-files. Reservation persists ordinary query intent only. It
creates no native acquisition, product effect, response or proof. The existing
Separate1 path and `observed()` behavior remain literal.

This avoids interleaving constructor/reservation work with the bounded group.
A preceding unqualified full Photos attempt retained a 1940 ms epoch/1940.537 ms
monotonic group; native elapsed was also 1940 ms. The largest gap, 958.153 ms,
was between still-PNG completion and the file-work start. The unchanged 1.5-second
original group check correctly rejected it. No original was retimed or retried.

Each internal token binds the actual kind/owner, slot, root/store, process/run,
lock, guard, shared observer/native source and retained child state/header.
Dispatch checks those bindings and the original current guards. Native sequence
continues to advance normally; the current native tail and NativeBefore/
HostBefore are taken only at actual dispatch. Existing send/recover/retain/
qualified and original-frame checks execute normally. Uncertain issued commands
are never sent again. Saved originals remain historical, and an expired old
group cannot acquire another nonce or a new clock envelope. The shared 25-second
operation budget, 1.5-second acquisitions/groups, 250 ms agreement and 3-second
quiet windows remain unchanged.

Six distinct component contracts passed, with source revisions recorded:

- `prepared08.log`: expired issued original rejected without replay or changed
  start clock. The following positive case failed on a fixture prefix error.
- `prepared09.log`: the first attempted fixture correction was attached to an
  unrouted upload-only hook; the same strict manifest check still rejected it.
- `prepared10.log`: corrected actual list producer and positive case passed in
  9.539 seconds. All four reserves had no request/start/proof; each dispatch
  sampled its real clock after a 1.6-second prebirth wait. The executed hook and
  stored original response were explicitly checked per nonce. A new response
  copy is filtered before AFC acquisition; no retained original or timestamp is
  changed, and actual host files remain unchanged.
- `prepared11.log`: four remaining cases passed in 32.241 seconds: changed
  prepared metadata, cold partial-reserved reopen with identical nonces,
  unchanged saved original and Separate1 refusal. The prior expired case was
  not repeated: its deadline rejects before the corrected packet filter is read.

Those files are under `.ios-host-tmp/snapshot-photos-end-resume-20261027-`.
The adapter source was identical across the component runs; only the new fixture
producer was corrected. All failed logs and original roots remain private.
Repeated attempts do not increase the six-case count.

The separate real host Pending/PNG/unlink/quiet/archive integration passed in
22.495 seconds in `integration12.log`. It observed twelve actual reservations
before their groups. Original epoch/monotonic/native spans were
168/167.821/168 ms, 153/153.059/153 ms and 158/158.181/158 ms. All three groups,
independent native/host quiet, one conditional unlink, original PNG inode/bytes
and pure archive replay passed. It adds no Upload, Photos, Return or End journey.
The affected three old Combined and six Separate cases passed in 110.390 seconds
in `legacy13.log`, including lost unlink returns, weak expiry, expired admission,
wrong manager/profile and foreign prefix/nonce cases. Each reviewed selection
used an unchanged outer 180; all new original roots were retained.

The five approved shared suites passed in 7.03 seconds in
`.ios-host-tmp/snapshot-prepared-quiet-resume-20261027-common14.log`;
versions, all 885 documentation files and whitespace checks passed. These are
contract/inventory checks and do not qualify another scenario or the separate
unqualified End2 work. Native/Qt/OS/SDK producers
remain declared host models. This packet qualifies the stated internal query/
file-channel behavior, not installed iOS execution or complete Feature 11.
Independent Actor/rendered fidelity, broader destination/whole composition and
source/Main/SDK/witness retirement remain separate obligations. The unqualified
PhotosEnd2/SDK-slot work is excluded from this packet.
