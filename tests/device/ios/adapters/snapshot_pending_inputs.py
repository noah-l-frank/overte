"""Original reception of only the two owned pending-capture mode choices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need
from ios.adapters import lifecycle_inputs as base,snapshot_pending_choices as choices
from ios.adapters.snapshot_export_controls import identity
from feature_journeys.contract import identifier

VERSION=1
ACTION='feature-ios-snapshot-pending-inputs'
FILE=ACTION+'.json'
LIMIT=base.LIMIT
IDS=choices.IDS


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    identifier(value['runId']);return value


def native_command(value,control):
    exact(value,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'})
    need(control in IDS and type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['operation']=='activate'
        and integer(value['sequence'],1) and integer(value['observedElapsedMs']))
    for key in ('commandId','instance','fieldToken'):identity(value[key])
    return value


def root(value,control,request):
    native_command(request,control);choices.metadata(value);need('snapshot.mode.'+value['option']==control and value['popupOpen'] and value['inputReady']);return value


def validate(value,query,pid,epoch=None,previous=None):
    return base._validate(value,query,pid,epoch,previous,query_validator=command,input_validator=native_command,root_validator=root,profile='snapshot-pending')


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def delivered(value,expected,control,original_root):
    return base._delivered(value,expected,control,original_root,original_validator=original,input_validator=native_command,
        root_validator=root,delivery_key='iosSnapshotPendingInputDeliveryVersion')


class IOSSnapshotPendingInputs(base.IOSLifecycleInputs):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotPendingInputsAcquisitionVersion'
