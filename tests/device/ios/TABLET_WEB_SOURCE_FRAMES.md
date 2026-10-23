# Tablet original frame replay and active browser boundary

`TabletWebSourceOwner.frame_at(reference)` is a historical-only original reader.
It revalidates the actual stored acquisition, child original files, complete
source-prefix history, native/host clock bracket and same-phase association.
It returns independent copies of the selected returned acquisition, its nine
original source components and browser receipt, and the earlier returned frames.
It sends no query or input and performs no app/page fact derivation.

This read surface permits disposal and screenshot code to inspect actual native
originals from an incomplete app setup. It does not admit an app, make a failed
acquisition successful, invent a quiet interval or qualify cleanup. `facts_at`
still additionally requires the independently admitted original app/code/button
joins and derives actual page facts. A live owner cannot call `frame_at`.

Every active acquisition requires browser fixture version 1 explicitly, even
when the neutral browser parser also accepts retired-only fixture version 2.
The actual browser callback result is persisted before this policy is checked;
a rejected version remains in the failed, blocking acquisition. Rejection
occurs before the following native-after query. Historical returned acquisitions
independently enforce the same active-only version policy, including when the
stored browser bytes and enclosing digest are changed together. Historical
failed ownership is retained rather than normalized into an active receipt.

This adds no DTO version or registry row: SourceOwner and Acquisition remain
writer 2/read 1,2. Existing literal source envelopes and `facts_at` return values
are unchanged. Host tests exercise actual private original files and real
journals, with explicitly modeled native producers. Native sources remain
uncompiled and device behavior unqualified; the whole Tablet adapter is partial.
