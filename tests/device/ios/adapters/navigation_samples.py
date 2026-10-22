"""Durable per-role navigation image index and immutable original archives.

This owns read-only image attempts, never normal inputs or a whole feature.
An uncertain attempt must be explicitly resolved before another can start.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.navigation_scene import validate_status as scene_status
from ios.adapters.graphics_history import follow_native
from ios.adapters.navigation_challenge import evaluate as challenge
from ios.adapters.navigation_sample import NavigationSampleOwner,NavigationMarkerPending
from ios.adapters.navigation_state import validate as state_packet,ACTION

VERSION=1
ROW=frozenset(('requestId','ticket','status','childStarted','archiveSha256','frameId'))


class NavigationSamples:
    def __init__(self,store,root,binding,run,role,stage,lock,guard,*,factory=None,historical=False):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
             and role in ('primary','actor') and type(stage) is int and stage in (0,1) and type(historical) is bool)
        identifier(run);context(binding)
        need(store.path.name=='ios-navigation-'+role+'-'+str(stage)+'-samples.json'
             and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.store,self.root,self.binding,self.run,self.role,self.stage=store,Path(root),deepcopy(binding),run,role,stage
        self.lock,self.historical,self.factory=lock,historical,factory
        self.guard=(lambda:True) if historical else guard
        need(factory is None if historical else callable(factory))
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        PrivateFeatureState(self.root/'navigation-index-root-check')._parent()
        lock.assert_held();self.previous=store.read()
        if self.previous is None:
            need(not historical);self.state=dict(phase='ready',rows=[],seenFrames=[],latestObserved=None);self.save()
        else:self.state=self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosNavigationSamplesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,stage=self.stage,
                    artifactRoot=str(self.root),payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationSamplesVersion','binding','runId','role','stage','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationSamplesVersion']) is int
            and value['iosNavigationSamplesVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','rows','seenFrames','latestObserved'})
        need(state['phase'] in ('ready','reading','failed') and type(state['rows']) is list and len(state['rows'])<=512
             and type(state['seenFrames']) is list)
        requests=[];frames=[];observed=[];pending=[]
        for index,row in enumerate(state['rows']):
            exact(row,ROW);request=row['requestId'];need(type(request) is str and request.startswith('ios-'));identifier(request[4:])
            identifier(row['ticket']);need(type(row['childStarted']) is bool and row['status'] in ('reserved','observed','marker-pending','abandoned'))
            requests.append(request)
            if row['status']=='reserved':
                need(row['archiveSha256'] is row['frameId'] is None);pending.append(index)
            else:
                need(type(row['archiveSha256']) is str and len(row['archiveSha256'])==64
                     and all(c in '0123456789abcdef' for c in row['archiveSha256']))
                if row['frameId'] is not None:identifier(row['frameId']);frames.append(row['frameId'])
                if row['status'] in ('observed','marker-pending'):need(row['childStarted'] and row['frameId'] is not None)
                if row['status']=='observed':observed.append(request)
        need(len(set(requests))==len(requests) and len(set(frames))==len(frames) and frames==state['seenFrames']
             and pending==([len(state['rows'])-1] if state['phase']=='reading' else [])
             and state['latestObserved']==(observed[-1] if observed else None))
        abandoned=[index for index,row in enumerate(state['rows']) if row['status']=='abandoned']
        need(abandoned==([len(state['rows'])-1] if state['phase']=='failed' else []))
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def child_path(self,row):
        return self.store.path.with_name('ios-navigation-'+self.role+'-'+str(self.stage)+'-'+row['requestId'][4:]+'-sample.json')

    def archive_store(self,row):return PrivateFeatureState(self.child_path(row).with_name(self.child_path(row).stem+'-archive.json'))

    def live_child(self,row):
        need(not self.historical);self.bound();child=self.factory(row['requestId'])
        need(isinstance(child,NavigationSampleOwner) and not child.historical and child.store.path==self.child_path(row)
             and child.root==self.root and child.lock.path==self.lock.path and same(child.binding,self.binding)
             and child.run==self.run and child.role==self.role and child.stage==self.stage and child.request==row['requestId'])
        return child

    def frozen_child(self,row,original):
        value=deepcopy(original)
        class Frozen(PrivateFeatureState):
            def read(self):return deepcopy(value)
            def write(self,*_args):need(False)
            def discard(self,*_args):need(False)
        return NavigationSampleOwner(Frozen(self.child_path(row)),self.root,self.binding,self.run,self.role,self.stage,
            row['requestId'],self.lock,lambda:True,historical=True)

    def archive_envelope(self,row,original):
        return dict(iosNavigationImageArchiveVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            stage=self.stage,requestId=row['requestId'],ticket=row['ticket'],originalSha256=digest(original),payload=pack([original]))

    def original(self,row):
        archive=self.archive_store(row).read();need(archive is not None)
        exact(archive,{'iosNavigationImageArchiveVersion','binding','runId','role','stage','requestId','ticket','originalSha256','payload'})
        values=unpack(archive['payload']);need(len(values)==1 and type(archive['iosNavigationImageArchiveVersion']) is int
            and archive['iosNavigationImageArchiveVersion']==VERSION and same(archive,self.archive_envelope(row,values[0])))
        if row['archiveSha256'] is not None:need(digest(archive)==row['archiveSha256'])
        return values[0],archive

    def row(self,request):
        need(type(request) is str);rows=[row for row in self.state['rows'] if row['requestId']==request];need(len(rows)==1);return rows[0]

    def archive(self,request):
        """Only immutable originals and actual retained bytes; never a live read."""
        self.bound();row=self.row(request);need(row['status'] in ('observed','marker-pending'))
        original,_archive=self.original(row);child=self.frozen_child(row,original)
        sample,result=child.archive();need(child.state['phase']==row['status'] and sample['ticket']==row['ticket']
             and (result is None if row['status']=='marker-pending' else result is not None))
        self.bound();return sample,result

    def continuity(self,row,sample):
        previous=[entry for entry in self.state['rows'] if entry is not row and entry['frameId'] is not None]
        if not previous:return
        old,_result=self.archive(previous[-1]['requestId']);before,after=old['frame'],sample['frame']
        follow_native(before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'])
        state_packet(after['navigationBefore'],dict(schemaVersion=1,commandId=after['navigationBefore']['requestId'],
            action=ACTION,runId=self.run),int(self.binding['processIdentity']),previous=before['navigationAfter'])
        need(before['retirement']['instance']==after['capture']['instance']
             and before['retirement']['sequence']<after['capture']['sequence']
             and before['clockJoin']['hostAfterMonotonic']<=after['clockJoin']['hostBeforeMonotonic'])
        scene_status(sample['provider'],instance=sample['providerInstance'],run=self.run,scene_url=sample['provider']['sceneUrl'],
                     previous=old['provider'])
        need(sample['providerInstance']==old['providerInstance'] and sample['fixtureUrl']==old['fixtureUrl'])

    def seal(self,row,child):
        need(row is self.state['rows'][-1] and row['status']=='reserved' and row['childStarted'])
        store=self.archive_store(row)
        if store.read() is None:
            original=deepcopy(child.store.read());archive=self.archive_envelope(row,original)
        else:
            original,archive=self.original(row)
            frozen=self.frozen_child(row,original)
            need(same({key:value for key,value in frozen.state.items() if key!='drains'},
                      {key:value for key,value in child.state.items() if key!='drains'})
                 and len(child.state['drains'])>=len(frozen.state['drains'])
                 and same(child.state['drains'][:len(frozen.state['drains'])],frozen.state['drains']))
            child=frozen
        sample,result=child.archive();need(sample['ticket']==row['ticket'])
        frame=sample['frame']['capture']['source']['renderTrace']['frameId']
        need(frame not in self.state['seenFrames']);self.continuity(row,sample)
        if store.read() is None:store.write(archive,None)
        else:need(same(store.read(),archive))
        need(same(store.read(),archive))
        row.update(status=child.state['phase'],archiveSha256=digest(archive),frameId=frame)
        self.state['seenFrames'].append(frame)
        if result is not None:self.state['latestObserved']=row['requestId']
        self.state['phase']='ready';self.save();return result

    def read(self,ticket,url,label,host_barrier):
        need(not self.historical);identifier(ticket);self.bound()
        need(self.state['phase']=='ready' and len(self.state['rows'])<512)
        row=dict(requestId='ios-'+uuid.uuid4().hex,ticket=ticket,status='reserved',childStarted=False,archiveSha256=None,frameId=None)
        self.state['rows'].append(row);self.state['phase']='reading';self.save()
        child=self.live_child(row);need(child.store.read() is None and self.archive_store(row).read() is None)
        row['childStarted']=True;self.save()
        pending=False
        try:child.capture(ticket,url,label,host_barrier)
        except NavigationMarkerPending:pending=True
        result=self.seal(row,child)
        clock=child.state['record']['frame']['clockJoin'];ended,epoch=child.monotonic(),child.epoch_ms()
        need(number(ended,clock['hostBeforeMonotonic'],clock['hostBeforeMonotonic']+1.5)
             and ended-clock['hostBeforeMonotonic']<1.5
             and number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500)
             and epoch-clock['hostBeforeEpochMs']<1500
             and abs(epoch-clock['hostBeforeEpochMs']-(ended-clock['hostBeforeMonotonic'])*1000)<=250)
        self.bound()
        if pending:raise NavigationMarkerPending('Original indexed navigation marker has not rendered')
        need(result is not None);return deepcopy(dict(requestId=row['requestId'],**result))

    def changed(self,request):
        """Compare the immediately previous observed original, never a chosen baseline."""
        self.bound();row=self.row(request);need(row['status']=='observed')
        index=self.state['rows'].index(row);previous=[entry for entry in self.state['rows'][:index] if entry['status']=='observed']
        need(bool(previous));sample,_=self.archive(request);old,_=self.archive(previous[-1]['requestId'])
        result,_subject=challenge(self.run,self.binding,sample,previous=old,changed=True)
        self.bound();return deepcopy(result)

    def recover(self):
        """No capture replay. Uncertain/missing ownership stays unresolved."""
        need(not self.historical);self.bound();need(self.state['phase']=='reading')
        row=self.state['rows'][-1];child=self.live_child(row)
        if child.state is not None and child.state['phase'] in ('observed','marker-pending'):
            # Resolves only the old durable return. Callers still need a NEW
            # request for fresh observations and may not resend an input.
            self.seal(row,child);return
        if not row['childStarted']:
            need(child.store.read() is None and child.owner().store.read() is None and self.archive_store(row).read() is None)
            try:(self.root/child.owner().name).lstat()
            except FileNotFoundError:pass
            else:need(False)
            original=None
        else:
            need(child.state is not None);child.drain();original=deepcopy(child.store.read())
        archive=self.archive_envelope(row,original);store=self.archive_store(row)
        if store.read() is None:store.write(archive,None)
        else:need(same(store.read(),archive))
        row.update(status='abandoned',archiveSha256=digest(archive));self.state['phase']='failed';self.save()
