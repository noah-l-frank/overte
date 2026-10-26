"""Closed original packet/input owners for the actual pending-capture flow."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_source_packet import SnapshotWorkPacket,SnapshotCapturesPacket,SnapshotExportsPacket,SnapshotInputsPacket
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters import snapshot_pending_inputs as inputs,snapshot_pending_choices as choices


class PendingSegments(OriginalPacketSegments):PROFILE='snapshot-pending-sources'


class PendingInputs(SnapshotInputOwner):
    _owner_key='pendingSnapshotInputOwnerVersion'
    _proof_namespace='pending-snapshot-input-proof'
    _proof_schema='pendingSnapshotInputProof'
    @staticmethod
    def store_name(role):return 'pending-snapshot-'+role+'-inputs.json'
    def decode(self,value):
        state=super().decode(value);need(all(row['controlId'] in ('snapshot.name','snapshot.mode','snapshot.capture','snapshot.cancel') for row in state['events']));return state
    def reserve(self,control,original,*,operation='activate',text=None):
        need(control in ('snapshot.name','snapshot.mode','snapshot.capture','snapshot.cancel'))
        return super().reserve(control,original,operation=operation,text=text)


class PendingChoices(SnapshotInputOwner):
    _owner_key='pendingSnapshotChoiceOwnerVersion'
    _proof_namespace='pending-snapshot-choice-proof'
    _proof_schema='pendingSnapshotChoiceProof'
    _input_source=inputs
    _reference=staticmethod(choices.reference)
    _root_is_stable=False
    @staticmethod
    def store_name(role):return 'pending-snapshot-'+role+'-choices.json'
    @staticmethod
    def root(event):return deepcopy(event['reference']['root'])
    def decode(self,value):
        state=super().decode(value);roots=[{key:row['reference']['root'][key] for key in ('rootId','qmlSource','comboId')} for row in state['events']]
        need(not roots or all(root==roots[0] for root in roots));return state
    def check_current(self,event):choices.same_reference(event['reference'],choices.project(self.native.capture(),event['controlId']),event['controlId'])
    def reserve(self,control,original,*,operation='activate',text=None):
        need(control in choices.IDS and operation=='activate' and text is None)
        return super().reserve(control,original,operation=operation,text=text)


class PendingWorkPacket(SnapshotWorkPacket):
    _store_prefix='pending-snapshot';_key='pendingSnapshotWorkPacketVersion';_namespace='pending-snapshot-work';_schema='pendingSnapshotWork';_segments=PendingSegments
class PendingCapturesPacket(SnapshotCapturesPacket):
    _store_prefix='pending-snapshot';_key='pendingSnapshotCapturesPacketVersion';_namespace='pending-snapshot-captures';_schema='pendingSnapshotCaptures';_segments=PendingSegments
class PendingExportsPacket(SnapshotExportsPacket):
    _store_prefix='pending-snapshot';_key='pendingSnapshotExportsPacketVersion';_namespace='pending-snapshot-exports';_schema='pendingSnapshotExports';_segments=PendingSegments
class PendingInputsPacket(SnapshotInputsPacket):
    _store_prefix='pending-snapshot';_key='pendingSnapshotInputsPacketVersion';_namespace='pending-snapshot-inputs';_schema='pendingSnapshotInputs';_segments=PendingSegments
class PendingChoicesPacket(SnapshotInputsPacket):
    _store_prefix='pending-snapshot';_key='pendingSnapshotChoicesPacketVersion';_namespace='pending-snapshot-choices';_schema='pendingSnapshotChoices';_segments=PendingSegments
    _name='native-choices';_kind='pending-choices';_source=inputs;_segment_subject='choices'
class PendingManifest(SnapshotManifest):
    _store_prefix='pending-snapshot';_owner_key='pendingSnapshotManifestOwnerVersion';_namespace='pending-snapshot-manifest';_schema_prefix='pendingSnapshotManifest'

PACKETS=dict(work=PendingWorkPacket,captures=PendingCapturesPacket,exports=PendingExportsPacket,inputs=PendingInputsPacket,choices=PendingChoicesPacket,manifest=PendingManifest)
