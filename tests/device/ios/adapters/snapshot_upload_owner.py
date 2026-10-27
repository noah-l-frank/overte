"""One normal captured-file Upload/Cancel and its actual original resources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_input_owner import SnapshotInputPending
from ios.adapters.snapshot_upload_packets import SnapshotUploadInputs,packet_types
from ios.adapters import snapshot_uploads as uploads,snapshot_export_controls as controls,snapshot_inputs,snapshot_work,snapshot_captures,snapshot_exports


class SnapshotUploadPending(SnapshotInputPending):pass


class IOSSnapshotUploadOwner:
    def __init__(self,runtime,selector,run,lock,sources,capture,phase,*,epoch_ms,monotonic,sleep,combined=False,frontend_http=False,frontend_caller=False):
        need(type(combined) is type(frontend_http) is type(frontend_caller) is bool and (not frontend_http or combined) and (not frontend_caller or frontend_http));self.combined,self.frontend_http,self.frontend_caller=combined,frontend_http,frontend_caller
        need(type(capture) is IOSSnapshotCaptureOwner and capture.combined==combined and capture.historical and capture.run==run and same(capture.binding,sources['binding'])
            and phase.run==run and phase.area=='snapshots' and phase.fixture_url==capture.phase.fixture_url)
        self.runtime,self.selector,self.run,self.lock,self.sources,self.capture,self.phase=runtime,selector,run,lock,sources,capture,phase
        self.binding,self.fixture_url=deepcopy(capture.binding),phase.fixture_url;self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.historical=False;self.root=capture.store.path.parent;self.setup()
        restore(sources['clock_source'],self.state['nativeTail'])
    @classmethod
    def history(cls,store,lock,binding,run,fixture_url,*,combined=False,frontend_http=False,frontend_caller=False):
        need(type(combined) is type(frontend_http) is type(frontend_caller) is bool and (not frontend_http or combined) and (not frontend_caller or frontend_http))
        need(store.path==lock.path.with_name('snapshot-upload-owner.json'))
        owner=object.__new__(cls);owner.store,owner.lock,owner.binding,owner.run,owner.fixture_url=store,lock,deepcopy(binding),run,fixture_url;owner.combined,owner.frontend_http,owner.frontend_caller=combined,frontend_http,frontend_caller
        owner.historical=True;owner.sources=owner.runtime=owner.selector=owner.phase=None;owner.root=store.path.parent
        owner.capture=IOSSnapshotCaptureOwner.archive(PrivateFeatureState(owner.root/'ios-snapshot-primary-capture-owner.json'),lock,binding,run,fixture_url,combined=combined)
        owner.setup();need(owner.previous is not None);return owner
    def version(self):return 4 if self.frontend_caller else 3 if self.frontend_http else 2 if self.combined else 1
    def packets(self):return packet_types(self.frontend_http,self.frontend_caller)
    def capture_tail(self):
        if not self.frontend_caller:return self.capture.state['nativeTail']
        # Later JourneyFiles cleanup appends actual Capture originals. Those
        # cannot replace the immutable original boundary where this upload
        # acquired its already copied PNG.
        rows=[row for row in self.capture.state['slots'] if row['kind']=='filework' and row['label']=='copy-filework']
        need(len(rows)==1);child=self.capture.history('filework',rows[0]['index']);frame=child.historical();child.qualified()
        tail=frame['acquisition']['nativeAfter']
        if not same(tail,self.capture.state['nativeTail']):follow_native(tail,self.capture.state['nativeTail'])
        return deepcopy(tail)
    def setup(self):
        self.lock.assert_held();self.capture_result=self.capture.result();artifact=self.capture.history('artifact',self.capture.state['artifact']);fact,raw=artifact.originals()
        self.file=deepcopy(fact['file']);self.pins=dict(captureResultSha256=digest(self.capture_result),artifactJournalSha256=digest(artifact.previous))
        self.store=PrivateFeatureState(self.root/'snapshot-upload-owner.json');self.previous=self.store.read()
        self.state=dict(ticket=None,verb=None,phaseOriginal=None,slots=[],input=None,cancel=None,baseline=None,job=None,decision=None,quiet=[],result=None,
            inputSources={},nativeTail=deepcopy(self.capture_tail()))
        if self.frontend_http:self.state.update(httpBefore=None,httpAfter=None)
        if self.frontend_caller:self.state.update(causalBefore=None,causalAfter=None)
        if self.previous is not None:self.state=self.load(self.previous)
        elif not self.historical:
            prefixes=('snapshot-upload-','upload-native-','upload-input-proof-')
            if self.combined:prefixes+=('upload-combined-work-','snapshot-combined-upload-parts-')
            if self.frontend_http:prefixes+=('upload-combined-http-','snapshot-http-upload-parts-')
            if self.frontend_caller:prefixes+=('upload-causal-dispatch-','snapshot-causal-upload-parts-')
            need(not any(path.name.startswith(prefixes) for path in self.root.iterdir()))
            self.save()
    def envelope(self):return dict(snapshotUploadOwnerVersion=self.version(),binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,pins=self.pins,payload=pack([self.state]))
    def guard(self):
        self.lock.assert_held();self.capture.bound();need(same(self.store.read(),self.previous))
        if not self.historical:need(self.sources['check']() is not False)
        return True
    def save(self):
        need(not self.historical);self.guard();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def load(self,value):
        exact(value,{'snapshotUploadOwnerVersion','binding','runId','fixtureUrl','pins','payload'});rows=unpack(value['payload']);need(len(rows)==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(type(value['snapshotUploadOwnerVersion']) is int and same(value,self.envelope()) and type(state['slots']) is list and len(state['slots'])<=512
                and type(state['quiet']) is list and len(state['quiet'])<=3)
            labels=set();counts={kind:0 for kind in self.packets()};tail=deepcopy(self.capture_tail());causal_previous=None
            for position,slot in enumerate(state['slots']):
                exact(slot,{'kind','label','index','sha256'});need(slot['kind'] in self.packets() and type(slot['label']) is str and slot['label'] not in labels)
                labels.add(slot['label']);counts[slot['kind']]+=1;need(type(slot['index']) is int and slot['index']==counts[slot['kind']])
                if slot['sha256'] is not None:
                    child=self.child(slot,True);need(digest(child.previous)==slot['sha256']);frame=child.historical()
                    follow_native(tail,frame['acquisition']['nativeBefore']);tail=frame['acquisition']['nativeAfter']
                    if self.frontend_caller and slot['kind']=='causal':
                        child._source.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=causal_previous)
                        causal_previous=frame['packet']
                else:need(position==len(state['slots'])-1)
            need(same(tail,state['nativeTail']))
            if state['ticket'] is None:
                need(state['verb'] is state['phaseOriginal'] is None and not state['slots'] and all(state[key] is None for key in ('input','cancel','baseline','job','decision','result')) and not state['quiet'] and not state['inputSources'])
            else:self.phase_original(state['phaseOriginal'],state['ticket'],state['verb'])
            if state['input'] is not None:need(state['baseline'] is not None)
            if state['cancel'] is not None:need(state['job'] is not None)
            if state['quiet']:need(state['decision'] is not None)
            for key in ('input','cancel'):
                if state[key] is not None:
                    reader=self.inputs(True);need(integer(state[key],1,len(reader.state['events'])))
                    need(state[key]==(1 if key=='input' else 2))
                    control=reader.state['events'][state[key]-1]['controlId'];need(control=='snapshot.upload-cancel' if key=='cancel' else control.startswith('snapshot.upload.'))
            need(type(state['inputSources']) is dict and set(state['inputSources'])<=set(('input','cancel')))
            for key in state['inputSources']:self.delivery_source(key)
            if state['baseline'] is not None:self.baseline(self.packet('uploads',state['baseline']))
            if state['job'] is not None:need(state['input'] is not None)
            if state['decision'] is not None:need(uploads.decision(self.packet('uploads',state['decision']),state['job']))
            for group in state['quiet']:self.quiet_group(group)
            if self.frontend_http:
                if state['httpBefore'] is not None:need(state['ticket'] is not None);self.http_original(state['httpBefore'])
                if state['httpAfter'] is not None:need(state['input'] is not None and state['httpBefore'] is not None);self.http_original(state['httpAfter'])
                if state['job'] is not None:need(state['httpAfter'] is not None)
            if self.frontend_caller:
                if state['causalBefore'] is not None:need(state['ticket'] is not None);self.causal_original(state['causalBefore'])
                if state['causalAfter'] is not None:need(state['input'] is not None and state['causalBefore'] is not None);self.causal_original(state['causalAfter'])
                if state['job'] is not None:need(state['causalAfter'] is not None);self.causal_call(self.packet('causal',state['causalAfter']))
            if state['result'] is not None:need(same(state['result'],self.proof()))
        finally:self.state=prior
        return deepcopy(state)
    def phase_original(self,value,ticket,verb):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(verb in ('upload','upload-fail') and value['active'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']==dict(verb=verb,inputs={}))
    def active(self):
        need(not self.historical);value=self.phase.read(self.state['phaseOriginal'])['status'];self.phase_original(value,self.state['ticket'],self.state['verb'])
        need(same(value['activations'],self.state['phaseOriginal']['activations']));return value
    def slot(self,label,kind):
        old=[row for row in self.state['slots'] if row['label']==label]
        if old:need(len(old)==1 and old[0]['kind']==kind);return old[0]
        need(not self.historical and kind in self.packets());row=dict(kind=kind,label=label,index=1+sum(item['kind']==kind for item in self.state['slots']),sha256=None)
        self.state['slots'].append(row);self.save();return row
    def child(self,slot,history=False):
        cls=self.packets()[slot['kind']]
        if self.combined and slot['kind']=='work':
            from ios.adapters.snapshot_combined_packets import CombinedUploadWorkPacket
            cls=CombinedUploadWorkPacket
        store=PrivateFeatureState(self.root/('snapshot-upload-primary-'+cls._name+'-'+format(slot['index'],'04d')+'.json'))
        args=(store,self.lock,self.binding,self.run,'primary',slot['index'])
        if history:return cls.history(*args)
        return cls(*args,self.sources['observer'],self.sources['clock_source'],self.guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
    def packet(self,kind,index):
        slot=next(row for row in self.state['slots'] if row['kind']==kind and row['index']==index);need(slot['sha256'] is not None)
        child=self.child(slot,True);need(digest(child.previous)==slot['sha256']);return child.historical()['packet']
    def observe(self,label,kind):
        self.active();slot=self.slot(label,kind);child=self.child(slot)
        if slot['sha256'] is not None:need(digest(child.previous)==slot['sha256']);return slot['index']
        if child.state is None:child.reserve()
        if child.state['phase']=='reserved':child.send()
        if child.state['phase']=='issued':child.retain()
        frame=child.historical();tail=frame['acquisition']['nativeAfter'];follow_native(self.state['nativeTail'],frame['acquisition']['nativeBefore'])
        earlier=[row for row in self.state['slots'] if row['kind']==kind and row['index']<slot['index'] and row['sha256'] is not None]
        if earlier:
            module=child._source;module.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=self.packet(kind,earlier[-1]['index']))
        self.state['nativeTail']=deepcopy(tail);slot['sha256']=digest(child.previous);self.save();return slot['index']
    def http_original(self,index):
        from ios.adapters import snapshot_combined_preflight_http as http
        need(self.frontend_http);value=self.packet('http',index)
        root=self.capture.root_original(self.capture.state['roots']);http.admit(value,root)
        settled=self.capture.history('work',self.capture.state['settled']['work']).historical()['packet']
        worker=self.capture.work_source().admit(settled,root,quiet=True)
        for state in http.events(value).values():
            created=state['created']['details']
            need(same(created['engine'],worker['manager']) and same(created['submitted'],worker['code'])
                and same(created['codeSources'],worker['codeSources']))
        return value
    def causal_original(self,index):
        from ios.adapters.snapshot_frontend_branch import original
        need(self.frontend_caller);return original(self,self.packet('causal',index))
    def causal_call(self,value):
        from ios.adapters.snapshot_frontend_branch import call
        need(self.frontend_caller);return call(self,value)
    def causal_label(self,prefix):
        rows=[row for row in self.state['slots'] if row['kind']=='causal' and row['label'].startswith(prefix+'-')]
        if rows and rows[-1]['sha256'] is None:return rows[-1]['label']
        return prefix+'-'+str(len(rows)+1)
    def causal_quiet_span(self):
        need(self.frontend_caller and len(self.state['quiet'])==3)
        frames=[]
        for group in self.state['quiet']:
            slot=next(row for row in self.state['slots'] if row['kind']=='causal' and row['index']==group['causal'])
            frames.append(self.child(slot,True).historical())
        for before,after in zip(frames,frames[1:]):
            need(after['packet']['sequence']>before['packet']['sequence']
                and after['acquisition']['hostBeforeMonotonic']>=before['acquisition']['hostAfterMonotonic'])
        first,last=frames[0],frames[-1]
        need(all(last['packet']['clockBefore'][key]-first['packet']['clockAfter'][key]>=3000 for key in ('epochMs','monotonicMs'))
            and last['acquisition']['hostBeforeEpochMs']-first['acquisition']['hostAfterEpochMs']>=3000
            and (last['acquisition']['hostBeforeMonotonic']-first['acquisition']['hostAfterMonotonic'])*1000>=3000)
    def inputs(self,history=False):
        args=(PrivateFeatureState(self.root/SnapshotUploadInputs.store_name('primary')),self.lock,self.binding,self.run,'primary')
        return SnapshotUploadInputs.history(*args) if history else SnapshotUploadInputs(*args,self.sources['native'],self.guard)
    def deliver(self,key,control):
        reader=self.inputs()
        if self.state[key] is None:
            claimed=[self.state[item] for item in ('input','cancel') if self.state[item] is not None]
            if len(reader.state['events'])==len(claimed):
                view=self.view();rows=[row for row in view['controls'] if row['id']==control]
                need(len(rows)==1 and rows[0]['snapshotFileOwned'] and rows[0]['snapshotFileName']==self.file['name'])
                reader.reserve(control,view)
            else:
                # An original child reservation may precede the parent CAS.
                # Adopt only its exact next owned event; issued inputs recover
                # from their native originals and never cross transport again.
                need(len(reader.state['events'])==len(claimed)+1)
                event=reader.state['events'][-1];need(event['controlId']==control)
                rows=[row for row in event['reference']['controls'] if row['id']==control]
                need(len(rows)==1 and rows[0]['snapshotFileOwned'] and rows[0]['snapshotFileName']==self.file['name'])
            self.state[key]=len(reader.state['events']);self.save()
        event=reader.state['events'][self.state[key]-1]
        if event['phase']=='reserved':self.active();reader.send()
        if event['phase']=='issued':
            index=self.observe(key+'-delivery-'+str(self.state[key]),'inputs');slot=next(row for row in self.state['slots'] if row['kind']=='inputs' and row['index']==index)
            reader.recover(self.packet('inputs',index))
        if key not in self.state['inputSources']:
            self.state['inputSources'][key]=self.observe(key+'-original-'+str(self.state[key]),'inputs');self.delivery_source(key);self.save()
        need(reader.state['events'][self.state[key]-1]['phase']=='delivered');return reader.validate_original(self.state[key])
    def view(self):
        value=controls.project(self.sources['native'].capture());captured=self.capture.runtime.inputs(self.capture,historical=True)
        initial=captured.state['events'][self.capture.state['captureInput']-1]['reference']['scope'];current=value['scope']
        need(current['processId']==initial['processId'] and current['instance']==initial['instance']
            and all(current[key]>=initial[key] for key in ('sampleEpochMs','elapsedMs','sequence')));return value
    def delivery_source(self,key):
        need(self.state[key] is not None and key in self.state['inputSources']);reader=self.inputs(True);event=reader.state['events'][self.state[key]-1]
        value=self.packet('inputs',self.state['inputSources'][key]);snapshot_inputs.delivered(value,event['command'],event['controlId'],reader.root(event))
        found=[row for row in value['source']['events'] if row['kind']=='received' and row['details']['command']['commandId']==event['command']['commandId']]
        need(len(found)==1);return found[0]
    def baseline(self,value):
        uploads.original(value);need(value['source']['complete'] and value['source'].get('iosSnapshotUploadsSourceVersion')==2
            and value['source']['activity']==dict(slots=0,alive=0) and all(not row['scopeActive'] for row in value['source']['uploads'])
            and all(not row['alive'] for row in value['source']['resources']) and all(not row['stackAlive'] for row in value['source']['callbacks']))
        for row in value['source']['uploads']:uploads.local_objects_gone(value,row['instance'])
    def associate(self,value):
        uploads.original(value);need(value['source']['complete'] and value['source'].get('iosSnapshotUploadsSourceVersion')==2)
        initial=self.packet('uploads',self.state['baseline']);old={row['instance'] for row in initial['source']['uploads']}
        rows=[row for row in value['source']['uploads'] if row['instance'] not in old]
        need(len(rows)==1);row=rows[0];need(row['privateName'] and row['fileName']==self.file['name'])
        need(row['bornEpochMs']>=self.delivery_source('input')['clock']['epochMs'] and row['bornEpochMs']>=initial['clockAfter']['epochMs'])
        files=[item for item in value['source']['resources'] if item['upload']==row['instance'] and item['kind']=='file']
        need(len(files)==1 and files[0]['opened'] and uploads.file_revision(files[0]['firstFile'])==self.file['revision'] and files[0]['firstFile']['bytes']==self.file['size'])
        if self.state['job'] is not None:need(self.state['job']==row['instance'])
        return row['instance']
    def quiet_group(self,group):
        exact(group,{'uploads','work','captures','exports'}|({'causal'} if self.frontend_caller else set()));value=self.packet('uploads',group['uploads']);need(self.associate(value)==self.state['job'])
        if self.frontend_caller:
            from ios.adapters import snapshot_causal_dispatch as causal
            packet=self.causal_original(group['causal']);call=self.causal_call(packet);need(causal.drained(packet,[call['instance']]))
        uploads.local_objects_gone(value,self.state['job']);work=self.packet('work',group['work']);source=self.capture.work_source()
        root=self.capture.root_original(self.capture.state['roots']);actual=source.admit(work,root,quiet=True)
        if self.combined:
            before=self.capture.history('work',self.capture.state['settled']['work']).historical()['packet']
            source.validate(work,dict(schemaVersion=1,action=source.ACTION,commandId=work['requestId'],runId=self.run),int(self.binding['processIdentity']),previous=before)
            need(same(actual['manager'],source.admit(before,root,quiet=True)['manager']))
        decision=uploads.decision(self.packet('uploads',self.state['decision']),self.state['job']);begin=decision['nativeOriginal']['capturedEpochMs']
        returns=[]
        for event in actual['events']:
            if event['closure']!='onNativeUploadStatus' or event['event']!='entry' or event['capturedEpochMs']<begin or event['state']['pendingUploads']!=1:continue
            calls=[row for row in actual['events'] if row['call']==event['call']]
            if [row['event'] for row in calls]==['entry','returned','finally'] and all(row['state']['pendingUploads']==0 for row in calls[1:]):returns.append(calls)
        need(len(returns)==1)
        snapshot_captures.drained(self.packet('captures',group['captures']));snapshot_exports.drained(self.packet('exports',group['exports']));return value
    def proof(self):
        need(self.state['decision'] is not None and len(self.state['quiet'])==3)
        need(digest(self.capture.result())==self.pins['captureResultSha256'])
        decision=uploads.decision(self.packet('uploads',self.state['decision']),self.state['job']);frames=[self.quiet_group(row) for row in self.state['quiet']]
        first,last=frames[0],frames[-1]
        need(all(last['clockBefore'][key]-first['clockAfter'][key]>=3000 for key in ('epochMs','monotonicMs')))
        slots=[next(row for row in self.state['slots'] if row['kind']=='uploads' and row['index']==group['uploads']) for group in (self.state['quiet'][0],self.state['quiet'][-1])]
        spans=[self.child(slot,True).historical()['acquisition'] for slot in slots]
        need(spans[-1]['hostBeforeEpochMs']-spans[0]['hostAfterEpochMs']>=3000 and (spans[-1]['hostBeforeMonotonic']-spans[0]['hostAfterMonotonic'])*1000>=3000)
        self.inputs(True).validate_original(self.state['input'])
        if self.state['cancel'] is not None:self.inputs(True).validate_original(self.state['cancel'])
        result=dict(snapshotUploadResultVersion=self.version(),runId=self.run,binding=self.binding,pins=self.pins,upload=self.state['job'],nativeDecision=decision,
            knownObjectsAndBodyFDQuiet=True,hostOriginalRetained=True,authenticatedBackendOriginalRequired=True,nativeSignalDeliveryRequired=True,
            nativeScriptSignalReturned=True,originalReviewUIRequired=True,transportProcessProofRequired=True,wholeFeatureRequired=True)
        if self.combined:result.update(workProfile='combined',frontendHTTPConsumerRequired=True)
        if self.frontend_http:
            self.http_original(self.state['httpBefore']);self.http_original(self.state['httpAfter'])
            result.update(frontendHTTPOriginalsRetained=True,frontendBranchAcceptanceRequired=True)
        if self.frontend_caller:
            self.causal_quiet_span()
            result.update(frontendCausalOriginalsRetained=True,diagnosticQueueScopesDrained=True)
        return result
    @operation
    def start(self,ticket,verb='upload'):
        need(not self.historical);self.guard()
        if self.state['ticket'] is None:
            status=self.phase.read()['status'];self.phase_original(status,ticket,verb);self.state.update(ticket=ticket,verb=verb,phaseOriginal=status);self.save()
        need(self.state['ticket']==ticket and self.state['verb']==verb);self.active()
        if self.state['job'] is not None:
            need(self.state['input'] is not None);self.delivery_source('input')
            return dict(nativeUploadObserved=True,upload=self.state['job'],independentBackendOriginalRequired=True,wholeFeatureRequired=True)
        if self.state['baseline'] is None:
            index=self.observe('baseline','uploads');self.baseline(self.packet('uploads',index));self.state['baseline']=index;self.save()
        if self.frontend_http and self.state['httpBefore'] is None:
            self.state['httpBefore']=self.observe('http-before','http');self.http_original(self.state['httpBefore']);self.save()
        if self.frontend_caller and self.state['causalBefore'] is None:
            from ios.adapters import snapshot_causal_dispatch as causal
            label=self.causal_label('causal-before')
            before=self.observe(label,'causal');value=self.causal_original(before)
            if value['source']['calls']:need(causal.drained(value,[row['instance'] for row in value['source']['calls']]))
            self.state['causalBefore']=before;self.save()
        if self.state['input'] is None:
            view=self.view();rows=[row for row in view['controls'] if row['id'].startswith('snapshot.upload.') and row['snapshotFileOwned'] and row['snapshotFileName']==self.file['name'] and row['inputReady']]
            need(len(rows)==1);control=rows[0]['id']
        else:control=self.inputs(True).state['events'][self.state['input']-1]['controlId']
        self.deliver('input',control)
        if self.frontend_http and self.state['httpAfter'] is None:
            self.state['httpAfter']=self.observe('http-after','http');self.http_original(self.state['httpAfter']);self.save()
        index=self.observe('start-'+str(1+sum(row['label'].startswith('start-') for row in self.state['slots'])),'uploads')
        job=self.associate(self.packet('uploads',index))
        if self.frontend_caller:
            # The existing upload observer can publish its real ID before the
            # causal constructor association/queue has returned on its thread.
            # Retain that pending source fact, then let a later start acquire a
            # new original after recovering the already delivered input.
            label=self.causal_label('causal-after')
            self.state['causalAfter']=self.observe(label,'causal');self.causal_original(self.state['causalAfter']);self.save()
        self.state['job']=job
        if self.frontend_caller:self.causal_call(self.packet('causal',self.state['causalAfter']))
        self.save();return dict(nativeUploadObserved=True,upload=self.state['job'],independentBackendOriginalRequired=True,wholeFeatureRequired=True)
    @operation
    def cancel(self):
        need(not self.historical and self.state['job'] is not None and self.state['result'] is None);self.guard();self.active()
        if self.state['cancel'] is None and len(self.inputs().state['events'])<2:
            attempt=1+sum(row['label'].startswith('cancel-ready-') for row in self.state['slots'])
            index=self.observe('cancel-ready-'+str(attempt),'uploads');value=self.packet('uploads',index);need(self.associate(value)==self.state['job'])
            jobs=[row for row in value['source']['uploads'] if row['instance']==self.state['job']]
            need(len(jobs)==1 and jobs[0]['scopeActive'])
        self.deliver('cancel','snapshot.upload-cancel')
        return self.finish()
    @operation
    def finish(self):
        need(not self.historical and self.state['job'] is not None);self.guard()
        if self.state['result'] is not None:return self.proof()
        if self.state['decision'] is None:
            index=self.observe('terminal-'+str(1+sum(row['label'].startswith('terminal-') for row in self.state['slots'])),'uploads')
            uploads.decision(self.packet('uploads',index),self.state['job']);self.state['decision']=index;self.save()
        while len(self.state['quiet'])<3:
            if self.state['quiet']:self.sleep(1.6)
            attempt=1+sum(row['kind']=='uploads' and row['label'].startswith('quiet-') for row in self.state['slots'])
            label='quiet-'+str(attempt);group={kind:self.observe(label+'-'+kind,kind) for kind in (('uploads','work','captures','exports','causal') if self.frontend_caller else ('uploads','work','captures','exports'))}
            self.quiet_group(group);self.state['quiet'].append(group);self.save()
        result=self.proof();self.state['result']=deepcopy(result);self.save();return result
