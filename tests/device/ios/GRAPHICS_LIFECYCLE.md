# Ordinary iOS Graphics background and activation

`graphics_lifecycle.py` owns the shared `background-resume` input through a
version-1 private one-send ledger. The initially measured settings, native birth,
PID and lifecycle counters are preserved. Owned Graphics/Go To/menu UI must be
closed first. Ordinary indefinite Home input and ordinary same-process
activation each require durable intent before dispatch. SDK input replies are
not effects: original OS app state/PID must show background and foreground,
and a newly acquired original native snapshot must show both lifecycle counter
increments, unchanged launch count and unchanged Graphics preferences.

`IOSGraphicsRuntime._graphics_lifecycle_status` reads the existing session,
canonical candidate/source continuity with `allow_background=True`, original
SDK app state, and candidate/source continuity again. A process change, stopped
app, boolean app-state value or inconsistent foreground/app-state pair fails.
It never requires HTTP/AFC native UI while the app is backgrounded. The ordinary
activation follows the existing `iosE2ELaunchCompleted` path; no forced restart,
new WebDriver session, install or launch-argument change is introduced.

A lost Home reply can leave the application backgrounded. Reconstruction uses
validated original scene/preference archives and the independent OS/source
status guard; it does not reconstruct the foreground-only native reader until
actual foreground is observed. Existing issued Home/activation phases receive
reads only. Lost activation, ignored Home and ignored activation cannot trigger
a second lifecycle input. A replaced native source or changed preferences still
fails after OS foreground. Final ledger retirement requires a fresh native read
and observed completion; it does not claim GPU/Web or whole-run quiet cleanup.

The ownership decomposition was reviewed at frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`. iOS canonical source/PID continuity,
OS status, ordinary activation and background-safe reconstruction are separate
platform implementations. Runtime input forwarding also validates the owned
ledger phase and restores the surrounding feature operation after dispatch.

Nine lifecycle cases plus preference/sample/scene/history regressions pass
(42 selected no-build tests). The tests use actual ordinary iOS UI/AFC framing
for scene setup, real loopback scene responses and private ownership files;
native settings/lifecycle, OS SDK and candidate boundaries are synthetic.
Counterexamples include failed intent persistence, lost/ignored inputs, changed
OS PID, missing native transition counters and a restart masquerading as resume.
Native code remains uncompiled and devices untested. The complete fifteen-step
Graphics coordinator, restart transfer, actor and final lifetime proof remain.
