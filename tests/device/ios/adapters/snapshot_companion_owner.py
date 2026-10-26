"""Durable original Photos companion code admission, without Photos effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,NativeUIError,Locator
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_companion_artifact import artifact
from ios.adapters import snapshot_companion_source as source

NAMESPACE='ios-snapshot-companion'


class CompanionInspectionPending(NativeUIError):pass


class IOSSnapshotCompanionOwner:
    _namespace=NAMESPACE
    _schema='iosSnapshotCompanion'
    _owner_key='iosSnapshotCompanionOwnerVersion'
    _frame_key='snapshotCompanionFrameVersion'
    _control_prefix='snapshot.companion'
    _source=source
    _artifact_reader=staticmethod(artifact)
    _artifact_role='photos'
    def __init__(self,runtime,lock,run,phase):
        from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
        need(isinstance(runtime,IOSSnapshotCompanionRuntime) and runtime.artifact['role']==self._artifact_role);self.runtime,self.lock,self.run,self.phase=runtime,lock,identifier(run),phase
        self.binding=deepcopy(context(runtime.binding));self.artifact=deepcopy(runtime.artifact);self.os_scope=deepcopy(runtime.initial);self.fixture_url=phase.fixture_url
        self.monotonic,self.epoch_ms,self.sleep=runtime.monotonic,runtime.epoch_ms,runtime.sleep
        self.store=PrivateFeatureState(runtime.session_state.path.with_name(self._namespace+'-owner.json'));self.historical=False
        self.previous=self.store.read();self.state=dict(ticket=None,phaseOriginal=None,queries=[],result=None)
        self.frames=self.frame_store();lock.assert_held()
        self.ui=NativeUI(runtime.client,runtime.session,self.bound,monotonic=self.monotonic,sleep=self.sleep,timeout=1)
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(self.state)

    @classmethod
    def archive(cls,store,lock,binding,run,fixture_url,artifact_path):
        """Actual archive/original-file reads only; no SDK or native factory."""
        import time
        owner=object.__new__(cls);owner.store,owner.lock,owner.binding,owner.run=store,lock,deepcopy(context(binding)),identifier(run)
        owner.artifact=cls._artifact_reader(artifact_path,binding['artifactSha256']);owner.fixture_url=fixture_url;owner.historical=True
        owner.monotonic=time.monotonic;lock.assert_held();owner.previous=store.read();need(owner.previous is not None)
        owner.os_scope=deepcopy(owner.previous['osScope'])
        owner.frames=owner.frame_store();owner.state=unpack(owner.previous['payload'])[0];owner.state=owner.decode(owner.previous);return owner

    def frame_store(self):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,'primary',self.bound,self.storage,
            namespace=self._namespace,schema_prefix=self._schema,monotonic=self.monotonic)

    def envelope(self,state):
        return {self._owner_key:1,'binding':self.binding,'runId':self.run,'fixtureUrl':self.fixture_url,'artifact':self.artifact,'osScope':self.os_scope,'payload':pack([state])}

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        if not self.historical:self.runtime.check()
        return True

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def phase_original(self,value,ticket):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']==dict(verb='capture',inputs=dict(mode='still',format='png')))

    def active(self):
        value=self.phase.read(self.state['phaseOriginal']);self.phase_original(value['status'],self.state['ticket']);return value['status']

    def storage(self,event,wire):
        self.bound();need(event=='original');query=self.state['queries'][-1]
        need(query['clicked'] and query['frame'] is None);query['wire']=deepcopy(wire);self.save();return True

    def frame(self,value,query,previous=None):
        exact(value,{self._frame_key,'raw','osBefore','osAfter','phaseBefore','phaseAfter','hostBefore','hostAfter'})
        need(type(value[self._frame_key]) is int and value[self._frame_key]==1
            and type(value['raw']) is str and len(value['raw'])<=349528)
        raw=base64.b64decode(value['raw'],validate=True);need(1<=len(raw)<=262144);packet=decode(raw.decode('utf-8'),limit=262144)
        self._source.original(packet,action=query['action'],nonce=query['nonce'],pid=int(self.binding['processIdentity']),bundle=self.artifact['bundle']['bundleId'],previous=previous)
        if packet['action']=='identity' and packet['status']=='ready':
            from ios.adapters.bundle_identity import compare
            compare(packet['bundle'],self.artifact['bundle'])
        need(same(value['osBefore'],value['osAfter']) and same(value['osAfter'],self.os_scope))
        from ios.adapters.installed_code import source as process_source
        for field in ('osBefore','osAfter'):
            original=value[field];exact(original,{'process','source'});process_source(original['source']);process=original['process'];exact(process,{'bundleId','pid','foreground'})
            need(process==dict(bundleId=packet['bundleId'],pid=packet['processId'],foreground=True))
        self.phase_original(value['phaseBefore'],self.state['ticket']);self.phase_original(value['phaseAfter'],self.state['ticket'])
        phase_packet(value['phaseAfter'],run=self.run,area='snapshots',request=value['phaseAfter']['requestId'],epoch=value['phaseAfter']['capturedEpochMs'],previous=value['phaseBefore'])
        need(same(value['phaseBefore']['activations'],value['phaseAfter']['activations']))
        for clock in (value['hostBefore'],value['hostAfter']):
            exact(clock,{'epochMs','monotonicMs'});need(type(clock['epochMs']) in (int,float) and type(clock['monotonicMs']) in (int,float))
        from adapters.native_feature_observation import number
        a,b=value['hostBefore'],value['hostAfter'];need(number(a['epochMs'],1,1e15) and number(b['epochMs'],a['epochMs'],a['epochMs']+1500)
            and number(a['monotonicMs'],0,1e15) and number(b['monotonicMs'],a['monotonicMs'],a['monotonicMs']+1500)
            and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
        return packet

    def original(self,query,previous=None):
        wire=query['wire'] if query['frame'] is None else self.frames.expand(query['frame'])
        need(wire is not None and wire['phase'] in ('opened','saved'));return self.frame(self.frames.read(wire),query,previous)

    def inventory(self,state):
        paths={self.store.path}
        for query in state['queries']:
            if query['wire'] is not None:paths.add(self.frames.path(query['wire']))
            if query['frame'] is not None:paths.add(self.frames.path(self.frames.expand(query['frame'])))
        for index,path in enumerate(self.store.path.parent.iterdir()):
            need(index<8192)
            if path.name.startswith(self._namespace+'-'):need(path in paths)

    def decode(self,value):
        exact(value,{self._owner_key,'binding','runId','fixtureUrl','artifact','osScope','payload'});rows=unpack(value['payload'])
        need(type(value[self._owner_key]) is int and value[self._owner_key]==1 and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'ticket','phaseOriginal','queries','result'});need(type(state['queries']) is list and len(state['queries'])<=96)
        exact(self.os_scope,{'process','source'})
        from ios.adapters.installed_code import source as process_source
        process_source(self.os_scope['source']);need(self.os_scope['process']==dict(bundleId=self.artifact['bundle']['bundleId'],pid=int(self.binding['processIdentity']),foreground=True))
        prior=self.state;self.state=state
        try:
            if state['ticket'] is not None:self.phase_original(state['phaseOriginal'],state['ticket'])
            seen=set();previous=None;source_id=None;identity=None
            for index,query in enumerate(state['queries'],1):
                exact(query,{'index','action','nonce','field','button','cleared','written','clicked','wire','frame'})
                need(query['index']==index and query['action'] in ('identity','clock') and type(query['nonce']) is str and re.fullmatch('ios-[0-9a-f]{32}',query['nonce']) and query['nonce'] not in seen);seen.add(query['nonce'])
                for key in ('cleared','written','clicked'):need(type(query[key]) is bool)
                need(not query['written'] or query['cleared']);need(not query['clicked'] or query['written'])
                for key in ('field','button'):need(query[key] is None or type(query[key]) is str and re.fullmatch('/element/[A-Za-z0-9_.:%-]{1,480}',query[key]))
                if query['wire'] is not None:self.frames.original(query['wire']);need(query['clicked'])
                if query['frame'] is not None:
                    need(query['frame']['index']==index);packet=self.original(query,previous);previous=packet
                    if packet['action']=='identity' and packet['status']=='ready':
                        if identity is None:identity=packet
                        else:need(same(packet['preparedClock'],identity['preparedClock']) and same(packet['bundle'],identity['bundle']))
                    os_source=self.frames.read(self.frames.expand(query['frame']))['osAfter']['source']
                    if source_id is None:source_id=os_source
                    else:need(same(source_id,os_source))
                elif query['wire'] is not None and query['wire']['phase']!='planned':self.original(query,previous)
                else:need(index==len(state['queries']))
            if state['result'] is not None:need(same(state['result'],self.result()))
            self.inventory(state)
        finally:self.state=prior
        return deepcopy(state)

    def query(self,action):
        need(not self.historical and action in ('identity','clock') and len(self.state['queries'])<96)
        rows=self.state['queries']
        if rows and rows[-1]['frame'] is None:
            query=rows[-1];need(query['action']==action)
        else:
            query=dict(index=len(rows)+1,action=action,nonce='ios-'+uuid.uuid4().hex,field=None,button=None,cleared=False,written=False,clicked=False,wire=None,frame=None)
            rows.append(query);self.save()
        if query['wire'] is None:
            if query['field'] is None:query['field']=self.ui._resolve(Locator('accessibility id',self._control_prefix+'.nonce'));self.save()
            if not query['cleared']:
                query['cleared']=True;self.save();self.ui._request('POST',query['field']+'/clear',{})
            if not query['written']:
                need(self.ui._request('GET',query['field']+'/text')=='');query['written']=True;self.save()
                self.ui._request('POST',query['field']+'/value',dict(text=query['nonce'],value=list(query['nonce'])))
            need(self.ui._request('GET',query['field']+'/text')==query['nonce'])
            if query['button'] is None:query['button']=self.ui._resolve(Locator('accessibility id',self._control_prefix+'.'+action));self.save()
            if not query['clicked']:
                self.active();self.ui._check();query['clicked']=True;self.save();self.ui._request('POST',query['button']+'/click',{})
            before=self.runtime.probe();phase_before=self.active();start=dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000)
            raw=self.runtime.original(action);packet=decode(raw.decode('utf-8'),limit=262144);need(packet.get('nonce')==query['nonce'])
            end=dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000);after=self.runtime.probe();phase_after=self.active()
            frame=dict({self._frame_key:1},raw=base64.b64encode(raw).decode(),osBefore=before,osAfter=after,
                phaseBefore=phase_before,phaseAfter=phase_after,hostBefore=start,hostAfter=end)
            previous=None if len(rows)==1 else self.original(rows[-2]);self.frame(frame,query,previous)
            if packet['action']=='identity' and packet['status']=='ready':
                identities=[self.original(row) for row in rows[:-1] if row['action']=='identity' and row['frame'] is not None]
                for prior in identities:
                    if prior['status']=='ready':need(same(prior['preparedClock'],packet['preparedClock']) and same(prior['bundle'],packet['bundle']))
            query['frame']=self.frames.write(query['index'],frame);query['wire']=None;self.save()
        elif query['frame'] is None:
            self.original(query,None if len(rows)==1 else self.original(rows[-2]));query['frame']=self.frames.compact(dict(query['wire'],phase='saved'));query['wire']=None;self.save()
        return self.original(query,None if len(rows)==1 else self.original(rows[-2]))

    def result(self):
        rows=self.state['queries'];need(len(rows)>=3 and all(row['frame'] is not None for row in rows[-3:]))
        before,identity,after=(self.original(row) for row in rows[-3:])
        if any(packet['status']!='ready' for packet in (before,identity,after)):
            # Retain this exact unqualified group. A later admit starts a new
            # group with new nonces; this historical reply never becomes ready.
            raise CompanionInspectionPending('Retained companion inspection group remains unqualified')
        return self._source.admission(identity,before,after,self.artifact['bundle'])

    @operation
    def admit(self,ticket):
        self.bound();need(not self.historical);identifier(ticket)
        if self.state['ticket'] is None:
            status=self.phase.read();self.phase_original(status['status'],ticket);self.state.update(ticket=ticket,phaseOriginal=status['status']);self.save()
        else:need(self.state['ticket']==ticket)
        if self.state['result'] is not None:
            # Re-admission is a fresh independently queried group; the old
            # admission remains in immutable original files.
            self.state['result']=None;self.save()
        actions=('clock','identity','clock');count=len(self.state['queries']);complete=count-(1 if count and self.state['queries'][-1]['frame'] is None else 0)
        offset=complete%3
        for action in actions[offset:]:
            packet=self.query(action)
            if packet['status']!='ready':raise CompanionInspectionPending('Actual companion identity is pending or unavailable')
        self.state['result']=self.result();self.save();return deepcopy(self.state['result'])
