"""Actual world Web geometry for an ordinary calibrated OpenXR gesture.

The native observer supplies the current entity/item/window transform. A
computed aim is input geometry only; it grants no hit, focus or feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.chat_journey.source_chunks import json_digest
from adapters.android.input_geometry import observed_grip_pose
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.pico4.browser_source import PicoBrowserIO,geometry_original,identity,IDENTITY
from adapters.normal_ui import NativeUIError

VERSION=1


def vector(value,size,bound=1e8):
    need(type(value) is list and len(value)==size and all(number(x,-bound,bound) for x in value))
    return value


def rotate(q,v):
    x,y,z,w=q;a,b,c=v
    cross=(y*c-z*b,z*a-x*c,x*b-y*a)
    second=(y*cross[2]-z*cross[1],z*cross[0]-x*cross[2],x*cross[1]-y*cross[0])
    return [v[i]+2*(w*cross[i]+second[i]) for i in range(3)]


def validate(packet,command):
    ray=packet['source']['worldRay'];epoch=packet['capturedEpochMs']
    exact(ray,{'worldWebRayVersion','capturedEpochMs','sourceIdentity','entityId','entityName','entityType','hostType',
        'sourceUrl','visible','ignorePickIntersection','position','rotation','dimensions','registrationPoint','dpi',
        'scenePoint','itemQuad','surfaceSize','worldPoint','sensorToWorld','headPosition'})
    need(type(ray['worldWebRayVersion']) is int and ray['worldWebRayVersion']==VERSION
        and integer(ray['capturedEpochMs'],1) and ray['capturedEpochMs']<=epoch)
    fresh(ray['capturedEpochMs'],epoch)
    entity=ray['entityId'];need(type(entity) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',entity)
        and entity!='00000000-0000-0000-0000-000000000000' and ray['sourceIdentity']=='web-entity:'+entity
        and ray['entityName']=='OVERTE_PARITY_WEB_REFERENCE' and ray['entityType']=='Web' and ray['hostType']=='local'
        and ray['visible'] is True and ray['ignorePickIntersection'] is False)
    need(type(ray['sourceUrl']) is str and ray['sourceUrl'].startswith(command['fixtureUrl']+'tickets/')
        and re.fullmatch('[0-9a-f]{32}/index\\.html',ray['sourceUrl'][len(command['fixtureUrl']+'tickets/'):]))
    position=vector(ray['position'],3);rotation=vector(ray['rotation'],4,1)
    need(abs(sum(x*x for x in rotation)-1)<=1e-5)
    dimensions=vector(ray['dimensions'],3);need(all(x>0 for x in dimensions))
    need(vector(ray['registrationPoint'],3)==[.5,.5,.5] and number(ray['dpi'],1,1024))
    size=ray['surfaceSize'];need(type(size) is list and len(size)==2 and all(integer(x,1,4096) for x in size))
    factor=39.3701*ray['dpi'];rendered=[x*factor for x in dimensions[:2]];scale=min(1,4096/max(rendered))
    need(all(abs(size[i]-int(rendered[i]*scale))<=1 for i in range(2)))
    point=vector(ray['scenePoint'],2);need(all(0<=point[i]<size[i] for i in range(2)))
    quad=ray['itemQuad'];need(type(quad) is list and len(quad)==4)
    for corner in quad:vector(corner,2)
    horizontal=[quad[1][i]-quad[0][i] for i in range(2)];vertical=[quad[3][i]-quad[0][i] for i in range(2)]
    need(abs(horizontal[0]*vertical[1]-horizontal[1]*vertical[0])>1e-6
        and all(abs(quad[2][i]-quad[0][i]-horizontal[i]-vertical[i])<=.001 for i in range(2)))
    dom=geometry_original(packet['source']['geometryRaw'],command,packet['source']['nativeView']['url'],epoch)
    uv=[dom['center'][key]/dom['viewport'][dimension] for key,dimension in (('x','width'),('y','height'))]
    need(all(abs(point[i]-quad[0][i]-uv[0]*horizontal[i]-uv[1]*vertical[i])<=.001 for i in range(2)))
    local=[point[0]/factor-dimensions[0]/2,dimensions[1]/2-point[1]/factor,0]
    offset=rotate(rotation,local);expected=[position[i]+offset[i] for i in range(3)]
    actual=vector(ray['worldPoint'],3)
    need(all(abs(actual[i]-expected[i])<=.001+abs(expected[i])*2e-7 for i in range(3)))
    vector(ray['sensorToWorld'],16);vector(ray['headPosition'],3)
    # The existing helper verifies affine tracking calibration and the bounded
    # physical grip range; a world target is never a touch/screen coordinate.
    observed_grip_pose(ray['sensorToWorld'],ray['headPosition'],actual)
    return ray


class PicoWorldBrowserIO(PicoBrowserIO):
    def measure_ray(self,run,url,owner,view,control):
        json_digest(view);identity(view)
        packet=self.request(run,url,owner,'measure-ray',control=control,
            **{key:view[key] for key in ('handle','creation','grant','page')})
        need(packet['source']['nativeView']=={key:view[key] for key in IDENTITY})
        ray=packet['source']['worldRay']
        need(ray['sourceIdentity']==view['sourceIdentity'] and ray['sourceUrl']==view['sourceUrl'])
        return packet


class PicoWorldRayClick:
    """One ordinary trigger gesture behind the enclosing owner's durable intent.

    The caller owns phase/input journals and independently observes the effect.
    Publication hooks are host-only; they cannot reenter the locked input SDK.
    An uncertain gesture permanently consumes this warm one-shot object.
    """
    def __init__(self,io,stage,intent,stream_intent,before_publish):
        need(type(io) is PicoWorldBrowserIO and not io.read_only
            and all(callable(value) for value in (stage,intent,stream_intent,before_publish)))
        self.io,self.stage,self.intent,self.stream_intent,self.before_publish=io,stage,intent,stream_intent,before_publish
        self.issued=self.failed=False

    def click(self,run,url,owner,view,control):
        need(not self.issued and not self.failed and control not in ('scroll-up','scroll-down'))
        io=self.io;io.lock.assert_held()
        try:
            acquired_start=io.monotonic();requested=io.clock_ms()
            reference=io.measure_ray(run,url,owner,view,control);ray=reference['source']['worldRay']
            pose=observed_grip_pose(ray['sensorToWorld'],ray['headPosition'],ray['worldPoint'])
            value=dict(operation='world-browser-trigger',control=control,reference=reference,pose=pose)
            seal=json_digest(value)
            geometry=geometry_original(reference['source']['geometryRaw'],
                dict(commandId=reference['commandId'],runId=run,control=control),view['url'],reference['capturedEpochMs'])
            earliest=min(reference['capturedEpochMs'],ray['capturedEpochMs'],geometry['capturedEpochMs'])
            epoch=io.clock_ms();started=io.monotonic()
            need(integer(requested,1) and integer(epoch,earliest) and number(acquired_start,0,1e15)
                and number(started,acquired_start,acquired_start+5))
            age=max(epoch-earliest,requested-earliest+(started-acquired_start)*1000);need(age<=1500)
            self.issued=True
            # The original clocks above cover this actual durable write too.
            self.intent(deepcopy(value));io.lock.assert_held();need(io.guard() is not False)
            current=io.clock_ms();need(integer(current,epoch) and current-earliest<=1500)
            original_envelope=None;envelope_sha=None;publications=0
            def validate_envelope(envelope):
                json_digest(envelope);exact(envelope,{'schemaVersion','sessionNonce','sequence','commands'})
                need(type(envelope['schemaVersion']) is int and envelope['schemaVersion']==1 and integer(envelope['sequence'],1)
                    and type(envelope['sessionNonce']) is str and re.fullmatch('[0-9a-f]{64}',envelope['sessionNonce'])
                    and type(envelope['commands']) is list and len(envelope['commands'])==1)
                command=envelope['commands'][0];exact(command,{'id','operation','arguments'})
                need(command['operation']=='input.primary' and command['id']=='input-primary-'+str(envelope['sequence'])
                    and json_digest(command['arguments'])==json_digest(pose))
            def stream_intent(envelope):
                nonlocal original_envelope,envelope_sha
                need(original_envelope is None);validate_envelope(envelope)
                original_envelope=deepcopy(envelope);envelope_sha=json_digest(original_envelope)
                self.stream_intent(deepcopy(envelope))
            def pure_fence(envelope=None):
                nonlocal publications
                io.lock.assert_held();need(not self.failed and json_digest(value)==seal)
                now=io.monotonic();need(number(now,started,started+1.5) and age+(now-started)*1000<=1500)
                if envelope is not None:
                    validate_envelope(envelope)
                    need(original_envelope is not None and json_digest(envelope)==envelope_sha
                        and json_digest(original_envelope)==envelope_sha)
                    self.before_publish(deepcopy(envelope));publications+=1
                now=io.monotonic();need(number(now,started,started+1.5) and age+(now-started)*1000<=1500)
                need(json_digest(value)==seal)
            pure_fence()
            result=self.stage(deepcopy(pose),intent=stream_intent,before_publish=pure_fence)
            # The input lock has exited. A late reply retains uncertain parent
            # ownership; no second gesture can be attempted by this object.
            io.lock.assert_held();need(io.guard() is not False)
            final=io.clock_ms();now=io.monotonic()
            need(integer(final,epoch) and number(now,started,started+1.5)
                and max(final-earliest,age+(now-started)*1000)<=1500)
            need(publications>=1 and original_envelope is not None and json_digest(original_envelope)==envelope_sha
                and json_digest(value)==seal);return result
        except BaseException:
            self.failed=True
            raise NativeUIError('Original world Web trigger is unresolved; input ownership remains') from None


def bind_world_click(adapter,target,io,intent,stream_intent,before_publish):
    """Use the existing launcher/session; no new input stream or device owner."""
    identity=adapter.require_pico_session_identity(target)
    def stage(pose,*,intent,before_publish):
        need(adapter.require_pico_session_identity(target)==identity)
        return adapter.pico_input_session(target).stage(identity,'input.primary',pose,
            intent=intent,before_publish=before_publish)
    return PicoWorldRayClick(io,stage,intent,stream_intent,before_publish)
