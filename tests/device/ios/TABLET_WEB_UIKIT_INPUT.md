# Native UIKit input observation

This separate E2E-only producer observes the actual runtime application's
`sendEvent:` method. It is not the Qt Pointer/Keys source or a DOM event ledger.
The source hook and passive transport are integrated for host inspection. Native
code has not been compiled or executed on a device. This prerequisite does not
qualify the complete Tablet Web area.

`IOSUIKitInputObservation.h` is included only by the existing ARC-enabled
`IOSWebView.mm`. Its startup hook runs under the actual nonempty
`--testScript` and `--testResultsLocation` flags. `interface/src/main.cpp:496`
first constructs a temporary QCoreApplication and later, at line 540, the
real Application/QApplication. A Q_COREAPP_STARTUP_FUNCTION can run for both;
it is deliberately NOT used to install this hook. Instead the two existing
iOS E2E first-window initializers in `interface/src/Application.cpp:296` and
`:303` (the mutually exclusive GL/Vulkan branches) call a pure-C++ bridge,
implemented in the existing ARC translation unit, after the QApplication base
has fully constructed and immediately before `new MainWindow` or `new VKWindow`.
The source checks the actual main thread and QApplication/platform availability,
then refuses installation after any Qt or UIKit window exists. This is a
source-level construction-order argument, not a native execution result or a
claim to observe UIKit activity before installation. Only actual target births
and complete contacts observed after installation can qualify. Queries cannot
install, retry, reset, or repair it. An inherited implementation is shadowed on the actual application class;
the superclass method is not modified. An owned implementation is replaced on
that same runtime class. Method signature, original IMP, installation race, and
later method replacement are checked. The recorded application class is actual
runtime metadata, not an assumed Qt private implementation name.

The wrapper calls the saved original IMP exactly once with the original
application, selector, and event. Observer exceptions are caught outside that
call. The original application's exception propagates unchanged through
`@finally`. Entered, normal return, and finally are distinct original clocks;
nested dispatches keep separate pending entries. Event arguments are unsafe
unretained. Temporary event collections and UIView ancestry walks end before
forwarding. Persistent rows contain only zeroing weak references and immutable
metadata. There is no recognizer, input injection, method exchange, timer,
notification-based synthetic end, or read-side reinstallation.

Object births differ from logical contact lifetimes. Reusing an ended UITouch
or UIPress starts a new contact UUID only on a real began phase. UIKit may keep
an ended touch or UIEvent alive in a cache. Ended/cancelled and returned/finally
therefore prove neither object death nor native resource retirement. Object
expiry is recorded only after its actual zeroing weak reference becomes nil.
An unknown phase, missing began, duplicate active contact, changed target,
overflow, clock discontinuity, or changed hook leaves completeness false for
that process; no recovery erases the history.

A newly created genuine Tablet WKWebView receives an immutable original native
source association at its real view-created callsite. Touch/press ancestry is
compared against that actual weak WK object. An association contains the
original handle, creation, policy grant and SourceStamp; a read request cannot
assign ownership. Unknown targets remain unowned. UIWindow births remain
separate from ordinary UIView births. Hardware presses expose only opaque
object and lifetime IDs and phases. Coordinates, pressure, touch timestamps,
keys, characters, text, composition contents, lengths, and object descriptions
are never read or serialized.

Version 2 additionally observes the actual ordinary source-token UIButton for a
source-qualified Tablet app button. A separate ARC bridge is invoked by the
existing normal-control factory after its native button creation. It re-reads
the real Qt control for the exact current source token and requires its genuine
returned proxy/model/root/visual metadata. The target uses a closed `qtControl`
variant; it has no invented WK handle, navigation, policy grant or document.
Its actual fixture property remains input provenance. The independent button
original must match the native target's source instance, root instance, button
UUID, QML control birth, semantic generation, fixture and real Script caller.

Changing a Qt source changes the existing normal-control token. The unchanged
factory removes the old actual UIButton from its superview and dictionary
before creating a new native button. A UIKit-held old object/contact keeps its
old original association and weak responsibility. Rebinding the same live
physical UIButton to a different Qt identity is rejected; ordinary Script
generation changes require no rewrite of native target/contact history.

A later whole-area owner must independently join this original source to the
actual process, native trace/Sources records, normal UIKit input intent, trusted
DOM observations and actual presentation. A quiet interval needs original
same-source native clocks and host acquisition brackets. A zero active-contact
inventory only proves contact/dispatch quiescence. Owned WK/input objects still
held by UIKit remain unresolved. Event weak death does not prove a rendered
frame was removed. Final process death, when necessary, must use an explicit
observable-cleanup then normal terminal Stop protocol with independent death
receipts; this source does not bypass current session Stop guards or fabricate
cleanup facts. Pointer/Qt Keys and native editor/keyboard/presentation duties
remain separate.

The current closed source is `iosUIKitInputVersion:2`, with exact historical
version 1 reading and live version 2 required, action
`feature-ios-uikit-input`, with a 2 MiB original JSON bound. The existing generic
decoder bound remains unchanged. `FeatureObservation.uikit_input(clock)` uses
the existing actual private AFC file and separate original native process-clock
bracket. The probe issues each query nonce once; a missing native getter returns
an unavailable envelope rather than an empty contact inventory.

The Python reader retains exact immutable object/target/contact/dispatch
prefixes. Newly filled normal-return/finally/end/weak-expiry timestamps and new
rows cannot precede the previous actual snapshot's clockAfter. Genuine contact
began and event object birth precede their original dispatch use. Full opaque
hit-view-to-owned-target ancestry is retained and each observed owned ancestor participates
in positive weak retirement. An ended cached object can begin a later distinct
contact without changing its original object birth.

Host verification: seven pure original/chronology/transport tests, seven actual
source/startup boundary checks and three actual Node/probe/fixture/AFC route
tests. These tests include UIPress, reused ended touches, exceptional original
return versus finally, and unknown outsider targets. Native startup viability
and UIKit weak-release timing still require a separately authorized real-device
qualification after compilation.
