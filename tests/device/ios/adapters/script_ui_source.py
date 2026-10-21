"""Original iOS Script survey over the existing native HTTP/AFC input transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import need
from adapters.script_feature.ui_source import ScriptUISource
from adapters.token_script_file_ui import file_control
from ios.adapters.normal_input import NativeInput


class IOSScriptUISource(ScriptUISource):
    def __init__(self, native, clock_ms, guard, pid, *, monotonic=time.monotonic):
        need(isinstance(native,NativeInput))
        self.native=native
        super().__init__(self._acquire,clock_ms,guard,pid,ios=True,monotonic=monotonic)

    def _acquire(self):
        original=self.native.capture(native_epoch_ms=self.clock_ms)
        need(original.get('scriptObservationVersion')==1 and type(original.get('scriptObservationVersion')) is int)
        receipt=deepcopy(self.native.last_receipt)
        need(type(receipt) is dict and receipt.get('observation')==original)
        controls=[{key:deepcopy(item) for key,item in row.items() if key!='frame'}
                  for row in original['controls'] if file_control(row['id'])]
        return dict(schemaVersion=1,commandId=receipt['commandId'],action='observe',
            instance=original['instance'],generation=original['instance'],
            sourceSequence=original['scriptSourceSequence'],lastCommandSequence=original['lastSequence'],
            elapsedMs=original['elapsedMs'],capturedEpochMs=original['sampleEpochMs'],
            processId=original['processId'],fileControlsVersion=original['fileControlsVersion'],
            ready=original['ready'],controls=controls,scriptInventory=deepcopy(original['scriptInventory']),
            originalKind='ios-normal-ui-v1',originalReceipt=receipt)
