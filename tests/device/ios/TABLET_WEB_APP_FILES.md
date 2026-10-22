# Ordinary Tablet-only app input files

`tablet_web_app_files.py` supplies ordinary Script input bytes only. It creates
no World entity, directly changes no avatar/camera/policy, and supplies no
execution, rendered-page or cleanup verdict. Native source code remains
uncompiled and device outcomes are unqualified.

The original canonical inline HTML is 8887 bytes for the checked fixture and its
canonical data URL is 11888 bytes. Existing native Script files remain limited
to 8192 bytes each. The app therefore uses the existing four file names without
changing their schema or byte bound: a small `script.js`, two actual
`Script.require` modules containing consecutive unchanged data-URL segments, and
a metadata module. Concatenation reconstructs exactly the canonical
`inline_data_url(run,ticket,fixtureUrl)` bytes. No HTTP page becomes an inline
load receipt, and the native Sources/DOM/trace still independently prove the
actual decoded inline carrier, binding and document.

The real app has three ordinary Tablet.addButton controls: WEB TEST, WEB INLINE
and WEB RETURN. Their callbacks call only the existing public
Tablet.gotoWebScreen routes for the controlled HTTP index, canonical data URL
and controlled HTTP reference. The echo validator/responder is copied verbatim
from the pinned original parity client.js; no expected echo/counter is supplied.
Script ending disconnects its own original signal handlers and removes its own
three buttons. It deliberately never navigates or closes a page: the owning
normal UI flow must close its actually owned page first and separately prove
original policy/view/carrier/input/Script callback and VM retirement.

Every bundle has a separate actual native storage run UUID, distinct from the
feature run. Both values are retained unchanged: NativeScriptFiles receipts and
the actual native directory use the storage UUID, while the input code and
fixture resource ownership use the feature run. A later inline-open phase can
normally retire the first Script/buttons/files, then load a new owned bundle
with that phase's actual image challenge ticket. No native history or counter
is reset. Files cannot overwrite an earlier unknown bundle; the old native
absence and Script lifetime remain separate responsibilities.

Reserve persists only exclusive input metadata and original hashes. The outer
whole owner must persist its stage-issued intent before one stage attempt and
never retry an uncertain mutation. Verify performs independent original native
readback of all four byte strings. Release uses only the saved storage UUID and
owner token, observes actual directory absence, then retires its metadata;
whole cleanup must separately archive the genuine native absence receipts.

Five host tests execute the actual generated JavaScript through Node with
ordinary Tablet/Script boundary models, check all unchanged canonical inline
bytes and existing file bounds, real echo/invalid-message handling, disconnected
handlers, normal button routes, separate native storage generations, lost stage
without resending, and changed native file readback. They do not execute UIKit,
Overte native Script engines or a device. Actual returned TabletButtonProxy and
visual/control ownership is still the next source dependency.
