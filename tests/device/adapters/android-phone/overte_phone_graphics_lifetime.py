"""Original per-role Graphics fixture/Web lifetime; measurement only, no input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_phone_scene_loads import validate as loads_packet,continuity as load_continuity,committed
from adapters.native_phone_web_runtime import validate as web_packet,continuity as web_continuity,active_marker,released
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from overte_phone_graphics_fixture import GraphicsFixtureReader
from overte_phone_graphics_measurements import aligned_entities
from overte_phone_graphics_scene import restored,eligible
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1
CURSORS=('provider','subject','loads','web')


class PhoneGraphicsLifetime:
    def __init__(self,adapter,selector,source,role,stage,lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,GraphicsFixtureReader) and role in ('primary','actor') and integer(stage,0,1)
            and isinstance(lock,PhoneScriptSourceLock) and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role,self.stage,self.lock=adapter,selector,source,role,stage,lock
        self.monotonic,self.sleep=monotonic,sleep
        self.run,self.fixture_url=source.run,source.fixture_url
        lock.assert_held();path=adapter.state_path(selector)
        need(lock.path==path.with_name('phone-script-sources.lock'))
        self.store=PrivateFeatureState(path.with_name('phone-graphics-'+role+'-'+str(stage)+'-lifetime.json'))
        _ui,_observer,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0])
        self.previous=self.store.read()
        if self.previous is None:
            provider=source.status()
            self.state=dict(binding=self.binding,phase='ready',sequence=0,provider=provider,subject=None,loads=None,web=None,
                activeProofs=[],original=None,windows=[])
            self.save()
        else:
            if source.instance is None:source.status()
            self.state=self.decode(self.previous);need(same(self.binding,self.state['binding']))
        self.subject=adapter._graphics_subject_observer(selector,read_only=True)
        self.loads=adapter._scene_load_observer(selector,read_only=True)
        self.web=adapter._web_runtime_observer(selector,read_only=True)
        self.deadline=None;self.local_clock=None

    def request(self,packet,kind):
        action={'subject':'feature-graphics-subject-observe','loads':'feature-scene-load-observe','web':'feature-phone-web-runtime-observe'}[kind]
        result=dict(schemaVersion=1,commandId=packet['requestId' if kind=='subject' else 'commandId'],action=action,runId=self.run)
        if kind=='web':result['fixtureUrl']=self.fixture_url
        return result

    def validate_packet(self,kind,packet,epoch):
        need(type(packet) is dict)
        if kind=='provider':
            validate_status(packet,instance=self.source.instance,run=self.run,url=self.source.client.url,request=packet['requestId'])
            fresh(packet['capturedEpochMs'],epoch)
        elif kind=='subject':subject_packet(packet,self.request(packet,kind),self.pid,epoch,require_avatar=True)
        elif kind=='loads':loads_packet(packet,self.request(packet,kind),self.pid,epoch);need(packet['complete'] is True)
        else:web_packet(packet,self.request(packet,kind),self.pid,epoch);need(packet['status']=='ready')
        return packet

    def follows(self,kind,old,new):
        if old is None:return
        if kind=='provider':validate_status(new,instance=self.source.instance,run=self.run,url=self.source.client.url,request=new['requestId'],previous=old)
        elif kind=='loads':load_continuity(old,new,self.pid)
        elif kind=='web':web_continuity(old,new,self.pid,self.fixture_url)
        else:need(new['instance']==old['instance'] and new['sequence']>old['sequence']
            and new['requestedEpochMs']>=old['capturedEpochMs'] and new['capturedEpochMs']>=old['capturedEpochMs'])

    def group(self,row,mode,original=None):
        exact(row,{'sequence','providerBefore','subject','loads','web','providerAfter'})
        need(integer(row['sequence'],1,256))
        epoch=row['providerAfter']['capturedEpochMs']
        for kind,key in (('provider','providerBefore'),('subject','subject'),('loads','loads'),('web','web'),('provider','providerAfter')):
            self.validate_packet(kind,row[key],epoch)
        self.follows('provider',row['providerBefore'],row['providerAfter'])
        clocks=[row['providerBefore']['capturedEpochMs'],row['subject']['requestedEpochMs'],row['subject']['capturedEpochMs'],
            row['loads']['capturedEpochMs'],row['web']['source']['nativeBefore']['capturedEpochMs'],
            row['web']['capturedEpochMs'],epoch]
        need(clocks==sorted(clocks) and clocks[-1]-clocks[0]<=1500)
        subject=row['subject'];provider=row['providerAfter'];committed(row['loads'],subject['source']['sceneUrl'])
        if mode=='active':
            need(row['providerBefore']['active'] and provider['active']
                and row['providerBefore']['ticket']==provider['ticket'] and provider['sceneTicket'] is not None)
            aligned_entities(subject,self.run,provider['sceneTicket'],self.fixture_url)
            need(any(r['status']==200 and r['completedEpochMs']<=subject['requestedEpochMs'] for r in provider['responses']))
            marker=[r for r in subject['source']['entities'] if r['id']==subject_ids(self.run)['marker']]
            need(len(marker)==1);active_marker(row['web'],marker[0]['sourceUrl'])
        else:
            need(mode=='released' and not row['providerBefore']['active'] and not provider['active'] and original is not None)
            restored(original,subject);released(row['web'])
        return row

    def decode(self,value):
        exact(value,{'graphicsLifetimeVersion','runId','fixtureUrl','providerInstance','role','stage','payload'})
        need(type(value['graphicsLifetimeVersion']) is int and value['graphicsLifetimeVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance
            and value['role']==self.role and type(value['stage']) is int and value['stage']==self.stage)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','phase','sequence','provider','subject','loads','web','activeProofs','original','windows'})
        context(state['binding']);need(same(state['binding'],self.binding) and state['phase'] in ('ready','releasing','released')
            and integer(state['sequence'],0,256) and type(state['activeProofs']) is list and len(state['activeProofs'])<=8
            and type(state['windows']) is list and len(state['windows'])<=8)
        for kind in CURSORS:
            packet=state[kind]
            if packet is not None:self.validate_packet(kind,packet,packet['capturedEpochMs'])
        need(state['provider'] is not None)
        original=state['original']
        if original is not None:
            # This retains the actual old-process original; no PID relabelling.
            subject_packet(original,self.request(original,'subject'),original['processId'],original['capturedEpochMs'],require_avatar=True)
            eligible(original)
        last=None
        for row in state['activeProofs']:
            self.group(row,'active');last=self.ordered(last,row)
        for window in state['windows']:
            exact(window,{'samples','elapsedMs','complete'})
            need(type(window['samples']) is list and len(window['samples'])<=64 and type(window['complete']) is bool
                and integer(window['elapsedMs'],0,20000) and original is not None and state['activeProofs'])
            for row in window['samples']:
                self.group(row,'released',original);last=self.ordered(last,row)
            if window['complete']:
                need(len(window['samples'])>=3 and window['elapsedMs']>=3000
                    and self.epoch(window['samples'][-1])-self.epoch(window['samples'][0])>=3000)
        if last is not None:
            need(last['sequence']==state['sequence'])
            for kind,key in (('provider','providerAfter'),('subject','subject'),('loads','loads'),('web','web')):
                old,new=last[key],state[kind];need(new is not None)
                if not same(old,new):self.follows(kind,old,new)
        else:need(state['sequence']==0)
        if state['phase']=='ready':need(original is None and not state['windows'])
        else:need(original is not None and state['activeProofs'] and state['windows'])
        if state['phase']=='released':need(state['windows'][-1]['complete'])
        return state

    def ordered(self,old,new):
        if old is not None:
            need(new['sequence']==old['sequence']+1)
            for kind,key in (('provider','providerAfter'),('subject','subject'),('loads','loads'),('web','web')):
                self.follows(kind,old[key],new['providerBefore'] if kind=='provider' else new[key])
        else:need(new['sequence']==1)
        return new

    @staticmethod
    def epoch(row):return row['providerBefore']['capturedEpochMs']

    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=dict(graphicsLifetimeVersion=VERSION,runId=self.run,fixtureUrl=self.source.client.url,providerInstance=self.source.instance,
            role=self.role,stage=self.stage,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False)
        now=self.monotonic();need(number(now,0,1e15) and (self.local_clock is None or now>=self.local_clock)
            and (self.deadline is None or now<self.deadline));self.local_clock=now;return now

    def accept(self,kind,value):
        self.bound();self.validate_packet(kind,value,value['capturedEpochMs']);self.follows(kind,self.state[kind],value)
        self.state[kind]=deepcopy(value);self.save();self.bound();return value

    def provider(self):return self.accept('provider',self.source.status(self.state['provider']))

    def read_group(self,mode):
        started=self.bound();initial_epoch=self.source.clock();first=self.provider()
        self.subject.last=deepcopy(self.state['subject'])
        subject=self.accept('subject',self.subject.read(self.run,require_avatar=True))
        self.loads.last=deepcopy(self.state['loads']);loads=self.accept('loads',self.loads.read(self.run))
        self.web.last=deepcopy(self.state['web']);web=self.accept('web',self.web.read(self.run,self.fixture_url))
        last=self.provider();row=dict(sequence=self.state['sequence']+1,providerBefore=first,subject=subject,loads=loads,web=web,providerAfter=last)
        self.group(row,mode,self.state['original']);fresh(self.epoch(row),self.source.clock())
        # A frozen native/host clock cannot turn a slow source group fresh.
        need(max(self.source.clock()-self.epoch(row),
            initial_epoch-self.epoch(row)+math.ceil((self.bound()-started)*1000))<=1500)
        return deepcopy(row)

    def observe_active(self):
        need(self.state['phase']=='ready' and len(self.state['activeProofs'])<8)
        started=self.bound();self.deadline=started+15
        try:
            row=self.read_group('active');self.state['activeProofs'].append(deepcopy(row))
            self.state['sequence']=row['sequence'];self.save();self.bound();return row
        finally:self.deadline=None

    def wait_released(self,original):
        need(self.state['activeProofs'] and len(self.state['windows'])<8)
        subject_packet(original,self.request(original,'subject'),original['processId'],original['capturedEpochMs'],require_avatar=True)
        eligible(original)
        if self.state['original'] is not None:need(same(original,self.state['original']))
        started=self.bound();self.deadline=started+20
        try:
            # Every invocation starts a new local quiet window. Incomplete old
            # windows/cursors remain original history, never accumulated green.
            self.state.update(phase='releasing',original=deepcopy(original))
            self.state['windows'].append(dict(samples=[],elapsedMs=0,complete=False));self.save()
            first_local=None
            for attempt in range(64):
                row=self.read_group('released');now=self.bound()
                if first_local is None:first_local=now
                window=self.state['windows'][-1];window['samples'].append(deepcopy(row))
                window['elapsedMs']=math.floor((now-first_local)*1000)
                self.state['sequence']=row['sequence'];self.save()
                if len(window['samples'])>=3 and now-first_local>=3 and self.epoch(row)-self.epoch(window['samples'][0])>=3000:
                    window['complete']=True;self.state['phase']='released';self.save();self.decode(self.previous);self.bound()
                    return deepcopy(self.previous)
                need(attempt<63);self.sleep(.25);self.bound()
        finally:self.deadline=None

    @classmethod
    def archive(cls,value,*,run,fixture_url,provider_instance,role,stage,binding):
        """Validate originals only. No SDK, clock reads, retirement or new facts."""
        from types import SimpleNamespace
        from feature_journeys.graphics_resources import fixture_url as validate_url
        from feature_journeys.contract import identifier
        identifier(run);identifier(provider_instance);validate_url(fixture_url);context(binding)
        need(role in ('primary','actor') and integer(stage,0,1))
        owner=object.__new__(cls);owner.run=run;owner.fixture_url=fixture_url+'/runs/'+run+'/'
        owner.role,owner.stage,owner.binding=role,stage,deepcopy(binding)
        owner.pid=int(binding['processIdentity'].split(':')[0])
        owner.source=SimpleNamespace(instance=provider_instance,client=SimpleNamespace(url=fixture_url))
        return deepcopy(owner.decode(value))
