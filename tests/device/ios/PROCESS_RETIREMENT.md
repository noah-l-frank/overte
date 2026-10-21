# Original iOS process-retirement quiet windows

`IOSProcessRetirement` composes the read-only numeric-PID source with independent
role/stage ownership. It cannot stop/launch a process, produce feature facts or
remove runtime metadata. `IOSGraphicsRuntime._graphics_process_retirement`
requires explicit full candidate binding, source, run, role, stage and the
existing source lock. Only a retiring/retired existing SDK session is admitted;
no foreground native query or session creation is possible after app death.

Each `advance()` persists its passive-read responsibility first, obtains a new
original OS/DVT packet and separate controller acquisition receipt, and retains
both in an immutable hash-referenced record. Reconstructing restores the actual
original nonce/counter/anchor floor. Lost uncommitted reads are explicitly
abandoned and reset quiet credit. A committed record with a lost return is
adopted unchanged; it is never turned into a fresh read. Every successful
`advance()` still performs another actual OS read.

A complete window needs at least three independently acquired agreeing absence
observations and at least three seconds from the first acquisition's **end** to
the final acquisition's **start** on all four original clocks: Node host UTC,
Node monotonic, controller UTC and controller monotonic. Absolute epochs may
differ. Numeric old-PID presence, replacement bundle PID or conflicting OS state
resets the window. Initial request time and a frozen Node clock earn no credit.
Windows are bounded to twenty seconds/81 observations, with eight attempts and
256 total records. An aged attempt creates a new window and keeps earlier
originals. No returned input, expected absence or requested PID fills a read.

`current()` checks the original controller acquisition's age without changing
any timestamp; a completed historical window alone supplies no current fact.
Even after completion another `advance()` makes a new read and may revoke quiet
credit on presence. Pure `archive()` accepts an exact original record map for
post-removal validation, does not query any SDK and cannot mint a new receipt.

`IOSGraphicsLifetime.observe_restored` supplies the separate pre-stop part:
both roles observe original world/avatar/camera restoration, committed scene
work and their own complete native Web ledger. A retained paused software image
remains `held` with its actual nonzero counters. Even an all-zero single
snapshot leaves the lifetime phase `releasing` and a non-complete window. The
later process proof is separate; no native post-death zero packet is invented.
The full final stop/paired archive coordinator must still compose these APIs.

Twenty-nine selected no-build host cases cover the new owner, producer consumer,
canonical stopped-session factories and restored-world snapshots. They use
actual private files/loopback fixture requests with synthetic native/OS data.
The source-only plugin remains uninstalled; native code is uncompiled and
physical iOS/process/resource behavior is unqualified.
