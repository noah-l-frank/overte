"""Owned one-attempt Processing/Source1 original capture; no product input/cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,number,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import assets_image_reader as reader_source,assets_image_reader_processing as processing_source
from ios.adapters.assets_budget import operation
from ios.adapters.assets_model_raw_sources import ModelRawSources
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.graphics_history import follow_native,restore_native

VERSION=1


class ProcessingRawSources(ModelRawSources):
    SCHEMA_PREFIX='iosAssetsImageProcessRaw'
    RECORD_KEY='iosAssetsImageProcessingRawSourceRecordVersion'
    MIGRATION_KEY='iosAssetsImageProcessingRawSourceMigrationVersion'
    def __init__(self,owner,guard,save):
        self.NAMESPACE='assets-image-process-native'
        self.MIGRATION_PREFIX=self.NAMESPACE+'-migration-'
        super().__init__(owner,'primary',guard,save)


class AssetsImageReaderProcessingSources(AssetsModelSources):
    def __init__(self,store,binding,run,lock,guard,*,native,processing,image_reader,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
            and isinstance(native,NativeFeatureObservation) and native.ios and native.native_clock_bound
            and type(processing) is processing_source.IOSAssetsImageReaderProcessing and type(image_reader) is reader_source.IOSAssetsImageReader
            and callable(epoch_ms) and callable(monotonic))
        self.store,self.binding,self.run,self.lock=store,deepcopy(context(binding)),identifier(run),lock
        self.role=self.storage_role='primary';self.native=native;self.readers=dict(processing=processing,reader=image_reader);self.check=guard
        self.monotonic,self.epoch_ms=monotonic,epoch_ms;self.pid=int(binding['processIdentity'])
        need(str(self.pid)==binding['processIdentity'] and all(value.pid==self.pid for value in (native,processing,image_reader))
            and store.path.name=='ios-assets-image-processing-'+run+'.json'
            and lock.path==store.path.with_name('script-feature-sources.lock'))
        lock.assert_held();self.previous=store.read();self.state=None;self.active=False;self._cached=[]
        self.raws=ProcessingRawSources(self,self.local_guard,self.save)
        self.originals=OriginalFrameStore(store.path.parent,binding,run,'primary',self.local_guard,self.intent,
            namespace='assets-image-process-source',schema_prefix='iosAssetsImageProcessSource',monotonic=monotonic)
        if self.previous is not None:
            self.state=self.decode(self.previous)
            if self._cached:
                sample=self._cached[-1]['sample'];restore_native(self.native,sample['clockJoin']['nativeAfter'])
                processing.last=deepcopy(sample['originals']['processing']);image_reader.last=deepcopy(sample['originals']['reader'])
                processing._parent_history=deepcopy(image_reader.last)

    def local_guard(self):self.lock.assert_held();PrivateFeatureState(self.store.path)._parent();return True
    def guard(self):
        self.local_guard();need(self.check() is not False and self.native.guard() is not False and same(self.store.read(),self.previous));return True
    def reader_module(self,kind):return {'processing':processing_source,'reader':reader_source}[kind]
    def envelope(self):
        self.state['rawSources']=self.raws.manifest()
        return dict(iosAssetsImageReaderProcessingSourcesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([self.state]))

    def decode(self,value):
        exact(value,{'iosAssetsImageReaderProcessingSourcesVersion','binding','runId','role','payload'})
        need(type(value['iosAssetsImageReaderProcessingSourcesVersion']) is int and value['iosAssetsImageReaderProcessingSourcesVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'frames','pending','interrupted','nextIndex','rawSources'})
        self.raws.load(state['rawSources']);need(type(state['frames']) is list and len(state['frames'])<=32
            and type(state['interrupted']) is list and len(state['interrupted'])<=8 and integer(state['nextIndex'],1,41))
        frames=[];seen=set();previous=None;raw_seen=[]
        for reference in state['frames']:
            original=self.originals.expand(reference);need(original['index'] not in seen and original['index']<state['nextIndex']);seen.add(original['index'])
            frame=self.originals.read(original);self.frame(frame,previous);need(frame['index']==original['index']);frames.append(frame);previous=frame;raw_seen+=frame['rawRefs']
        for row in state['interrupted']:
            exact(row,{'index','pending'});need(integer(row['index'],1,state['nextIndex']-1) and row['index'] not in seen);seen.add(row['index'])
            self.pending(row['pending'],row['index']);raw_seen+=row['pending']['rawRefs']
        need(seen==set(range(1,state['nextIndex'])))
        if state['pending'] is not None:self.pending(state['pending'],state['nextIndex']);raw_seen+=state['pending']['rawRefs']
        need(len(raw_seen)==len(self.raws.refs) and sorted(raw_seen,key=lambda ref:ref['index'])==self.raws.refs)
        if self.raws.pending is not None:need(state['pending'] is not None and any(row['command']['commandId']==self.raws.pending['queryId'] for row in state['pending']['queries']))
        self._cached=frames;return state

    def frame(self,value,previous=None):
        exact(value,{'assetImageProcessingOriginalVersion','index','queries','rawRefs','sample'})
        need(type(value['assetImageProcessingOriginalVersion']) is int and value['assetImageProcessingOriginalVersion']==VERSION and integer(value['index'],1,40))
        self.pending(dict(queries=value['queries'],rawRefs=value['rawRefs'],original=None,snapshot=None),value['index'])
        sample=value['sample'];exact(sample,{'assetImageProcessingSourceFrameVersion','binding','runId','role','clockJoin','originals'})
        need(type(sample['assetImageProcessingSourceFrameVersion']) is int and sample['assetImageProcessingSourceFrameVersion']==VERSION
            and same(sample['binding'],self.binding) and sample['runId']==self.run and sample['role']==self.role)
        originals=sample['originals'];exact(originals,{'nativeBarrier','processing','reader','processingAcquisition','readerAcquisition','bindingHostSpan'})
        validate_join(sample['clockJoin'],originals)
        records=[self.raws.read_record(reference) for reference in value['rawRefs']];clocks=[];external=[]
        for row in value['queries']:
            query=row['command'];self.query(row)
            matches=[record['raw'] for record in records if same(record['query'],query) and decode(record['raw'],limit=262144).get('requestId')==query['commandId']]
            need(matches and all(raw==matches[0] for raw in matches));packet=decode(matches[0],limit=262144)
            if row['kind']=='clock':native_packet(packet,query['commandId'],self.pid,packet['capturedEpochMs']);clocks.append(packet)
            else:self.reader_module(row['kind']).validate(packet,query,self.pid);external.append(packet)
        need(len(clocks)>=2 and same(clocks[0],sample['clockJoin']['nativeBefore']) and same(clocks[-1],sample['clockJoin']['nativeAfter'])
            and same(external,[originals['processing'],originals['reader']]))
        for a,b in zip(clocks,clocks[1:]):follow_native(a,b)
        for key,module,acquisition_key in (('processing',processing_source,'iosAssetsImageReaderProcessingAcquisitionVersion'),
                ('reader',reader_source,'iosAssetsImageReaderAcquisitionVersion')):
            packet=originals[key];need(packet['runId']==self.run and packet['processId']==self.pid)
            acquisition=processing_source.acquisition(packet,originals[key+'Acquisition'],acquisition_key)
            need(sample['clockJoin']['hostBeforeMonotonic']<=acquisition['hostBeforeMonotonic']
                and acquisition['hostAfterMonotonic']<=sample['clockJoin']['hostAfterMonotonic']
                and sample['clockJoin']['nativeBefore']['capturedEpochMs']<=packet['clockBefore']['epochMs']
                and packet['clockAfter']['epochMs']<=sample['clockJoin']['nativeAfter']['capturedEpochMs']
                and sample['clockJoin']['nativeBefore']['capturedEpochMs']<=acquisition['nativeRequestedEpochMs']
                and acquisition['nativeAfterEpochMs']<=sample['clockJoin']['nativeAfter']['capturedEpochMs'])
        processing_source.parent_links(originals['processing'],originals['reader'])
        need(originals['processing']['source']['assetImageReaderProcessingHistoryVersion']==1)
        span=originals['bindingHostSpan'];need(type(span) is list and len(span)==2
            and number(span[0],sample['clockJoin']['hostBeforeMonotonic'],sample['clockJoin']['hostAfterMonotonic'])
            and number(span[1],span[0],sample['clockJoin']['hostAfterMonotonic']) and span[1]-span[0]<1.5
            and all(span[0]<=originals[key+'Acquisition']['hostBeforeMonotonic']
                and originals[key+'Acquisition']['hostAfterMonotonic']<=span[1] for key in self.readers))
        if previous is not None:
            old=previous['sample'];need(value['index']>previous['index']
                and sample['clockJoin']['hostBeforeMonotonic']>=old['clockJoin']['hostAfterMonotonic'])
            follow_native(old['clockJoin']['nativeAfter'],sample['clockJoin']['nativeBefore'])
            for key in self.readers:
                packet=originals[key];self.reader_module(key).validate(packet,
                    dict(schemaVersion=1,action=self.reader_module(key).ACTION,commandId=packet['requestId'],runId=self.run),self.pid,
                    previous=old['originals'][key])
        return value

    @operation
    def reserve(self):
        self.guard();need(self.state is None);self.state=dict(frames=[],pending=None,interrupted=[],nextIndex=1,rawSources=self.raws.manifest());self.save()

    @operation
    def recover_capture(self):
        self.guard();return deepcopy(super().recover_capture()['sample'])

    @operation
    def capture(self,host_barrier):
        need(self.state is not None and self.state['pending'] is None and self.raws.pending is None and len(self.state['frames'])<32 and not self.active);self.guard()
        self.state['pending']=dict(queries=[],rawRefs=[],original=None,snapshot=None);self.save();wrappers=[];self.active=True
        for kind,reader in [('clock',self.native),*self.readers.items()]:
            old_send,old_original=reader.send,reader.original;wrappers.append((reader,old_send,old_original))
            def send(query,kind=kind,old_send=old_send):
                need(len(self.state['pending']['queries'])<24);self.state['pending']['queries'].append(dict(kind=kind,command=deepcopy(query)));self.save();return old_send(query)
            def read(kind=kind,old_original=old_original):
                raw=old_original()
                if raw:
                    matches=[row for row in self.state['pending']['queries'] if row['kind']==kind];need(matches and len(self.state['pending']['rawRefs'])<24)
                    self.raws.capture(matches[-1]['command'],raw);self.raws.accept_capture();self.state['pending']['rawRefs'].append(deepcopy(self.raws.refs[-1]));self.save()
                return raw
            reader.send,reader.original=send,read
        try:
            clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(host_barrier)
            processing=self.readers['processing'];packet=processing.read(self.run,source1=self.readers['reader'])
            originals=dict(nativeBarrier=deepcopy(clock.started['nativeBefore']),processing=packet,reader=deepcopy(processing.parent_original),
                processingAcquisition=deepcopy(processing.acquisition),readerAcquisition=deepcopy(processing.parent_acquisition),bindingHostSpan=list(processing.binding_host_span))
            sample=dict(assetImageProcessingSourceFrameVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
                clockJoin=clock.finish(originals,[('nativeBarrier','capturedEpochMs')]),originals=originals)
            frame=dict(assetImageProcessingOriginalVersion=VERSION,index=self.state['nextIndex'],queries=deepcopy(self.state['pending']['queries']),
                rawRefs=deepcopy(self.state['pending']['rawRefs']),sample=sample)
            self.frame(frame,self._cached[-1] if self._cached else None);reference=self.originals.write(self.state['nextIndex'],frame)
            self.state['frames'].append(reference);self.state['pending']=None;self.state['nextIndex']+=1;self.save();return deepcopy(sample)
        except BaseException as primary:
            if self.state['pending'] is not None and self.state['pending']['original'] is not None:
                try:self.state['pending']['snapshot']=self.prefix(self.state['pending']['original']);self.save()
                except BaseException as secondary:primary.add_note('Retaining ImageReader processing prefix failed: '+type(secondary).__name__)
            raise
        finally:
            self.active=False
            for reader,send,original in wrappers:reader.send,reader.original=send,original
