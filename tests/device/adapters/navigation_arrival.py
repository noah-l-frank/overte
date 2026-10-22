"""Independent original navigation pose and two-eye source joins.

No input, camera setter or image-feature verdict. A stereo source capture alone
cannot establish the full Navigation challenge/changed-world image contract.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_graphics_subject import validate as subject_packet
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.vr_graphics_subject import first_person_head
from adapters.world_render_evidence import validate as capture_packet,original_pixels,camera_batches
from contracts import validate_probe_snapshot
from navigation_observation import FreshNavigation,project_probe,arrived,viewpoint_urls,same_viewpoint

VERSION=1
STEREO_VERSION=2


def pose_packet(value,run,binding,scene_url,epoch):
    exact(value,{'navigationPoseVersion','probe','subject'})
    need(type(value['navigationPoseVersion']) is int and value['navigationPoseVersion']==VERSION)
    context(binding);pid=int(binding['processIdentity'].split(':',1)[0]);probe=value['probe'];subject=value['subject']
    validate_probe_snapshot(probe);fresh(probe['sampleEpochMs'],epoch)
    need(type(probe.get('nativeMotion')) is dict and probe['nativeMotion']['processId']==pid
         and integer(probe['nativeMotion']['sampleSequence'],1) and integer(probe['nativeMotion']['sampleEpochMs'],1)
         and 0<=probe['sampleEpochMs']-probe['nativeMotion']['sampleEpochMs']<=1500)
    subject_packet(subject,dict(schemaVersion=1,commandId=subject.get('requestId'),action='feature-graphics-subject-observe',runId=run),
        pid,epoch,require_avatar=True,require_framework=True)
    first_person_head(subject)
    projection,_advanced=FreshNavigation().accept(project_probe(probe))
    labels=[label for label,url in viewpoint_urls(scene_url).items() if arrived(projection,url,label)]
    need(len(labels)<=1)
    source=subject['source'];actual=[probe['avatar']['feetPosition'][axis] for axis in 'xyz']
    need(math.dist(actual,source['avatarPose']['feetPosition'])<=.05
         and 0<=subject['capturedEpochMs']-probe['sampleEpochMs']<=1500)
    # Both independent sources must describe the actual same original address.
    # Never turn the requested destination or a Camera position into avatar feet.
    need(source['sceneUrl']==probe['scene']['url'] or same_viewpoint(source['sceneUrl'],probe['scene']['url']))
    return labels[0] if labels else None


def advance(old,new):
    a,b=old['probe'],new['probe'];need(b['sampleSequence']>a['sampleSequence'] and b['sampleEpochMs']>=a['sampleEpochMs']
        and b['render']['frameCount']>=a['render']['frameCount']
        and b['nativeMotion']['sampleSequence']>=a['nativeMotion']['sampleSequence']
        and b['nativeMotion']['sampleEpochMs']>=a['nativeMotion']['sampleEpochMs'])
    a,b=old['subject'],new['subject'];need(a['instance']==b['instance'] and b['sequence']>a['sequence']
        and b['capturedEpochMs']>=a['capturedEpochMs'] and b['requestId']!=a['requestId'])


class NavigationArrival:
    def __init__(self,probe,subject,clock_ms,guard,run,binding,scene_url,*,monotonic=time.monotonic):
        need(all(callable(f) for f in (probe,clock_ms,guard,monotonic)));context(binding);viewpoint_urls(scene_url)
        self.probe,self.subject,self.clock_ms,self.guard=probe,subject,clock_ms,guard
        self.run,self.binding,self.scene_url=run,deepcopy(binding),scene_url
        self.monotonic=monotonic;self.last=None;self.requests=set()
    def read(self,*,floor=None):
        try:
            need(self.guard() is not False);started=self.monotonic();need(number(started,0,1e15))
            old=self.last if self.last is not None else floor
            probe=self.probe(0 if old is None else old['probe']['sampleSequence'])
            subject=self.subject.read(self.run,require_avatar=True,require_framework=True)
            value=dict(navigationPoseVersion=VERSION,probe=probe,subject=subject)
            pose_packet(value,self.run,self.binding,self.scene_url,self.clock_ms())
            if old is not None:advance(old,value)
            if floor is not None and floor!=old:advance(floor,value)
            request=subject['requestId'];need(request not in self.requests and len(self.requests)<4096)
            self.requests.add(request)
            now=self.monotonic();need(number(now,0,1e15) and started<=now and now-started<5 and self.guard() is not False)
            self.last=deepcopy(value);return value
        except Exception:raise NativeUIError('Original navigation pose sources are unavailable or disagree') from None


def camera_position(view):
    # Solve the actual affine world-to-camera matrix. No fixed Phone eye or
    # reconstruction of the submitted GPU camera is substituted for this input.
    rows=[[view[c*4+r] for c in range(3)]+[-view[12+r]] for r in range(3)]
    for c in range(3):
        pivot=max(range(c,3),key=lambda r:abs(rows[r][c]));need(abs(rows[pivot][c])>1e-12)
        rows[c],rows[pivot]=rows[pivot],rows[c];scale=rows[c][c];rows[c]=[v/scale for v in rows[c]]
        for r in range(3):
            if r!=c:
                scale=rows[r][c];rows[r]=[a-scale*b for a,b in zip(rows[r],rows[c])]
    return [row[3] for row in rows]


def stereo_pose(before,capture,after,raw,run,binding,scene_url,epoch,*,require_location=True):
    """Original HMD pose/GPU/eye/presentation proof shared by stereo surfaces.

    Navigation additionally requires its independently observed known location.
    Other surfaces retain their actual unchanged world URL and must separately
    qualify their original UI/document and per-eye pixels.
    """
    context(binding);pid=int(binding['processIdentity'].split(':',1)[0]);end=epoch
    a=pose_packet(before,run,binding,scene_url,before['subject']['capturedEpochMs']);b=pose_packet(after,run,binding,scene_url,end)
    need(type(require_location) is bool and a==b and (not require_location or a is not None))
    if not require_location:
        need(before['subject']['source']['sceneUrl']==after['subject']['source']['sceneUrl'])
    advance(before,after)
    capture_packet(capture,capture.get('requestId'),pid,end,stereo=True,require_cameras=True);original_pixels(capture,raw)
    need(before['subject']['capturedEpochMs']<=capture['requestedEpochMs']
         and capture['capturedEpochMs']<=after['subject']['requestedEpochMs'])
    h1,h2=first_person_head(before['subject']),first_person_head(after['subject'])
    need(math.dist(before['subject']['source']['avatarPose']['feetPosition'],after['subject']['source']['avatarPose']['feetPosition'])<=.05)
    source=capture['source'];recorded=source['renderTrace']['recordedView']
    need(all(math.dist(recorded['position'],h['worldPosition'])<=.15 for h in (h1,h2)))
    from adapters.vr_graphics_subject import rotation_columns
    actual=rotation_columns(recorded['rotation'])
    for h in (h1,h2):
        expected=rotation_columns(h['worldRotation'])
        need(all(abs(actual[c][r]-expected[c][r])<=.08 for c in range(3) for r in range(3)))
    forward=[batch for batch in camera_batches(source) if batch['role']=='forward'];need(forward)
    for batch in forward:
        centres={}
        for camera in batch['cameras']:centres.setdefault(camera['slot'],{})[camera['eye']]=camera_position(camera['view'])
        for pair in centres.values():
            need(set(pair)=={'left','right'});centre=[(a+b)/2 for a,b in zip(pair['left'],pair['right'])]
            need(all(math.dist(centre,h['worldPosition'])<=.15 for h in (h1,h2)))
    # Native exact pixels, two distinct original eye descriptors and successful
    # same-frame OpenXR submission are proved. No scene marker/change is guessed.
    return dict(location=a,frameIndex=source['stereo']['frameIndex'],executionSequence=source['stereo']['executionSequence'],
        submissionSequence=source['presentation']['submissionSequence'],imageSha256=source['image']['sha256'])


def stereo_frame(value,raw,run,binding,scene_url):
    """Historical original frame/pose analysis, never a current sample verdict."""
    version=value.get('navigationStereoSourceVersion') if type(value) is dict else None
    exact(value,{'navigationStereoSourceVersion','runId','binding','before','capture','after'}|({'uiBefore','uiAfter','nativeBefore','nativeAfter'} if version==2 else set()))
    need(type(version) is int and version in (1,2)
         and value['runId']==run and value['binding']==binding)
    before,after,capture=value['before'],value['after'],value['capture'];context(binding)
    pid=int(binding['processIdentity'].split(':',1)[0]);end=value['nativeAfter']['capturedEpochMs'] if version==2 else after['subject']['capturedEpochMs']
    if version==2:
        from adapters.native_feature_observation import validate as native_packet
        native_a,native_b=value['nativeBefore'],value['nativeAfter']
        for packet in (native_a,native_b):
            native_packet(packet,packet.get('requestId'),pid,end);need(integer(packet.get('requestedEpochMs'),1))
        need(native_a['instance']==native_b['instance']==before['subject']['instance']
             and native_a['requestId']!=native_b['requestId'] and native_b['sequence']>native_a['sequence']
             and native_a['lifecycle']==native_b['lifecycle'] and native_a['graphics']==native_b['graphics']
             and native_a['capturedEpochMs']<=before['probe']['sampleEpochMs']
             and after['subject']['capturedEpochMs']<=native_b['requestedEpochMs'])
        from adapters.pico4.graphics_source import validate as ui_packet,PROFILES,accept_inventory
        a_ui,b_ui=value['uiBefore'],value['uiAfter']
        for packet in (a_ui,b_ui):
            ui_packet(packet,packet.get('commandId'),pid,end)
            need(not packet['tabletShown'] and not packet['editorFocused'] and not packet['graphicsInventory']['keyboard3D']['raised'])
        accept_inventory(a_ui['graphicsInventory'],b_ui['graphicsInventory'],profiles=PROFILES)
        need(a_ui['instance']==b_ui['instance'] and a_ui['generation']==b_ui['generation']
             and a_ui['commandId']!=b_ui['commandId'] and b_ui['sourceSequence']>a_ui['sourceSequence']
             and b_ui['elapsedMs']>=a_ui['elapsedMs'] and a_ui['lastCommandSequence']==b_ui['lastCommandSequence']
             and before['subject']['capturedEpochMs']<=a_ui['capturedEpochMs']<=capture['requestedEpochMs']
             and capture['capturedEpochMs']<=b_ui['capturedEpochMs']<=after['probe']['sampleEpochMs'])
    return stereo_pose(before,capture,after,raw,run,binding,scene_url,end)
