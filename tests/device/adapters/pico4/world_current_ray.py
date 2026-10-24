"""One normal existing Session.primary publication from CurrentInput1 originals.

No new journey/session, focus setter, gesture recovery or target-effect ACK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need,number,fresh
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.source_chunks import json_digest
from adapters.android.input_geometry import observed_grip_pose
from adapters.pico4.world_current_input import PicoWorldCurrentInput,decode,validate


class PicoWorldCurrentRay:
    def __init__(self,source,stage,intent,stream_intent,before_publish):
        need(type(source) is PicoWorldCurrentInput and all(callable(v) for v in (stage,intent,stream_intent,before_publish)))
        self.source,self.stage,self.intent,self.stream_intent,self.before_publish=source,stage,intent,stream_intent,before_publish
        self.issued=self.failed=False;self.envelope=None

    def publish(self):
        source=self.source
        need(not self.issued and not self.failed and source.lock._owner is None and source._warm_anchor is not None)
        try:
            original=source.original();seal=json_digest(original);started,requested,original_seal=source._warm_anchor
            need(seal==original_seal and original['request']['operation']=='measure-current-ray')
            packet=decode(original['raw']);validate(packet,original['request'],source.pid,source.clock_ms(),original['documentOriginal'])
            doc=decode(original['documentOriginal']['raw']);ray=packet['source']['worldRay']
            pose=observed_grip_pose(ray['sensorToWorld'],ray['headPosition'],ray['worldPoint'])
            earliest=min(doc['requestedEpochMs'],packet['requestedEpochMs'])
            def original_fresh():
                source.require_warm(original)
            original_fresh();self.issued=True
            with source.lock.held():
                value=dict(operation='world-current-trigger',calibrationOriginal=deepcopy(original),pose=deepcopy(pose))
                self.intent(deepcopy(value));original_fresh();source.lock.assert_held()
                envelope=None;envelope_seal=None;publications=0
                def check(command):
                    exact(command,{'schemaVersion','sessionNonce','sequence','commands'})
                    need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                         and type(command['sessionNonce']) is str and re.fullmatch('[0-9a-f]{64}',command['sessionNonce'])
                         and integer(command['sequence'],1) and type(command['commands']) is list and len(command['commands'])==1)
                    item=command['commands'][0];exact(item,{'id','operation','arguments'})
                    need(item['operation']=='input.primary' and item['id']=='input-primary-'+str(command['sequence'])
                         and json_digest(item['arguments'])==json_digest(pose))
                def stream(command):
                    nonlocal envelope,envelope_seal
                    need(envelope is None);check(command);envelope=deepcopy(command);envelope_seal=json_digest(envelope)
                    self.stream_intent(deepcopy(command))
                def publish(command):
                    nonlocal publications
                    # Original Session/transport hold their own lock here.
                    # Host-only pinned bytes/elapsed checks, no SDK/clock read.
                    source.lock.assert_held();check(command)
                    need(envelope is not None and json_digest(command)==envelope_seal and json_digest(envelope)==envelope_seal
                         and json_digest(original)==seal and json_digest(source.original())==seal)
                    now=source.monotonic();need(number(now,started,started+1.5) and requested-earliest+(now-started)*1000<=1500)
                    self.before_publish(deepcopy(command));publications+=1
                    need(json_digest(original)==seal and json_digest(source.original())==seal)
                    now=source.monotonic();need(number(now,started,started+1.5) and requested-earliest+(now-started)*1000<=1500)
                publication=self.stage(deepcopy(pose),intent=stream,before_publish=publish)
                need(envelope is not None and publications>=1 and json_digest(envelope)==envelope_seal)
                result=dict(calibrationOriginal=deepcopy(original),streamEnvelope=deepcopy(envelope),publication=deepcopy(publication))
                returned=deepcopy(result)
            # No new sample/clock anchor after real outer release. Old capture
            # ages still cover SDK work, ACK and final result copy.
            need(json_digest(original)==seal and json_digest(source.original())==seal)
            saved_envelope,saved_calibration=deepcopy(envelope),deepcopy(original)
            original_fresh()
            self.envelope,self._calibration,self._calibration_seal=saved_envelope,saved_calibration,seal
            return returned
        except BaseException:
            self.failed=True
            raise NativeUIError('Current World trigger is unresolved; preserve original intent/stream and do not replay') from None

    def check_focus(self,returned,focus_original):
        """Join fresh independent focus/DOM; publication alone grants no effect."""
        need(self.issued and not self.failed and self.envelope is not None)
        source=self.source;packet=decode(focus_original['raw']);call=focus_original['request']
        need(call['operation']=='observe-current-focus' and packet['status']=='ready')
        validate(packet,call,source.pid,source.clock_ms(),focus_original['documentOriginal'])
        need(json_digest(returned['calibrationOriginal'])==self._calibration_seal and json_digest(self._calibration)==self._calibration_seal)
        calibrated=self._calibration['request']
        need(calibrated['control'] in ('text','foreign')
             and all(call[key]==calibrated[key] for key in ('control','runId','ownerToken','fixtureUrl')))
        old=decode(self._calibration['raw'])['source'];new=packet['source']
        from adapters.pico4.world_current_document import semantic
        # A new readable grant after publication cannot resolve the old input.
        need(json_digest(semantic(old['authorityBefore']['native']))==json_digest(semantic(new['authorityAfter']['native']))
             and json_digest(old['originalFinish'])==json_digest(new['originalFinish'])
             and json_digest(returned['streamEnvelope'])==json_digest(self.envelope))
        from adapters.pico4.browser_source import geometry_original
        geometry=geometry_original(decode(new['focusRaw'])['geometryRaw'],call,
            new['authorityBefore']['native']['url'],packet['capturedEpochMs'])
        need(geometry['editor']['focused'] is True and new['nativeEditor']['focused'] is True and new['nativeEditor']['enabled'] is True)
        result=deepcopy(focus_original)
        source.require_warm(focus_original)
        return result


def bind_current_ray(adapter,target,source,intent,stream_intent,before_publish,admission):
    need(callable(admission));identity=adapter.require_pico_session_identity(target)
    session=adapter.pico_input_session(target)
    def stage(pose,*,intent,before_publish):
        need(adapter.require_pico_session_identity(target)==identity)
        admission() # Existing exact phase fence, outside the Session lock.
        return session.stage(identity,'input.primary',pose,intent=intent,before_publish=before_publish)
    return PicoWorldCurrentRay(source,stage,intent,stream_intent,before_publish)
