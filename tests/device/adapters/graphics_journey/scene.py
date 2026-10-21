"""Owned ordinary Graphics scene/view preparation and restoration.

This component proves its own original setup/cleanup. It does not advertise a
feature operation or substitute setup evidence for a fresh Graphics sample.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import time
from urllib.parse import urlsplit,urlunsplit,unquote

from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_scene_loads import validate as loads_packet,continuity,committed,resource_hash
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier
from feature_journeys.graphics_resources import RESOURCE,validate_status
from feature_journeys.graphics_fixture import LEGACY_PROFILE
from feature_journeys.witness import Client
from adapters.graphics_journey.geometry import near
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.graphics_journey.restart_proof import validate as restart_proof

VERSION=4


def operation(method):
    """A deadline belongs to the current call, never a later owner's input."""
    @wraps(method)
    def invoke(self,*args,**kwargs):
        outer=self.started is None
        if outer:self.started=self.monotonic()
        try:return method(self,*args,**kwargs)
        finally:
            if outer:self.started=None
    return invoke


def rotation_equal(a,b,tolerance=.001):return near(a,b,tolerance) or near(a,[-v for v in b],tolerance)


def viewpoint(url,feet,orientation):
    resource_hash(url)
    need(type(feet) is list and len(feet)==3 and all(number(v,-1e6,1e6) for v in feet)
         and type(orientation) is list and len(orientation)==4 and all(number(v,-1.01,1.01) for v in orientation))
    def decimal(value):return format(value,'.9f').rstrip('0').rstrip('.') or '0'
    location='/'+','.join(decimal(v) for v in feet)+'/'+','.join(decimal(v) for v in orientation)
    parsed=urlsplit(url);query=[item for item in parsed.query.split('&') if item and unquote(item.partition('=')[0])!='location']
    query.append('location='+location)
    result=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'&'.join(query),''))
    need(resource_hash(result)==resource_hash(url));return result


