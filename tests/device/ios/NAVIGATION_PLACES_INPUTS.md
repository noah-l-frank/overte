# Original normal Places input recipes

`navigation_places_inputs.IOSPlacesFlow` uses the existing version-2 native
Places controls and normal Qt pointer/IME transport. The factory binds it to the
existing admitted candidate, original UI source instance and source lock. It
creates no session, launches nothing and does not enable a complete feature.

On an already owned open Places page it implements ordinary add/cancel,
rename/cancel, owned bookmark visit/delete, directory search and owned directory
selection. Calls use the unchanged common action inventory and actual supplied
run/ticket/fixture URL. Only run-scoped names/queries and the controlled A/B
addresses are accepted. Root/process/source identity, original observation and
input counters, original field values and current token references remain bound.

The independent typed native model is read before the actual UI capture. Their
original root/source/clock join establishes current tab, popup, dialog original
name/address and draft before a normal input. Bookmark add refuses a conflicting
name or a current address outside A. Rename/visit/delete require the actual owned
row and address. Search edits the real field and leaves product filtering to QML;
the adapter does not calculate a wanted result list. Unowned search drafts are
refused. Row selection retains its original reference through delivery, so a
changed address cannot be recaptured and accepted as the selected owned row.

Every low-level input first invokes the required private `intent` callback with
its unchanged original UI packet, selected reference and actual action call.
The [scoped action owner](NAVIGATION_PLACES_ACTIONS.md) now durably saves it before
returning and retains whole-call responsibility. Failure prevents
delivery. The native transport separately recaptures and validates that exact
reference, then sends once. A subsequent original verifies the consumed input
sequence. Only read waits repeat; no failed or uncertain input is retried.

These recipes return delivery acknowledgment only. Independent original
bookmarks/files, loaded models, HTTP consumption and actual rendered arrival
still determine feature state. Tablet/address ownership, initial open/close,
named lookup/error handling, restart transfer and whole-run failure/recovery,
independent publication and repeated cleanup remain with the unfinished Worlds
coordinator. This open-page owner is not the complete Worlds coordinator.

Host tests execute real Python HTTP/AFC codecs, private atomic intent journals
and temporary bookmark files with modeled native Qt controls/models. They check
cancellation, rename/delete preserving unowned entries, ignored ACKs, failed
journal writes, changed roots, collisions, foreign calls and source rollback.
Native compilation, actual product behavior/timing and devices remain unverified.
