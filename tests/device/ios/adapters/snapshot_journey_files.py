"""Closed two-prefix file cleanup after actual pending cancellation/capture.

The standalone capture owner keeps its original one-prefix finalization. This
outer owner accounts for both original namespaces with the existing native
conditional remover and file-job quiet readers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner,SnapshotCapturePending
from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner
from ios.adapters import snapshot_file_absence,snapshot_capture_controls as controls


class IOSSnapshotJourneyFilesOwner:
    def __init__(self,capture):
        need(type(capture) is IOSSnapshotCaptureOwner and not capture.historical)
        self.capture,self.lock,self.binding,self.run=capture,capture.lock,deepcopy(context(capture.binding)),capture.run
        self.fixture_url=capture.phase.fixture_url;self.monotonic,self.epoch_ms,self.sleep=capture.monotonic,capture.epoch_ms,capture.sleep
        self.historical=False;self.setup()
    @classmethod
    def archive(cls,store,lock,binding,run,fixture_url):
        owner=object.__new__(cls);owner.lock,owner.binding,owner.run,owner.fixture_url=lock,deepcopy(context(binding)),run,fixture_url
        owner.capture=IOSSnapshotCaptureOwner.archive(PrivateFeatureState(store.path.with_name('ios-snapshot-primary-capture-owner.json')),lock,binding,run,fixture_url)
        owner.historical=True;owner.setup(store);need(owner.previous is not None);return owner
    def setup(self,store=None):
        self.lock.assert_held();self.store=store or PrivateFeatureState(self.capture.store.path.with_name('ios-snapshot-journey-files-owner.json'))
        need(self.store.path==self.capture.store.path.with_name('ios-snapshot-journey-files-owner.json'))
        for path in self.store.path.parent.iterdir():
            if path.name.startswith('ios-snapshot-journey-files-'):need(path==self.store.path)
        self.pending=IOSSnapshotPendingOwner.archive(PrivateFeatureState(self.store.path.with_name('pending-snapshot-owner.json')),self.lock,self.binding,self.run,self.fixture_url)
        self.pins=self.pair();self.previous=self.store.read();self.state=dict(owned=None,removals=[],restored=False,quiet=[],result=None)
        if self.previous is not None:self.state=self.load(self.previous)
    def pair(self):
        pending=self.pending.result();captured=self.capture.result();need(self.pending.state['initial']['name']==self.capture.state['originalName'])
        follow_native(self.pending.state['nativeTail'],self.capture.state['roots']['clockJoin']['nativeBefore'])
        inputs=self.capture.runtime.inputs(self.capture,historical=True);row=inputs.state['events'][self.capture.state['captureInput']-1]
        reference=next(value for value in row['reference']['controls'] if value['id']=='snapshot.capture')
        need(reference['snapshotRootId']==self.pending.state['initial']['rootId'] and reference['snapshotQmlSource']==self.pending.state['initial']['qmlSource'])
        artifact=self.capture.history('artifact',self.capture.state['artifact'])
        return dict(pendingJournalSha256=digest(self.pending.previous),pendingResultSha256=digest(pending),captureResultSha256=digest(captured),artifactJournalSha256=digest(artifact.previous))
    def guard(self):
        self.capture.bound();need(same(self.store.read(),self.previous) and same(self.pending.store.read(),self.pending.previous));return True
    def envelope(self):return dict(iosSnapshotJourneyFilesOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,pins=self.pins,payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.guard();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def load(self,value):
        exact(value,{'iosSnapshotJourneyFilesOwnerVersion','binding','runId','fixtureUrl','pins','payload'});rows=unpack(value['payload']);need(len(rows)==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(type(value['iosSnapshotJourneyFilesOwnerVersion']) is int and value['iosSnapshotJourneyFilesOwnerVersion']==1 and same(value,self.envelope())
                and type(state['removals']) is list and len(state['removals'])<=1 and type(state['quiet']) is list and len(state['quiet'])<=3 and type(state['restored']) is bool)
            if state['owned'] is not None:self.admit(self.capture.history('owned',state['owned']))
            for index in state['removals']:need(integer(index,1,128));self.capture.history('remove',index).proof()
            if state['restored']:need(self.capture.state['restored']);self.capture.restoration_original()
            for row in state['quiet']:self.sample(row)
            if state['result'] is not None:need(same(state['result'],self.proof()))
        finally:self.state=prior
        return deepcopy(state)
    def admit(self,owned):
        frame=owned.historical();owned.qualified();source=frame['packet']['source'];capture=self.capture
        pending_manifest=self.pending.history('manifest',self.pending.state['baseline']['manifest']).historical()
        capture_manifest=capture.history('manifest',capture.state['baseline']['manifest']).historical()
        expected={value['query']['prefix']:value for value in (pending_manifest,capture_manifest)}
        need(source['complete'] and len(expected)==2 and len(source['prefixes'])==2 and {row['prefix'] for row in source['prefixes']}==set(expected))
        for row in source['prefixes']:
            original=expected[row['prefix']];need(row['initiallyEmpty'] and same(row['query'],original['query']) and row['sampleEpochMs']==original['packet']['sampleEpochMs'])
        captured=capture.result()['capture'];prefix=capture_manifest['query']['prefix']
        need(len(source['files'])<=1 and all(row['prefix']==prefix and same(row['file'],captured['file'])
            and row['capture']['requestId']==captured['captureId'] and row['capture']['captureInstance']==captured['captureInstance']
            and row['capture']['nativeDrained'] and row['capture']['terminal']=='complete' for row in source['files']));return source
    def removal(self,slot):
        child=self.capture.child(slot)
        if child.state['phase']=='issued':
            child.acknowledge();number=len(child.state['observations'])+1
            observed=self.capture.observed('journey-removed-'+str(slot['index'])+'-'+str(number),'owned');child.observe(observed)
        child.proof();sha=digest(child.previous)
        if slot['sha256']!=sha:slot['sha256']=sha;self.capture.save()
        if child.index not in self.state['removals']:self.state['removals'].append(child.index);self.save()
    def group(self,row):
        exact(row,{'manifests','filework','owned','work','captures','exports'});need(type(row['manifests']) is list and len(row['manifests'])==2)
        for index in row['manifests']:need(integer(index,1,128))
        return ([self.capture.history('manifest',index) for index in row['manifests']],self.capture.history('filework',row['filework']),self.capture.history('owned',row['owned']),
            [self.capture.history('remove',index) for index in self.state['removals']])
    def sample(self,row):
        group=self.group(row);self.admit(group[2]);value=snapshot_file_absence.original_sample(*group)
        self.capture.drained({kind:self.capture.history(kind,row[kind]) for kind in ('work','captures','exports')});return value
    def proof(self):
        need(self.state['restored'] and len(self.state['quiet'])==3 and same(self.pins,self.pair()))
        groups=[self.group(row) for row in self.state['quiet']];samples=[self.sample(row) for row in self.state['quiet']]
        quiet=snapshot_file_absence.quiet(groups,samples)
        return dict(iosSnapshotJourneyFilesResultVersion=1,runId=self.run,pins=deepcopy(self.pins),fileChannel=quiet,
            hostOriginalRetained=True,standaloneCaptureFinalized=False,originalJournalRetirementRequired=True,independentWitnessRequired=True,pairedCleanupRequired=True,wholeFeatureRequired=True)
    @operation
    def cleanup(self):
        need(not self.historical);self.guard()
        if self.state['result'] is not None:return self.proof()
        capture=self.capture;need(capture.state['phase'] in ('copied','cleaning'));capture.state['phase']='cleaning';capture.save()
        # Resolve an existing issued remover before another passive probe can
        # replace its original command. An uncertain delete is never resent.
        for slot in capture.state['slots']:
            if slot['kind']=='remove' and slot['label'].startswith('journey-remove-'):
                child=capture.child(slot)
                if child.state is not None and child.state['phase']!='reserved':self.removal(slot)
        attempt=1+sum(row['kind']=='work' and row['label'].startswith('journey-before-') for row in capture.state['slots'])
        capture.drained(capture.packets('journey-before-'+str(attempt)))
        if self.state['owned'] is None:
            capture.observed('journey-cleanup-list','manifest');owned=capture.observed('journey-cleanup-owned','owned');self.admit(owned);self.state['owned']=owned.index;self.save()
        owned=capture.history('owned',self.state['owned']);source=self.admit(owned)
        for file in source['files']:
            slot=capture.slot('journey-remove-'+file['id'],'remove');child=capture.child(slot)
            if child.state is None:child.reserve(owned,file['id'])
            if child.state['phase']=='reserved':child.send()
            self.removal(slot)
        if not self.state['restored']:
            if not capture.state['restored']:
                if capture.state['originalName']=='':
                    view=controls.project(capture.sources['native'].capture());row=next(row for row in view['controls'] if row['id']=='snapshot.name')
                    need(row['snapshotNameOwned'] and row['snapshotName']=='parity-'+self.run[:16]+'-still-png')
                    capture.input('journey-restore-focus','snapshot.name');capture.input('journey-restore-name','snapshot.name',text='')
                from adapters.native_clock_join import NativeClockAcquisition
                acquisition=NativeClockAcquisition(capture.sources['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic);acquisition.begin(self.epoch_ms());ui=capture.sources['native'].capture()
                capture.state['restoration']=dict(ui=ui,clockJoin=acquisition.finish(dict(ui=ui),[('ui','sampleEpochMs')]))
                capture.restoration_original();capture.state['nativeTail']=deepcopy(capture.state['restoration']['clockJoin']['nativeAfter']);capture.state['restored']=True;capture.save()
            self.state['restored']=True;self.save()
        while len(self.state['quiet'])<3:
            if self.state['quiet']:self.sleep(1.6)
            number=len(self.state['quiet'])+1;label='journey-quiet-'+str(number)
            manifests=[capture.observed(label+'-'+mode,'manifest',mode=mode).index for mode in ('animated','still-png')]
            work=capture.observed(label+'-filework','filework');owned=capture.observed(label+'-owned','owned');self.admit(owned)
            group=([capture.history('manifest',index) for index in manifests],work,owned,[capture.history('remove',index) for index in self.state['removals']])
            snapshot_file_absence.sample(*group,guard=self.guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            sources=capture.packets(label);capture.drained(sources)
            self.state['quiet'].append(dict(manifests=manifests,filework=work.index,owned=owned.index,**{kind:source.index for kind,source in sources.items()}));self.save()
        self.state['result']=self.proof();self.save();return deepcopy(self.state['result'])
