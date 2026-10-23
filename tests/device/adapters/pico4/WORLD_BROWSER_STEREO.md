# Original world-browser stereo ownership

Feature 6 remains partial. The existing `PicoBrowserStereo` owner and common
browser image verifier now accept the explicit `world` surface. They reuse the
same `NavigationArrival`, original two-eye world-render capture, PNG writer,
native memory/receipt retirement and enclosing ScriptSourceLock. They do not
create another capture system or advertise a complete feature capability.

The default tablet wire forms, artifact names and acquisition order remain
unchanged. World ownership uses separate v1 discriminators:
`picoWorldBrowserStereoOwnerVersion` and `picoWorldBrowserStereoSourceVersion`.
World journal names start with `world-web-`; tablet names retain `tablet-web-`.
Both envelopes reject the other surface, mixed discriminators and boolean
version aliases. The selected surface is also sealed for a warm owner.

The actual private `_browser_stereo(..., surface='world')` factory selects the
existing passive `PicoWorldBrowserIO` and canonical render/source lock. Before
capture it reads the original world document and passive `measure-ray` packet.
After capture it obtains a new measurement and independently reads the current
document again. The measurements retain the existing v3 native world-ray wire
form and v1 entity/item geometry; no new C++ producer is introduced.

Every world measurement must match the original current native view's complete
handle/creation/grant/page/URL identity, native instance, entity source identity,
initial source URL and actual consumed DOM response. The original entity UUID,
geometry, item quad, DPI/capped surface and measured target remain unchanged
across the exposure. Tracking calibration and physical head pose remain actual
separate observations; they are not required to freeze. Each measured head
must agree with the corresponding original HMD bracket within the existing
stereo pose bound. Current graphics observations independently require the
tablet closed and retain actual VR-keyboard ownership.

Original native/DOM/ray clocks must precede or follow the real capture in their
respective brackets. The existing 1500 ms complete freshness bracket and 20 s
owning capture deadline remain unchanged. The complete acquired world frame is
durably retained before a document/entity disagreement is refused. A captured
but unresolved frame does not cause another GPU request after reconstruction.
Original image bytes and physical stamps are checked again on every retirement
or archive read; an immutable decoder memo cannot validate changed originals.

The common Journey accepts `pico-stereo-world-web-v1` only for `world-web` and
keeps `pico-stereo-tablet-web-v1` for `tablet-web`. It uses the same independent
per-eye challenge/subject verifier and existing capture/query replay limits.
The extra world measurement nonces/cursors enter those existing replay guards.
The original full capture is published without cropping or eye duplication.
Trusted external pixel regions still select the image areas to measure. This
packet does not claim a projection/draw/material qualification for arbitrary
billboard, pulse, alpha or occluded Web entities. In particular, the original
pointer's raw-DPI mapping must not be substituted for the renderer's full
entity UV projection.

The six new owning cases pass in 6.155 s at the registered selector; coverage
passes in 0.090 s with 229 additive catalog groups. Fourteen existing tablet
stereo/ownership/common-verifier cases pass in 23.232 s. Four repository suites
pass in 2.793 s; registry, probe syntax and whitespace checks pass. All 13 code
and test input files remain unchanged during this final selection. The first
standalone positive passes in 0.925 s. Two earlier red commands are retained:
one new fixture incorrectly supplied null text metadata for a text control;
one counterexample omitted required Journey constructor arguments. Both were
test-only corrections; production source rules were preserved.

The tests exercise actual Python consumers, physical original files, the common
Journey, private factory and capture/retirement owners. Entity, native DOM,
Android, Qt, HMD, GPU and renderer producers and their pixels are explicit host
seams. No complete application/APK or physical device qualification follows.
Original failed-path and successful-path files, source hashes and logs are
retained in private local evidence.

Next compose normal world Script load/phase ownership, existing calibrated ray
and IME input, independent HTTP/DOM/native observations, this stereo owner and
the separate original world VM profile. The independent actor/publisher and
whole Script/Web/entity/timer/callback/resource retirement remain unfinished.
