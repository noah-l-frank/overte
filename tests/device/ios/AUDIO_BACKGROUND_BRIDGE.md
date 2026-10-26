# Continue the same recording parent after its original interruption

Version four of the existing Audio recording owner reads literal versions one
through four. Only its new grammar admits one explicit background transition.
All other consecutive native cuts retain the existing lifecycle-equality guard.
The parent cannot continue normal input while its bridge is unfinished.

`IOSAudioRuntime.resume_recording` composes the original
[background child](AUDIO_BACKGROUND.md) under the parent's existing source lock.
Lost Home/activation results recover through that OS-only child before parent
continuation; neither input is repeated. The exact completed child envelope,
original candidate bundle and owned Start prefix are durable before the parent
may acquire its next cut. No child clocks or samples are copied into a new
freshness envelope.

The fresh parent foreground acquisition must follow the child's actual final
native and host cut. It preserves that cancelled Audio state and ordinary input
counter. Its embedded proof links the child's original files and immutable
before-reference. The before reference must be the immediately preceding parent
record; the resulting bridge reference belongs to the parent's own journal.
Changing or removing a child source, changing its Start prefix, or detaching the
bridge from that journal prevents replay. The actual saved child metadata must
remain present and identical as well.

Pure replay uses a checked exact-prefix codec view. It revalidates every old
record and the unchanged operation grammar, and matches both lists to exact
prefixes of the complete parent. It supplies no SDK, native reader or new state
manager. The outer parent still validates its entire current inventory,
including later originals; the prefix view cannot conceal an orphan file.
This also avoids treating later legitimate originals as missing prefix-owned
files. A stored bridge cut interrupted before its reference append is adopted
with unchanged original bytes and inode, without new native or OS work.

Thirteen focused bridge/legacy cases pass. The canonical composition exercises
normal page opening, Start, background cancellation, same-process resume,
the new parent cut and ordinary Home/page/Close. It also exercises lost Home
recovery, repeated historical adoption, failed CAS, missing child sources,
incomplete children, prefix substitution and a version-three page archive.
The separate 53-case mute/error/completion/PCM/page/admission selection passes;
earlier source/recording/background cases remain passing. Literal one/two tests
select their real writer grammar before constructing an owner, preserving old
originals rather than relabeling new state as legacy. Native/UI/SDK/clocks are
explicit models; private files, original codecs, locks and normal request paths
run. No device or native compilation is qualified.

This completes the recording interruption join, not the whole Audio area.
Current microphone authorization, independent Actor/acoustic evidence and actual
loaded code, settings, page, callback, source and process/SDK retirement remain
required. The ordinary [session barrier](AUDIO_SESSION_OWNERSHIP.md) retains
unfinished responsibility; complete Audio admission remains closed.
