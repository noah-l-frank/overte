# Native world and tablet Web video journeys

`web-video-parity` contains separate world and tablet modules after the existing
launch prerequisite. Both use the repository-owned reference from
[`fixture/parity`](fixture/parity/README.md), through normal Running Scripts and
Web controls. They do not load a substitute browser or cooperative mock bridge.

The native adapter must implement and explicitly advertise all five operations:

- `web.reference.open`: load `/parity/client.js` through Running Scripts and its
  ordinary consent flow, then expose the requested world or tablet surface.
- `web.reference.play`: activate that surface's actual Play control.
- `web.reference.pause`: activate the actual Pause control.
- `web.reference.seek`: activate the reference button for red at 0s or blue at 4s;
  the caller selects the phase opposite the observed paused frame.
- `web.reference.close`: close the owned surface and stop only its diagnostic
  script through normal controls. Partial opens must also be cleaned up.

These actions return only delivery acknowledgments. The adapter never returns a
playback verdict. Existing adapters do not gain these capabilities automatically.
A missing operation is a reported skip; `--require-complete` fails that run.
There is no physical acceptance or activation recorded by this change.

For a separately authorized future run, start the existing fixture server and
use `webParity.scriptUrl` from its ready file as
`OVERTE_E2E_WEB_REFERENCE_SCRIPT_URL`. Supply an explicit native capture rectangle
for each surface with `OVERTE_E2E_WEB_VIDEO_ROIS`, for example:

```json
{"world": [80, 60, 464, 276], "tablet": [80, 60, 464, 276]}
```

Those example coordinates are not device defaults. Frame the complete reference
video, excluding controls, in a fixed front-facing camera. The analyzer requires
at least 96x54 pixels with the correct aspect ratio. Geometry errors are capture
infrastructure errors; they are not evidence of a product failure. Never replace
an unusable native capture with a generated image, DOM state or player time.

The module uses the existing native `artifact.screenshot` operation and retains
every immutable image, SHA256, phase and actual monotonic capture interval.
It checks process/foreground continuity before and after every capture.

1. Play: 17 captures must show the encoded counter, moving square, all three
   color phases and sufficient real duration.
2. Pause: six consecutive captures over at least two seconds must show one valid
   stable encoded frame within a bounded settling period. A frame already in
   flight at the tap is retained and may retire; continuous playback still fails.
   Black/missing video is not a pause observation.
3. Seek: choose 0s or 4s to differ from that actual paused frame. A bounded wait
   requires the target encoded frame, followed by six stable captures there.
   A no-op seek cannot pass by coincidence.
4. Resume: 17 further captures must independently show moving video and all
   color phases again.

A successful path retains at least 46 captures; a delayed pause or seek also
retains every intermediate native image. A frozen texture with moving surrounding DOM or an
advancing player clock fails. Normal cleanup runs after partial failures too;
cleanup failure prevents a completed control-sequence verdict.

The existing runner owns reservation, installed-artifact binding, module timeout,
private diagnostics, final cleanup, JSON and JUnit. Use its independent expected
source and artifact flags with each newly built E2E candidate. No image hash or
bundle ID alone is installed-code identity. A bounded pixel module pass does not
qualify text input, audible audio, Web bridge, lifecycle or all 14 feature
areas. Those need their own journeys and observations.

Hardware-free regression checks exercise the actual journey and pixel analyzer
with only native action/capture and clock seams substituted:

```sh
python3 tests/run-unittest-suite.py tests/device/self_tests --pattern test_web_video_journey.py
```

The synthetic test images qualify the assertion logic only. They are never
reachable from the production module as a capture fallback.
