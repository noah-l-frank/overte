"""Durable internal normal still/PNG capture, original bytes and file cleanup.

This composes existing owners. Scene fidelity, external destinations, Actor
evidence, host-original retirement and paired finalization remain mandatory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.native_script_roots import validate as roots_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as original_reads
from adapters.original_packet_segments import CHUNK_BYTES as PART_BYTES
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters import snapshot_capture_controls as controls,snapshot_work,snapshot_captures,snapshot_exports,snapshot_completion,snapshot_chunks,snapshot_file_absence
from ios.adapters.snapshot_manifest import absent
from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime,TYPES
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters.snapshot_owned_packet import original as owned_original
from types import SimpleNamespace


class SnapshotCapturePending(NativeUIError):pass


class IOSSnapshotCaptureOwner:
    def __init__(self,runtime,selector,run,lock,sources,*,phase,epoch_ms,monotonic,sleep,combined=False):
        need(type(combined) is bool);self.combined=combined
        need(isinstance(runtime,IOSSnapshotCaptureRuntime) and isinstance(phase,PhaseFixtureReader) and phase.area=='snapshots' and phase.run==run)
        self.runtime,self.selector,self.run,self.lock,self.sources=runtime,selector,identifier(run),lock,sources
        self.binding=deepcopy(context(sources['binding']));self.guard=sources['check'];self.phase=phase
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-snapshot-primary-capture-owner.json'))
        self.previous=self.store.read();self.state=dict(phase='new',ticket=None,phaseOriginal=None,roots=None,baseline=None,slots=[],inputSlots=[],captureInput=None,
            artifact=None,result=None,settled=None,quiet=[],nativeTail=None,originalName=None,restored=False,restoration=None)
        self.historical=False;lock.assert_held()
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory()
        if self.state['nativeTail'] is not None:restore(sources['clock_source'],self.state['nativeTail'])

    @classmethod
    def archive(cls,store,lock,binding,run,fixture_url,*,combined=False):
        """Actual local originals only; no SDK or live source construction."""
        need(type(combined) is bool);owner=object.__new__(cls);owner.runtime=object.__new__(IOSSnapshotCaptureRuntime);owner.combined=combined
        owner.selector=None;owner.run=identifier(run);owner.lock=lock;owner.binding=deepcopy(context(binding));owner.store=store
        owner.sources=None;owner.phase=SimpleNamespace(fixture_url=fixture_url);owner.guard=lambda:True;owner.historical=True
        lock.assert_held();owner.previous=store.read();need(owner.previous is not None);owner.state=unpack(owner.previous['payload'])[0]
        owner.state=owner.decode(owner.previous);return owner

    def envelope(self,state):
        return dict(iosSnapshotCaptureOwnerVersion=2 if self.combined else 1,runId=self.run,binding=self.binding,fixtureUrl=self.phase.fixture_url,payload=pack([state]))

    def work_source(self):
        if getattr(self,'combined',False):
            from ios.adapters import snapshot_combined_work
            return snapshot_combined_work
        return snapshot_work

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False)

    def save(self):
        self.bound();need(not self.historical);value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def inventory(self,reads=None):
        # The coordinator cannot adopt unknown prior child ownership. Exact
        # original files belonging to declared children remain their owners'
        # responsibility; no source/child metadata is discarded here.
        names={self.store.path.name,'ios-snapshot-primary-inputs.json'}
        for slot in self.state['slots']:
            cls=self.runtime.component_type(self,slot['kind']);kind=getattr(cls,'_name',slot['kind']);names.add('ios-snapshot-primary-'+kind+'-'+format(slot['index'],'04d')+'.json')
        for index,path in enumerate(self.store.path.parent.iterdir()):
            need(index<8192)
            if path.name.startswith('ios-snapshot-primary-') and path.name.endswith('.json'):need(path.name in names)
            prefixes=('snapshot-manifest-','snapshot-chunk-','snapshot-input-proof-','snapshot-artifact-work-','snapshot-native-',
                'snapshot-work-source-parts-','snapshot-combined-capture-parts-','snapshot-captures-source-parts-','snapshot-exports-source-parts-','snapshot-inputs-source-parts-',
                'snapshot-file-work-parts-','snapshot-primary-file-work-parts-','snapshot-'+self.run+'-primary-')
            if path.name.startswith(prefixes):need(reads is not None and path in reads)
        if self.previous is None:need(not self.store.path.with_name('ios-snapshot-primary-inputs.json').exists())

    def decode(self,value):
        exact(value,{'iosSnapshotCaptureOwnerVersion','runId','binding','fixtureUrl','payload'});rows=unpack(value['payload'])
        need(type(value['iosSnapshotCaptureOwnerVersion']) is int and value['iosSnapshotCaptureOwnerVersion']==(2 if self.combined else 1) and len(rows)==1
            and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','ticket','phaseOriginal','roots','baseline','slots','inputSlots','captureInput','artifact','result','settled','quiet','nativeTail','originalName','restored','restoration'})
        need(state['phase'] in ('new','preparing','prepared','capturing','copied','cleaning','file-cleaned') and type(state['slots']) is list
            and len(state['slots'])<=768 and type(state['inputSlots']) is list and len(state['inputSlots'])<=16 and type(state['quiet']) is list and len(state['quiet'])<=3
            and type(state['restored']) is bool)
        if state['ticket'] is not None:identifier(state['ticket']);self.phase_original(state['phaseOriginal'],state['ticket'])
        if state['roots'] is not None:self.root_original(state['roots'])
        labels=set();indices={};prior=self.state;self.state=state
        try:
          with original_reads(fresh=True) as reads:
            for slot in state['slots']:
                exact(slot,{'label','kind','index','sha256'});need(slot['kind'] in TYPES and type(slot['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',slot['label'])
                    and slot['label'] not in labels and integer(slot['index'],1,1024));labels.add(slot['label'])
                kind=slot['kind'];indices[kind]=indices.get(kind,0)+1;need(slot['index']==indices[kind])
                self.child_responsibility(slot,reads)
            if state['inputSlots'] and self.store.path.with_name('ios-snapshot-primary-inputs.json').exists():
                inputs=self.runtime.inputs(self,historical=True);need(len(inputs.state['events'])<=len(state['inputSlots']))
                for index,slot in enumerate(state['inputSlots'],1):
                    exact(slot,{'label','index','control','text'});need(slot['index']==index and slot['control'] in ('snapshot.name','snapshot.capture')
                        and slot['text'] in (None,'','parity-'+self.run[:16]+'-still-png'))
                    if index<=len(inputs.state['events']):
                        event=inputs.state['events'][index-1];need(event['controlId']==slot['control'] and event['command'].get('text')==slot['text'])
                        if event['phase']=='delivered':inputs.validate_original(index)
                    else:need(index==len(state['inputSlots']))
            elif state['inputSlots']:need(len(state['inputSlots'])==1 and state['inputSlots'][0]['index']==1)
            if state['result'] is not None:need(same(self.result(),state['result']))
            if state['restored']:self.restoration_original()
            if state['phase']=='file-cleaned':self.cleanup_original()
            self.inventory(reads)
        finally:self.state=prior
        return deepcopy(state)

    def child_responsibility(self,slot,reads):
        """Decode a declared child even before its parent digest was saved.

        This read grants no completed effect. The live child still owns its
        reserved/issued transition and must adopt its own exact saved proof.
        Incomplete or missing original bytes stay unresolved; none are written.
        """
        kind=slot['kind'];name=getattr(self.runtime.component_type(self,kind),'_name',kind)
        path=self.store.path.with_name('ios-snapshot-primary-'+name+'-'+format(slot['index'],'04d')+'.json')
        if PrivateFeatureState(path).read() is None:
            need(slot['sha256'] is None);return
        child=self.child(slot,True)
        if slot['sha256'] is not None:need(digest(child.previous)==slot['sha256'])
        state=child.state;need(state is not None)
        if kind=='remove':
            if state['phase']=='observed':child.proof()
            else:need(slot['sha256'] is None)
        elif kind=='artifact':
            if state['work'] is not None:
                if state['work']['phase']=='planned':need(not child.frames().path(state['work']).exists())
                else:child.originals()
            if state['phase'] in ('opened','copied'):
                child.read(partial=state['phase']=='opened');reads.add(child.path())
            else:need(slot['sha256'] is None)
        elif state['phase'] in ('saved','retained'):child.historical()
        else:
            need(slot['sha256'] is None)
            storage=state.get('storage')
            if storage is not None:
                frame=child.files().read(storage)
                if kind in ('manifest','chunk'):child._frame(frame,child.pid)
                else:owned_original(frame,child.pid,child._kind)
            # Raw parts may have been saved before the small final frame.
            # Reopen and validate the unchanged actual query response. Its
            # eventual acquisition qualification remains the live child's job.
            parent=state.get('rawParts')
            if parent is not None:
                child.parent(parent,state['query']);parts=child.parts();snapshots=parts.inspect(parent)
                count=max(1,(parent['bytes']+PART_BYTES-1)//PART_BYTES)
                if len(snapshots)==count and all(row is not None and row['complete'] for row in snapshots):
                    raw=parts.read(parent).decode('utf-8')
                    packet=decode(raw,limit=child._source.LIMIT);child._source.validate(packet,state['query'],child.pid)

    def root_original(self,value):
        exact(value,{'packet','clockJoin'});packet=value['packet'];roots_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-script-roots-observe'),
            int(self.binding['processIdentity']),packet['capturedEpochMs']);validate_join(value['clockJoin'],dict(roots=packet))
        need(value['clockJoin']['nativeBefore']['processId']==int(self.binding['processIdentity']));return packet['source']['defaultScriptsUrl']

    def phase_original(self,value,ticket):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']==dict(verb='capture',inputs=dict(mode='still',format='png')))

    def active(self):
        value=self.phase.read(self.state['phaseOriginal'])
        capture=value['ticket']==self.state['ticket'] and value['verb']=='capture' and value['inputs']==dict(mode='still',format='png')
        cleanup=self.state['phase']=='cleaning' and value['verb']=='cleanup' and value['inputs']=={}
        need((capture or cleanup) and value['status']['instance']==self.state['phaseOriginal']['instance'])
        return value

    def slot(self,label,kind):
        found=[slot for slot in self.state['slots'] if slot['label']==label]
        if found:need(found[0]['kind']==kind);return found[0]
        index=1+sum(slot['kind']==kind for slot in self.state['slots'])
        need(len(self.state['slots'])<768 and index<=(1024 if kind=='chunk' else 128))
        slot=dict(label=label,kind=kind,index=index,sha256=None);self.state['slots'].append(slot);self.save();return slot

    def child(self,slot,historical=False):return self.runtime.component(self,slot['kind'],slot['index'],historical=historical)

    def observed(self,label,kind,*,mode='still-png',manifest=None,basename=None,offset=None):
        slot=self.slot(label,kind);child=self.child(slot);known=slot['sha256'];tail=deepcopy(self.state['nativeTail'])
        if child.state is None:
            if kind=='chunk':child.reserve_original(manifest,basename,offset)
            elif kind=='manifest':child.reserve(mode)
            else:child.reserve()
        if child.state['phase']=='reserved':
            if kind in ('manifest','chunk'):child.send(self.epoch_ms())
            else:child.send()
        if child.state['phase']=='issued':
            if kind in ('manifest','chunk'):child.recover()
            else:child.retain()
        frame=child.historical()
        if kind not in ('manifest','chunk'):child.qualified()
        if known is not None:need(digest(child.previous)==known);return child
        span=frame['clockJoin' if 'clockJoin' in frame else 'acquisition']
        if tail is not None:follow_native(tail,span['nativeBefore'])
        slot['sha256']=digest(child.previous);self.state['nativeTail']=deepcopy(span['nativeAfter']);self.save()
        return child

    def input(self,label,control,*,text=None):
        slots=self.state['inputSlots'];found=[slot for slot in slots if slot['label']==label]
        inputs=self.runtime.inputs(self)
        if found:
            slot=found[0];need(slot['control']==control and slot['text']==text)
        else:
            need(len(slots)<16);slot=dict(label=label,index=len(inputs.state['events'])+1,control=control,text=text);slots.append(slot);self.save()
        index=slot['index']
        if len(inputs.state['events'])<index:
            self.active();value=controls.project(self.sources['native'].capture())
            inputs.reserve(control,value,operation='activate' if text is None else 'replace',text=text)
        need(index<=len(inputs.state['events']));event=inputs.state['events'][index-1]
        need(event['controlId']==control and event['command'].get('text')==text)
        if event['phase']=='reserved':self.active();inputs.send()
        elif event['phase']=='issued':
            original=self.observed(label+'-delivery','inputs').historical()['packet'];inputs.recover(original)
        inputs.validate_original(index);return index

    def prepare(self,ticket):
        self.bound();identifier(ticket)
        if self.state['ticket'] is None:
            status=self.phase.read();need(status['ticket']==ticket);self.phase_original(status['status'],ticket)
            self.state.update(phase='preparing',ticket=ticket,phaseOriginal=status['status']);self.save()
        else:need(self.state['ticket']==ticket)
        if self.state['roots'] is None:
            self.state['roots']=self.runtime.roots(self);self.root_original(self.state['roots'])
            self.state['nativeTail']=deepcopy(self.state['roots']['clockJoin']['nativeAfter']);self.save()
        current=controls.project(self.sources['native'].capture());rows=[row for row in current['controls'] if row['id']=='snapshot.capture'];need(current['open'] and len(rows)==1)
        row=rows[0];prefix='parity-'+self.run[:16]+'-still-png'
        need(row['snapshotMode']==0 and row['snapshotFormat']=='png' and row['snapshotSettingsLoaded'] and not row['snapshotCapturing']
            and not row['snapshotProcessing'] and not row['snapshotSystemBlocked'] and row['snapshotImageCount']==0)
        if self.state['originalName'] is None:
            need(row['snapshotNameSha256']==controls.EMPTY or row['snapshotNameOwned'] and row['snapshotName']==prefix)
            self.state['originalName']='' if row['snapshotNameSha256']==controls.EMPTY else row['snapshotName'];self.save()
        if row['snapshotName']!=prefix or not row['snapshotNameOwned']:
            self.input('name-focus','snapshot.name');self.input('name-set','snapshot.name',text=prefix)
        baseline=self.observed('empty-before','manifest');absent(baseline.historical(),int(self.binding['processIdentity']),self.run,'still-png')
        work=self.observed('work-before','work');native=self.observed('captures-before','captures')
        self.work_source().admit(work.historical()['packet'],self.root_original(self.state['roots']),quiet=True);snapshot_captures.drained(native.historical()['packet'])
        self.state.update(phase='prepared',baseline=dict(manifest=baseline.index,work=work.index,captures=native.index));self.save()

    def packets(self,label):
        return {kind:self.observed(label+'-'+kind,kind) for kind in ('work','captures','exports')}

    def drained(self,values):
        self.work_source().admit(values['work'].historical()['packet'],self.root_original(self.state['roots']),quiet=True)
        snapshot_captures.drained(values['captures'].historical()['packet']);snapshot_exports.drained(values['exports'].historical()['packet'])

    def settled(self):
        if self.state['settled'] is not None:return self.state['settled']
        start=1+sum(slot['kind']=='captures' and slot['label'].startswith('poll-') for slot in self.state['slots'])
        for attempt in range(start,33):
            values=self.packets('poll-'+str(attempt))
            try:self.drained(values)
            except NativeUIError:
                self.sleep(.1);continue
            self.state['settled']={kind:child.index for kind,child in values.items()};self.save();return self.state['settled']
        raise SnapshotCapturePending('Original Snapshot callbacks have not drained')

    def history(self,kind,index):
        slot=next(slot for slot in self.state['slots'] if slot['kind']==kind and slot['index']==index)
        need(slot['sha256'] is not None);child=self.child(slot,True);need(digest(child.previous)==slot['sha256']);return child

    def result(self):
        baseline=self.state['baseline'];settled=self.state['settled'];need(baseline is not None and settled is not None and self.state['artifact'] is not None)
        return snapshot_completion.decoded(self.runtime.inputs(self,historical=True),self.state['captureInput'],
            self.history('work',baseline['work']).historical()['packet'],self.history('work',settled['work']).historical()['packet'],
            self.history('captures',baseline['captures']).historical()['packet'],self.history('captures',settled['captures']).historical()['packet'],
            self.history('manifest',baseline['manifest']),self.history('artifact',self.state['artifact']),self.root_original(self.state['roots']),_combined=self.combined)

    @operation
    def capture(self,ticket):
        self.bound()
        if self.state['phase'] in ('new','preparing'):self.prepare(ticket)
        need(self.state['ticket']==ticket and self.state['phase'] in ('prepared','capturing','copied'))
        if self.state['phase']=='copied':need(same(self.result(),self.state['result']));return deepcopy(self.state['result'])
        self.state['phase']='capturing';self.save();index=self.input('capture','snapshot.capture')
        self.state['captureInput']=index;self.save();self.settled()
        first=self.observed('copy-before','manifest');rows=first.historical()['packet']['files'];need(len(rows)==1 and rows[0]['name'].endswith('.png'))
        chunks=[]
        for part,offset in enumerate(range(0,max(1,rows[0]['size']),snapshot_chunks.CHUNK_BYTES),1):
            chunks.append(self.observed('copy-chunk-'+str(part),'chunk',manifest=first,basename=rows[0]['name'],offset=offset))
        last=self.observed('copy-after','manifest');work=self.observed('copy-filework','filework')
        slot=self.slot('artifact','artifact');artifact=self.child(slot)
        if artifact.state is None:artifact.capture(first,last,chunks,work.historical()['packet'])
        elif artifact.state['phase']!='copied':artifact.recover()
        slot['sha256']=digest(artifact.previous);self.state['artifact']=artifact.index;self.save()
        self.state['result']=self.result();self.state['phase']='copied';self.save();return deepcopy(self.state['result'])

    def cleanup_original(self):
        need(len(self.state['quiet'])==3 and self.state['restored']);self.restoration_original();groups=[];samples=[]
        for row in self.state['quiet']:
            group=([self.history('manifest',row['manifest'])],self.history('filework',row['filework']),self.history('owned',row['owned']),
                [self.history('remove',slot['index']) for slot in self.state['slots'] if slot['kind']=='remove'])
            groups.append(group);samples.append(snapshot_file_absence.original_sample(*group))
            self.drained({kind:self.history(kind,row[kind]) for kind in ('work','captures','exports')})
        quiet=snapshot_file_absence.quiet(groups,samples)
        return dict(fileChannel=quiet,hostOriginalRetained=True,sceneFidelityRequired=True,destinationOutcomeRequired=True,independentWitnessRequired=True,pairedCleanupRequired=True)

    def restoration_original(self):
        value=self.state['restoration'];need(value is not None);exact(value,{'ui','clockJoin'})
        span=validate_join(value['clockJoin'],dict(ui=value['ui']));ui=ui_packet(value['ui'],int(self.binding['processIdentity']),span['nativeAfter']['capturedEpochMs'])
        projected=controls.project(ui);rows=[row for row in projected['controls'] if row['id']=='snapshot.capture'];need(len(rows)==1)
        row=rows[0];name=self.state['originalName']
        need(row['snapshotMode']==0 and row['snapshotFormat']=='png' and not row['snapshotCapturing'] and not row['snapshotProcessing']
            and not row['snapshotSystemBlocked'] and (row['snapshotNameSha256']==controls.EMPTY if name=='' else row['snapshotNameOwned'] and row['snapshotName']==name))
        return value

    @operation
    def restore_name_before_destination(self):
        """Restore actual controls while this original Capture phase is active.

        Later destination phases keep the PNG, and paired file cleanup can use
        this already owned UI original without issuing a late name edit.
        """
        need(self.combined and not self.historical and self.state['phase']=='copied' and self.state['result'] is not None)
        self.bound()
        if self.state['restored']:return deepcopy(self.restoration_original())
        self.active()
        if self.state['originalName']=='':
            # An already issued name edit may have reached the native UI. Its
            # original input journal must recover before testing the current
            # restored field, without another ordinary edit.
            known=any(row['label']=='journey-restore-name' for row in self.state['inputSlots'])
            if not known:
                view=controls.project(self.sources['native'].capture());row=next(row for row in view['controls'] if row['id']=='snapshot.name')
                need(row['snapshotNameOwned'] and row['snapshotName']=='parity-'+self.run[:16]+'-still-png')
            self.input('journey-restore-focus','snapshot.name');self.input('journey-restore-name','snapshot.name',text='')
        acquisition=NativeClockAcquisition(self.sources['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        acquisition.begin(self.epoch_ms());ui=self.sources['native'].capture()
        self.state['restoration']=dict(ui=ui,clockJoin=acquisition.finish(dict(ui=ui),[('ui','sampleEpochMs')]))
        self.restoration_original();self.state['nativeTail']=deepcopy(self.state['restoration']['clockJoin']['nativeAfter'])
        self.state['restored']=True;self.save();return deepcopy(self.state['restoration'])

    @operation
    def cleanup(self):
        self.bound();need(self.state['phase'] in ('capturing','copied','cleaning','file-cleaned'))
        if self.state['phase']=='file-cleaned':return self.cleanup_original()
        # Unknown capture/name inputs are resolved only through actual original
        # reception. A cleanup call cannot issue another product capture.
        inputs=self.runtime.inputs(self)
        if inputs.state['events'] and inputs.state['events'][-1]['phase']!='delivered':
            event=inputs.state['events'][-1]
            if event['phase']=='reserved':raise SnapshotCapturePending('Original Snapshot input remains reserved')
            original=self.observed('cleanup-delivery','inputs').historical()['packet'];inputs.recover(original)
        self.state['phase']='cleaning';self.save()
        attempt=1+sum(slot['kind']=='work' and slot['label'].startswith('cleanup-before-') for slot in self.state['slots'])
        self.drained(self.packets('cleanup-before-'+str(attempt)))
        self.observed('cleanup-list','manifest');owned=self.observed('cleanup-owned','owned')
        source=owned.historical()['packet']['source'];prefix='parity-'+self.run[:16]+'-still-png'
        need(source['complete'] and len(source['prefixes'])==1 and source['prefixes'][0]['prefix']==prefix and source['prefixes'][0]['initiallyEmpty']
            and len(source['files'])<=1 and all(file['prefix']==prefix for file in source['files']))
        for file in source['files']:
            if self.state['result'] is not None:need(file['file']['name']==self.state['result']['capture']['file']['name'])
            slot=self.slot('remove-'+file['id'],'remove');remove=self.child(slot)
            if remove.state is None:remove.reserve(owned,file['id'])
            if remove.state['phase']=='reserved':remove.send()
            if remove.state['phase']=='issued':
                remove.acknowledge();observed=self.observed('removed-'+file['id']+'-'+str(len(remove.state['observations'])+1),'owned');remove.observe(observed)
            remove.proof();slot['sha256']=digest(remove.previous);self.save()
        if not self.state['restored']:
            if self.state['originalName']=='':
                current=controls.project(self.sources['native'].capture());rows=[row for row in current['controls'] if row['id']=='snapshot.name']
                need(len(rows)==1 and rows[0]['snapshotNameOwned'] and rows[0]['snapshotName']==prefix)
                self.input('restore-focus','snapshot.name');self.input('restore-name','snapshot.name',text='')
            acquisition=NativeClockAcquisition(self.sources['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            acquisition.begin(self.epoch_ms());ui=self.sources['native'].capture()
            self.state['restoration']=dict(ui=ui,clockJoin=acquisition.finish(dict(ui=ui),[('ui','sampleEpochMs')]))
            self.restoration_original();self.state['nativeTail']=deepcopy(self.state['restoration']['clockJoin']['nativeAfter'])
            self.state['restored']=True;self.save()
        for number in range(len(self.state['quiet'])+1,4):
            if number>1:self.sleep(1.6)
            base='quiet-'+str(number)+'-'
            attempt=1+sum(slot['kind']=='manifest' and slot['label'].startswith(base) for slot in self.state['slots'])
            label=base+str(attempt);manifest=self.observed(label+'-manifest','manifest');work=self.observed(label+'-filework','filework');owned=self.observed(label+'-owned','owned')
            removals=[self.history('remove',slot['index']) for slot in self.state['slots'] if slot['kind']=='remove']
            snapshot_file_absence.sample([manifest],work,owned,removals,guard=self.guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            sources=self.packets(label);self.drained(sources)
            self.state['quiet'].append(dict(manifest=manifest.index,filework=work.index,owned=owned.index,**{kind:source.index for kind,source in sources.items()}));self.save()
        result=self.cleanup_original();self.state['phase']='file-cleaned';self.save();return result
