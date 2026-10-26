"""Closed original navigation reception profile; no editor outcome from ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need
from ios.adapters import lifecycle_inputs as base,lifecycle_navigation_controls as controls
from ios.adapters.keyboard_source import identifier
from ios.adapters.snapshot_export_controls import identity as uuid

VERSION=1
ACTION='feature-ios-lifecycle-navigation-inputs'
FILE=ACTION+'.json'
LIMIT=base.LIMIT
IDS=controls.IDS


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']) is not None)
    identifier(value['runId']);return value


def native_command(value,control):
    exact(value,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'})
    need(control in IDS and type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['operation']=='activate'
         and integer(value['sequence'],1) and integer(value['observedElapsedMs']))
    for key in ('commandId','instance','fieldToken'):uuid(value[key])
    return value


def root(value,control,request):
    native_command(request,control);controls.metadata(value);need(value['controlId']==control);return value


def validate(value,query,pid,epoch=None,previous=None):
    return base._validate(value,query,pid,epoch,previous,query_validator=command,input_validator=native_command,
                          root_validator=root,profile='lifecycle-navigation')


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def delivered(value,expected,control,original_root):
    return base._delivered(value,expected,control,original_root,original_validator=original,input_validator=native_command,
        root_validator=root,delivery_key='iosLifecycleNavigationInputDeliveryVersion')


class IOSLifecycleNavigationInputs(base.IOSLifecycleInputs):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosLifecycleNavigationInputsAcquisitionVersion'
