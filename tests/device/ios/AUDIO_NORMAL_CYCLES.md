# Original normal Audio mute and automatic recording cycles

This cycle extension introduced owner and observation version 2. The current
[page composition writes version 3](AUDIO_PAGE_CYCLES.md), reads all three
literal versions, and retains the unchanged immutable frame and
native source schemas. Literal-1 owners retain their prior supported inputs;
their original files are neither rewritten nor retimed. The current installed
runtime constructs the same owner under the existing candidate/process/source
binding and held Script source lock. The Audio page must already be open.
This component advertises no complete Audio capability.

## Normal inputs and measured results

`act(ticket, 'mute', enabled=True|False)` binds the actual active fixture input,
actual current audio mode and freshly observed control token. The existing
ordinary Audio recipe scrolls the real page if needed and toggles only when
the original native state differs. Intent is durable before the single normal
click. The result comes from a separately acquired native Audio observation
joined to the original UI checkbox; the requested boolean is never returned as
an effect. An already matching setting emits no mute click and preserves its
original cycle. Lost returns are resolved from new observations without a
second toggle. A mismatched fixture value or reused ticket fails before input.

A normal Start while originally muted now qualifies the actual new native
error cycle: one `microphone-muted` event, no active recording, zero original
captured/played/buffered frames and the same actual muted state. A different
native error or an unexpected capturing cycle fails. Both the rejected Start
and a normal mute retain two separate originals at least 300 ms apart on
original native and host clocks. Requested sleep alone supplies no quiet.

Muting an owned active capture must retain its exact original capturing prefix,
append actual cancellation with `microphone-muted`, and empty the native live
buffers. Unmuting the stopped cycle preserves its previous error/cancellation
history without starting or replaying input. These are live recording buffer
facts; they do not prove absence of independently retained tap files or memory.

`act(ticket, 'await-completion')` sends no Stop or Preview command. It links to
the exact successful normal Start original in this owner's completed operation
membership, then observes the product's automatic capturing, playing, draining
and completed history under the unchanged 25-second API budget. It requires
the same native cycle, unchanged original event prefix, full valid played and
captured frame counts and zero terminal live buffers. An existing foreign
capture, rejected Start, actual error, missing completion or missing original
cannot be promoted to completion. Successful historical repeats preserve the
old event clocks; new observation envelopes do not retime product events.

## PCM and recovery join

The connected host case performs ordinary mute, original rejected Start,
ordinary unmute, a second normal Start and automatic completion, then uses the
existing PCM lease. It retains exact original input/sink bytes, links the lease
to that second Start's actual ticket/cycle/reference, releases once and requires
independent native file/memory absence. Both recording and PCM archives replay
without changing the original history. Source start/cancel, PCM storage,
allocation/release and owned automatic completion remain separate proofs.

Saved-before-parent-append recovery reuses the actual immutable original inode
and bytes. Lost or ignored normal input remains pending without resend. The
strict source history, phase, clock, file inventory and candidate guards remain;
the native AudioClient product implementation is unchanged.

Fifty error/mute/completion/legacy/PCM host cases pass across the focused
selections, including the connected mute-to-PCM case and literal-1 read grammar.
Private files, file identities,
CAS journals, codecs and normal input recipes execute on the host; native
audio, UIKit, SDK, automatic timer and clock producers are declared models. No
microphone, physical sound, native compiler, device or simulator is used.

The [ordinary page recipe](AUDIO_PAGE_INPUTS.md) now supplies normal toolbar,
launcher, direct/fallback entry and selection restoration inputs. Its durable
page/recording composition is now joined in version three; actual lifetime
retirement remains required, along with current microphone
authorization, background/permission recovery, independent acoustic/Actor
publication and full callback/source/page/process/SDK retirement. Accepted
loopback sink writes are not acoustic playback. All complete capability gates
remain closed and the fourteen-area completion count is unchanged.
