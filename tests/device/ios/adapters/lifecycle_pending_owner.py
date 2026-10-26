"""Durable one-send native held-callback inputs and exact original recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters import pending_commit_owner as native
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.adapters.lifecycle_originals import IOSLifecycleSources,validate as original
from ios.adapters import lifecycle_pending_commands as receipts


class LifecyclePendingOwner:
    def __init__(self,store,history,sources,reader):
        need(isinstance(store,PrivateFeatureState) and isinstance(history,LifecycleEditorHistory) and isinstance(sources,IOSLifecycleSources)
             and isinstance(reader,receipts.IOSLifecyclePendingCommands) and isinstance(sources.pending,native.NativePendingCommitOwner))
        self.store,self.history,self.sources,self.reader=store,history,sources,reader
        self.binding,self.run,self.lock=history.binding,history.run,history.lock
        need(store.path==history.store.path.with_name('ios-lifecycle-primary-pending.json') and same(sources.binding,self.binding)
             and sources.run==self.run and sources.pending.ios and sources.pending.pid==int(self.binding['processIdentity']))
        self.previous=store.read();self.state=dict(events=[],storage={}) if self.previous is None else self.decode(self.previous)
        sources.pending.intent=self.intent

    def files(self,live=False):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,'primary',self.bound if live else lambda:True,
            self.storage if live else lambda *_:need(False),namespace='ios-lifecycle-pending-proof',schema_prefix='iosLifecyclePendingProof')

    def bound(self):
        self.history.check();need(same(self.store.read(),self.previous));return True

    def envelope(self):return dict(iosLifecyclePendingOwnerVersion=1,binding=self.binding,runId=self.run,state=deepcopy(self.state))

    def before(self,event,reference):
        self.history.files.expand(reference);index=reference['index'];need(integer(index,1,len(self.history.state['frames'])))
        need(same(reference,self.history.state['frames'][index-1]));value=self.history.read(index);facts=original(value,self.binding,self.run)
        holder=facts['holder'];raw=value['originals']['pending'];operation=event['operation']
        if operation=='hold':
            field=facts['field'];need(field is not None and field['identity']['editor']=='scripts' and field['focused']
                 and field['textOwned'] and field['text']=='retry-'+self.run and facts['keyboard']['keyboard']
                 and holder['commit']=={} and holder['current']==field['identity'])
            alias=[row for row in self.history.state['aliases'] if row['generation']==3];need(len(alias)==1 and alias[0]['identity']==holder['current'] and alias[0]['after']<=index)
        else:
            need(self.state['events']);held=self.receipt(self.state['events'][0]);need(held['performed'])
            need(holder['commit'] and holder['commit']['captureCommandId']==held['commit']['captureCommandId']
                 and holder['commit']['observation']['eventId']==held['commit']['observation']['eventId'])
            if operation=='attempt':
                field=facts['field'];need(field is not None and field['identity']['editor']=='scripts' and not field['focused']
                    and field['text']=='' and not facts['keyboard']['keyboard'] and holder['commit']['observation']['pending']
                    and raw['current']['token']!=holder['commit']['fieldToken'])
                alias=[row for row in self.history.state['aliases'] if row['generation']==4]
                need(len(alias)==1 and alias[0]['identity']==holder['current'] and alias[0]['after']<=index)
        return value

    def expected(self,event,request):
        native.command(request,ios=True);value=self.before(event,event['preparations'][-1]);before=value['originals']['pending']
        expected=dict(schemaVersion=1,commandId=request['commandId'],action='feature-pending-commit-owner',operation=event['operation'],runId=self.run,
            eventId='' if event['operation']=='hold' else before['commit']['observation']['eventId'],ownerInstance=before['instance'],intentSequence=before['lastIntentSequence']+1)
        if event['operation']!='release':expected.update(fieldToken=before['current']['token'],observationSequence=before['sequence'])
        need(same(request,expected))

    def receipt(self,event):
        need(event['phase']=='returned' and event['proof'] is not None)
        store=self.files();frame=store.read(store.expand(event['proof']));exact(frame,{'packet'})
        packet=frame['packet'];need(packet['runId']==self.run and packet['processId']==int(self.binding['processIdentity']))
        return receipts.response(packet,event['request'])

    def decode(self,value):
        exact(value,{'iosLifecyclePendingOwnerVersion','binding','runId','state'})
        need(type(value['iosLifecyclePendingOwnerVersion']) is int and value['iosLifecyclePendingOwnerVersion']==1
             and same(value['binding'],self.binding) and value['runId']==self.run)
        state=value['state'];exact(state,{'events','storage'});need(type(state['events']) is list and len(state['events'])<=3 and type(state['storage']) is dict)
        need(all(type(row) is dict and 'operation' in row for row in state['events']))
        operations=tuple(row['operation'] for row in state['events'])
        need(operations in ((),('hold',),('hold','attempt'),('hold','release'),('hold','attempt','release')))
        previous=getattr(self,'state',None);self.state=state
        try:
            commands=set()
            for index,event in enumerate(state['events'],1):
                exact(event,{'index','operation','phase','preparations','request','proof','afterStart','after'})
                need(type(event['index']) is int and event['index']==index and event['phase'] in ('planned','issued','returned')
                     and type(event['preparations']) is list and 1<=len(event['preparations'])<=8)
                first=None
                for ref in event['preparations']:
                    before=self.before(event,ref);current=before['originals']['pending']
                    if first is None:first=before
                    else:
                        a=original(first,self.binding,self.run)['holder'];b=original(before,self.binding,self.run)['holder']
                        need(same(a['current'],b['current']) and same(a['held'],b['held']) and first['originals']['pending']['instance']==current['instance']
                             and first['originals']['pending']['lastIntentSequence']==current['lastIntentSequence'])
                if event['request'] is not None:
                    self.expected(event,event['request']);need(event['request']['commandId'] not in commands);commands.add(event['request']['commandId'])
                if event['phase']=='planned':need(event['request'] is None and event['proof'] is None)
                else:need(event['request'] is not None)
                if event['phase']=='returned':self.receipt(event)
                else:need(event['proof'] is None and index==len(state['events']))
                if event['afterStart'] is not None:need(event['phase']=='returned' and integer(event['afterStart'],event['preparations'][-1]['index']))
                if event['after'] is not None:self.effect(event)
            for key,ref in state['storage'].items():
                need(type(key) is str and key.isdigit() and 1<=int(key)<=len(state['events']));self.files().original(ref);need(ref['index']==int(key))
        finally:self.state=previous
        return deepcopy(state)

    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)

    def intent(self,request):
        self.bound();event=self.state['events'][-1];need(event['phase']=='planned' and event['request'] is None)
        self.expected(event,request);event.update(phase='issued',request=deepcopy(request));self.save();return True

    def storage(self,kind,value):
        self.bound();event=self.state['events'][-1];need(kind=='original' and event['phase']=='issued' and value['index']==event['index'])
        self.files().original(value);key=str(event['index']);old=self.state['storage'].get(key)
        if old is None:need(value['phase']=='planned')
        else:
            need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                 and all(same(old[k],value[k]) for k in old if k not in ('phase','file'))
                 and (old['phase']=='planned' or same(old['file'],value['file'])))
        self.state['storage'][key]=deepcopy(value);self.save()

    def recover(self,event):
        self.bound();need(event['phase']=='issued');saved=self.state['storage'].get(str(event['index']))
        if saved is not None:
            need(saved['phase'] in ('opened','saved'));frame=self.files().read(saved);exact(frame,{'packet'});packet=frame['packet']
            if saved['phase']=='opened':saved=dict(saved,phase='saved');self.storage('original',saved)
            proof=self.files().compact(saved)
        else:
            packet=self.reader.read(self.run);need(packet['runId']==self.run and packet['processId']==int(self.binding['processIdentity']))
            receipts.response(packet,event['request']);proof=self.files(True).write(event['index'],dict(packet=deepcopy(packet)))
        receipts.response(packet,event['request']);event.update(phase='returned',proof=proof);self.save();return self.receipt(event)

    def effect(self,event):
        need(event['after'] is not None);self.history.files.expand(event['after'])
        need(integer(event['afterStart'],1,len(self.history.state['frames']))
             and integer(event['after']['index'],1,len(self.history.state['frames'])) and event['after']['index']==event['afterStart']+1)
        index=event['after']['index'];need(same(event['after'],self.history.state['frames'][index-1]))
        before=self.before(event,event['preparations'][-1]);after=self.history.read(index);self.history.follows(before,after)
        a=original(before,self.binding,self.run);b=original(after,self.binding,self.run);receipt=self.receipt(event)
        need(receipt['performed'] and before['originals']['ui']['lastSequence']==after['originals']['ui']['lastSequence'])
        actual=after['originals']['pending'];request=event['request']
        need(actual['instance']==request['ownerInstance'] and actual['lastIntentSequence']==request['intentSequence']
             and b['holder']['commit'] and b['holder']['commit']['captureCommandId']==receipt['commit']['captureCommandId']
             and b['holder']['commit']['observation']['eventId']==receipt['commit']['observation']['eventId'])
        if event['operation']=='hold':
            need(b['holder']['held']==a['holder']['current'] and b['holder']['commit']['observation']['pending']
                 and same(a['field'],b['field']) and b['keyboard']['keyboard'])
        elif event['operation']=='attempt':
            end=b['holder']['commit']['observation'];need(not end['pending'] and end['events'][-1]['kind']=='rejected'
                and end['events'][-1]['reason']=='context-retired' and same(a['field'],b['field']) and not b['keyboard']['keyboard'])
        else:need(not b['holder']['commit']['observation']['pending'] and b['holder']['resources']['pendingRuns']==[]
                  and same(a['field'],b['field']) and a['keyboard']['keyboard']==b['keyboard']['keyboard'])
        return deepcopy(receipt)

    def act(self,operation):
        self.bound();need(operation in ('hold','attempt','release'));found=[row for row in self.state['events'] if row['operation']==operation]
        if found:event=found[0]
        else:
            need(not self.state['events'] or self.state['events'][-1]['phase']=='returned')
            self.history.append(self.sources.sample(self.sources.epoch_ms()))
            event=dict(index=len(self.state['events'])+1,operation=operation,phase='planned',preparations=[deepcopy(self.history.state['frames'][-1])],
                request=None,proof=None,afterStart=None,after=None)
            self.state['events'].append(event);self.save()
        if event['phase']=='planned':
            # Unissued recovery refreshes only a lease for that same original
            # context. Every prior preparation remains an immutable reference.
            self.history.append(self.sources.sample(self.sources.epoch_ms()));event['preparations'].append(deepcopy(self.history.state['frames'][-1]));self.save()
            before=self.before(event,event['preparations'][-1])['originals']['pending'];self.sources.pending.last=deepcopy(before)
            self.sources.pending.operate(self.run,operation,event_id='' if operation=='hold' else before['commit']['observation']['eventId'])
        result=self.recover(event) if event['phase']=='issued' else self.receipt(event)
        need(result['performed'])
        if event['after'] is None:
            if event['afterStart'] is None:event['afterStart']=len(self.history.state['frames']);self.save()
            if len(self.history.state['frames'])==event['afterStart']:
                if self.history.state['original'] is not None:self.history.recover_original()
                else:self.history.append(self.sources.sample(self.sources.epoch_ms()))
            need(len(self.history.state['frames'])==event['afterStart']+1);event['after']=deepcopy(self.history.state['frames'][-1])
            try:self.effect(event)
            except BaseException:event['after']=None;raise
            self.save()
        return self.effect(event)
