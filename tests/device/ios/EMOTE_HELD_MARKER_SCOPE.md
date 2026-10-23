# Quiet Emote marker holders before process end

`IOSEmoteHeldMarkerScope` writes explicit marker-scope version two. The existing
version-one facade retains its full-resource-drain interpretation and refuses
version two; the new reader likewise refuses version one. No old carrier is
migrated, relabeled or rewritten. The original frame/storage versions, normal
Script/View input recipes and once-only delivery journals stay unchanged.

Version two distinguishes ended native callbacks and policy grants from actual
cached native/image/GPU holders. Its separate disposition version one preserves
every original context, descriptor and counter. Each pending holder group has a
private original and a deterministic terminal-compatible resource reference.
No pending count is set to zero. Full rendered admission requires all original
version-five resource kinds, apart from optional native presentation. Partial
setup remains explicit and cannot supply successful render admission.

Every quiet cut requires all callbacks and policy grants to have actually
retired. The selected candidate restarts if any context, descriptor, counter or
resource-event timestamp changes. At least three actual original cuts must span
three seconds after the first acquisition and before the final acquisition.
Host epoch/monotonic and native epoch/monotonic gaps must independently agree
within 500 milliseconds; none may reach sixty seconds. Historical reconstruction
checks the same ordered window and exact original contexts again. A new holder
event cannot borrow an earlier quiet prefix.

The native version-five source in `ios/web/IOSWebClosureTrace.h` records creation
and last event timestamps only at actual context/lease events. Observing it does
not update a context's event timestamp. Its QImage carrier owns the original
allocation until the final implicit copy releases it. These existing gated
native sources were inspected, not changed or compiled. A new host producer
models those retained cached holders and event timestamps before producing
originals; no retained packet is changed to fit a later phase.

Four policy cases and three private-input cases pass. They reject callbacks,
policy grants, missing render admission, foreign births/scopes and literal
version substitution, while retaining unknown input delivery without replay.
Three connected normal marker cases pass in 12.836 seconds: real normal
Script-manager/picker recipes, actual staged JavaScript/companion execution in
host Node, Script worker/end originals, native-file absence, original quiet
windows, retained cache counters, repeated input-free cleanup, lost Stop return
without another Stop, changed quiet-order rejection, host-epoch disagreement,
and a real modeled new-holder event restarting the existing quiet candidate.

The scope's `released` phase in version two means its ordinary input/file owner
is released while listed native holders remain owned. This is not Complete.
The whole Emote coordinator, live terminal/publication join, actual process/SDK
end and canonical routing must still consume this version explicitly. Complete
capability admission stays closed. Native compilation, physical devices and
physical acquisition/API deadlines remain unqualified.
