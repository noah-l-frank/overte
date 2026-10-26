# Ordinary Record input after a durable actual OS grant

`IOSAudioRuntime.authorized_starts` composes the existing recording owner and
its [original authorization collector](AUDIO_AUTHORIZATION_ORIGINALS.md). It
uses the same source lock, installed binding, normal token/viewport recipe and
native recording effects. Complete Audio capability admission remains closed.

Immediately before the ordinary Record intent, the coordinator acquires an
independent before-Start authorization cut. It saves the actual OS permission,
decision and host check before allowing the existing intent callback. Unknown
or denied OS permission prevents Record delivery. A later real grant may permit
a new decision only while the original operation has no Record intent. Each
decision keeps its original source reference; old grants are never retimed.

The actual SDK input runs under the existing final-transport guard. This guard
checks the original UI/intent/IO objects, exact Record intent, private owner and
source CAS metadata, and every grant-original hash/inode. It performs host/file
checks only, avoiding recursive SDK queries. UTC and monotonic elapsed time
from the actual acquisition beginning must both remain below 1.5 seconds,
including persistence and validation work. All ordinary candidate/token/source
checks still run. The actual first native recording event must also follow the
grant's original native clock and occur within 1.5 seconds. The common
25-second Audio API budget remains unchanged.

Once a Record intent exists, recovery can only resolve its actual product
effect. Lost, ignored, expired or otherwise uncertain input cannot trigger a
second click. A saved before-cut whose reference append was interrupted is
adopted with its original bytes/inode and no extra permission query; if it is
now too old, its decision is explicitly expired. Only a genuinely new cut can
authorize a later previously-undelivered input.

The same owned Start must then have an independent after-Start authorization
cut. A denied/unknown after result stays failed and cannot be replaced by a
later green resample. Repeated completed results are explicitly historical.
Pure parent/source/decision archives reconstruct no SDK/native reader, write
nothing and preserve all original references. A grant says only that this
ordinary input was authorized at the measured boundary; recording state comes
from the actual native history, and acoustic/peer success remains separate.

The 65-case decision/source/recording/background/admission selection passes.
It covers denied/unknown permission, lost/ignored Record, final-transport
expiry, same-byte replacement with a new inode, failed CAS, immutable original
recovery and pure replay. The separate connected page case passes normal
opening, grant, Start, automatic capture/play/drain/completion, PCM retirement
and restoration/Close. No extra Record command is sent.

A real-host-clock case initially failed the existing 250 ms native/host span
check after Start. Frame validation was reopening every raw original once per
query. It now reads each original once per validation call and runs the same
query/body, hash/inode, parent and packet checks on those fresh reads. No
success or parsed result survives that call. The unchanged real-host timing
case passes in 1.517 seconds and passes again in the compatibility selection;
the native clock offset remains original. Native/UI/SDK producers are still
explicit models, so this qualifies host logic/CPU behavior, not device timing
or native compilation.

Whole Audio still requires ordinary Settings/restart permission recovery,
independent acoustic/Actor evidence, loaded code/settings ownership and actual
page/callback/source/process/SDK retirement. Its ordinary session barrier keeps
every unfinished carrier owned.
