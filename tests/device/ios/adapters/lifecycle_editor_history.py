"""Durable original editor generations; no complete Lifecycle capability.

Aliases follow actual loader/context evidence. Archived replay is historical,
and never supplies a new current observation or repeats a normal input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import lifecycle_fields as fields,lifecycle_originals as originals,keyboard_source as keyboard

EDITORS=('create','chat','scripts','scripts')


class LifecycleEditorHistory:
    def __init__(self,store,binding,run,lock,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
             and store.path.name=='lifecycle-editor-owner.json' and lock.path==store.path.parent/'script-feature-sources.lock')
        self.store,self.binding,self.run,self.lock,self.guard=store,deepcopy(context(binding)),identifier(run),lock,guard
        self.lock.assert_held();self.previous=store.read()
        self.state=dict(frames=[],original=None,baseline=None,aliases=[])
        self.files=OriginalFrameStore(store.path.parent,self.binding,run,'primary',self.check,self.intent,
            namespace='lifecycle-editor',schema_prefix='iosLifecycleEditor')
        if self.previous is not None:
            value=self.previous;exact(value,{'iosLifecycleEditorOwnerVersion','binding','runId','state'})
            need(type(value['iosLifecycleEditorOwnerVersion']) is int and value['iosLifecycleEditorOwnerVersion']==1
                 and same(value['binding'],self.binding) and value['runId']==self.run)
            self.state=deepcopy(value['state']);self.shape();self.replay()
        else:self.inventory(set())

    def check(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));return True

    def envelope(self):return dict(iosLifecycleEditorOwnerVersion=1,binding=self.binding,runId=self.run,state=deepcopy(self.state))

    def shape(self):
        exact(self.state,{'frames','original','baseline','aliases'})
        need(type(self.state['frames']) is list and len(self.state['frames'])<=64
             and type(self.state['aliases']) is list and len(self.state['aliases'])<=4)
        for index,ref in enumerate(self.state['frames'],1):self.files.expand(ref);need(ref['index']==index)
        pending=self.state['original']
        if pending is not None:self.files.original(pending);need(pending['index']==len(self.state['frames'])+1)
        if self.state['baseline'] is not None:need(type(self.state['baseline']) is int and self.state['baseline']==1 and self.state['frames'])

    def save(self):
        self.check();self.shape();value=self.envelope();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,kind,value):
        need(kind=='original');old=self.state['original'];self.files.original(value)
        if old is not None:
            need(all(same(old[key],value[key]) for key in old if key not in ('phase','file')))
            need((old['phase'],value['phase']) in (('planned','opened'),('opened','saved')))
            if old['file'] is not None:need(same(old['file'],value['file']))
        else:need(value['phase']=='planned')
        self.state['original']=deepcopy(value);self.save()

    def inventory(self,paths):
        for path in self.store.path.parent.iterdir():
            if path.name.startswith('lifecycle-editor-'):
                need(path==self.store.path or path in paths)

    def read(self,index):
        need(integer(index,1,len(self.state['frames'])))
        value=self.files.read(self.files.expand(self.state['frames'][index-1]));originals.validate(value,self.binding,self.run);return value

    def follows(self,before,after):
        a,b=before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore']
        need(a['instance']==b['instance'] and a['sequence']<b['sequence'] and a['capturedEpochMs']<=b['capturedEpochMs']
             and all(b['lifecycle'][key]>=a['lifecycle'][key] for key in a['lifecycle']))
        old,new=before['originals'],after['originals']
        need(old['ui']['instance']==new['beforeUI']['instance']
             and old['ui']['lastSequence']<=new['beforeUI']['lastSequence'] and old['ui']['elapsedMs']<=new['beforeUI']['elapsedMs'])
        fields.validate(new['beforeUI']['lifecycleFieldInventory'],pid=int(self.binding['processIdentity']),previous=old['ui']['lifecycleFieldInventory'])
        k=new['keyboard'];query=dict(schemaVersion=1,commandId=k['requestId'],action=keyboard.ACTION,runId=self.run)
        keyboard.validate(k,query,int(self.binding['processIdentity']),previous=old['keyboard'])
        previous,current=old['pending'],new['pending']
        need(previous['instance']==current['instance'] and previous['sequence']<current['sequence']
             and previous['lastIntentSequence']<=current['lastIntentSequence']
             and previous['capturedEpochMs']<=current['capturedEpochMs']
             and previous['resources']['archivedEvents']<=current['resources']['archivedEvents'])
        if previous['commit']:
            need(current['commit'] and all(same(previous['commit'][key],current['commit'][key]) for key in ('captureCommandId','fieldToken')))
            a,b=previous['commit']['observation'],current['commit']['observation']
            need(all(same(a[key],b[key]) for key in ('instance','eventId','processId','createdEpochMs','source'))
                 and a['sequence']<b['sequence'] and a['elapsedMs']<=b['elapsedMs']
                 and same(a['events'],b['events'][:len(a['events'])]))

    def replay(self):
        self.check();self.shape();values=[];paths=set()
        for index,ref in enumerate(self.state['frames'],1):
            value=self.read(index);paths.add(self.files.path(self.files.expand(ref)))
            if values:self.follows(values[-1],value)
            values.append(value)
        if self.state['original'] is not None:paths.add(self.files.path(self.state['original']))
        self.inventory(paths)
        if self.state['baseline'] is not None:self.baseline_proof(values[0])
        for generation,alias in enumerate(self.state['aliases'],1):
            exact(alias,{'generation','before','after','identity'})
            need(alias['generation']==generation and integer(alias['before'],1,len(values))
                 and integer(alias['after'],alias['before']+1,len(values)))
            if generation>1:need(alias['before']>=self.state['aliases'][generation-2]['after'])
            need(same(alias,self.alias_proof(values[alias['before']-1],values[alias['after']-1],generation,alias['before'],alias['after'])))
        return values

    def append(self,value):
        self.replay();need(self.state['original'] is None and len(self.state['frames'])<64)
        originals.validate(value,self.binding,self.run)
        if self.state['frames']:self.follows(self.read(len(self.state['frames'])),value)
        ref=self.files.write(len(self.state['frames'])+1,value)
        self.state['frames'].append(ref);self.state['original']=None;self.save();return ref['index']

    def recover_original(self):
        self.replay();pending=self.state['original'];need(pending is not None and pending['phase'] in ('opened','saved'))
        value=self.files.read(pending);originals.validate(value,self.binding,self.run)
        if self.state['frames']:self.follows(self.read(len(self.state['frames'])),value)
        if pending['phase']=='opened':
            saved=deepcopy(pending);saved['phase']='saved';self.intent('original',saved);pending=saved
        self.state['frames'].append(self.files.compact(pending));self.state['original']=None;self.save()
        return len(self.state['frames'])

    def baseline_proof(self,value):
        observed=originals.validate(value,self.binding,self.run)
        need(observed['field'] is None and not observed['keyboard']['keyboard'] and not observed['holder']['commit']
             and not observed['holder']['resources']['pendingRuns'])

    def baseline(self):
        values=self.replay();need(len(values)==1 and self.state['baseline'] is None and not self.state['aliases'])
        self.baseline_proof(values[0]);self.state['baseline']=1;self.save()

    def alias_proof(self,before,after,generation,before_index,after_index):
        a,b=before['originals']['ui']['lifecycleFieldInventory'],after['originals']['ui']['lifecycleFieldInventory']
        projected=originals.validate(after,self.binding,self.run)
        alias=fields.alias_transition(a,b,EDITORS[generation-1],generation)
        need(projected['field']['focused']==(generation!=4) and projected['keyboard']['keyboard']==(generation!=4))
        if generation==4:
            prior=self.state['aliases'][2]['identity'];holder=projected['holder']
            need(same(holder['held'],prior) and holder['commit'] and holder['commit']['observation']['pending'])
            rows=[row for row in b['fields'] if same(row['identity'],prior)];need(len(rows)==1)
            need(rows[0]['current'] is None or not rows[0]['current']['attached'] and not rows[0]['current']['focused'])
        return dict(alias,before=before_index,after=after_index)

    def qualify(self,before_index,after_index):
        values=self.replay();generation=len(self.state['aliases'])+1
        need(self.state['baseline']==1 and generation<=4 and integer(before_index,1,len(values))
             and integer(after_index,before_index+1,len(values)))
        if self.state['aliases']:need(before_index>=self.state['aliases'][-1]['after'])
        alias=self.alias_proof(values[before_index-1],values[after_index-1],generation,before_index,after_index)
        self.state['aliases'].append(alias);self.save();return deepcopy(alias)

    def historical_editor(self,index):
        """Historical partial editor projection; this is never a fresh read."""
        self.replay();projected=originals.validate(self.read(index),self.binding,self.run);field=projected['field']
        if field is None:return dict(editor='none',text='',focused=False,generation=0,keyboard=projected['keyboard']['keyboard'])
        aliases=[row for row in self.state['aliases'] if row['after']<=index and same(row['identity'],field['identity'])]
        need(len(aliases)==1 and field['textOwned'])
        return dict(editor=field['identity']['editor'],text=field['text'],focused=field['focused'],
                    generation=aliases[0]['generation'],keyboard=projected['keyboard']['keyboard'])
