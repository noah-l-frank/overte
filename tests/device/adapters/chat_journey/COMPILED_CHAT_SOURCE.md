# Original compiled Chat source v1

`ChatScriptSource.capture(ticket, after_epoch)` reads the actual native configured
Script root, the original Script manager/V8 inventory, and a new original root
again. All three belong to the same actual process and native birth, have fresh
ordered original requests, and fit the existing 1.5-second native and host bound.
No filename, expected hash, code, input or desired result is sent to either
getter. This qualifies source identity; compilation does not establish execution,
Chat delivery, UI state, settings restoration or resource release.

The Chat-only reviewed manifest is
[chat-script-source.v1.json](../../feature_journeys/chat-script-source.v1.json).
The fixed Phone source selection at
`5527d540e99cc6dba4204a5e904a854e6e1cd2b4`,
`tests/device/adapters/android-phone/overte_phone_chat_measurements.py`, supplies
the reusable configured-root/submitted-code/compiled-script join. The actual
shared Chat file has identical UTF-8 and UTF-16 hashes and 18,706 code units.
The different Pico peer script and Phone v18 journey/cleanup protocol are not
selected. The existing Pico v16 journey remains unchanged.

The join additionally uses the actual complete manager-membership inventory.
Exactly one assigned manager names the physical Chat under the configured root,
including pending managers absent from the running table. Its actual unique
running engine may have the original physical URL or, for file roots, the
original normalized `file:///~//communityScripts/armored-chat/armored_chat.js`
key. Manager instance, physical assignment, load generation and assignment time
must match its actual submitted code. Exactly one actual compilation has the
corresponding original resource name, reviewed encoding/units/hash, a real script
ID, and a compilation time after submission. A compiled Chat copy in another
live manager cannot be ignored under a different table name. Missing/partial
membership, incomplete compilations, pending duplicate Chat assignments and
unknown sources fail closed.

Construction requires the exact parent `ScriptSourceLock` already held. Every
capture uses that same object. Separate primary, actor and independent witness
owners use separate readers and journals; the independent process uses the same
OS lock path. The owner records a durable `reading` intent before querying, then
retains the full three original packets in immutable private
`ChatSourceChunks`. New captures preserve the original manager/code/compilation
identity. Fully consumed histories may be reconstructed without querying or
publishing input; every new capture still obtains new original requests.
Interrupted reads and orphan chunks cannot be adopted or replayed. This owner
does not discard its root or original chunks.

Copies, chunk/root persistence, final original guards and wall-clock reads all
remain inside the original monotonic/native age bounds. A frozen host clock
cannot hide a native jump, and a frozen native clock cannot hide a slow host
copy or durable write. Failed warm owners stop acquiring; no failure receipt
overwrites their earlier source intent.

`PicoBoundAdapter._chat_script_source(target, run, role=...,
source_lock=..., witness=False)` binds the existing actual Pico candidate/process
and native observation routes. The three role stores are distinct. Generic
cleanup preserves their roots and rootless chunks and cannot report success
because process teardown occurred. This packet adds the passive component and
factory only: the whole Chat parent/model join remains separate work, and no
public Chat capability is granted by constructing or reading it.

Verification uses synthetic native/V8 packet seams with the actual Python
readers, durable journals, Linux source locks, Pico factory and original
candidate/cleanup code. It does not run V8, an application, a device or an actual
Chat network. Eight component tests include changed birth/root/order, missing
membership/code, duplicate/pending managers, foreign compilations, passive
reconstruction, lost reads/orphans, and slow copies/CAS/final clocks. Two actual
Pico factory tests cover independent native read routes with the exact lock and
candidate changes plus rootless source chunks. The combined 10 tests passed in
1.787 seconds:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device:android/vr/pico/tests/device \
python3 -m unittest self_tests.test_chat_script_source test_chat_script_source -v
```
