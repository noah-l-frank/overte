# Original QML transport admission

`NativeNavigationIO(..., before_send=None)` optionally binds one callable. The
same owner can instead call `bind_before_send(callback)` once after construction;
rebinding requires the exact same callable object. A different owner or clearing
an existing callback fails closed. Retain bound-method objects when binding more
than once.

After `PicoNavigation.input` has bound the candidate, taken and validated the
fresh original snapshot and constructed its exact command, `NativeNavigationIO.send`
runs its final original process/session/foreground guard. It then invokes the
callback with a deep copy of that command immediately before the existing
`write_debug_app_file` call. Mutating the callback argument cannot change the
published command. Any exception prevents publication; this path never retries
the callback or write. The callback must perform its own final freshness check
after any durable writes it performs. This callback is not an input receipt or
evidence of the requested effect.

Without a callback the existing behavior is preserved. This hook covers QML
commands only. It does not replace the original OpenXR controller session's
separate, host-only `stage(..., intent=callback)` boundary.

Host tests use the original Pico navigation and normal Chat wrappers with explicit
synthetic SDK, Qt and native observations; no device execution is claimed.

`bind_controller_admission(callback, intent=host_callback, before_publish=None)` is a separate optional
pair for normal tablet Open/Close. Both callable objects have the same immutable
ownership rule. The adapter retains the ordinary target eligibility and original
process/session/foreground guards, then calls `callback(operation)` outside the
session lock. It forwards `host_callback` to the unchanged original
`PicoOpenXrAdapterSession.stage(..., intent=...)`. That original callback receives
the exact envelope inside the original session lock and must perform only host
CAS/fsync and elapsed-age checks: no HTTP, SDK, guard or session reentry. This
route does not prove neutral release or the requested tablet effect. With no
bound pair, the existing controller callback remains unchanged.

An optional `before_publish` callable belongs to that same immutable owner tuple.
It is forwarded to the original session/transport's final publication admission.
This callback must validate the exact already-persisted original envelope and
its host age without IO, another intent write, a guard, HTTP or session reentry.
The original transport invokes it after SDK/profile validation before command
publication and again before the actual native grant commit marker.
