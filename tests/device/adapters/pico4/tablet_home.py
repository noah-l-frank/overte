"""Observed VR Home entity, reached only by the ordinary OpenXR trigger ray."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json

from adapters.android.input_geometry import observed_grip_pose
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.script_journey.files import ScriptFileIO,nonce

VERSION=1
FILE='tablet-home-observation.json'
COMMAND='files/overte-e2e/tablet-home-observation-command.json'


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','homeObservationVersion',
        'tabletShown','onHomeScreen','tabletId','homeId','parentId','entityType','entityName',
        'visible','ignorePickIntersection','hostType','sensorToWorld','headPosition','position'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['commandId']==command and nonce(command) and value['action']=='observe'
         and nonce(value['instance']) and value['generation']==value['instance']
         and integer(value['sourceSequence'],1) and value['lastCommandSequence']==0
         and integer(value['elapsedMs']) and integer(value['processId'],1) and value['processId']==pid
         and type(value['homeObservationVersion']) is int and value['homeObservationVersion']==VERSION
         and all(type(value[key]) is bool for key in ('tabletShown','onHomeScreen','visible','ignorePickIntersection'))
         and all(nonce(value[key]) for key in ('tabletId','homeId','parentId'))
         and value['tabletId']==value['parentId'] and value['homeId']!=value['tabletId']
         and value['entityType']=='Gizmo' and value['entityName']=='homeButton' and value['hostType']=='local')
    fresh(value['capturedEpochMs'],epoch)
    need(0<=epoch-value['capturedEpochMs']<=1500)
    for key in ('position','headPosition'):
        need(type(value[key]) is list and len(value[key])==3 and all(number(v,-1e8,1e8) for v in value[key]))
    # Validate affine STAGE conversion and calibration even for a no-input read.
    observed_grip_pose(value['sensorToWorld'],value['headPosition'],value['position'])
    return value


def validate_input(value,pid,epoch,control):
    validate(value,value.get('commandId'),pid,epoch)
    need(control=='tablet.home-ray' and value['tabletShown'] and value['visible']
         and not value['ignorePickIntersection'] and not value['onHomeScreen'])


class PicoHomeSource(ScriptFileIO):
    wire_action='tablet-home-observe'
    validate_capture=staticmethod(validate)

    def __init__(self,adapter,target,native):
        def send(envelope):
            exact(envelope,{'schemaVersion','commandId','action','request'})
            request=envelope['request'];exact(request,{'schemaVersion','commandId','action'})
            need(envelope['schemaVersion']==request['schemaVersion']==1
                 and envelope['action']==self.wire_action and request['action']=='observe'
                 and envelope['commandId']==request['commandId'])
            native.guard()
            adapter.adb.write_debug_app_file(target,'org.overte.pico',COMMAND,json.dumps(request,separators=(',',':'))+'\n')
            native.guard()
        super().__init__(send,lambda:adapter.adb.read_debug_app_file(target,'org.overte.pico',
            'files/overte-e2e/'+FILE,attempts=1),native.clock_ms,native.guard,native.pid,
            monotonic=native.monotonic,sleep=native.sleep)

    def input(self,*_args,**_kwargs):need(False)


class PicoTabletHome:
    def __init__(self,source,stage):
        need(callable(stage));self.source,self.stage=source,stage

    def ensure(self,intent):
        before=self.source.capture()
        need(before['tabletShown'])
        if before['onHomeScreen']:return before
        validate_input(before,self.source.pid,self.source.clock_ms(),'tablet.home-ray')
        pose=observed_grip_pose(before['sensorToWorld'],before['headPosition'],before['position'])
        # Persist original geometry before granting this one bounded gesture.
        # Any exception retains uncertainty: this method never restages it.
        intent('tablet-home-ray',before,'tablet.home-ray')
        need(self.source.guard() is not False)
        validate_input(before,self.source.pid,self.source.clock_ms(),'tablet.home-ray')
        self.stage(pose)
        started=self.source.monotonic()
        for attempt in range(81):
            current=self.source.capture()
            need(self.source.monotonic()-started<=8 and all(current[key]==before[key]
                for key in ('instance','tabletId','homeId')) and current['tabletShown'])
            if current['onHomeScreen']:return current
            need(attempt<80);self.source.sleep(.1)
        need(False)


def bind_home(adapter,target,native):
    """One shared existing-session binding for normal Pico Home gestures."""
    source=PicoHomeSource(adapter,target,native)
    identity=adapter.require_pico_session_identity(target)
    def stage(pose):
        need(adapter.require_pico_session_identity(target)==identity)
        return adapter.pico_input_session(target).stage(identity,'input.primary',pose)
    return PicoTabletHome(source,stage)
