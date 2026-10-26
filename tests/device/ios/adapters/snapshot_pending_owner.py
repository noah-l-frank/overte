"""Ordinary animated pending capture/cancel with original timer/file proofs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from types import SimpleNamespace
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_cancellation import pending
from ios.adapters.snapshot_manifest import absent
from ios.adapters.snapshot_pending_packets import PACKETS,PendingInputs,PendingChoices
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters import snapshot_capture_controls as controls,snapshot_pending_choices as choices,snapshot_work,snapshot_captures,snapshot_exports


class SnapshotPendingCapturePending(NativeUIError):pass


class IOSSnapshotPendingOwner(IOSSnapshotCaptureOwner):
    """Reuse the existing child/input machinery in its own closed profile."""
    def __init__(self,runtime,selector,run,lock,sources,*,phase,epoch_ms,monotonic,sleep):
        from ios.adapters.snapshot_pending_runtime import IOSSnapshotPendingRuntime
        need(isinstance(runtime,IOSSnapshotPendingRuntime) and isinstance(phase,PhaseFixtureReader) and phase.run==run and phase.area=='snapshots')
        self.runtime,self.selector,self.run,self.lock,self.sources=runtime,selector,identifier(run),lock,sources
        self.binding=deepcopy(context(sources['binding']));self.guard=sources['check'];self.phase=phase
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep;self.historical=False
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('pending-snapshot-owner.json'));self.previous=self.store.read();lock.assert_held()
        self.state=self.empty()
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(set())
        if self.state['nativeTail'] is not None:restore(sources['clock_source'],self.state['nativeTail'])
    @staticmethod
    def empty():return dict(ticket=None,phaseOriginal=None,roots=None,nativeTail=None,slots=[],inputSlots=[],choiceSlots=[],initial=None,baseline=None,
        captureInput=None,pendingWork=None,cancelInput=None,cancelledWork=None,afterNative=None,afterManifest=None,cancellation=None,restoration=None,quiet=[],result=None)
    @classmethod
    def archive(cls,store,lock,binding,run,fixture_url):
        from ios.adapters.snapshot_pending_runtime import IOSSnapshotPendingRuntime
        owner=object.__new__(cls);owner.store,owner.lock,owner.binding,owner.run=store,lock,deepcopy(context(binding)),identifier(run)
        owner.runtime=object.__new__(IOSSnapshotPendingRuntime);owner.phase=SimpleNamespace(fixture_url=fixture_url);owner.guard=lambda:True;owner.historical=True
        lock.assert_held();owner.previous=store.read();need(owner.previous is not None);owner.state=owner.empty();owner.state=owner.decode(owner.previous);return owner
    def envelope(self,state):return dict(iosSnapshotPendingOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.phase.fixture_url,payload=pack([state]))
    def phase_original(self,value,ticket):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'][-1]['ticket']==ticket and value['activations'][-1]['stimulus']==dict(verb='capture-cancel',inputs=dict(mode='animated',format='png')))
    def active(self):
        value=self.phase.read(self.state['phaseOriginal']);self.phase_original(value['status'],self.state['ticket'])
        need(value['status']['instance']==self.state['phaseOriginal']['instance']);return value
    def inventory(self,reads):
        allowed={self.store.path}|{self.child_store(slot).path for slot in self.state['slots']}|{
            self.store.path.with_name(cls.store_name('primary')) for cls in (PendingInputs,PendingChoices)}
        for path in self.store.path.parent.iterdir():
            if path.name.startswith('pending-snapshot-'):need(path in allowed or path in reads)
    def child_store(self,slot):return PrivateFeatureState(self.store.path.with_name('pending-snapshot-primary-'+PACKETS[slot['kind']]._name+'-'+format(slot['index'],'04d')+'.json'))
    def decode(self,value):
        exact(value,{'iosSnapshotPendingOwnerVersion','binding','runId','fixtureUrl','payload'});rows=unpack(value['payload']);need(len(rows)==1)
        state=rows[0];exact(state,set(self.empty()));need(type(value['iosSnapshotPendingOwnerVersion']) is int and value['iosSnapshotPendingOwnerVersion']==1 and same(value,self.envelope(state)))
        prior=self.state;self.state=state
        try:
            need(type(state['slots']) is list and len(state['slots'])<=256 and type(state['inputSlots']) is list and len(state['inputSlots'])<=16
                and type(state['choiceSlots']) is list and len(state['choiceSlots'])<=2 and type(state['quiet']) is list and len(state['quiet'])<=3)
            if state['ticket'] is not None:self.phase_original(state['phaseOriginal'],identifier(state['ticket']))
            if state['roots'] is not None:self.root_original(state['roots'])
            if state['initial'] is not None:
                exact(state['initial'],{'name','rootId','qmlSource'});need(state['initial']['name'] in ('','parity-'+self.run[:16]+'-animated'))
            with read_scope(fresh=True) as reads:
                counters={};labels=set();previous={};tail=None if state['roots'] is None else state['roots']['clockJoin']['nativeAfter'];restoration_adopted=False
                for slot in state['slots']:
                    exact(slot,{'label','kind','index','sha256'});need(slot['kind'] in PACKETS and type(slot['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',slot['label']) and slot['label'] not in labels)
                    labels.add(slot['label']);counters[slot['kind']]=counters.get(slot['kind'],0)+1;need(type(slot['index']) is int and slot['index']==counters[slot['kind']])
                    if self.child_store(slot).read() is None:need(slot['sha256'] is None);continue
                    child=self.child(slot,True)
                    if slot['sha256'] is not None:
                        need(digest(child.previous)==slot['sha256']);frame=child.historical()
                        if slot['label'].startswith('quiet-') and state['restoration'] is not None and not restoration_adopted:
                            restoration_adopted=True;restored=state['restoration']['clockJoin'];need(tail is not None);follow_native(tail,restored['nativeBefore']);tail=restored['nativeAfter']
                        span=frame.get('clockJoin',frame.get('acquisition'));need(tail is not None);follow_native(tail,span['nativeBefore']);tail=span['nativeAfter']
                        if slot['kind']!='manifest':
                            child.qualified()
                            if slot['kind'] in previous:child._source.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=previous[slot['kind']])
                            previous[slot['kind']]=frame['packet']
                    else:
                        if child.state.get('rawParts') is not None:child.parts().inspect(child.state['rawParts'])
                        if child.state.get('storage') is not None:
                            ref=child.state['storage']
                            if ref['phase']=='planned':need(not child.files().path(ref).exists())
                            else:child.files().read(ref)
                for cls,name,slots in ((PendingInputs,'inputSlots',state['inputSlots']),(PendingChoices,'choiceSlots',state['choiceSlots'])):
                    path=self.store.path.with_name(cls.store_name('primary'))
                    events=[] if PrivateFeatureState(path).read() is None else self.runtime.inputs(self,historical=True,choices=cls is PendingChoices).state['events']
                    need(len(events)<=len(slots))
                    for index,row in enumerate(slots,1):
                        exact(row,{'label','index','control','text'});need(type(row['index']) is int and row['index']==index)
                        if index<=len(events):need(row['control']==events[index-1]['controlId'] and row['text']==events[index-1]['command'].get('text'))
                if state['cancellation'] is not None:need(same(state['cancellation'],self.cancellation()))
                if state['restoration'] is not None:
                    self.restoration_original()
                    if not restoration_adopted:
                        restored=state['restoration']['clockJoin'];need(tail is not None);follow_native(tail,restored['nativeBefore']);tail=restored['nativeAfter']
                need(same(state['nativeTail'],tail))
                for group in state['quiet']:self.quiet_sample(group)
                if state['result'] is not None:need(same(state['result'],self.result()))
                self.inventory(reads)
        finally:self.state=prior
        return deepcopy(state)
    def slot(self,label,kind):
        rows=[row for row in self.state['slots'] if row['label']==label]
        if rows:need(rows[0]['kind']==kind);return rows[0]
        need(kind in PACKETS and len(self.state['slots'])<256);row=dict(label=label,kind=kind,index=1+sum(item['kind']==kind for item in self.state['slots']),sha256=None)
        self.state['slots'].append(row);self.save();return row
    def observed(self,label,kind,*,mode='animated',**_kwargs):
        slot=self.slot(label,kind);child=self.child(slot)
        if child.state is None:child.reserve(mode) if kind=='manifest' else child.reserve()
        if child.state['phase']=='reserved':child.send(self.epoch_ms()) if kind=='manifest' else child.send()
        if child.state['phase']=='issued':child.recover() if kind=='manifest' else child.retain()
        frame=child.historical()
        if kind!='manifest':child.qualified()
        if slot['sha256'] is None:
            if kind!='manifest':
                prior=[row for row in self.state['slots'] if row['kind']==kind and row['index']<slot['index'] and row['sha256'] is not None]
                if prior:child._source.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=self.history(kind,prior[-1]['index']).historical()['packet'])
            span=frame.get('clockJoin',frame.get('acquisition'))
            if self.state['nativeTail'] is not None:follow_native(self.state['nativeTail'],span['nativeBefore'])
            self.state['nativeTail']=deepcopy(span['nativeAfter']);slot['sha256']=digest(child.previous);self.save()
        need(slot['sha256']==digest(child.previous));return child
    def control(self):
        value=controls.project(self.sources['native'].capture());rows=[row for row in value['controls'] if row['id']=='snapshot.capture'];need(value['open'] and len(rows)==1)
        row=rows[0];need(row['snapshotSettingsLoaded'] and row['snapshotFormat']=='png' and not row['snapshotProcessing'] and not row['snapshotSystemBlocked'] and row['snapshotImageCount']==0)
        if self.state['initial'] is not None:need(all(row[key]==self.state['initial'][target] for key,target in [('snapshotRootId','rootId'),('snapshotQmlSource','qmlSource')]))
        return row
    def choice(self,label,control):
        slots=self.state['choiceSlots'];rows=[row for row in slots if row['label']==label];owner=self.runtime.inputs(self,choices=True)
        if rows:row=rows[0];need(row['control']==control)
        else:row=dict(label=label,index=len(slots)+1,control=control,text=None);slots.append(row);self.save()
        if len(owner.state['events'])<row['index']:
            self.active();view=choices.project(self.sources['native'].capture(),control)
            need(view['root']['rootId']==self.state['initial']['rootId'] and view['root']['qmlSource']==self.state['initial']['qmlSource']);owner.reserve(control,view)
        event=owner.state['events'][row['index']-1]
        if event['phase']=='reserved':self.active();owner.send()
        elif event['phase']=='issued':owner.recover(self.observed(label+'-delivery','choices').historical()['packet'])
        owner.validate_original(row['index'])
    def mode(self,label,option):
        self.input(label+'-popup','snapshot.mode');self.choice(label+'-choice','snapshot.mode.'+option)
        need(self.control()['snapshotMode']==(1 if option=='animated' else 0))
    def next_observed(self,prefix,kind):
        rows=[row for row in self.state['slots'] if row['kind']==kind and row['label'].startswith(prefix)]
        return self.observed(rows[-1]['label'] if rows and rows[-1]['sha256'] is None else prefix+str(len(rows)+1),kind)
    def cancellation(self):
        need(all(self.state[key] is not None for key in ('captureInput','pendingWork','cancelInput','cancelledWork','afterNative','afterManifest')))
        baseline=self.state['baseline']
        return pending(self.runtime.inputs(self,historical=True),self.state['captureInput'],self.state['cancelInput'],
            self.history('captures',baseline['captures']).historical()['packet'],self.history('work',self.state['pendingWork']).historical()['packet'],
            self.history('work',self.state['cancelledWork']).historical()['packet'],self.history('captures',self.state['afterNative']).historical()['packet'],
            self.history('manifest',baseline['manifest']),self.history('manifest',self.state['afterManifest']),self.root_original(self.state['roots']))
    def quiet_sample(self,group):
        exact(group,{'manifest','work','captures','exports'});frames=[]
        for kind in ('manifest','work','captures','exports'):
            index=group[kind]
            need(integer(index,1,128));frames.append(self.history(kind,index).historical())
        absent(frames[0],int(self.binding['processIdentity']),self.run,'animated')
        snapshot_work.admit(frames[1]['packet'],self.root_original(self.state['roots']),quiet=True);snapshot_captures.drained(frames[2]['packet']);snapshot_exports.drained(frames[3]['packet'])
        spans=[frame.get('clockJoin',frame.get('acquisition')) for frame in frames]
        return dict(nativeBefore=min(span['nativeBefore']['capturedEpochMs'] for span in spans),nativeAfter=max(span['nativeAfter']['capturedEpochMs'] for span in spans),
            hostBefore=min(span['hostBeforeMonotonic'] for span in spans)*1000,hostAfter=max(span['hostAfterMonotonic'] for span in spans)*1000)
    def restoration_original(self):
        value=self.state['restoration'];exact(value,{'ui','clockJoin'});span=validate_join(value['clockJoin'],dict(ui=value['ui']));pid=int(self.binding['processIdentity'])
        need(span['nativeBefore']['processId']==pid);ui_packet(value['ui'],pid,span['nativeAfter']['capturedEpochMs'])
        rows=controls.project(value['ui'])['controls'];row=next(row for row in rows if row['id']=='snapshot.capture')
        need(row['snapshotRootId']==self.state['initial']['rootId'] and row['snapshotQmlSource']==self.state['initial']['qmlSource'] and row['snapshotMode']==0
            and row['snapshotFormat']=='png' and not row['snapshotCapturing'] and not row['snapshotProcessing'] and not row['snapshotSystemBlocked'] and row['snapshotImageCount']==0
            and (row['snapshotNameSha256']==controls.EMPTY if self.state['initial']['name']=='' else row['snapshotNameOwned'] and row['snapshotName']==self.state['initial']['name']))
    def result(self):
        need(self.state['cancellation'] is not None and len(self.state['quiet'])==3 and self.state['restoration'] is not None);self.restoration_original()
        proof=self.cancellation();samples=[self.quiet_sample(group) for group in self.state['quiet']]
        need(samples[-1]['nativeBefore']-samples[0]['nativeAfter']>=3000 and samples[-1]['hostBefore']-samples[0]['hostAfter']>=3000)
        return dict(iosSnapshotPendingResultVersion=1,runId=self.run,cancellation=proof,nativeQuietMilliseconds=samples[-1]['nativeBefore']-samples[0]['nativeAfter'],
            hostQuietMilliseconds=samples[-1]['hostBefore']-samples[0]['hostAfter'],originalSettingsRestored=True,
            originalJournalRetirementRequired=True,independentWitnessRequired=True,wholeFeatureRequired=True)
    @operation
    def cancel(self,ticket):
        self.bound();identifier(ticket)
        if self.state['result'] is not None:need(self.state['ticket']==ticket);return self.result()
        if self.state['ticket'] is None:
            actual=self.phase.read();self.phase_original(actual['status'],ticket);self.state.update(ticket=ticket,phaseOriginal=actual['status']);self.save()
        else:need(self.state['ticket']==ticket);self.active()
        if self.state['roots'] is None:self.state['roots']=self.runtime.roots(self);self.state['nativeTail']=deepcopy(self.state['roots']['clockJoin']['nativeAfter']);self.save()
        if self.state['initial'] is None:
            row=self.control();need(row['snapshotMode']==0 and not row['snapshotCapturing'] and (row['snapshotNameSha256']==controls.EMPTY or row['snapshotName']=='parity-'+self.run[:16]+'-animated'))
            self.state['initial']=dict(name='' if row['snapshotNameSha256']==controls.EMPTY else row['snapshotName'],rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource']);self.save()
        if self.state['baseline'] is None:
            self.input('name-focus','snapshot.name');self.input('name-set','snapshot.name',text='parity-'+self.run[:16]+'-animated');self.mode('animated','animated')
            baseline={kind:self.observed('before-'+kind,kind).index for kind in ('manifest','work','captures','exports')};self.quiet_sample(baseline);self.state['baseline']=baseline;self.save()
        if self.state['captureInput'] is None:self.state['captureInput']=self.input('pending-capture','snapshot.capture');self.save()
        if self.state['pendingWork'] is None:self.state['pendingWork']=self.observed('actual-pending','work').index;self.save()
        if self.state['cancelInput'] is None:self.state['cancelInput']=self.input('pending-cancel','snapshot.cancel');self.save()
        if self.state['cancelledWork'] is None:
            child=self.next_observed('actual-cancelled-','work')
            try:snapshot_work.admit(child.historical()['packet'],self.root_original(self.state['roots']),quiet=True)
            except NativeUIError:raise SnapshotPendingCapturePending('Actual script timers/callbacks remain owned') from None
            self.state['cancelledWork']=child.index;self.save()
        if self.state['afterNative'] is None:
            child=self.next_observed('after-cancel-native-','captures')
            try:snapshot_captures.drained(child.historical()['packet'])
            except NativeUIError:raise SnapshotPendingCapturePending('Actual native captures/resources remain owned') from None
            self.state['afterNative']=child.index;self.save()
        if self.state['afterManifest'] is None:self.state['afterManifest']=self.observed('after-cancel-files','manifest').index;self.save()
        if self.state['cancellation'] is None:self.state['cancellation']=self.cancellation();self.save()
        if self.state['restoration'] is None:
            self.mode('restore','still');self.input('restore-name-focus','snapshot.name');self.input('restore-name','snapshot.name',text=self.state['initial']['name'])
            acquisition=NativeClockAcquisition(self.sources['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic);acquisition.begin(self.epoch_ms())
            ui=self.sources['native'].capture();self.state['restoration']=dict(ui=ui,clockJoin=acquisition.finish(dict(ui=ui),[('ui','sampleEpochMs')]))
            self.restoration_original();follow_native(self.state['nativeTail'],self.state['restoration']['clockJoin']['nativeBefore'])
            self.state['nativeTail']=deepcopy(self.state['restoration']['clockJoin']['nativeAfter']);self.save()
        while len(self.state['quiet'])<3:
            if self.state['quiet']:self.sleep(1.6)
            label='quiet-'+str(len(self.state['quiet'])+1);group={kind:self.observed(label+'-'+kind,kind).index for kind in ('manifest','work','captures','exports')}
            self.quiet_sample(group);self.state['quiet'].append(group);self.save()
        self.state['result']=self.result();self.save();return deepcopy(self.state['result'])
