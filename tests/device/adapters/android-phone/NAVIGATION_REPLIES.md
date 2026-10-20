# Phone original navigation error replies

The internal `_navigation_replies(selector)` factory uses the existing original
candidate APK/install digest, process PID/start identity, native clock, foreground/
session guards and one-attempt private run-as reads. Its only file is
`files/overte-e2e/feature-navigation-replies.json`. It can read the passive real
AddressManager source without opening or requiring a Scripts editor. It sends
no expected result, URI, network error or requested state to the native getter.

Follow the [native source and original fixture-receipt join](../../native/NAVIGATION_REPLIES.md).
The reader requires actual current RequestTicket generation/activity, original
HTTP response identity and a separately selected fixture origin/run/ticket/time
barrier. It returns original raw receipts only. Actual normal Places/Go To input,
modal/source identity, bookmark persistence, current grounded arrival/image and
independent peer/recovery/cleanup composition remain missing in the full adapter.
No complete `feature.world-navigation.*` triple is advertised.

All 104 Phone component host cases pass after the merge conflict was resolved;
the earlier run on unresolved probe source is rejected. Three new cases cover
original read/join, ignored source/foreign PID/superseded scope and changed
installation before a new command. Ten shared reader/probe/HTTP cases also pass.
The Qt/Android/native boundaries are synthetic; native code is uncompiled and
no device was contacted or qualified.
