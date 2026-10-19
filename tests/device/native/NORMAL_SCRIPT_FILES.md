# Ordinary Script file-bundle control contract, version 1

This packet adds a common UI recipe and a source-only E2E resolver for the
**existing** `NativeFileBrowser.qml` Script bundle workflow. It adds no runner,
test-only picker, file helper invocation or client feature. The three isolated platform branches now connect their normal native
producers/transports to this recipe. It advertises no capability, and the new
C++ sources remain uncompiled. All hardware qualification is outstanding.

`ScriptFileUi.h` is the E2E-only native source/input core for the first Phone
binding. It observes the actual platform-supplied Qt root/window and current
clipped controls, with fresh source counters, an original native instance,
window/root generation, monotonic times, PID and source-sensitive control tokens.
Duplicate/oversized/unready trees fail. An actual file picker masks the normal
From File entry. Its admitted input cursor is consumed before a single input;
old instance/generation/token/cursor or more than five-second-old observation
cannot authorize events. The owning platform supplies the normal pointer-click
route. Folder replacement/Return use `NativeFieldInput`; main selection uses
ordinary Home/Down/Return events only while the actual selector owns focus and
the index fits its real model. No handler invocation or model assignment is
used. The core requires the default-off feature flag and explicit test launch.
Phone wraps this core through its closed private probe transport; Pico/iOS use
their existing normal token/input owners with this shared resolver. This source
review and the Python checks do not compile or qualify those sources.

`NormalScriptFileControls.h` identifies only the real **From File** control and
the actual `nativeFileBrowser` with caption **Open Script and Companion Files**,
bundle mode, JS primary filter and no save/directory-selection mode. It reads
the real FolderListModel delegate URL, caption, selected flags, directory,
chosen URLs, reviewed manifest and current main-file choice. A row's source
identity is its actual file URL; a primary selector's identity includes its
actual bundle/model and selection. Source changes must retire platform tokens.
The resolver never calls `documentBundle`, sets the selection/currentIndex,
loads code, or emits selectedFile/selectedBundle.

The required producer marker is `fileControlsVersion:1`, optional in the
existing native UI observation envelope and mandatory for this recipe. The
native platform must retain its existing fresh PID/process/session/generation,
candidate and control-token checks. Metadata definitions/validation are shared
in `adapters/token_script_file_ui.py`. IDs are closed:

* `scripts.from-file`: ordinary Running Scripts entry button.
* `script-file.folder`: actual focused text editor for the folder path; adds
  original `text` and `picker` metadata. Replace/Submit use ordinary key/IME
  and Return events, followed by actual field/directory readback.
* `script-file.row.<0..9999>`: the real current visible delegate; adds actual
  `sourceUrl`, `rowLabel`, typed `selected` and `directory` flags. Native token
  identity and the same resolved input element must bind the complete source
  URL across capture/activation; basename matches do not authorize input.
* `script-file.select`, `script-file.cancel`: ordinary selection/cancellation.
* `script-file.primary`: the existing actual ComboBox; adds `currentText` and
  `currentIndex`. A normal selector input must use native keyboard/pointer
  events and actual readback, never assign currentIndex.
* `script-file.change-selection`, `script-file.confirm`,
  `script-file.review-cancel`: existing review buttons.

`picker` metadata is attached to actual folder/cancel/review-cancel/confirm
controls. It has exactly `caption`, `directory`, `review`, `error`,
`relativePaths`, `selectedUrls`, `bundleRoot`, `bundleUrls`. URLs/paths are
actual original native values; empty review fields describe the selection
screen. A review must contain its real nonempty matching path/URL inventory.
Metadata is private diagnostic data, not a public feature result or an expected
selection echoed into an observation. Existing platform byte/geometry/clock
bounds must apply before this common recipe sees a capture.

The owning adapter must independently stage/bind the run's original main and
companion bytes, with a private `feature-script-<32hex>` directory under its
actual authorized app root. It must persist picker/source/file ownership before
input. This packet neither creates a device directory nor infers a sandbox
path. A later stager must not overwrite/delete existing unrelated files.

The recipe opens once, observes the actual picker, navigates normally to that
owned directory and selects the real main/companion delegates in order. It
requires actual chosen-URL readback after each click and a real review with
only those files and that source root. It uses the observed main selector and,
if needed, one normal selection input with readback before the single Use Files
click. Picker disappearance is a UI result only. A separate engine/module/
advancing-effect observation must establish execution and companion success.

Cancellation observes disappearance for at least 300 ms; ignored cancellation
fails and leaves ownership unresolved. Waits are bounded to ten seconds/101
reads with a monotonic-clock guard. Reads alone may retry. A lost/changed
instance, unavailable native marker, ignored field/row/select/confirm action,
missing companion, extra review file, foreign reused row or ignored primary
choice fails without replaying input. Another dialog cannot be adopted.

Nine device-free tests execute this actual common recipe with a native UI
boundary reading real temporary fixture files. They confirm test/control logic,
not Qt accessibility, keyboard delivery, native picker behavior or script
execution. The separate [fixture storage source](SCRIPT_FIXTURE_STORAGE.md) now defines
exclusive staging, original readback and persistent file cleanup intent. The
full owner still needs dialog/engine cleanup, verified restart handoff and the
complete version 4 Script state/effect/journal join. System folder
picker and OS permission paths need their own concrete normal UI bindings;
this packet does not pretend to implement those paths.
