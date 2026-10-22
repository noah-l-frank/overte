# Actual Qt keyboard/IME dispatch source

`IOSWorldWebKeysObservation` and its proposed Application hooks are passive,
compiled only under `OVERTE_E2E_FEATURE_TESTS && Q_OS_IOS`, with actual
`--testScript` required before startup/dispatch/read. Startup precedes the first
real GL/Vulkan window and retains actual initial windows/modifiers. The read
cannot start or clear the source. There is no input synthesis, event filter,
`processEvents`, setter, queue drain or product handler change.

The two-file `/tmp/overte-world-web-keys-hooks.patch` adds the startup call next
to the existing Pointer startup and an independent keyboard RAII around the
existing actual `QApplication::notify`. Both real returned paths retain their
actual bool, including false. Actual callback entry, return and finally remain
distinct. A release entered during a nested event loop may remove a held-key
entry but cannot qualify drainage while its dispatch remains pending.

Native source originals retain process-source birth, weak original target and
device births, immutable event edges, exact key/text/modifier/scan/virtual-key/
auto-repeat/count/Qt-time fields or actual IME commit/preedit/replacement fields.
Nested notify for the same live event shares one batch and does not manufacture
another key birth. Auto-repeat retains the original down key. Positive actual
release joins the original press; target death does not clear down/preedit state.
There is no reset. Overflow, missing startup, unknown release, missing return,
clock regression or contradictory ownership remains unavailable/incomplete.

Closed command: `{schemaVersion:1,commandId,action,runId}`, action
`feature-ios-world-web-keys`, file `feature-ios-world-web-keys.json`, limit
1048576. This source owns a separate actual native UTC/elapsed read bracket,
source/read birth and counter with a 1040000-byte native payload cap; the common
NativeReadBracket and all existing source limits remain unchanged.
`Test.featureIOSWorldWebKeys` calls the singleton
`IOSWorldWebKeysObservation::instance().read(commandId,runId)` on the native main
thread. `FeatureObservation.world_web_keys(clock_source)` should construct
`IOSWorldWebKeys` with that exact original native clock. Registry key:
`ios-world-web-keys` writer/read 1. The source schema is
`iosWorldWebKeySourceVersion:1`, native envelope `iosWorldWebKeysVersion:1`.

The reader reconstructs actual down/ended/preedit/pending state from all retained
dispatches and immutable edges, preserving source birth and completed returns
through subsequent observations. `drained()` requires positive initial coverage,
zero pending dispatches/down keys/Qt modifiers, and an actually observed empty
preedit argument. That argument is the last Qt-delivered IME event, never an
observation of editor composition or a successful handler effect. In particular,
a false-returned IME event cannot prove that the editor cleared. A W3C
release ACK is not accepted as an original. Whole cleanup additionally requires
the current native geometry's actual hidden keyboard, Web/input/lifetime and
pixel retirement originals. Seven host tests cover genuine modeled press/
release, pending returned-false release, nested notify, auto-repeat, actual IME
clear versus weak target death, missing startup/overflow/forged empty state and
historical source/return mutation. Four additional actual POST/AFC codec tests
round-trip a transcript larger than 400000 bytes, retain the old generic decoder
default bound, reject excess bytes and incorrect native clocks/process births,
and refuse held/overflow/unknown-startup retirement. Native code is source-only,
uncompiled; the native/SDK boundary producers in these host tests are models.

Off-main delivery poisons the source through an atomic complete flag, without
accessing the main-thread inventories. The process-wide ledger is bounded at
1024 dispatches, 3072 edges and 64 weak
devices/targets. Conservative exhaustion fails closed for the remaining process
lifetime; it must never be reset to obtain a successful result.
