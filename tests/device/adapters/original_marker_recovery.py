"""Retain incomplete passive marker reads and require their original prefixes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from adapters.original_file_reads import record as record_original_read
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.native_script_terminal import validate as terminal_packet,terminal
from adapters.native_script_work import validate as work_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters.web_closures import continuity as web_continuity
from ios.adapters.script_dialogs import validate as dialogs_packet,ACTION as DIALOG_ACTION

VERSION=1


class OriginalMarkerRecovery:
    @classmethod
    def archive(cls,value,scope,store):
        """Strict original recovery reader; all live mutation stays forbidden."""
        from adapters.original_marker_scope import OriginalMarkerScope
        need(isinstance(scope,OriginalMarkerScope) and isinstance(store,PrivateFeatureState))
        scope.lock.assert_held();result=object.__new__(cls)
        result.scope=scope;result.profile=scope.components.profile
        prefix='WorldWeb' if result.profile=='worldweb' else result.profile.title()
        result.key='ios'+prefix+'MarkerRecoveryVersion';result.record_key='ios'+prefix+'MarkerAbandonedReadVersion'
        result.store,result.previous,result.historical=store,value,True
        result.state=result.decode(value);return result

    def __init__(self,scope):
        from adapters.original_marker_scope import OriginalMarkerScope
        need(isinstance(scope,OriginalMarkerScope));self.scope=scope
        self.profile=scope.components.profile
        prefix='WorldWeb' if self.profile=='worldweb' else self.profile.title()
        self.key='ios'+prefix+'MarkerRecoveryVersion'
        self.record_key='ios'+prefix+'MarkerAbandonedReadVersion'
        self.store=PrivateFeatureState(scope.store.path.with_name('ios-'+self.profile+'-'+scope.role+'-marker-recovery.json'))
        self.previous=self.store.read();self.state=dict(records=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        s=self.scope
        return dict(**{self.key:VERSION},runId=s.run,role=s.role,binding=s.binding,artifactRoot=str(s.root),payload=pack([state]))

    def bound(self):need(not getattr(self,'historical',False));self.scope.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def record_store(self,index):
        need(integer(index,1,128));s=self.scope
        return PrivateFeatureState(s.root/(self.profile+'-marker-read-abandoned-'+s.run+'-'+s.role+'-'+str(index)+'.json'))

    def prior(self,value):
        s=self.scope;frames=s.frames
        try:return s.decode(value)
        finally:s.frames=frames

    def partial_file(self,original):
        if original is None:return None
        s=self.scope;s.originals.original(original);path=s.originals.path(original)
        if original['phase']=='planned':need(not path.exists());return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            s.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);s.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes'])
        if original['phase']=='saved':need(len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256']);s.originals.read(original)
        record_original_read(path)
        return dict(identity=original['file'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def record(self,reference):
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read()
        need(value is not None and digest(value)==reference['sha256'])
        exact(value,{self.record_key,'index','priorOwner','partialFile'})
        need(type(value[self.record_key]) is int and value[self.record_key]==VERSION
            and value['index']==reference['index'])
        state=self.prior(value['priorOwner']);need(state['pending'] is not None
            and same(value['partialFile'],self.partial_file(state['pending']['original'])))
        return value

    def decode(self,value):
        exact(value,{self.key,'runId','role','binding','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'records','pending'});need(type(state['records']) is list and len(state['records'])<=128)
        for index,reference in enumerate(state['records'],1):need(reference['index']==index);self.record(reference)
        pending=state['pending']
        if pending is not None:
            exact(pending,{'record','targetOwner','reference'});prior=self.prior(pending['record']['priorOwner'])
            target=deepcopy(prior);target['pending']=None
            need(same(pending['targetOwner'],self.scope.envelope(target)) and pending['record']['index']==len(state['records'])+1)
            if pending['reference'] is not None:need(same(self.record(pending['reference']),pending['record']))
        else:need(len(state['records'])==128 or self.record_store(len(state['records'])+1).read() is None)
        return deepcopy(state)

    def recover(self):
        self.bound();s=self.scope;pending=self.state['pending']
        if pending is None:
            if s.state['pending'] is None:return True
            need(len(self.state['records'])<128)
            record=dict(**{self.record_key:VERSION},index=len(self.state['records'])+1,
                priorOwner=deepcopy(s.previous),partialFile=self.partial_file(s.state['pending']['original']))
            target=deepcopy(s.state);target['pending']=None
            pending=dict(record=record,targetOwner=s.envelope(target),reference=None);self.state['pending']=pending;self.save()
        need(same(s.previous,pending['record']['priorOwner']) or same(s.previous,pending['targetOwner']))
        index=pending['record']['index'];store=self.record_store(index);previous=store.read()
        if previous is None:store.write(pending['record'],None)
        else:need(same(previous,pending['record']))
        reference=dict(index=index,sha256=digest(pending['record']));self.record(reference)
        pending['reference']=reference;self.save()
        if same(s.previous,pending['record']['priorOwner']):s.state=unpack(pending['targetOwner']['payload'])[0];s.save()
        self.state['records'].append(reference);self.state['pending']=None;self.save();return True

    def follow(self,frame,*,historical=False):
        if historical:
            self.scope.lock.assert_held();need(getattr(self,'historical',False) and any(same(frame,row) for row in self.scope.frames))
        else:self.bound()
        s=self.scope;need(self.state['pending'] is None)
        for reference in self.state['records']:
            record=self.record(reference);prior=self.prior(record['priorOwner']);partial=prior['pending']['partial']
            native=frame['clockJoin']['nativeBefore'];epoch=frame['clockJoin']['nativeAfter']['capturedEpochMs']
            if 'nativeStart' in partial:native_prefix(partial['nativeStart']['nativeBefore'],native)
            if 'clockJoin' in partial:native_prefix(partial['clockJoin']['nativeAfter'],native)
            if 'world' in partial:
                p=frame['world'];s.components.world_packet(p,dict(schemaVersion=1,commandId=p['requestId'],action=s.components.WORLD_ACTION,runId=s.run),s.pid,epoch,partial['world'])
            if 'terminal' in partial:
                p=frame['terminal'];terminal_packet(p,dict(schemaVersion=1,commandId=p['commandId'],action='feature-script-terminal-observe'),s.pid,epoch,previous=partial['terminal'])
            if 'dialogs' in partial:
                p=frame['dialogs'];dialogs_packet(p,dict(schemaVersion=1,commandId=p['requestId'],action=DIALOG_ACTION,runId=s.run),s.pid,epoch,partial['dialogs'])
            if 'web' in partial:web_continuity(partial['web'],frame['web'],s.pid)
            if 'widgets' in partial:
                a,b=partial['widgets'],frame['widgets'];need(a['instance']==b['instance'] and a[s.components.generation_key]==b[s.components.generation_key]
                    and b[s.components.source_sequence_key]>a[s.components.source_sequence_key] and b['lastSequence']>=a['lastSequence']
                    and b['sampleEpochMs']>=a['sampleEpochMs'] and b['elapsedMs']>=a['elapsedMs'])
            if partial.get('work') is not None:
                old=partial['work']
                if frame['work'] is not None and frame['work']['source']['manager']['instance']==old['source']['manager']['instance']:
                    p=frame['work'];work_packet(p,dict(schemaVersion=1,commandId=p['requestId'],action='feature-script-work-observe',
                        managerInstance=p['source']['manager']['instance']),s.pid,epoch,previous=old)
                else:
                    original=old['source'];terminal(frame['terminal'],original['manager'],original['code'],
                        after_sequence=partial['terminal']['source']['eventSequence'],after_epoch=old['source']['work']['capturedEpochMs'])
        return True
