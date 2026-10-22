# Original Pico host-input read seal

Every adapter instance still runs the unchanged original Pico candidate verifier
before admitting a candidate. The original arguments (including types and all
flags), environment and input inventory are frozen before that verification.
A changed argument during verification fails before device access.

After successful verification, `CandidateReadSeal` opens and hashes the original
APK, identity, expected inputs, evidence envelope, every original build receipt,
aapt/apksigner launchers and every original network-policy and decoder/JAR/JVM
file reported by that verifier. Each read-only descriptor has `CLOEXEC`; the
original kernel inode remains held for this adapter lifetime. Initial SHA-256,
path resolution and complete device/inode/mode/uid/gid/size/mtime/ctime/nlink
identity must agree before and after hashing. No candidate is admitted by this
helper and it cannot refresh its original inputs.

Subsequent guards compare the original held descriptor and actual current path
with that same kernel identity, and recheck all argument values/types,
environment, source-policy paths, actual tool resolution and the original
original decoder dependency inventory. The cold SDK walk has hard limits of
128 directories, 4096 total entries and depth 16; at most 256 files and 128
directories may be held. Original directory descriptors/ctime detect additions
and removals, so a query never recursively rescans the SDK or JVM. Kernel ctime detects writes even when
original bytes and mtime are restored; a held descriptor prevents inode reuse
from hiding a replacement. Missing, new, replaced, rewritten or changed inputs
permanently poison this lifetime and close its descriptors. Reversing a change
does not revive a failed seal. Explicit close and object finalization also close
all still-owned descriptors. A lost descriptor number naming a foreign file
is refused and that unrelated replacement is left open. Reduced component test seams lacking the complete original
network digest inventory keep the original full verifier on every call.

This removes repeated tool execution over already verified unchanged host
inputs. It does not cache installation, process, OpenXR or foreground facts.
The existing live PackageManager path checks, two installed APK SHA-256 reads,
original process/start binding and OpenXR identity guards remain in place.
The final host-input check still brackets those live installed-byte reads.
No verifier, policy, expected digest, native freshness bound or CI rule changes.

The inventory has the same external-input boundary as the original verifier's
reported digests. Arbitrary additional files read by a tool outside that
original inventory are not newly qualified here. Host cases use explicit
synthetic APKs, signing/decoder tools and transport; they establish neither real
SDK signing nor physical device performance. A live Android candidate remains
subject to the complete original cold verifier and actual installed-byte and
process guards.

Focused checks from `android/vr/pico/tests/device`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_native_execution_binding -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_normal_scripts.PicoNormalScriptsTests.test_pico_chat_active_original_owner_guard_still_allows_a_fresh_complete_query_bundle -v
```

These exercise the actual original verifier and dispatch path, decoder and
physical policy mutations, complete original build receipts, argument and
in-place type changes, atomic same-byte replacement, restored mtime writes,
new nested JARs and original JVM bytes, tool environment, immutable returned
results, read-only/CLOEXEC descriptors, no descriptor leak on rejected initial
hashes, permanent failure, explicit release and actual object finalization.
The complete original Pico Chat source quartet uses the actual monotonic clock;
no clock mock or wider timeout supplies its successful result.
