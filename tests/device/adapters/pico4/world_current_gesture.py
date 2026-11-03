"""One normal primary gesture, with an explicitly historical intent receipt.

Calibration must be current immediately before every actual publication. The
two-second ordinary pulse is not a new current calibration or target effect.
CurrentRay1 remains unchanged; this private protocol has its own version.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need,number,decode
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.source_chunks import json_digest
from adapters.android.input_geometry import observed_grip_pose
from adapters.pico4.world_current_input import PicoWorldCurrentInput
from adapters.pico4.world_current_keyboard import PicoWorldCurrentKeyboard,units
from adapters.pico4.world_current_focus_parent import epochs


def calibration(original,*,key_id=None):
    packet=decode(original['raw'])
    if 'picoWorldCurrentKeyboardVersion' in packet:
        from adapters.pico4.world_current_keyboard import validate
        validate(packet,original['request'],packet['processId'],packet['capturedEpochMs'],original['focusOriginal'])
        keys=packet['source']['keyboard'];target=decode(original['focusOriginal']['raw'])['source']['authorityAfter']['native']['sourceIdentity'][len('web-entity:'):]
        need(keys['created'] and keys['enabled'] and keys['raised'] and keys['ready'] and not keys['inputToHud']
             and not keys['preferMallets'] and keys['inputTarget']==target and all(keys['hmd'][k] for k in ('active','visible','mounted')))
        matches=[v for v in keys['keys'] if v['id']==key_id and v['layer']==keys['activeLayer']]
        need(len(matches)==1);key=matches[0]
        need(key['visible'] and key['ready'] and not key['pressed'] and key['type'] in (0,1,3,4))
        pose=observed_grip_pose(keys['sensorToWorld'],keys['headPosition'],key['geometry']['worldCenter'])
        clocks=epochs(original['focusOriginal'])+[packet[k] for k in ('requestedEpochMs','capturedEpochMs')]
        clocks.extend(packet['source'][side]['native']['capturedEpochMs'] for side in ('nativeBefore','nativeAfter'))
        clocks.append(keys['capturedEpochMs'])
        return pose,clocks,key
    from adapters.pico4.world_current_input import validate
    need(key_id is None and original['request']['operation']=='measure-current-ray')
    validate(packet,original['request'],packet['processId'],packet['capturedEpochMs'],original['documentOriginal'])
    ray=packet['source']['worldRay']
    return observed_grip_pose(ray['sensorToWorld'],ray['headPosition'],ray['worldPoint']),epochs(original),None


def receipt(value):
    exact(value,{'picoWorldCurrentGestureVersion','calibrationOriginal','keyEntity','streamEnvelope','publication',
                 'startedMonotonic','requestedEpochMs','finishedMonotonic','publicationWindows'})
    need(type(value['picoWorldCurrentGestureVersion']) is int and value['picoWorldCurrentGestureVersion']==1
         and number(value['startedMonotonic'],0,1e15) and integer(value['requestedEpochMs'],1)
         and number(value['finishedMonotonic'],value['startedMonotonic'],value['startedMonotonic']+5))
    pose,clocks,key=calibration(value['calibrationOriginal'],key_id=value['keyEntity'])
    envelope=value['streamEnvelope'];exact(envelope,{'schemaVersion','sessionNonce','sequence','commands'})
    need(type(envelope['schemaVersion']) is int and envelope['schemaVersion']==1 and type(envelope['sessionNonce']) is str
         and re.fullmatch('[0-9a-f]{64}',envelope['sessionNonce']) and integer(envelope['sequence'],1)
         and type(envelope['commands']) is list and len(envelope['commands'])==1)
    command=envelope['commands'][0];exact(command,{'id','operation','arguments'})
    need(command['id']=='input-primary-'+str(envelope['sequence']) and command['operation']=='input.primary'
         and json_digest(command['arguments'])==json_digest(pose))
    windows=value['publicationWindows'];need(type(windows) is list and 0<len(windows)<=8)
    previous=value['startedMonotonic']
    for window in windows:
        exact(window,{'monotonic','calibrationStartedMonotonic','calibrationRequestedEpochMs'})
        start=window['calibrationStartedMonotonic'];request=window['calibrationRequestedEpochMs']
        need(number(start,value['startedMonotonic'],value['finishedMonotonic']) and integer(request,1)
             and number(window['monotonic'],max(previous,start),value['finishedMonotonic'])
             and window['monotonic']-start<=1.5 and request-min(clocks)+(window['monotonic']-start)*1000<=1500)
        previous=window['monotonic']
    return value


class PicoWorldCurrentGesture:
    def __init__(self,source,stage,intent,stream_intent,before_publish,*,started,requested,key_id=None):
        need(type(source) in (PicoWorldCurrentInput,PicoWorldCurrentKeyboard)
             and all(callable(v) for v in (stage,intent,stream_intent,before_publish))
             and number(started,0,1e15) and integer(requested,1))
        self.source,self.stage,self.intent,self.stream_intent,self.before_publish=source,stage,intent,stream_intent,before_publish
        self.started,self.requested,self.key_id=started,requested,key_id;self.issued=self.failed=False

    def publish(self):
        source=self.source;need(not self.issued and not self.failed and source.lock._owner is None)
        try:
            original=source.original();seal=json_digest(original);pose,clocks,_=calibration(original,key_id=self.key_id)
            anchor=source._warm_anchor if type(source) is PicoWorldCurrentInput else source._anchor
            need(anchor is not None);cal_started,cal_requested,cal_seal=anchor;need(cal_seal==seal)
            def host_fence():
                need(json_digest(original)==seal and json_digest(source.original())==seal)
                now=source.monotonic()
                need(number(now,self.started,self.started+5) and number(now,cal_started,cal_started+1.5)
                     and cal_requested-min(clocks)+(now-cal_started)*1000<=1500)
                return now
            source.require_warm(original);host_fence();self.issued=True
            with source.lock.held():
                self.intent(dict(operation='world-current-gesture',calibrationOriginal=deepcopy(original),keyEntity=self.key_id,pose=deepcopy(pose)))
                source.require_warm(original);host_fence();envelope=None;envelope_seal=None;windows=[]
                def check(value):
                    exact(value,{'schemaVersion','sessionNonce','sequence','commands'})
                    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and type(value['sessionNonce']) is str
                         and re.fullmatch('[0-9a-f]{64}',value['sessionNonce']) and integer(value['sequence'],1)
                         and type(value['commands']) is list and len(value['commands'])==1)
                    item=value['commands'][0];exact(item,{'id','operation','arguments'})
                    need(item['operation']=='input.primary' and item['id']=='input-primary-'+str(value['sequence'])
                         and json_digest(item['arguments'])==json_digest(pose))
                def stream(value):
                    nonlocal envelope,envelope_seal
                    need(envelope is None);check(value);envelope=deepcopy(value);envelope_seal=json_digest(envelope)
                    self.stream_intent(deepcopy(value));host_fence()
                def publish(value):
                    # Session lock: only exact pinned host bytes/elapsed CAS.
                    # Never SDK clock, source getter, neutral wait or new query.
                    source.lock.assert_held();check(value)
                    need(envelope is not None and json_digest(value)==envelope_seal and len(windows)<8)
                    host_fence();self.before_publish(deepcopy(value));now=host_fence()
                    windows.append(dict(monotonic=now,calibrationStartedMonotonic=cal_started,calibrationRequestedEpochMs=cal_requested))
                publication=self.stage(deepcopy(pose),intent=stream,before_publish=publish)
                need(envelope is not None and windows and json_digest(envelope)==envelope_seal)
                result=dict(picoWorldCurrentGestureVersion=1,calibrationOriginal=deepcopy(original),keyEntity=self.key_id,
                    streamEnvelope=deepcopy(envelope),publication=deepcopy(publication),startedMonotonic=self.started,
                    requestedEpochMs=self.requested,finishedMonotonic=source.monotonic(),publicationWindows=deepcopy(windows))
                receipt(result)
            # Explicit HISTORICAL calibration. Do not call require_warm on the
            # old source after an actual two-second native pulse/ACK.
            need(json_digest(original)==seal and json_digest(source.original())==seal and source.guard() is not False)
            returned=deepcopy(result);returned['finishedMonotonic']=source.monotonic();receipt(returned)
            need(number(source.monotonic(),self.started,self.started+5))
            return returned
        except BaseException:
            self.failed=True
            raise NativeUIError('World gesture unresolved; retain the original intent and stream without replay') from None


def bind_current_gesture(adapter,target,source,intent,stream_intent,before_publish,admission,*,started,requested,key_id=None):
    need(callable(admission));identity=adapter.require_pico_session_identity(target);session=adapter.pico_input_session(target)
    def stage(pose,*,intent,before_publish):
        need(adapter.require_pico_session_identity(target)==identity);admission()
        return session.stage(identity,'input.primary',pose,intent=intent,before_publish=before_publish)
    return PicoWorldCurrentGesture(source,stage,intent,stream_intent,before_publish,started=started,requested=requested,key_id=key_id)
