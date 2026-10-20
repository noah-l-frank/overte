# Phone ordinary Script file UI protocol, version 1

This internal E2E component reuses the existing Android private command channel.
It advertises no full feature capability. The canonical candidate-bound Phone
factory constructs it with the original installed-APK/PID/start/session guard;
an environment flag cannot create a native producer. Both feature-enabled build
and explicit test launch/results are required. No build/device run has occurred.

Outer commands are exactly `{schemaVersion:1,commandId:<32hex>,
action:"phone-script-file-ui",request:<inner>}`. IDs must agree. The probe rejects
extra fields, unsafe integers, arbitrary text/code/source names and unsupported
actions before native dispatch. Duplicate outer IDs never replay input. Native
admission is independently strict too. Original results are atomically published
as mode 0600 `phone-script-file-ui.json`; unavailable hooks publish
`available:false`, which is rejected. No request accepts desired observations.

An observation inner request is exactly `{schemaVersion:1,commandId,action:"observe"}`.
The original response has exactly `schemaVersion`, `commandId`, `action`,
`instance`, `generation`, `sourceSequence`, `lastCommandSequence`, `elapsedMs`,
`capturedEpochMs`, `processId`, `fileControlsVersion`, `ready`, `controls`.
Phone builds may add the strictly versioned passive
[`scriptInventory`](SCRIPT_UI_INVENTORY.md) extension. Existing picker input
accepts its absence; complete UI observations require it.
Instance/generation/control tokens are native 32-hex values; PID and all cursors
are real native values. A generation changes with the actual Qt root/window.
Rows have exactly `{id,token,enabled,focused}` plus the closed metadata in
`token_script_file_ui.py`. Capture rejects unready, duplicate/oversized rows,
wrong clocks/types/PID, nonadvancing sources, retired instances/generations and
captures older than 1500 ms or more than 250 ms in the future.

Input inner requests have exactly `schemaVersion`, `commandId`, `action`,
`instance`, `generation`, `sequence`, `observedElapsedMs`, `controlId`,
`controlToken`; `replace` adds only `text`, `select-index` only `index`:

* `activate`: one normal pointer click on the actual current visible control.
* `replace`: only the actual focused `script-file.folder` editor, with an
  absolute owned `feature-script-<32hex>` path, optionally `/script-bundle`.
  Native key/IME input is followed by independent actual field readback.
* `submit`: ordinary Return in that same actually focused folder editor.
* `select-index`: ordinary Home/Down/Return while the actual primary ComboBox
  owns focus, with an index within its real model and 0..31. No property setter
  changes the selection. Host readback must identify the selected real main.

The core re-observes current controls before admission. Instance, generation,
source-sensitive token and exactly next native input sequence must match; the
source monotonic observation may be at most five seconds old. It consumes the
cursor before dispatch and always releases issued pointer/key events on the
retained window. A rejected/uncertain input is not replayed. The acknowledgement
is exactly `{schemaVersion,commandId,action,performed,instance,generation,
sequence,processId}`; it represents delivery only. The common picker separately
observes the resulting selection/review/primary/dialog state, and later engine/
module/effect observations must establish execution.

Each private exchange is bounded to 262144 bytes, five seconds and 51 reads.
Missing/foreign/partial result reads may poll that same request. Typed matching
invalid results fail. No input is sent again while waiting for a receipt. All
transport exceptions are closed and disclose no selector, entered path or raw
native error. The existing context/candidate guard surrounds every exchange.

The factory's directory comes from the future owning stager; this protocol
does not assume, create, overwrite or delete device files. Persistent ownership
must precede opening the picker and survive uncertain input. A normal Cancel
and actual disappearance are required; application teardown alone cannot claim
complete source/file cleanup. System document/folder pickers and permission
paths are not implemented by this Qt picker component.

Host tests execute the actual Python candidate wrapper/IO/common recipe and
original JavaScript dispatcher with explicit native boundaries and real
temporary local fixture files. They prove control logic only. The native
source/input core and actual keyboard/mouse delivery remain uncompiled and
unqualified; all future device work belongs to Proxmox Jenkins.
