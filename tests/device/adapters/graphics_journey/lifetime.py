"""Original per-role Graphics fixture/Web lifetime; measurement only, no input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import hashlib
from pathlib import Path
import re
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_scene_loads import validate as loads_packet,continuity as load_continuity,committed
from adapters.native_web_runtime import validate as web_packet,continuity as web_continuity,active_marker,released
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.graphics_fixture import PICO_PROFILE,PICO_RESOURCE
from feature_journeys.graphics_resources import validate_status,fixture_url as validate_url
from feature_journeys.contract import identifier
from adapters.graphics_journey.fixture import GraphicsFixtureReader
from adapters.graphics_journey.scene import GraphicsScene
from adapters.graphics_journey.samples import retirement
from adapters.graphics_journey.source_history import restore_ui
from adapters.pico4.graphics_source import validate as graphics_packet,resources as graphics_resources,PROFILES
from adapters.authentication_journey.login_source import accept_inventory
from adapters.script_journey.files import validate as tablet_packet
from adapters.native_tablet_http import validate as http_packet,continuity as http_continuity,released as http_released
from adapters.script_journey.history import pack,unpack,same,canonical
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
CURSORS=('provider','subject','loads','web','http','graphics','tablet')
ROW={'sequence','providerBefore','subject','loads','web','http','graphics','tablet','captures','providerAfter'}


class GraphicsLifetime:
    def __init__(self,adapter,selector,source,role,stage,lock,*,artifact_root,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,GraphicsFixtureReader) and role in ('primary','actor') and integer(stage,0,1)
            and isinstance(lock,ScriptSourceLock) and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role,self.stage,self.lock=adapter,selector,source,role,stage,lock
        need(adapter.graphics_scene_policy.fixture_profile==PICO_PROFILE)
        self.monotonic,self.sleep=monotonic,sleep
        self.artifact_root=Path(artifact_root)
        PrivateFeatureState(self.artifact_root/'graphics-lifetime-boundary.json')._parent()
        self.run,self.fixture_url=source.run,source.fixture_url
        lock.assert_held();path=adapter.state_path(selector)
        need(lock.path==path.with_name('script-sources.lock'))
        self.store=PrivateFeatureState(path.with_name('graphics-'+role+'-'+str(stage)+'-lifetime.json'))
        _ui,_observer,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0])
        self.previous=self.store.read()
        if self.previous is None:
            provider=source.status()
            self.state=dict(binding=self.binding,phase='ready',sequence=0,provider=provider,subject=None,loads=None,web=None,
                http=None,graphics=None,tablet=None,captureProofs=None,queries={key:[] for key in CURSORS},
                activeProofs=[],original=None,windows=[])
            self.save()
        else:
            if source.instance is None:source.status()
            self.state=self.decode(self.previous);need(same(self.binding,self.state['binding']))
        self.subject=adapter._graphics_subject_observer(selector,read_only=True)
        self.loads=adapter._scene_load_observer(selector,read_only=True)
        self.web=adapter._web_runtime_observer(selector,read_only=True)
        need(self.web.require_renderers is True)
        self.http=adapter._tablet_http_observer(selector,read_only=True)
        self.graphics=adapter._graphics_ui_observer(selector,read_only=True)
        self.tablet=adapter._script_file_io(selector,read_only=True)
        restore_ui(self.graphics,self.state['graphics'],graphics_packet)
        restore_ui(self.tablet,self.state['tablet'],tablet_packet)
        self.deadline=None;self.local_clock=None

    def reference(self,value,*,loading):
        if type(value) is dict:
            if 'graphicsLifetimeArchiveVersion' in value:
                need(loading);exact(value,{'graphicsLifetimeArchiveVersion','sha256','name'})
                need(type(value['graphicsLifetimeArchiveVersion']) is int and value['graphicsLifetimeArchiveVersion']==1
                    and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']))
                name='graphics-lifetime-'+value['sha256']+'.json';need(value['name']==name)
                record=PrivateFeatureState(self.artifact_root/name).read()
                need(type(record) is dict and record.get('runId')==self.run
                    and hashlib.sha256(canonical(record)).hexdigest()==value['sha256'])
                exact(record,{'graphicsLifetimeArchiveVersion','runId','payload'})
                need(type(record['graphicsLifetimeArchiveVersion']) is int and record['graphicsLifetimeArchiveVersion']==1)
                rows=unpack(record['payload']);need(len(rows)==1);return rows[0]
            if set(value)==ROW or 'graphicsSceneVersion' in value:
                need(not loading)
                record=dict(graphicsLifetimeArchiveVersion=1,runId=self.run,payload=pack([value]))
                digest=hashlib.sha256(canonical(record)).hexdigest();name='graphics-lifetime-'+digest+'.json'
                store=PrivateFeatureState(self.artifact_root/name);old=store.read()
                if old is None:store.write(record,None);old=store.read()
                need(same(old,record));return dict(graphicsLifetimeArchiveVersion=1,sha256=digest,name=name)
            return {key:self.reference(child,loading=loading) for key,child in value.items()}
        if type(value) is list:return [self.reference(child,loading=loading) for child in value]
        return value

    def request(self,packet,kind):
        action={'subject':'feature-graphics-subject-observe','loads':'feature-scene-load-observe','web':'feature-web-runtime-observe',
            'http':'feature-tablet-http-observe'}[kind]
        result=dict(schemaVersion=1,commandId=packet['requestId' if kind=='subject' else 'commandId'],action=action,runId=self.run)
        if kind=='web':result['fixtureUrl']=self.fixture_url
        return result

    def validate_packet(self,kind,packet,epoch):
        need(type(packet) is dict)
        if kind=='provider':
            validate_status(packet,instance=self.source.instance,run=self.run,url=self.source.client.url,request=packet['requestId'])
            need(packet['graphicsProviderVersion']==2 and packet['profile']==PICO_PROFILE)
            fresh(packet['capturedEpochMs'],epoch)
        elif kind=='subject':subject_packet(packet,self.request(packet,kind),self.pid,epoch,require_avatar=True,require_framework=True)
        elif kind=='loads':loads_packet(packet,self.request(packet,kind),self.pid,epoch);need(packet['complete'] is True)
        elif kind=='web':web_packet(packet,self.request(packet,kind),self.pid,epoch,require_renderers=True);need(packet['status']=='ready')
        elif kind=='http':http_packet(packet,self.request(packet,kind),self.pid,epoch);need(packet['complete'] is True)
        elif kind=='graphics':
            graphics_packet(packet,packet['commandId'],self.pid,epoch);need(packet['graphicsObservationVersion']==2)
        else:
            need(kind=='tablet');tablet_packet(packet,packet['commandId'],self.pid,epoch)
            need('scriptInventory' in packet and packet['scriptInventory']['complete'])
        return packet

    def follows(self,kind,old,new):
        if old is None:return
        if kind=='provider':validate_status(new,instance=self.source.instance,run=self.run,url=self.source.client.url,request=new['requestId'],previous=old)
        elif kind=='loads':load_continuity(old,new,self.pid)
        elif kind=='web':web_continuity(old,new,self.pid,self.fixture_url)
        elif kind=='http':http_continuity(old,new,self.pid)
        elif kind in ('graphics','tablet'):
            need(new['instance']==old['instance'] and new['generation']==old['generation']
                and new['sourceSequence']>old['sourceSequence'] and new['elapsedMs']>=old['elapsedMs']
                and new['lastCommandSequence']>=old['lastCommandSequence'] and new['capturedEpochMs']>=old['capturedEpochMs'])
            if kind=='graphics':accept_inventory(old['graphicsInventory'],new['graphicsInventory'],profiles=PROFILES)
        else:need(new['instance']==old['instance'] and new['sequence']>old['sequence']
            and new['requestedEpochMs']>=old['capturedEpochMs'] and new['capturedEpochMs']>=old['capturedEpochMs'])

    def group(self,row,mode,original=None):
        exact(row,ROW)
        need(integer(row['sequence'],1,256))
        epoch=row['providerAfter']['capturedEpochMs']
        for kind,key in (('provider','providerBefore'),*((kind,kind) for kind in CURSORS[1:]),('provider','providerAfter')):
            self.validate_packet(kind,row[key],epoch)
        self.follows('provider',row['providerBefore'],row['providerAfter'])
        clocks=[row['providerBefore']['capturedEpochMs'],row['subject']['requestedEpochMs'],row['subject']['capturedEpochMs'],
            row['loads']['capturedEpochMs'],row['web']['source']['nativeBefore']['capturedEpochMs'],
            row['web']['capturedEpochMs'],row['http']['capturedEpochMs'],row['graphics']['capturedEpochMs'],
            row['tablet']['capturedEpochMs'],*([row['captures'][role]['inspection']['capturedEpochMs'] for role in ('primary','actor')]
                if row['captures'] is not None else []),epoch]
        need(clocks==sorted(clocks) and clocks[-1]-clocks[0]<=1500)
        subject=row['subject'];provider=row['providerAfter'];committed(row['loads'],subject['source']['sceneUrl'])
        if mode=='active':
            need(row['providerBefore']['active'] and provider['active']
                and row['providerBefore']['ticket']==provider['ticket'] and provider['sceneTicket'] is not None)
            need(row['captures'] is None)
            self.adapter.graphics_scene_policy.aligned_entities(subject,self.run,provider['sceneTicket'],self.fixture_url)
            need(any(r['status']==200 and r['ticket']==provider['sceneTicket'] and r['resource']==PICO_RESOURCE
                and r['completedEpochMs']<=subject['requestedEpochMs'] for r in provider['responses']))
            markers=[r for r in subject['source']['entities'] if r['type']=='Web']
            need(len(markers)==3)
            for marker in markers:active_marker(row['web'],marker['sourceUrl'])
        else:
            need(mode=='released' and not row['providerBefore']['active'] and not provider['active'] and original is not None)
            scene=self.restoration(original)
            scene.restored(scene.state['original']['subject'],subject,scene.state['handoff'])
            released(row['web'],require_renderers=True);http_released(row['http'])
            need(graphics_resources(row['graphics'])==[])
            tablet=row['tablet'];inventory=tablet['scriptInventory']
            need(not inventory['tabletShown'] and not inventory['managers'] and not inventory['pickers']
                and not tablet['controls'] and row['captures'] is not None)
            self.validate_captures(row['captures'])
        return row

    def restoration(self,value):
        scene=GraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.source.client,run=self.run)
        scene.state=scene.decode(value);scene.binding=scene.state['binding']
        need(same(scene.binding,self.binding) and scene.state['phase']=='restored' and not any(scene.state['leases'].values()))
        return scene

    def validate_captures(self,values):
        exact(values,{'primary','actor'})
        for role,item in values.items():
            exact(item,{'proof','inspection'});proof=item['proof'];packet=item['inspection']
            retirement(proof,proof['owner'],self.pid,self.binding,role)
            original=proof['files']['absent'];updated=deepcopy(proof);updated['files']['absent']=deepcopy(packet)
            retirement(updated,proof['owner'],self.pid,self.binding,role)
            need(packet['sequence']>original['sequence'] and packet['commandId']!=original['commandId']
                and packet['capturedEpochMs']>=original['capturedEpochMs'])

    def captures_follow(self,old,new):
        if old is None:return
        for role in ('primary','actor'):
            a,b=old[role],new[role];need(same(a['proof'],b['proof'])
                and b['inspection']['sequence']>a['inspection']['sequence']
                and b['inspection']['commandId']!=a['inspection']['commandId']
                and b['inspection']['capturedEpochMs']>=a['inspection']['capturedEpochMs'])

    def decode(self,value):
        exact(value,{'graphicsLifetimeVersion','runId','fixtureUrl','providerInstance','role','stage','artifactRoot','payload'})
        need(type(value['graphicsLifetimeVersion']) is int and value['graphicsLifetimeVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance
            and value['role']==self.role and type(value['stage']) is int and value['stage']==self.stage and value['artifactRoot']==str(self.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);state=self.reference(rows[0],loading=True)
        exact(state,{'binding','phase','sequence',*CURSORS,'activeProofs','original','windows','queries','captureProofs'})
        context(state['binding']);need(same(state['binding'],self.binding) and state['phase'] in ('ready','releasing','released')
            and integer(state['sequence'],0,256) and type(state['activeProofs']) is list and len(state['activeProofs'])<=8
            and type(state['windows']) is list and len(state['windows'])<=8)
        for kind in CURSORS:
            packet=state[kind]
            if packet is not None:self.validate_packet(kind,packet,packet['capturedEpochMs'])
        need(state['provider'] is not None)
        exact(state['queries'],set(CURSORS))
        for queries in state['queries'].values():
            need(type(queries) is list and len(queries)<=4096 and len(set(queries))==len(queries))
            for query in queries:identifier(query)
        original=state['original']
        if original is not None:
            self.restoration(original);need(state['captureProofs'] is not None)
            exact(state['captureProofs'],{'primary','actor'})
            for role,proof in state['captureProofs'].items():retirement(proof,proof['owner'],self.pid,self.binding,role)
        last=None
        for row in state['activeProofs']:
            self.group(row,'active');last=self.ordered(last,row)
        for window in state['windows']:
            exact(window,{'samples','elapsedMs','complete'})
            need(type(window['samples']) is list and len(window['samples'])<=64 and type(window['complete']) is bool
                and integer(window['elapsedMs'],0,20000) and original is not None and state['activeProofs'])
            for row in window['samples']:
                self.group(row,'released',original);last=self.ordered(last,row)
                need(all(same(row['captures'][role]['proof'],state['captureProofs'][role]) for role in ('primary','actor')))
            for before,after in zip(window['samples'],window['samples'][1:]):
                need(0<=self.epoch(after)-before['providerAfter']['capturedEpochMs']<=1500)
            if window['complete']:
                need(len(window['samples'])>=3 and window['elapsedMs']>=3000
                    and self.epoch(window['samples'][-1])-self.epoch(window['samples'][0])>=3000)
        if last is not None:
            need(last['sequence']==state['sequence'])
            for kind,key in (('provider','providerAfter'),*((kind,kind) for kind in CURSORS[1:])):
                old,new=last[key],state[kind];need(new is not None)
                if not same(old,new):self.follows(kind,old,new)
        else:need(state['sequence']==0)
        if state['phase']=='ready':need(original is None and not state['windows'] and state['captureProofs'] is None)
        else:need(original is not None and state['activeProofs'] and state['windows'])
        if state['phase']=='released':need(state['windows'][-1]['complete'])
        seen={key:set() for key in (*CURSORS,'primary','actor')}
        rows=state['activeProofs']+[row for window in state['windows'] for row in window['samples']]
        for row in rows:
            for kind,packet in [('provider',row['providerBefore']),*((kind,row[kind]) for kind in CURSORS[1:]),('provider',row['providerAfter'])]:
                query=packet['requestId' if kind in ('provider','subject') else 'commandId']
                need(query not in seen[kind] and query in state['queries'][kind]);seen[kind].add(query)
            if row['captures'] is not None:
                for role,item in row['captures'].items():
                    query=item['inspection']['commandId'];need(query not in seen[role]);seen[role].add(query)
        return state

    def ordered(self,old,new):
        if old is not None:
            need(new['sequence']==old['sequence']+1)
            for kind,key in (('provider','providerAfter'),*((kind,kind) for kind in CURSORS[1:])):
                self.follows(kind,old[key],new['providerBefore'] if kind=='provider' else new[key])
            if old['captures'] is not None and new['captures'] is not None:self.captures_follow(old['captures'],new['captures'])
        else:need(new['sequence']==1)
        return new

    @staticmethod
    def epoch(row):return row['providerBefore']['capturedEpochMs']

    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=dict(graphicsLifetimeVersion=VERSION,runId=self.run,fixtureUrl=self.source.client.url,providerInstance=self.source.instance,
            role=self.role,stage=self.stage,artifactRoot=str(self.artifact_root),payload=pack([self.reference(self.state,loading=False)]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False)
        now=self.monotonic();need(number(now,0,1e15) and (self.local_clock is None or now>=self.local_clock)
            and (self.deadline is None or now<self.deadline));self.local_clock=now;return now

    def accept(self,kind,value):
        self.bound();self.validate_packet(kind,value,value['capturedEpochMs']);self.follows(kind,self.state[kind],value)
        query=value['requestId' if kind in ('provider','subject') else 'commandId'];queries=self.state['queries'][kind]
        need(query not in queries and len(queries)<4096);queries.append(query)
        self.state[kind]=deepcopy(value);self.save();self.bound();return value

    def provider(self):return self.accept('provider',self.source.status(self.state['provider']))

    def read_group(self,mode):
        started=self.bound();initial_epoch=self.source.clock();first=self.provider()
        self.subject.last=deepcopy(self.state['subject'])
        subject=self.accept('subject',self.subject.read(self.run,require_avatar=True,require_framework=True))
        self.loads.last=deepcopy(self.state['loads']);loads=self.accept('loads',self.loads.read(self.run))
        self.web.last=deepcopy(self.state['web']);web=self.accept('web',self.web.read(self.run,self.fixture_url))
        self.http.last=deepcopy(self.state['http']);http=self.accept('http',self.http.read(self.run))
        graphics=self.accept('graphics',self.graphics.capture());tablet=self.accept('tablet',self.tablet.capture())
        captures=None
        if mode=='released':
            captures={}
            for role,proof in self.state['captureProofs'].items():
                previous=next((window['samples'][-1]['captures'][role]['inspection'] for window in reversed(self.state['windows']) if window['samples']),None)
                reader=self.adapter._graphics_retired_capture_observer(self.selector,proof,self.lock,previous=previous)
                captures[role]=dict(proof=deepcopy(proof),inspection=reader.request('inspect'));self.bound()
            self.validate_captures(captures)
        last=self.provider();row=dict(sequence=self.state['sequence']+1,providerBefore=first,subject=subject,loads=loads,web=web,
            http=http,graphics=graphics,tablet=tablet,captures=captures,providerAfter=last)
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

    def wait_released(self,original,capture_proofs):
        need(self.state['activeProofs'] and len(self.state['windows'])<8)
        self.restoration(original);exact(capture_proofs,{'primary','actor'})
        for role,proof in capture_proofs.items():retirement(proof,proof['owner'],self.pid,self.binding,role)
        if self.state['original'] is not None:need(same(original,self.state['original']))
        if self.state['captureProofs'] is not None:need(same(capture_proofs,self.state['captureProofs']))
        started=self.bound();self.deadline=started+20
        try:
            # Every invocation starts a new local quiet window. Incomplete old
            # windows/cursors remain original history, never accumulated green.
            self.state.update(phase='releasing',original=deepcopy(original),captureProofs=deepcopy(capture_proofs))
            self.state['windows'].append(dict(samples=[],elapsedMs=0,complete=False));self.save()
            first_local=None
            for attempt in range(64):
                iteration_started=self.bound();initial_epoch=self.source.clock()
                row=self.read_group('released');now=self.bound()
                if first_local is None:first_local=now
                window=self.state['windows'][-1];window['samples'].append(deepcopy(row))
                if len(window['samples'])>1:
                    need(0<=self.epoch(row)-window['samples'][-2]['providerAfter']['capturedEpochMs']<=1500)
                window['elapsedMs']=math.floor((now-first_local)*1000)
                self.state['sequence']=row['sequence'];self.save()
                if len(window['samples'])>=3 and now-first_local>=3 and self.epoch(row)-self.epoch(window['samples'][0])>=3000:
                    window['complete']=True;self.state['phase']='released';self.save();self.decode(self.previous);self.bound()
                    epoch=self.source.clock();finished=self.bound()
                    need(max(epoch-self.epoch(row),initial_epoch-self.epoch(row)+math.ceil((finished-iteration_started)*1000))<=1500)
                    return deepcopy(self.previous)
                need(attempt<63);self.sleep(.25);self.bound()
        finally:self.deadline=None

    @classmethod
    def archive(cls,value,*,adapter,selector,client,run,provider_instance,role,stage,binding,artifact_root):
        """Validate originals only. No SDK, clock reads, retirement or new facts."""
        from types import SimpleNamespace
        identifier(run);identifier(provider_instance);validate_url(client.url);context(binding)
        need(role in ('primary','actor') and integer(stage,0,1))
        owner=object.__new__(cls);owner.run=run;owner.fixture_url=client.url+'/runs/'+run+'/'
        owner.adapter,owner.selector,owner.artifact_root=adapter,selector,Path(artifact_root)
        owner.role,owner.stage,owner.binding=role,stage,deepcopy(binding)
        owner.pid=int(binding['processIdentity'].split(':')[0])
        owner.source=SimpleNamespace(instance=provider_instance,client=client)
        return deepcopy(owner.decode(value))
