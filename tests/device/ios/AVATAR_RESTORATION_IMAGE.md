# Avatar post-cleanup output

`IOSAvatarRestorationFrames` uses the committed common raw-frame owner's closed
Avatar profile. It preserves independent Avatar World and Renderer originals,
untouched private PNGs, exact GPU ownership and the original native clock joins.
Its initial fence must precede any marker setup. Its cleanup fence requires the
actual released marker scope and must follow the separate actual native endpoint
barrier for the resources being retired.

`avatar_restoration_image.restored` first applies the common actual marker
projection, original/restored camera and Domain, tree, GPU fence and native
barrier checks. It then compares every RGBA output pixel against the untouched
initial fence. Any difference refuses qualification, including a single pixel
outside both the marker crop and the avatar bounding box. It creates no
background, crop substitute or noise allowance. Both original frame hashes and
references remain in its version 1 measurement through the unchanged common
marker measurement.

This strict comparison can refuse legitimate idle animation or an unrelated
scene change. Without original draw attribution those changes cannot safely be
distinguished from stale Avatar or wearable pixels. That limitation is explicit;
unchanged pixels still do not replace separate entity weak expiry, timer and Qt
callback closure, account retirement, native quiet intervals or paired cleanup.
No device robustness or native compilation is claimed by these host tests.