class GraphicsScene:
    def __init__(self,adapter,selector,client,run,lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(client,Client) and client.run==run and client.area=='graphics'
             and isinstance(lock,ScriptSourceLock) and callable(monotonic) and callable(sleep))
        identifier(run);identifier(client.graphics_instance)
        self.policy=adapter.graphics_scene_policy
        self.adapter,self.selector,self.client,self.run,self.lock=adapter,selector,client,run,lock
        self.monotonic,self.sleep,self.started,self.last_clock=monotonic,sleep,None,None
        path=adapter.state_path(selector);need(lock.path==path.with_name('script-sources.lock'));lock.assert_held()
        self.store=PrivateFeatureState(path.with_name('graphics-scene.json'))
        _ui,_observer,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0])
        self.previous=self.store.read()
        self.state=dict(binding=self.binding,phase='reserved',original=None,subject=None,loads=None,provider=None,
            sceneTicket=None,targetFeet=None,targetOrientation=None,alignmentSubject=None,leases=dict(tablet=False,address=False,menu=False),actions=[],current=None,proof=None,handoff=None)
        if self.previous is not None:
            self.state=self.decode(self.previous);need(same(self.state['binding'],self.binding))
        self.subject=adapter._graphics_subject_observer(selector,read_only=True)
        self.loads=adapter._scene_load_observer(selector,read_only=True)
        if self.previous is None:self.save()

    def decode(self,value,*,allow_restart=True):
        exact(value,{'graphicsSceneVersion','scenePolicy','runId','fixtureUrl','providerInstance','payload'})
        need(type(value['graphicsSceneVersion']) is int and value['graphicsSceneVersion'] in (3,4) and value['runId']==self.run
            and value['fixtureUrl']==self.client.url and value['providerInstance']==self.client.graphics_instance
            and value['scenePolicy']==self.policy.profile)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','phase','original','subject','loads','provider','sceneTicket','targetFeet','targetOrientation','alignmentSubject','leases','actions','current','proof','handoff'})
        context(state['binding']);pid=int(state['binding']['processIdentity'].split(':')[0])
        original_pid=pid;floor=None
        if state['handoff'] is not None:
            need(allow_restart);handoff=state['handoff'];exact(handoff,{'previous','receipt','subject','loads'})
            previous=self.decode(handoff['previous'],allow_restart=False);receipt=restart_proof(handoff['receipt']);plan=receipt['input']
            need(same(previous['binding'],plan['oldBinding']) and same(state['binding'],plan['newBinding'])
                and previous['phase']=='active' and previous['original'] is not None and not any(previous['leases'].values())
                and same(state['original'],previous['original']) and state['sceneTicket']==previous['sceneTicket']
                and receipt['oldNative']['instance']==previous['subject']['instance']
                and receipt['oldNative']['capturedEpochMs']>=previous['subject']['capturedEpochMs'])
            need(plan['ownerFiles']==[str(self.store.path),*[str(self.adapter.world_render_store(self.selector,role=role).path) for role in ('primary','actor')]])
            original_pid=int(previous['binding']['processIdentity'].split(':')[0]);floor=handoff['subject']
            self.validate_subject(floor,pid);self.validate_loads(handoff['loads'],pid)
            need(floor['instance']==receipt['native']['instance'] and floor['requestedEpochMs']>=receipt['native']['capturedEpochMs']
                and not floor['source']['entities'] and len(floor['source']['absentIds'])==7
                and handoff['loads']['instance']!=previous['loads']['instance']
                and handoff['loads']['capturedEpochMs']>=floor['capturedEpochMs'])
            need(state['subject'] is not None and state['subject']['instance']==floor['instance']
                and state['subject']['sequence']>=floor['sequence'] and state['subject']['capturedEpochMs']>=floor['capturedEpochMs'])
            if not same(handoff['loads'],state['loads']):continuity(handoff['loads'],state['loads'],pid)
        need(state['phase'] in ('reserved','preparing','active','restoring','restored') and type(state['actions']) is list and len(state['actions'])<=16)
        exact(state['leases'],{'tablet','address','menu'});need(all(type(v) is bool for v in state['leases'].values()))
        if state['sceneTicket'] is not None:identifier(state['sceneTicket'])
        if state['targetFeet'] is not None:need(type(state['targetFeet']) is list and len(state['targetFeet'])==3 and all(number(v,-1e6,1e6) for v in state['targetFeet']))
        if state['alignmentSubject'] is None:need(state['targetFeet'] is None and state['targetOrientation'] is None)
        else:
            self.validate_subject(state['alignmentSubject'],pid)
            need(state['subject'] is not None and state['alignmentSubject']['instance']==state['subject']['instance']
                and state['alignmentSubject']['sequence']<=state['subject']['sequence'])
            self.policy.aligned_entities(state['alignmentSubject'],self.run,state['sceneTicket'],self.client.url+'/runs/'+self.run+'/')
            feet,orientation=self.policy.alignment(state['alignmentSubject'])
            need(state['targetFeet']==feet and state['targetOrientation']==orientation)
        if state['subject'] is not None:self.validate_subject(state['subject'],pid)
        if state['loads'] is not None:self.validate_loads(state['loads'],pid)
        if state['original'] is not None:
            exact(state['original'],{'subject','loads','restoreUrl'})
            self.validate_subject(state['original']['subject'],original_pid)
            need(state['subject'] is not None and state['loads'] is not None)
            original,latest=state['original']['subject'],state['subject']
            if state['handoff'] is None:
                need(latest['instance']==original['instance'] and latest['sequence']>=original['sequence']
                    and latest['capturedEpochMs']>=original['capturedEpochMs'])
                if not same(state['original']['loads'],state['loads']):continuity(state['original']['loads'],state['loads'],pid)
            self.policy.eligible(state['original']['subject']);self.validate_loads(state['original']['loads'],original_pid)
            committed(state['original']['loads'],state['original']['subject']['source']['sceneUrl'])
            pose=state['original']['subject']['source']['avatarPose']
            need(state['original']['restoreUrl']==viewpoint(state['original']['subject']['source']['sceneUrl'],pose['feetPosition'],pose['orientation']))
        if state['provider'] is not None:validate_status(state['provider'],instance=self.client.graphics_instance,run=self.run,url=self.client.url,request=state['provider']['requestId'])
        kinds=set()
        for action in state['actions']:
            exact(action,{'kind','url','phase','inputs'})
            need(action['kind'] in ('enter','align','restore','restore-close','camera') and action['kind'] not in kinds
                and action['phase'] in ('issued','acknowledged','observed') and type(action['inputs']) is list and len(action['inputs'])<=128)
            need(state['original'] is not None and state['sceneTicket'] is not None)
            root=self.client.url+'/runs/'+self.run+'/tickets/'+state['sceneTicket']+'/'+getattr(self.policy,'fixture_resource',RESOURCE)
            expected={'enter':viewpoint(root,[0,0,0],[0,0,0,1]),'restore':state['original']['restoreUrl'],'restore-close':None}
            if action['kind']=='camera':need(state['handoff'] is not None);expected['camera']=None
            if action['kind']=='align':
                need(state['targetFeet'] is not None);expected['align']=viewpoint(root,state['targetFeet'],state['targetOrientation'])
            need(action['url']==expected[action['kind']])
            for item in action['inputs']:
                exact(item,{'stage','subject','graphics','control'});self.validate_subject(item['subject'],pid)
                need(type(item['stage']) is str and len(item['stage'])<=80 and type(item['control']) is str and len(item['control'])<=256)
                baseline=floor or state['original']['subject']
                need(item['subject']['instance']==baseline['instance']
                    and baseline['sequence']<item['subject']['sequence']<=state['subject']['sequence'])
            kinds.add(action['kind'])
        need(state['current'] is None or integer(state['current'],0,len(state['actions'])-1))
        if state['phase'] in ('active','restoring','restored'):need(state['original'] is not None or not state['actions'])
        if state['phase']=='restored':
            need(not any(state['leases'].values()))
            if state['original'] is not None:
                exact(state['proof'],{'subject','loads'})
                self.validate_subject(state['proof']['subject'],pid);self.validate_loads(state['proof']['loads'],pid)
                self.restored(state['original']['subject'],state['proof']['subject'],state['handoff']);committed(state['proof']['loads'],state['proof']['subject']['source']['sceneUrl'])
                need(same(state['subject'],state['proof']['subject']) and same(state['loads'],state['proof']['loads']))
            else:need(state['proof'] is None and not state['actions'])
        return state

    @classmethod
    def restart_record(cls,previous,receipt,subject,loads):
        """Build a proposed CAS value from preserved originals, never measurements.

        The restart controller must validate old/new sources, durably save this
        proposal and apply it only after independently proving original PID death.
        Normal construction fully revalidates the closed nested receipt/archive.
        """
        receipt=restart_proof(receipt);state=unpack(previous['payload'])[0]
        need(type(previous['graphicsSceneVersion']) is int and previous['graphicsSceneVersion'] in (3,4)
            and state['handoff'] is None and state['phase']=='active'
            and not any(state['leases'].values()) and same(state['binding'],receipt['input']['oldBinding']))
        state.update(binding=deepcopy(receipt['input']['newBinding']),phase='preparing',subject=deepcopy(subject),loads=deepcopy(loads),
            targetFeet=None,targetOrientation=None,alignmentSubject=None,actions=[],current=None,proof=None,handoff=dict(previous=deepcopy(previous),receipt=receipt,
                subject=deepcopy(subject),loads=deepcopy(loads)))
        return deepcopy(previous)|dict(graphicsSceneVersion=VERSION,payload=pack([state]))

    def restored(self,original,current,handoff=None):
        if handoff is None:return self.policy.restored(original,current)
        # Only a decoded, qualified restart handoff may select the independent
        # new-process framework baseline. No current ID is relabelled as old.
        return self.policy.restored(original,current,framework_original=handoff['subject'])

    @classmethod
    def archive(cls,value,*,adapter,selector,client,run):
        """Pure historical validation; no SDK/read/repair or usable live owner."""
        scope=cls._archive_scope(adapter=adapter,selector=selector,client=client,run=run)
        return deepcopy(scope.decode(value))

    @classmethod
    def _archive_scope(cls,*,adapter,selector,client,run):
        # Decoder fields only. No runtime/source/guard exists on this object;
        # it cannot be used for a live read or ordinary input.
        need(isinstance(client,Client) and client.run==run and client.area=='graphics');identifier(run)
        scope=object.__new__(cls);scope.adapter,scope.selector,scope.client,scope.run=adapter,selector,client,run
        scope.policy=adapter.graphics_scene_policy
        scope.store=PrivateFeatureState(adapter.state_path(selector).with_name('graphics-scene.json'))
        return scope

    def validate_subject(self,packet,pid):
        subject_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='feature-graphics-subject-observe',runId=self.run),pid,packet['capturedEpochMs'],require_avatar=True,require_framework=self.policy.require_framework)
    def validate_loads(self,packet,pid):
        loads_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-scene-load-observe',runId=self.run),pid,packet['capturedEpochMs'])
        need(packet['complete'] is True)
    def bound(self):
        self.lock.assert_held();need(self.guard() is not False)
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or self.started<=now and now-self.started<45));self.last_clock=now
    def save(self):
        self.bound();need(same(self.store.read(),self.previous))
        value=dict(graphicsSceneVersion=VERSION,scenePolicy=self.policy.profile,runId=self.run,fixtureUrl=self.client.url,providerInstance=self.client.graphics_instance,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def accept_subject(self,packet):
        self.validate_subject(packet,self.pid);old=self.state['subject']
        if old is not None:need(packet['instance']==old['instance'] and packet['sequence']>old['sequence'] and packet['capturedEpochMs']>=old['capturedEpochMs'])
        self.state['subject']=deepcopy(packet);self.save();return packet
    def read_subject(self):
        self.subject.last=deepcopy(self.state['subject']);return self.accept_subject(self.subject.read(self.run,require_avatar=True,require_framework=self.policy.require_framework))
    def read_loads(self):
        self.loads.last=deepcopy(self.state['loads']);packet=self.loads.read(self.run)
        continuity(self.state['loads'],packet,self.pid);self.state['loads']=deepcopy(packet);self.save();return packet
    def provider(self):
        packet=self.client.graphics_status()
        validate_status(packet,instance=self.client.graphics_instance,run=self.run,url=self.client.url,request=packet['requestId'],previous=self.state['provider'])
        need(packet['active'] is True)
        need(packet.get('profile',LEGACY_PROFILE)==getattr(self.policy,'fixture_profile',LEGACY_PROFILE))
        if self.state['sceneTicket'] is not None:need(packet['sceneTicket']==self.state['sceneTicket'])
        self.state['provider']=deepcopy(packet);self.save();return packet
    def intent(self,stage,subject,graphics,control):
        need(self.state['original'] is not None and self.state['current'] is not None)
        self.accept_subject(subject);action=self.state['actions'][self.state['current']]
        need(action['phase']=='issued' and len(action['inputs'])<128)
        action['inputs'].append(dict(stage=stage,subject=deepcopy(subject),graphics=deepcopy(graphics),control=control));self.save()
    def lease(self,field,value):
        need(field in self.state['leases'] and type(value) is bool and self.state['current'] is not None)
        self.state['leases'][field]=value;self.save()
    def surface(self):
        surface=self.adapter._graphics_surface(self.selector,self.run,self.intent,
            lambda field:self.state['leases'][field],self.lease,
            lambda url:any(row['url']==url for row in self.state['actions'] if row['url'] is not None),lock=self.lock)
        surface.subject.last=deepcopy(self.state['subject']);return surface
    def action(self,kind,url=None):
        prior=[i for i,row in enumerate(self.state['actions']) if row['kind']==kind]
        if prior:
            index=prior[0];need(self.state['actions'][index]['url']==url);self.state['current']=index;self.save();return index,False
        need(len(self.state['actions'])<16)
        self.state['actions'].append(dict(kind=kind,url=url,phase='issued',inputs=[]));index=len(self.state['actions'])-1
        self.state['current']=index;self.save();return index,True
    def navigate(self,kind,url):
        index,new=self.action(kind,url)
        if new:
            self.surface().navigate(url);self.state['actions'][index]['phase']='acknowledged';self.save()
        return index
    def wait(self,check):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(101):
            packet=self.read_subject();loads=self.read_loads();self.bound()
            try:check(packet,loads)
            except NativeUIError:
                if self.monotonic()-started>=20 or attempt==100:break
                self.sleep(.1);continue
            return packet,loads
        raise NativeUIError('Owned Graphics scene did not reach its original readiness or restoration')

    @operation
    def prepare(self):
        self.bound();need(self.state['phase'] in ('reserved','preparing','active'))
        if self.state['original'] is None:
            first=self.read_subject();loads=self.read_loads();self.policy.eligible(first);committed(loads,first['source']['sceneUrl'])
            surface=self.surface()
            need(not surface.tablet_visible() and not surface.address_visible())
            second=self.read_subject();self.policy.eligible(second);self.policy.restored(first,second)
            pose=second['source']['avatarPose']
            self.state['original']=dict(subject=deepcopy(second),loads=deepcopy(loads),restoreUrl=viewpoint(second['source']['sceneUrl'],pose['feetPosition'],pose['orientation']))
            self.state['phase']='preparing';self.save()
        status=self.provider();need(status['sceneTicket'] is not None)
        if self.state['sceneTicket'] is None:self.state['sceneTicket']=status['sceneTicket'];self.save()
        root=self.client.url+'/runs/'+self.run+'/tickets/'+self.state['sceneTicket']+'/'+getattr(self.policy,'fixture_resource',RESOURCE)
        if self.state['handoff'] is not None:
            if not self.state['actions']:
                surface=self.surface();need(not surface.tablet_visible() and not surface.address_visible())
            current=self.read_subject()
            if current['source']['view']['mode']!=self.policy.camera_mode:
                index,new=self.action('camera')
                if new:self.surface().select_camera(self.policy.camera_mode)
                current=self.read_subject();need(current['source']['view']['mode']==self.policy.camera_mode)
                self.state['actions'][index]['phase']='observed';self.save()
        enter=self.navigate('enter',viewpoint(root,[0,0,0],[0,0,0,1]))
        def entered(packet,loads):
            self.policy.aligned_entities(packet,self.run,self.state['sceneTicket'],self.client.url+'/runs/'+self.run+'/')
            committed(loads,packet['source']['sceneUrl'])
            need(near(packet['source']['avatarPose']['modelScale'],self.state['original']['subject']['source']['avatarPose']['modelScale'],.0001))
        packet,_loads=self.wait(entered);self.state['actions'][enter]['phase']='observed';self.save()
        pose=packet['source']['avatarPose'];view=packet['source']['view']
        if self.state['targetFeet'] is None:
            feet,orientation=self.policy.alignment(packet)
            self.state.update(targetFeet=feet,targetOrientation=orientation,alignmentSubject=deepcopy(packet));self.save()
        align=self.navigate('align',viewpoint(root,self.state['targetFeet'],self.state['targetOrientation']))
        def ready(packet,loads):
            entered(packet,loads);self.policy.aligned_subject(packet,self.run,self.state['sceneTicket'],self.client.url+'/runs/'+self.run+'/')
            need(near(packet['source']['avatarPose']['feetPosition'],self.state['targetFeet'],.01)
                and rotation_equal(packet['source']['avatarPose']['orientation'],self.state['targetOrientation']))
        packet,loads=self.wait(ready);self.state['actions'][align]['phase']='observed';self.save()
        status=self.provider();need(any(row['status']==200 and row['completedEpochMs']<=packet['requestedEpochMs'] for row in status['responses']))
        self.state.update(phase='active',proof=None);self.save();self.bound()
        return deepcopy(dict(subject=packet,loads=loads,provider=status))

    @operation
    def restore(self):
        self.bound()
        if self.state['original'] is None:
            need(not self.state['actions'] and not any(self.state['leases'].values()))
            self.state.update(phase='restored',proof=None);self.save();return None
        need(self.state['phase'] in ('preparing','active','restoring','restored'))
        if self.state['sceneTicket'] is None and not self.state['actions']:
            need(not any(self.state['leases'].values()))
            packet=self.read_subject();loads=self.read_loads();self.restored(self.state['original']['subject'],packet,self.state['handoff']);committed(loads,packet['source']['sceneUrl'])
            self.state.update(phase='restored',proof=dict(subject=packet,loads=loads));self.save();return deepcopy(self.state['proof'])
        if self.state['phase']=='restored':
            packet=self.read_subject();loads=self.read_loads();self.restored(self.state['original']['subject'],packet,self.state['handoff']);committed(loads,packet['source']['sceneUrl'])
            self.state['proof']=dict(subject=packet,loads=loads);self.save();return deepcopy(self.state['proof'])
        self.state['phase']='restoring';self.save();index,new=self.action('restore-close')
        if new:
            surface=self.surface();surface.close_address();surface.close_tablet()
            self.state['actions'][index]['phase']='observed';self.save()
        else:
            surface=self.surface()
            if self.state['leases']['address'] and not surface.address_visible():surface.close_address()
            if self.state['leases']['tablet'] and not surface.tablet_visible():surface.close_tablet()
        index=self.navigate('restore',self.state['original']['restoreUrl'])
        def complete(packet,loads):self.restored(self.state['original']['subject'],packet,self.state['handoff']);committed(loads,packet['source']['sceneUrl'])
        packet,loads=self.wait(complete)
        need(not any(self.state['leases'].values()))
        self.state['actions'][index]['phase']='observed';self.state.update(phase='restored',proof=dict(subject=packet,loads=loads));self.save();self.bound()
        return deepcopy(self.state['proof'])

    @operation
    def retire(self):
        self.bound();need(self.state['phase']=='restored' and not any(self.state['leases'].values()))
        self.restore()
        self.decode(self.previous);need(same(self.store.read(),self.previous));self.store.discard(self.previous)
        need(self.store.read() is None)
