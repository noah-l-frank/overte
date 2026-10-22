# Passive iOS pointer dispatch originals

This source observes real `Application::notify` delivery around the original
`QApplication::notify` call. Every pointer dispatch records native entered,
normal returned and finally edges separately. A nested event loop can observe
zero contacts while the release handler still runs; positive pending dispatches
therefore prevent drainage. A thrown/unreturned handler poisons completeness.
A false normal Qt return remains an original false result. Pointer delivery and
physical end do not establish that a feature accepted an input or changed state.
Independent UI/entity/renderer/worker originals must establish those effects.

Startup occurs before the first actual product window. The original Qt window
count and global mouse buttons are retained; missing/late startup cannot become
a fabricated empty history. The getter never starts, resets or drains anything.
Devices and targets carry weak native identities. Their death does not end an
outstanding contact. Only actually delivered Mouse release or Touch end/cancel
can end one; reused point IDs require a new actual press. The original Qt mouse
button state and actual `MobileWorldTap` active state are additional checks.

The command accepts only schema version, command ID, action and run ID. Native
identity, clocks, counters, point IDs, positions and handler returns are read from
the actual dispatch. They cannot be supplied as desired observations.
`IOSPointerState.read(run)` preserves the separate native clock bracket through
the existing HTTP/AFC factory. `drained(before,current,after_epoch=...,
require_delivery=False)` validates the unchanged original prefix, complete startup
and actual current zero contacts/callbacks/buttons/world tap. An actor with no
input may use a complete known empty history. An owned uncertain input additionally
needs a real new matching `delivered(before,current,kind=...,position=...,
after_epoch=...)` press/end pair; an old release or a never-observed input cannot
supply that proof. These helpers do not close any whole feature or input journal.

This conservative ledger retains at most 1024 pointer dispatches, 3072 edges,
16 devices and 64 targets, including mouse moves. Unknown histories and overflow
permanently remain incomplete; no rollover/reset is permitted. Native JSON is
bounded to 1 MiB. A sufficiently long interactive process can exceed this bound
and must remain unqualified. No native execution, compiler or device was used.

Nine source host cases exercise actual Python callbacks and weak references with modeled
Qt DTO producers: touch/mouse end, doubleclick/cancel, nested same-event notify,
reads before a release returns, throw/finally, dead targets, actual WorldTap and
Qt button state, missing startup/unknown end/overflow, prefix mutation and strict
point-state typing. False dispatch returns remain distinguishable from accepted
feature effects. Native hooks are source-level prerequisites only.

Three additional transport cases exercise the existing fixture, Node probe,
HTTP command and AFC original-file paths. They preserve actual modeled
dispatch/end originals and separate native clock reads, reject supplied result
fields, consume each getter nonce once, retain unavailable status, refuse foreign
originals and block AFC after process replacement. They do not execute Qt.
