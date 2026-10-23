# Retained original native geometry floor

`OriginalGeometry.capture(native_before_floor=...)` may use an already retained
native BEFORE epoch instead of issuing another initial clock query. The default
still issues three new clock queries. The explicit floor must be a positive
integer at least as recent as the reader's last accepted sample. It supplies no
current time and does not change the receipt's original clock or sequence.

The owning source must validate the retained original's process, native birth,
nonce, history prefix and current acquisition association before sending the
geometry request. The geometry receipt has no process field, so the existing
process guard remains mandatory. A bare integer is not that provenance proof.

Both independent terminal native clock queries remain new. The original sample
must follow the supplied floor and remain fresh against both terminal queries;
the complete acquisition must still finish within 1.5 seconds. Invalid floors
are rejected before a native send. A future floor or slow terminal query cannot
produce an accepted sample. Failed delivery remains the caller's durable
responsibility; this helper does not authorize a repeated input.

Device-free tests cover default and explicit query counts, invalid and regressing
floors, future floors and a slow second terminal query. They do not establish
native compilation, device execution or completion of a feature adapter.
