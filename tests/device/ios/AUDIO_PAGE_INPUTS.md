# Ordinary Audio page input recipe

`AudioPageInputs` reuses the existing `IOSAudioIO`, `NativeUI` and original
launcher selection codec. It observes actual UIKit elements and Qt control
tokens; it invokes no QML handler, synthetic success setter or preferred page.
This is an input recipe, not a complete page owner or feature result.

From an actual closed tablet it uses the ordinary toolbar button, reads the
current launcher root/page/count, visits only actually observed page indicators,
and opens an observed AUDIO button. The existing SETTINGS → Audio category is
the separate normal fallback. It waits for the actual `audio.page` row. Missing
routes, changed roots, duplicate elements, changed tokens and ignored inputs
fail; another feature's control is never guessed as Audio.

The mandatory caller hook runs before every real click and receives its label,
actual control, original UI snapshot and resolved element reference. The caller
must durably own that intent and reject repeating unknown delivery. The same
actual resolved object is used after its token check, without re-resolution.
A lost return stays a lost return; an observed already-open page only returns
UI data and does not invent an acknowledgement for the old action.

Close uses ordinary Home, restores the original observed launcher selection
and closes the tablet. Its returned visibility does not prove weak page death,
audio settings restoration, deferred callback drainage or SDK retirement. An
already-open Audio page has no new launcher original; its caller must preserve
that distinct starting state rather than pretending this recipe opened it.

Eight explicit host cases pass using real private caller-intent journals and
the actual normal UI/Audio/launcher codecs. The W3C and Qt/UIKit targets are
declared models. Cases cover pagination and settings fallback, exact selection
restoration, no-op observation, lost/ignored delivery, failed intent/foreground
guards, ambiguous elements and missing routes. No device or compiler runs.

The [version-three recording owner](AUDIO_PAGE_CYCLES.md) now joins this recipe
to its existing immutable original store and one-send recording/PCM lifetime.
Actual page/resource retirement remains separate. This recipe itself enables
no capability and changes no native control or default.
