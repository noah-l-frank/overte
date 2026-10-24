"""Durable whole Web retirement from original native, file and GPU ownership.

Ordinary Stop/Home belongs to the existing Scope. This owner retains actual
before/after acquisitions, weak deaths, positive Qt dispatch endings and fenced
former-surface pixels. A missing or interrupted original remains responsibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy,copy
import time
import uuid
import re
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier,result
from ios.adapters.world_web_api_clock import check
from ios.adapters.world_web_file_receipts import WorldWebFileReceipts
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.world_web_retired import native_retired,quiet,quiet_summary,activity
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_restoration import restored
from ios.adapters.world_web_history import derive
from ios.adapters.emote_native_prefix import follow
from ios.adapters import pointer_state,world_web_keys
from ios.adapters.world_web_scene import scene

VERSION=2
READS=(1,2)


class WorldWebRetirement:
    def __init__(self,store,lease,baseline_image,files,sample_factory,inputs,origins,*,sample_requests=(),sleep=time.sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(lease,WorldWebLease)
            and isinstance(baseline_image,WorldWebSample) and baseline_image.source is lease.source
            and isinstance(files,WorldWebFileReceipts) and files.lock is lease.source.lock
            and same(files.binding,lease.binding) and files.run==lease.run and files.role=='primary'
            and callable(sample_factory) and callable(sleep))
        from ios.adapters.world_web_input import WorldWebInput
        need(isinstance(inputs,WorldWebInput) and inputs.source is lease.source)
        self.store,self.lease,self.baseline_image,self.files,self.sample_factory,self.inputs,self.sleep=store,lease,baseline_image,files,sample_factory,inputs,sleep
        self.source,self.scope,self.origins=lease.source,lease.scope,deepcopy(origins)
        self.binding,self.run,self.role,self.lock=deepcopy(lease.binding),lease.run,'primary',lease.source.lock
        self.lock.assert_held();need(store.path==self.source.store.path.with_name('ios-world-web-primary-retirement.json'))
        self.previous=store.read();self.version=VERSION if self.previous is None else self.previous.get('iosWorldWebRetirementVersion')
        need(type(self.version) is int and self.version in READS)
        self.state=dict(phase='new',ticket=None,baseline=None,barrier=None,images=list(dict.fromkeys([baseline_image.request,*sample_requests])),restoration=None,records=[],pending=None,interrupted=[],quiet=[])
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):return dict(iosWorldWebRetirementVersion=self.version,binding=self.binding,runId=self.run,role=self.role,payload=pack([state]))
    def record_store(self,index):
        need(integer(index,1,96));return PrivateFeatureState(self.store.path.with_name('ios-world-web-primary-retirement-'+str(index)+'.json'))
    def frame(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,96));raw=self.record_store(reference['index']).read()
        need(raw is not None and digest(raw)==reference['sha256']);exact(raw,{'iosWorldWebRetirementRecordVersion','binding','runId','payload'})
        need(type(raw['iosWorldWebRetirementRecordVersion']) is int and raw['iosWorldWebRetirementRecordVersion']==self.version and same(raw['binding'],self.binding) and raw['runId']==self.run)
        rows=unpack(raw['payload']);need(len(rows)==1 and rows[0]['index']==reference['index']);return deepcopy(rows[0])
    def bound(self):
        check();self.lock.assert_held();self.source.bound();need(same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);check()

    def sample(self,request):
        owner=self.baseline_image if request==self.baseline_image.request else self.sample_factory(request)
        need(isinstance(owner,WorldWebSample) and owner.request==request and owner.source is self.source and owner.lock is self.lock
            and same(owner.binding,self.binding) and owner.run==self.run);return owner

    def gpu_store(self,frame):
        def intent(kind,value):
            need(kind=='original' and frame is self.state['pending'] and value['index']==len(frame['gpu'])+1)
            key=str(value['index']);old=frame['gpuOriginals'].get(key)
            need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[field],old[field]) for field in value if field not in ('phase','file')))
            frame['gpuOriginals'][key]=deepcopy(value);self.save()
        def guard():
            check();self.lock.assert_held();need(same(self.store.read(),self.previous)
                and self.source.binding==self.binding and self.source.run==self.run)
            if self.source.historical:
                need(self.source.readers is None);self.source.guard_originals()
            else:self.source.bound()
        return OriginalFrameStore(self.scope.root,self.binding,self.run,'primary',guard,intent,
            namespace='wwrg-'+frame['gpuAcquisition'][:26],schema_prefix='worldWebRetirementGPU',monotonic=self.source.monotonic)

    def pending_gpu(self,frame,*,readable=False):
        """Keep interrupted evidence writes owned; never replay an unknown birth."""
        need(type(frame['gpuAcquisition']) is str and re.fullmatch('[0-9a-f]{32}',frame['gpuAcquisition'])
            and type(frame['gpu']) is list and len(frame['gpu'])<=64
            and type(frame['gpuOriginals']) is dict and len(frame['gpuOriginals'])<=64)
        store=self.gpu_store(frame)
        need(set(frame['gpuOriginals']) in ({str(i) for i in range(1,len(frame['gpu'])+1)},
            {str(i) for i in range(1,len(frame['gpu'])+2)}))
        for index in range(1,len(frame['gpuOriginals'])+1):
            original=store.original(frame['gpuOriginals'][str(index)]);need(original['index']==index)
            if index<=len(frame['gpu']):
                row=frame['gpu'][index-1];exact(row,{'requestId','original'})
                need(same(store.expand(row['original']),original))
            if original['phase']!='planned':
                body=store.read(original);exact(body,{'requestId','owner','clocksBefore','clocksAfter'})
                if index<=len(frame['gpu']):need(body['requestId']==frame['gpu'][index-1]['requestId'])
            else:need(not readable)

    def gpu_rows(self,frame):
        if self.version==1:return deepcopy(frame['gpu'])
        self.pending_gpu(frame,readable=True);store=self.gpu_store(frame)
        result=[]
        for index,row in enumerate(frame['gpu'],1):
            exact(row,{'requestId','original'});reference=row['original'];need(reference['index']==index)
            original=store.expand(reference);need(same(frame['gpuOriginals'].get(str(index)),original))
            body=store.read(original);exact(body,{'requestId','owner','clocksBefore','clocksAfter'})
            need(body['requestId']==row['requestId']);result.append(body)
        need(set(frame['gpuOriginals'])=={str(index) for index in range(1,len(result)+1)})
        return result

    def gpu_original(self,request,packet,clocks_before,clocks_after,first,last):
        owner=self.sample(request);need(packet is not None and packet['requestId']==request and packet['binding']==self.binding)
        start,end=owner.clocks.interval(clocks_before,clocks_after)
        follow(first['clockJoin']['nativeAfter'],start)
        follow(end,last['clockJoin']['nativeBefore'])
        class Frozen(PrivateFeatureState):
            def read(_self):return deepcopy(packet)
        frozen=copy(owner.frame_owner);frozen.store=Frozen(owner.frame_owner.store.path);frozen.guard=lambda:True
        frozen._load();need(frozen.state['phase']=='released' and absent(frozen.state['absence']))
        proof=frozen.state['absence'];need(first['clockJoin']['nativeAfter']['capturedEpochMs']<=proof['requestedEpochMs']
            <=proof['capturedEpochMs']<=last['clockJoin']['nativeBefore']['capturedEpochMs'])
        need(start['capturedEpochMs']<=proof['requestedEpochMs']<=proof['capturedEpochMs']<=end['capturedEpochMs'])
        return proof

    def positive_inputs(self,current):
        """Actual delivered endings, independently of W3C response/release ACK."""
        self.inputs.lock.assert_held();need(same(self.inputs.store.read(),self.inputs.previous))
        if self.inputs.previous is None:
            # A successful ordinary Script open need not have issued any world
            # tap/key recipe. Native retirement still independently requires
            # complete actual global pointer/key/IME and hidden-keyboard drain.
            need(self.inputs.state==dict(records=[]))
        else:self.inputs.decode(self.inputs.previous)
        end=current['originals']
        world_web_keys.drained(end['keys'])
        for row in self.inputs.state['records']:
            if row['phase']=='reading':continue
            original=self.source.frame(row['source']);begin=original['originals'];epoch=original['clockJoin']['nativeAfter']['capturedEpochMs']
            need(original['index']<current['index']);following=self.source.frame(self.source.state['records'][original['index']])['originals']
            if row['kind']=='tap':
                point=row['body']['actions'][0]['actions'][0]
                pointer_state.delivered(begin['pointer'],following['pointer'],kind='touch',position=[point['x'],point['y']],after_epoch=epoch)
            else:
                old=begin['keys']['source'];new=following['keys']['source'];prior={value['id'] for value in old['dispatches']}
                actual=[value for value in new['dispatches'] if value['id'] not in prior and value['kind'] in ('key-press','input-method') and value['enteredEpochMs']>=epoch]
                need(actual and all(value['returnedSequence']>0 and value['finallySequence']>0 for value in actual))

    def measure(self,frame):
        with self.source.validation_round(),self.lease.validation_round():return self._measure(frame)

    def _measure(self,frame):
        exact(frame,{'index','ticket','before','after','files','gpu','inputOwner','scope'}|({'gpuOriginals','gpuAcquisition'} if self.version==2 else set()))
        first,last=self.source.frame(frame['before']),self.source.frame(frame['after'])
        need(first['index']<last['index'] and first['ticket']==last['ticket']==frame['ticket']
            and first['phaseBefore']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        need(same(frame['scope'],self.scope.previous) and same(frame['inputOwner'],self.inputs.previous))
        self.files.original(frame['files']);file=self.files.original(frame['files'])
        need(first['clockJoin']['nativeAfter']['capturedEpochMs']<=file['clockJoin']['nativeBefore']['capturedEpochMs']
            <=file['clockJoin']['nativeAfter']['capturedEpochMs']<=last['clockJoin']['nativeBefore']['capturedEpochMs'])
        proof=native_retired(self.lease,self.state['baseline'],frame['after'],file);self.positive_inputs(last)
        expected=[]
        for request in self.state['images']:
            owner=self.sample(request)
            if owner.state is not None and owner.state['before'] is not None and owner.state['before']['index']<first['index']:expected.append(request)
        rows=self.gpu_rows(frame)
        need(type(frame['gpu']) is list and [row['requestId'] for row in rows]==expected and rows)
        for row in rows:
            exact(row,{'requestId','owner','clocksBefore','clocksAfter'})
            self.gpu_original(row['requestId'],row['owner'],row['clocksBefore'],row['clocksAfter'],first,last)
        return proof

    def capture(self):
        self.bound();need(self.state['pending'] is None and len(self.state['records'])<96)
        row=dict(index=len(self.state['records'])+1,ticket=self.state['ticket'],before=None,after=None,files=None,gpu=[],inputOwner=deepcopy(self.inputs.previous),scope=deepcopy(self.scope.previous))
        if self.version==2:row.update(gpuOriginals={},gpuAcquisition=uuid.uuid4().hex)
        self.state['pending']=row;self.save();row['before']=self.source.capture('retirement-before');self.save()
        row['files']=self.files.capture('absent',self.lease.packet()['files']);self.save()
        for request in self.state['images']:
            owner=self.sample(request);before=owner.clocks.snapshot();owner.retire_runtime()
            body=dict(requestId=request,owner=deepcopy(owner.frame_owner.store.read()),clocksBefore=before,clocksAfter=owner.clocks.snapshot())
            if self.version==2:
                reference=self.gpu_store(row).write(len(row['gpu'])+1,body);row['gpu'].append(dict(requestId=request,original=reference))
            else:row['gpu'].append(body)
            self.save()
        row['after']=self.source.capture('retirement-after');self.save();self.measure(row)
        value=dict(iosWorldWebRetirementRecordVersion=self.version,binding=self.binding,runId=self.run,payload=pack([row]));self.record_store(row['index']).write(value,None)
        ref=dict(index=row['index'],sha256=digest(value));self.state['records'].append(ref);self.state['pending']=None;self.save();return ref

    def cleanup(self,ticket):
        self.bound();identifier(ticket)
        if self.state['ticket'] is None:
            self.state.update(ticket=ticket,phase='cleaning',baseline=deepcopy(self.lease.before));self.save()
        need(self.state['ticket']==ticket)
        if self.state['pending'] is not None:
            # A read may be reacquired, never an issued ordinary input. Preserve
            # the original partial and any GPU/file query owners it references.
            if self.version==2:self.pending_gpu(self.state['pending'],readable=True)
            need(len(self.state['interrupted'])<16);self.state['interrupted'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
        self.scope.cleanup()
        if self.state['barrier'] is None:
            proof=self.capture();self.state['barrier']=proof;self.save()
        native=self.measure(self.frame(self.state['barrier']))
        if self.state['restoration'] is None:
            request='ios-'+uuid.uuid4().hex;self.state['images'].append(request);self.save();owner=self.sample(request)
            owner.capture(ticket);restored(self.baseline_image,owner,self.lease,after_native=native['afterNativeEpochMs'])
            self.state['restoration']=request;self.save()
        # A budget interruption does not discard an already measured original
        # quiet prefix. A repeated cleanup obtains a new original without
        # replaying Scope inputs; actual event changes start a new window.
        self.state['phase']='quiet';self.save();started=self.source.monotonic()
        for _attempt in range(61):
            reference=self.capture();frame=self.frame(reference)
            if self.state['quiet']:
                prior=self.frame(self.state['quiet'][-1])
                if not same(activity(self.source.frame(prior['after'])),activity(self.source.frame(frame['before']))):self.state['quiet']=[]
            self.state['quiet'].append(reference);self.save()
            if len(self.state['quiet'])>=3:
                first,last=self.frame(self.state['quiet'][0]),self.frame(reference)
                try:quiet(self.source.frame(first['after']),self.source.frame(last['before']))
                except NativeUIError:pass
                else:self.state['phase']='retired';self.save();return self.original()
            need(self.source.monotonic()-started<15);self.sleep(.1)
        need(False)

    def qualification(self,state):
        with self.source.validation_round(),self.lease.validation_round():
            previous=self.state;self.state=state
            try:return self._qualification(state)
            finally:self.state=previous

    def _qualification(self,state,checked=None):
        need(state['phase']=='retired' and state['ticket'] is not None and len(state['quiet'])>=3 and state['restoration'] is not None)
        def measured(reference):
            frame=self.frame(reference)
            if checked is None:return self.measure(frame)
            key=(reference['index'],reference['sha256']);need(key in checked)
            old,proof,signature=checked[key]
            need(same(frame,old) and self.record_signature(self.record_store(reference['index']).path)==signature)
            return deepcopy(proof)
        barrier=measured(state['barrier']);owner=self.sample(state['restoration'])
        pixels=restored(self.baseline_image,owner,self.lease,after_native=barrier['afterNativeEpochMs'])
        frames=[self.frame(reference) for reference in state['quiet']];need(all(measured(reference) for reference in state['quiet']))
        first,last=self.source.frame(frames[0]['after']),self.source.frame(frames[-1]['before']);quiet(first,last)
        need(owner.state['after']['index']<first['index'])
        current=self.source.frame(frames[-1]['after']);owned=self.lease.packet()
        history=derive(self.source.browser_frames(frames[-1]['after']),ownership=owned['files'],directory=owned['directory'],entity=owned['returned']['returned']['entityId'],origins=self.origins)
        need(not history['public']['open'] and not history['public']['focused'])
        held=[]
        if self.source.version>=4:
            from ios.adapters.world_web_held_resources import primary,public as held_public
            held=[row['resource'] for row in held_public(primary(self.lease,frames[-1]['after']))]
        clock=current['clockJoin'];public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=current['index']+len(state['records']),
            capturedEpochMs=clock['hostBeforeEpochMs'],state=history['public'],artifacts=[],resources=held,lifecycle=deepcopy(clock['nativeAfter']['lifecycle']))
        result('feature.world-web.observe',public)
        return dict(ticket=state['ticket'],public=public,acquisition={key:clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')},pixels=pixels,quiet=quiet_summary(first,last))

    def decode(self,value):
        with self.source.validation_round(),self.lease.validation_round():return self._decode(value)

    @staticmethod
    def record_signature(path):
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        return EmoteOriginalLease.signature(path.lstat())

    def _decode(self,value,*,with_measurement=False):
        exact(value,{'iosWorldWebRetirementVersion','binding','runId','role','payload'});rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','ticket','baseline','barrier','images','restoration','records','pending','interrupted','quiet'})
        need(state['phase'] in ('new','cleaning','quiet','retired') and type(state['records']) is list and len(state['records'])<=96
            and type(state['images']) is list and 1<=len(state['images'])<=64 and len(set(state['images']))==len(state['images']))
        need(type(state['quiet']) is list and all(reference in state['records'] for reference in state['quiet'])
            and [reference['index'] for reference in state['quiet']]==sorted({reference['index'] for reference in state['quiet']}))
        need(type(state['interrupted']) is list and len(state['interrupted'])<=16
            and (state['pending'] is None or type(state['pending']) is dict))
        previous=self.state;self.state=state;checked={};measured=None
        try:
            for row in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
                exact(row,{'index','ticket','before','after','files','gpu','inputOwner','scope'}|({'gpuOriginals','gpuAcquisition'} if self.version==2 else set()))
                need(integer(row['index'],1,len(state['records'])+1) and row['ticket']==state['ticket'])
                if self.version==2:self.pending_gpu(row,readable=state['phase']=='retired')
            prior=None
            for index,reference in enumerate(state['records'],1):
                need(reference['index']==index);path=self.record_store(index).path;signature=self.record_signature(path)
                frame=self.frame(reference);proof=self.measure(frame);need(self.record_signature(path)==signature)
                checked[(index,reference['sha256'])]=(deepcopy(frame),deepcopy(proof),signature)
                if prior is not None:need(frame['before']['index']>prior['after']['index'])
                prior=frame
            if state['phase']=='retired':measured=self._qualification(state,checked)
        finally:
            try:
                for (index,_sha),(_frame,_proof,signature) in checked.items():need(self.record_signature(self.record_store(index).path)==signature)
            finally:self.state=previous
        return (deepcopy(state),deepcopy(measured)) if with_measurement else deepcopy(state)
    def original(self):
        self.bound();self.decode(self.previous);return dict(iosWorldWebRetirementOriginalVersion=1,owner=deepcopy(self.previous))

    def validate_original(self,value):return self.qualified_original(value)[2]

    def qualified_original(self,value):
        # The exact original is qualified once in this readonly call. These
        # local results never survive a write or become a reusable verdict.
        value=deepcopy(value)
        exact(value,{'iosWorldWebRetirementOriginalVersion','owner'});need(type(value['iosWorldWebRetirementOriginalVersion']) is int and value['iosWorldWebRetirementOriginalVersion']==1)
        with self.source.validation_round(),self.lease.validation_round():
            state,measured=self._decode(value['owner'],with_measurement=True);need(measured is not None)
            sha=digest(value)
            verdict=dict(ticket=measured['ticket'],scene=scene(measured['public']),acquisition=measured['acquisition'],retirement=dict(originalSha256=sha,quiet=measured['quiet'],
                provenance=dict(version=1,namespace='ios-world-web-retirement',reference=dict(index=state['records'][-1]['index'],sha256=sha),originalSha256=sha)))
            return state,measured,verdict
