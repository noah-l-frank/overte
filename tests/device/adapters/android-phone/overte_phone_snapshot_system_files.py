"""Readonly original capture-file source during an owned OS handoff.

The passive native timer supplies new source acquisitions. This wrapper sends
no native command and cannot plan, unlink or seal a namespace. The existing
file owner still independently scans actual files through its narrow OS guard.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_handoff import PhoneSnapshotHandoff
from overte_phone_snapshot_capture_source import validate,continuity


class SnapshotSystemFileSource:
    read_only=True
    def __init__(self,handoff):
        need(isinstance(handoff,PhoneSnapshotHandoff))
        self.handoff,self.pid,self.clock_ms,self.last=handoff,handoff.owner['processId'],handoff.clock_ms,None

    def request(self,run,operation='observe',*,prefix='',file_id='',operation_id=''):
        try:
            need(run==self.handoff.owner['runId'] and operation=='observe' and prefix==file_id==operation_id=='')
            packet=self.handoff.read()['captureFiles']
            validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='phone-snapshot-files-observe',runId=run),self.pid,self.clock_ms())
            if self.last is not None:continuity(self.last,packet)
            self.last=deepcopy(packet);return deepcopy(packet)
        except Exception:raise NativeUIError('Original passive Snapshot file inventory is unavailable or unauthorized') from None
