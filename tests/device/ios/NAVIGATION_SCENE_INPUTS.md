# Owned ordinary scene entry and return inputs

`navigation_scene_inputs.NavigationSceneInputs` journals the normal iOS Go To
scene transition over the existing `IOSNavigation`, `NativeUI` and `NativeInput`
implementation. Its candidate-bound runtime factory creates no session, launches
nothing and advertises no complete capability.

Entry first verifies the [durable original admission](NAVIGATION_ADMISSION_OWNER.md),
retains its exact journal hash and records `enter-issued` before the first normal
input. It uses only viewpoint A of the attached controlled marker scene. The
existing component records its address/tablet responsibility in this same
private journal before opening UI. Native input source/process continuity is
checked against the original admitted UI, including after reconstruction. The
original UI packets before and after each completed ordinary transition remain
retained. A current UI counter or clock cannot rewind behind the completed entry.
Normal input uses the existing continuity guard within a bounded 30-second call.

Return first records `return-checking`. It retains the original provider scene
history and both native clock brackets around a new whole-tree inventory,
current navigation and UI. Before issuing another ordinary Go To, the join
requires the actual committed unchanged editable map, exactly the five base
entities plus this run's marker, original controlled body bytes/hash and socket
receipt, matching imported scene generations, genuine marker document and
grounded pose at an allowed viewpoint. Additional entities, unsaved edits,
foreign/native source births, a visible address/tablet/error or stale acquisition
prevent the return input. These checks do not infer current ownership from the
requested destination or the prior entry acknowledgment.

The only return destination is the original static scene's viewpoint A. The
component retains its original context while admitting these two closed route
families; arbitrary URLs and native entity/pose/camera setters are unavailable.
`return-issued` is saved before delivery. Successful acknowledgment becomes
`return-delivered`, separately from an actual restored-world measurement.

A lost result leaves issued responsibility durable. Reopening cannot resend an
entry/return or restart a partial return gate. A completely retained matching
Address child can resolve a lost parent result: the full closed child decoder,
actual selected QML root, original destination, input counters and original UI
receipt must agree. Return additionally revalidates its original ownership gate.
Candidate continuity and parent/child CAS bytes remain checked; no new normal
input or UI/source acquisition is performed. Unknown or incomplete children stay
unresolved. A repeated acknowledged call returns only its delivery acknowledgment.
All records remain present; neither acknowledgment proves arrival, rendering,
resource absence or cleanup. The private format remains version 1.

This component currently supports the admitted original process only. The whole
Worlds coordinator still needs independently observed entry/return effects,
normal Places/bookmark/error recipes, process-death-qualified restart transfer,
independent publication, Web/GPU/HTTP callback drainage, repeated quiet cleanup
and final journal retirement. No complete feature operation triple is enabled.
Eleven host tests cover complete-child lost-return adoption without another
query and reject unknown children, ignored input as scene ownership,
partial source reads, changed input histories, unknown body/map contents and a
late return preflight despite complete retained originals. They model native/SDK
state, execute the actual Python normal input code
and use real private journals and loopback scene bytes. Native compilation and
device timing/functionality remain unverified.
