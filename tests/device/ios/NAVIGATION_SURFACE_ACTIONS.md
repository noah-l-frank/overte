# Ordinary Places surface ownership

`navigation_surface_actions.NavigationSurfaceActions` connects normal UIKit/W3C
Open/Home/Places/Close inputs to one fixed private journal on the existing
candidate-bound session. It accepts actual `open` and `close` journey calls only,
retains their original fixture phases, and rejects a changed candidate, provider,
source history, or call before issuing another input.

The owner checkpoints before every mutating W3C click and session input release,
including the actual resolved element path and a separate original native UI
survey. It retains existing IOSNavigation's component ownership before surface
creation. Acknowledging Open additionally requires the actual native Places-v2
page root and component, with no draft popup. Close checks that exact owned root
before normal input and requires the actual tablet to be hidden afterward.
An existing unrelated tablet, a replaced page, an ignored Places input, or a
covered/changed surface cannot become a successful owned transition.

One call has a bounded 30-second deadline. Original UI observation counters,
input counters, process identity, elapsed time, and native timestamps continue
across retained inputs and calls. The first phase/intent survives failures before
or after transport; uncertain calls block both retries and new tickets. A repeat
of the latest acknowledged call returns its old delivery acknowledgment only.

The owner neither deletes its journal nor reports full cleanup. It establishes
surface/input ownership only; original scene arrivals, saved bookmarks, missing
lookup and dismissal, restart transfer, independent actor publication, pending
callbacks and repeated quiet cleanup remain duties of the whole Worlds owner.
The candidate-qualified factory is IOSNavigationRuntime._navigation_surface_actions.
Native compilation and devices remain unverified.

Nine host counterexamples exercise genuine fixture phases, actual private
journals, and real Python W3C/native-input codecs with modeled SDK/Qt state.
