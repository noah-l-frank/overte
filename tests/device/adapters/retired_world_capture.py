"""Read-only original capture inspection under the caller's existing source lock.

This factory reuses the Graphics retirement protocol. It neither releases GPU
memory nor removes files, and its reader is not a durable finalization owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.graphics_journey.samples import retirement
from adapters.script_journey.lock import ScriptSourceLock
from adapters.world_render_receipts import NativeWorldReceiptInventory


def observer(proof,lock,binding,native,guard,stores,read,*,previous=None):
    need(isinstance(lock,ScriptSourceLock) and callable(guard) and callable(read)
        and type(stores) is list and bool(stores))
    proof,binding,stores=deepcopy(proof),deepcopy(binding),list(stores)
    lock.assert_held();native.read(0)
    role=proof['owner']['role'];retirement(proof,proof['owner'],native.pid,binding,role)
    # The GPU context and TestScriptingInterface have independent native births.
    # The original GPU getter, not the unrelated generic observer UUID, must
    # agree with the retained original memory/file proof.
    instance=proof['memory']['instance']
    def quiet_guard():
        lock.assert_held();need(guard() is not False and native.guard() is not False
            and all(store.read() is None for store in stores));return True
    floor=proof['files']['absent'] if previous is None else previous
    updated=deepcopy(proof);updated['files']['absent']=deepcopy(floor)
    retirement(updated,proof['owner'],native.pid,binding,role)
    need(floor['sequence']>=proof['files']['absent']['sequence'])
    quiet_guard()
    def inspect(request):
        need(request['operation']=='inspect');return native.send(request)
    class AbsentInventory(NativeWorldReceiptInventory):
        def request(self,operation):
            packet=super().request(operation)
            current=deepcopy(proof);current['files']['absent']=deepcopy(packet)
            retirement(current,proof['owner'],native.pid,binding,role)
            return packet
    reader=AbsentInventory(inspect,read,native.clock_ms,quiet_guard,native.pid,
        lambda:deepcopy(proof['owner']),lambda:instance,monotonic=native.monotonic,sleep=native.sleep)
    reader.sequence,reader.captured=floor['sequence'],floor['capturedEpochMs']
    reader.histories={floor['requestId']:{row['receiptId']:row['issued'] for row in floor['source']['receipts']}}
    return reader
