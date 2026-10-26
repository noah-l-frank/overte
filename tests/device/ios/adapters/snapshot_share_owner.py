"""Normal Share cancel/receive/import joined to independent original bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.native_clock_join import digest
from adapters.native_clock_source_history import restore
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import Locator,NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_photos_context import PhotosClientContext,same_device
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.adapters.snapshot_share_query_owner import host_clock
from ios.adapters.installed_code import source as process_source
from ios.adapters.tablet_web_admission import installed_forward
from ios.adapters.snapshot_share_archive_runtime import IOSSnapshotShareArchiveRuntime
from ios.adapters.snapshot_share_actions import SnapshotShareUIAction
from ios.adapters.snapshot_share_packets import SnapshotShareInputs,PACKETS
from ios.adapters import snapshot_exports as exports,snapshot_export_controls as controls,snapshot_share_original as share,snapshot_share_chunks as chunks,snapshot_share_retirement as retirement,snapshot_share_process as extension
from snapshot_observation import inspect_snapshot


class SnapshotSharePending(NativeUIError):pass


class IOSSnapshotShareOwner:
    def __init__(self,runtime,selector,run,primary,archive,lock,archive_lock,phase,system_ui,*,epoch_ms,monotonic,sleep):
        from ios.adapters.snapshot_share_runtime import IOSSnapshotShareRuntime
        need(isinstance(runtime,IOSSnapshotShareRuntime) and isinstance(primary,PhotosClientContext) and isinstance(archive,SnapshotShareArchiveContext)
            and isinstance(phase,PhaseFixtureReader) and phase.area=='snapshots' and phase.run==run)
        exact(system_ui,{'select','cancel'})
        for value in system_ui.values():exact(value,{'using','value'});need(value['using']=='accessibility id');Locator(**value)
        self.runtime,self.selector,self.run,self.primary,self.archive,self.lock,self.archive_lock=runtime,selector,identifier(run),primary,archive,lock,archive_lock
        self.binding,self.archive_binding=deepcopy(context(primary.binding)),deepcopy(context(archive.binding));self.phase,self.fixture_url=phase,phase.fixture_url
        self.system_ui=deepcopy(system_ui);self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.root,self.archive_root=runtime.state_path(selector).parent,archive.session_store.path.parent
        need(self.root!=self.archive_root and lock.path==self.root/'script-feature-sources.lock' and archive_lock.path==self.archive_root/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.root/'snapshot-share-owner.json');self.previous=self.store.read()
        self.state=dict(capture=None,device=None,phaseOriginal=None,nativeTail=None,slots=[],opens=[],current=None,actions=[],liveQueries=[],receiverActions=[],
            handoffs=[],archiveSources=[],selectTicket=None,readyReceiver=None,exportComplete=False,imported=None,metadata=None,chunks=[],result=None,cleanup=None)
        self.queries=runtime.query_owner(self)
        self.files=OriginalFrameStore(self.archive_root,self.archive_binding,run,'primary',self.guard,self.source_intent,
            namespace='share-archive-source',schema_prefix='shareArchiveSource')
        if self.previous is not None:self.state=self.load(self.previous)
    def guard(self):
        self.lock.assert_held();self.archive_lock.assert_held();need(same(self.store.read(),self.previous));self.primary.probe();self.archive.probe();return True
    def envelope(self):return dict(iosSnapshotShareOwnerVersion=1,binding=self.binding,archiveBinding=self.archive_binding,runId=self.run,
        fixtureUrl=self.fixture_url,systemUI=self.system_ui,payload=pack([self.state]))
    def save(self):
        self.guard();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def load(self,value):
        exact(value,{'iosSnapshotShareOwnerVersion','binding','archiveBinding','runId','fixtureUrl','systemUI','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosSnapshotShareOwnerVersion']) is int and value['iosSnapshotShareOwnerVersion']==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()) and type(state['slots']) is list and len(state['slots'])<=256
                and type(state['opens']) is list and len(state['opens'])<=2 and type(state['actions']) is list and len(state['actions'])<=1024
                and type(state['archiveSources']) is list and len(state['archiveSources'])<=1024 and type(state['chunks']) is list and len(state['chunks'])<=512
                and type(state['receiverActions']) is list and len(state['receiverActions'])<=128 and type(state['liveQueries']) is list and len(state['liveQueries'])<=128
                and type(state['handoffs']) is list and len(state['handoffs'])<=8 and type(state['exportComplete']) is bool)
            if state['selectTicket'] is not None:identifier(state['selectTicket'])
            if state['capture'] is not None:self.capture()
            if state['device'] is not None:need(type(state['device']) is str and re.fullmatch('[a-f0-9]{64}',state['device']))
            if state['phaseOriginal'] is not None:
                phase=state['phaseOriginal'];phase_packet(phase,run=self.run,area='snapshots',request=phase['requestId'],epoch=phase['capturedEpochMs'])
            with read_scope(fresh=True) as reads:
                counts={};labels=set();previous_sources={}
                for row in state['slots']:
                    exact(row,{'label','kind','index','sha256','qualified'});need(row['kind'] in PACKETS and type(row['label']) is str and row['label'] not in labels)
                    labels.add(row['label']);counts[row['kind']]=counts.get(row['kind'],0)+1;need(type(row['index']) is int and row['index']==counts[row['kind']])
                    if self.packet_store(row).read() is not None:
                        child=self.packet(row,True)
                        if row['sha256'] is not None:
                            need(row['sha256']==digest(child.previous) and type(row['qualified']) is bool);frame=child.historical()
                            if row['kind'] in previous_sources:PACKETS[row['kind']]._source.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=previous_sources[row['kind']])
                            previous_sources[row['kind']]=frame['packet']
                            if row['qualified']:child.qualified()
                        else:need(row['qualified'] is None)
                    else:need(row['sha256'] is None and row['qualified'] is None)
                inputs_path=self.root/SnapshotShareInputs.store_name('primary');input_events=[]
                if PrivateFeatureState(inputs_path).read() is not None:input_events=self.inputs(True).state['events']
                need(len(input_events)<=len(state['opens']))
                for index,row in enumerate(state['opens'],1):
                    exact(row,{'index','ticket','inputIndex','control','baseline','exportId','exportLabel','status'});identifier(row['ticket'])
                    need(type(row['index']) is int and row['index']==index and type(row['inputIndex']) is int and row['inputIndex']==index
                        and row['status'] in ('declared','open','cancelled','complete'))
                    if index<=len(input_events):need(input_events[index-1]['controlId']==row['control'])
                    if row['exportId'] is not None:
                        packet=self.packet_original(row['exportLabel']);need(any(item['id']==row['exportId'] and item['action']=='share' and item['fileName']==state['capture']['file']['name'] for item in packet['source']['operations']))
                    if row['status']=='cancelled':self.cancel_result(row)
                need((not state['opens'] and state['current'] is None) or type(state['current']) is int and state['current']==len(state['opens']))
                previous_receiver=None
                for index,row in enumerate(state['actions'],1):
                    exact(row,{'index','label','role','plan','journal'});need(type(row['index']) is int and row['index']==index and row['label']==row['plan']['label'] and row['role'] in ('system','receiver','archive'))
                    control=row['plan']['control'];need(row['role']==('system' if control.startswith('system-') else 'archive' if control.startswith('snapshot.share.archive.') else 'receiver'))
                    if row['role']=='system':need(same(row['plan']['selector'],self.system_ui['select' if control=='system-select' else 'cancel']))
                    child=self.action(row,True)
                    if row['journal'] is not None:
                        need(child.previous is not None and digest(child.previous)==row['journal'])
                        if control=='snapshot.share.inspect':
                            receiver=self.receiver_original(index)
                            if previous_receiver is not None:share.original(receiver,previous_receiver)
                            previous_receiver=receiver
                for index in state['receiverActions']:self.receiver_original(index)
                if state['readyReceiver'] is not None:
                    receiver=self.receiver_original(state['readyReceiver']);need(receiver['phase']=='complete' and receiver['queries'][-1]['operationAlive'] is False
                        and any(event['kind']=='weak-expired' for event in receiver['events']))
                previous_index=0
                for index in state['liveQueries']:
                    need(integer(index,previous_index+1,len(self.queries.state['queries'])));previous_index=index;need(self.queries.query_original(index)['anchor'] is not None)
                for row in state['handoffs']:
                    exact(row,{'label','target','before','issued','after'});need(type(row['issued']) is bool and row['target'] in ('primary','archive'))
                    if row['after'] is not None:self.handoff_original(row)
                for index,row in enumerate(state['archiveSources'],1):
                    exact(row,{'index','label','path','limit','wire','proof'});need(type(row['index']) is int and row['index']==index and integer(row['limit'],1,720896)
                        and row['path'] in {'snapshot-share-chunk.json','snapshot-share-retirement-observation.json'}|{
                            'snapshot-share-'+self.run+'/'+name+'.json' for name in ('import-intent','import-original','original-extension')})
                    if row['wire'] is not None:
                        self.files.original(row['wire']);need(row['wire']['index']==index and row['proof'] is None)
                        if row['wire']['phase']!='planned':self.archive_source(index)
                    if row['proof'] is not None:need(self.files.expand(row['proof'])['index']==index and row['wire'] is None);self.archive_source(index)
                for index in state['chunks']:need(integer(index,1,len(state['archiveSources'])));self.archive_source(index)
                if state['result'] is not None:
                    need(same(state['result'],self.proof()) and any(row['label']=='share-client' and row['after'] is not None for row in state['handoffs']))
                if state['cleanup'] is not None:self.cleanup_state()
                allowed={self.store.path,inputs_path}|{self.packet_store(row).path for row in state['slots']}
                for path in self.root.iterdir():
                    if path.name.startswith(('snapshot-share-','share-native-','share-input-proof-')):need(path in allowed or path in reads)
                for path in self.archive_root.iterdir():
                    if path.name.startswith(('share-normal-','share-archive-source-')):
                        pending=any(row['wire'] is not None and path==self.files.path(row['wire']) for row in state['archiveSources'])
                        need(path in reads or pending)
        finally:self.state=prior
        return deepcopy(state)
    def capture(self):
        owner=IOSSnapshotCaptureOwner.archive(PrivateFeatureState(self.root/'ios-snapshot-primary-capture-owner.json'),self.lock,self.binding,self.run,self.fixture_url)
        result=owner.result();artifact=owner.history('artifact',owner.state['artifact']);fact,raw=artifact.originals()
        pin=dict(resultSha256=digest(result),artifactSha256=digest(artifact.previous),file=fact['file'])
        if self.state['capture'] is not None:need(same(pin,self.state['capture']))
        return owner,result,pin,raw
    def active(self,ticket,verb):
        identifier(ticket);value=self.phase.read(self.state['phaseOriginal'])['status']
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'],
            previous=self.capture()[0].state['phaseOriginal'] if self.state['phaseOriginal'] is None else self.state['phaseOriginal'])
        need(value['active'] and value['activations'][-1]['ticket']==ticket and value['activations'][-1]['stimulus']==dict(verb=verb,inputs={}))
        self.state['phaseOriginal']=deepcopy(value);self.save()
    def phase_guard(self):
        need(self.state['phaseOriginal'] is not None);value=self.phase.read(self.state['phaseOriginal'])['status']
        need(value['active'] and same(value['activations'],self.state['phaseOriginal']['activations']));return True
    def packet_store(self,row):return PrivateFeatureState(self.root/('snapshot-share-primary-'+PACKETS[row['kind']]._name+'-'+format(row['index'],'04d')+'.json'))
    def packet(self,row,history=False):
        cls=PACKETS[row['kind']];args=(self.packet_store(row),self.lock,self.binding,self.run,'primary',row['index'])
        if history:return cls.history(*args)
        actual=self.primary.foreground_sources();native=actual['clock_source']
        if self.state['nativeTail'] is not None:restore(native,self.state['nativeTail'])
        return cls(*args,actual['observer'],native,self.guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
    def observe(self,label,kind):
        rows=[row for row in self.state['slots'] if row['label']==label]
        if rows:row=rows[0];need(row['kind']==kind)
        else:
            row=dict(label=label,kind=kind,index=1+sum(item['kind']==kind for item in self.state['slots']),sha256=None,qualified=None)
            self.state['slots'].append(row);self.save()
        child=self.packet(row)
        if child.state is None:child.reserve()
        if child.state['phase']=='reserved':child.send()
        if child.state['phase']=='issued':child.retain()
        frame=child.historical()
        if row['sha256'] is None:
            older=[item for item in self.state['slots'] if item['kind']==kind and item['index']<row['index'] and item['sha256'] is not None]
            if older:
                previous=self.packet(older[-1],True).historical()['packet']
                PACKETS[kind]._source.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=previous)
            if self.state['nativeTail'] is not None:follow_native(self.state['nativeTail'],frame['acquisition']['nativeBefore'])
            self.state['nativeTail']=deepcopy(frame['acquisition']['nativeAfter']);row['sha256']=digest(child.previous)
            try:child.qualified();row['qualified']=True
            except NativeUIError:row['qualified']=False
            self.save()
        need(row['sha256']==digest(child.previous))
        if not row['qualified']:raise SnapshotSharePending('Original Share source remains historical and unqualified')
        return frame['packet']
    def next_source(self,prefix,kind):
        rows=[row for row in self.state['slots'] if row['label'].startswith(prefix)]
        return self.observe(rows[-1]['label'] if rows and rows[-1]['sha256'] is None else prefix+str(len(rows)+1),kind)
    def packet_original(self,label):
        rows=[row for row in self.state['slots'] if row['label']==label];need(len(rows)==1 and rows[0]['sha256'] is not None and rows[0]['qualified'] is True)
        child=self.packet(rows[0],True);need(digest(child.previous)==rows[0]['sha256']);child.qualified();return child.historical()['packet']
    def inputs(self,history=False):
        args=(PrivateFeatureState(self.root/SnapshotShareInputs.store_name('primary')),self.lock,self.binding,self.run,'primary')
        if history:return SnapshotShareInputs.history(*args)
        return SnapshotShareInputs(*args,self.primary.foreground_sources()['native'],self.guard)
    def op(self):
        need(integer(self.state['current'],1,len(self.state['opens'])));return self.state['opens'][self.state['current']-1]
    def latest_label(self,prefix,rows):
        selected=[row for row in rows if row['label'].startswith(prefix)]
        return selected[-1]['label'] if selected and selected[-1]['journal'] is None else prefix+str(len(selected)+1)
    def action(self,row,history=False):
        sdk=self.archive if row['role']=='archive' else self.primary;binding=self.archive_binding if row['role']=='archive' else self.binding
        def guard():
            self.guard()
            if row['plan']['control'] not in ('snapshot.share.archive.retire','snapshot.share.archive.retire-inspect'):self.phase_guard()
            if row['role']=='archive':self.archive.probe(True)
            if row['plan']['control']=='snapshot.share.archive.retire':self.cleanup_fresh(self.state['cleanup']['groups'][-1][-1])
            if row['role']=='receiver':
                need(self.state['liveQueries']);index=self.state['liveQueries'][-1];packet=self.queries.qualified(index);need(packet['anchor'] is not None)
                frame,_=self.queries.frame(self.queries.state['queries'][index-1]);need(0<=self.queries.stamp()['monotonicMs']-frame['hostAfter']['monotonicMs']<3000)
            return True
        return SnapshotShareUIAction(self.archive_root,self.archive_lock,binding,self.run,row['index'],row['plan'],lambda:True if history else guard(),
            client=None if history else sdk.client,session=None if history else sdk.session,epoch_ms=self.epoch_ms,monotonic=self.monotonic,historical=history)
    def acted(self,label,role,control,fields=()):
        selector=self.system_ui['select' if control=='system-select' else 'cancel'] if control.startswith('system-') else None
        plan=dict(label=label,control=control,selector=selector,fields=[list(value) for value in fields]);rows=[row for row in self.state['actions'] if row['label']==label]
        if rows:row=rows[0];need(row['role']==role and same(row['plan'],plan))
        else:
            row=dict(index=len(self.state['actions'])+1,label=label,role=role,plan=plan,journal=None)
            self.state['actions'].append(row);self.save()
        child=self.action(row,row['journal'] is not None)
        if row['journal'] is not None:need(row['journal']==digest(child.previous));return row,child.original() if control=='snapshot.share.inspect' else None
        if control!='snapshot.share.inspect' and child.state['issued']:
            row['journal']=digest(child.previous);self.save();return row,None
        value=child.execute();row['journal']=digest(child.previous);self.save();return row,value
    def live(self,prefix):
        rows=self.queries.state['queries'];last=rows[-1] if rows else None
        label=last['label'] if last is not None and last['phase']!='retained' else prefix+str(len(rows)+1)
        packet=self.queries.query(label);index=self.queries.state['queries'][-1]['index'];self.queries.qualified(index)
        if packet['anchor'] is None:raise SnapshotSharePending('The independently observed Share receiver is not running')
        if not self.state['liveQueries'] or self.state['liveQueries'][-1]!=index:self.state['liveQueries'].append(index);self.save()
        return packet
    def receiver_original(self,index):
        need(integer(index,1,len(self.state['actions'])));row=self.state['actions'][index-1]
        need(row['plan']['control']=='snapshot.share.inspect' and row['journal'] is not None);child=self.action(row,True)
        need(digest(child.previous)==row['journal']);child.qualified();raw=child.original();packet=decode(raw.decode('utf-8'));share.original(packet)
        need(packet['runId']==self.run and packet['receiverBundleId']==self.archive.artifact['extension']['bundle']['bundleId']
            and packet['basename']==self.state['capture']['file']['name'] and packet['queries']
            and packet['queries'][-1]['requestId']==dict(row['plan']['fields'])['snapshot.share.query'])
        share.stamp(packet['queries'][-1]['clock'],packet['events'][-1]['clock'])
        live=self.queries.query_original(self.queries.state['anchorQuery']);need(packet['processId']==live['anchor']['pid']);return packet
    def inspect_receiver(self):
        self.live('inspect-live-');label=self.latest_label('receiver-inspect-',self.state['actions'])
        rows=[row for row in self.state['actions'] if row['label']==label]
        nonce=dict(rows[0]['plan']['fields'])['snapshot.share.query'] if rows else 'ios-'+uuid.uuid4().hex
        row,_raw=self.acted(label,'receiver','snapshot.share.inspect',[('snapshot.share.query',nonce)]);packet=self.receiver_original(row['index'])
        prior=[item for item in self.state['actions'] if item['index']<row['index'] and item['plan']['control']=='snapshot.share.inspect' and item['journal'] is not None]
        if prior:share.original(packet,self.receiver_original(prior[-1]['index']))
        self.state['receiverActions'].append(row['index']);self.save();return packet
    def handoff(self,label,target):
        rows=[row for row in self.state['handoffs'] if row['label']==label]
        if rows:row=rows[0];need(row['target']==target)
        else:
            row=dict(label=label,target=target,before=dict(primary=self.primary.probe(),archive=self.archive.probe()),issued=False,after=None)
            self.state['handoffs'].append(row);self.save()
        if row['after'] is not None:self.handoff_original(row);return
        if not row['issued']:row['issued']=True;self.save();(self.primary if target=='primary' else self.archive).activate()
        row['after']=dict(primary=self.primary.probe(),archive=self.archive.probe());self.handoff_original(row);self.save()
    def handoff_original(self,row):
        need(row['issued'] and row['after'] is not None and row['target'] in ('primary','archive'));target=row['target'];other='archive' if target=='primary' else 'primary'
        for role,binding in (('primary',self.binding),('archive',self.archive_binding)):
            a,b=row['before'][role],row['after'][role];need(same(a['binding'],binding) and same(b['binding'],binding)
                and same(a['source'],b['source']) and a['process']['pid']==b['process']['pid']==int(binding['processIdentity']))
            fields={'binding','process','source'}|({'installed'} if role=='primary' and 'installed' in a else set());exact(a,fields);exact(b,fields)
            for original in (a,b):
                process_source(original['source']);exact(original['process'],{'bundleId','pid','foreground'})
                need(type(original['process']['pid']) is int and type(original['process']['foreground']) is bool
                    and original['process']['bundleId']==(self.primary if role=='primary' else self.archive).target['appId'])
            if 'installed' in fields:installed_forward(a['installed'],b['installed'])
        need(row['before'][target]['process']['foreground'] is False and type(row['before'][other]['process']['foreground']) is bool
            and row['after'][target]['process']['foreground'] is True and row['after'][other]['process']['foreground'] is False)
    def archive_runtime(self):
        scope={key:value for key,value in self.archive_binding.items() if key!='processIdentity'}
        return IOSSnapshotShareArchiveRuntime(self.archive.client,self.archive.session_store,self.archive.target,scope,self.archive.artifact_path,lambda:self.archive.probe(True) is not None,
            admission_store=self.archive.admission.store,lock=self.archive_lock,run=self.run,fixture_url=self.fixture_url,epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
    def source_intent(self,kind,value):
        need(kind=='original');row=self.state['archiveSources'][-1];self.files.original(value);old=row['wire'];need(value['index']==row['index'] and row['proof'] is None)
        if old is None:need(value['phase']=='planned')
        else:need((old['phase'],value['phase']) in (('planned','opened'),('opened','saved')) and all(same(old[key],value[key]) for key in old if key not in ('phase','file'))
            and (old['file'] is None or same(old['file'],value['file'])))
        row['wire']=deepcopy(value);self.save()
    def archive_source(self,index):
        need(integer(index,1,len(self.state['archiveSources'])));row=self.state['archiveSources'][index-1]
        ref=row['wire'] if row['proof'] is None else self.files.expand(row['proof']);need(ref is not None)
        frame=self.files.read(ref);exact(frame,{'snapshotShareArchiveFrameVersion','path','before','after','raw'})
        need(type(frame['snapshotShareArchiveFrameVersion']) is int and frame['snapshotShareArchiveFrameVersion']==1 and frame['path']==row['path'])
        host_clock(frame['before']);host_clock(frame['after'],frame['before']);raw=base64.b64decode(frame['raw'],validate=True)
        need(1<=len(raw)<=row['limit'] and base64.b64encode(raw).decode()==frame['raw']);return raw
    def archive_frame(self,index):
        self.archive_source(index);row=self.state['archiveSources'][index-1]
        return self.files.read(row['wire'] if row['proof'] is None else self.files.expand(row['proof']))
    def read_archive(self,label,path,limit):
        rows=[row for row in self.state['archiveSources'] if row['label']==label]
        if rows:row=rows[0];need(row['path']==path and row['limit']==limit)
        else:
            row=dict(index=len(self.state['archiveSources'])+1,label=label,path=path,limit=limit,wire=None,proof=None);self.state['archiveSources'].append(row);self.save()
        if row['proof'] is not None:return row['index'],self.archive_source(row['index'])
        if row['wire'] is None:
            stamp=self.queries.stamp if path=='snapshot-share-retirement-observation.json' else lambda:dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000)
            before=stamp();raw=self.archive_runtime().original_path(path,limit);after=stamp()
            frame=dict(snapshotShareArchiveFrameVersion=1,path=path,before=before,after=after,raw=base64.b64encode(raw).decode());row['proof']=self.files.write(row['index'],frame)
        else:
            self.archive_source(row['index']);wire=row['wire'];need(wire['phase'] in ('opened','saved'))
            if wire['phase']=='opened':self.source_intent('original',dict(wire,phase='saved'));wire=row['wire']
            row['proof']=self.files.compact(wire)
        row['wire']=None;self.save();return row['index'],self.archive_source(row['index'])

    @operation
    def open(self,ticket):
        self.guard();self.active(ticket,'share-open')
        if self.state['capture'] is None:
            capture,_result,pin,_raw=self.capture();self.state['capture']=pin;self.state['nativeTail']=deepcopy(capture.state['nativeTail'])
            self.state['device']=same_device(self.primary,self.archive);self.save()
        rows=[row for row in self.state['opens'] if row['ticket']==ticket]
        if rows:row=rows[0];need(self.state['current']==row['index'])
        else:
            need(self.state['result'] is None and len(self.state['opens'])<2 and (not self.state['opens'] or self.state['opens'][-1]['status']=='cancelled'))
            row=dict(index=len(self.state['opens'])+1,ticket=ticket,inputIndex=len(self.state['opens'])+1,control=None,baseline=None,exportId=None,exportLabel=None,status='declared')
            self.state['opens'].append(row);self.state['current']=row['index'];self.save()
        if row['baseline'] is None:
            label='open-before-'+str(row['index']);packet=self.observe(label,'exports');exports.drained(packet);row['baseline']=label;self.save()
        inputs=self.inputs()
        if len(inputs.state['events'])<row['inputIndex']:
            need(len(inputs.state['events'])==row['inputIndex']-1);view=controls.project(self.primary.foreground_sources()['native'].capture())
            controls_rows=[item for item in view['controls'] if item['id'].startswith('snapshot.share.') and item['snapshotFileName']==self.state['capture']['file']['name']]
            need(len(controls_rows)==1);row['control']=controls_rows[0]['id'];self.save();inputs.reserve(row['control'],view)
        event=inputs.state['events'][row['inputIndex']-1];need(event['controlId']==row['control'])
        if event['phase']=='reserved':self.active(ticket,'share-open');inputs.send()
        elif event['phase']=='issued':inputs.recover(self.next_source('open-delivery-'+str(row['index'])+'-','inputs'))
        inputs.validate_original(row['inputIndex']);before=self.packet_original(row['baseline']);after=self.next_source('open-after-'+str(row['index'])+'-','exports')
        exports.validate(after,dict(schemaVersion=1,action=exports.ACTION,commandId=after['requestId'],runId=self.run),int(self.binding['processIdentity']),previous=before)
        old={item['id'] for item in before['source']['operations']};new=[item for item in after['source']['operations'] if item['id'] not in old]
        need(len(new)==1 and new[0]['action']=='share' and new[0]['owned'] and new[0]['fileName']==self.state['capture']['file']['name'])
        if row['exportId'] is not None:need(row['exportId']==new[0]['id'])
        row['exportId']=new[0]['id'];row['exportLabel']=self.state['slots'][-1]['label'];self.save()
        if not new[0]['alive'] or not new[0]['state']['sheetPresent'] or not (new[0]['state']['sheetAttached'] or new[0]['state']['sheetPresenting']):
            raise SnapshotSharePending('The original system Share presentation is not visible')
        row['status']='open';self.save();return dict(snapshotSharePresentationVersion=1,operationId=row['exportId'],nativeOriginalSha256=digest(after),wholeFeatureRequired=True)

    @operation
    def cancel(self,ticket):
        self.guard();self.active(ticket,'share-cancel');row=self.op();need(row['status'] in ('open','cancelled'))
        if row['status']=='cancelled':return self.cancel_result(row)
        self.acted('system-cancel-'+str(row['index']),'system','system-cancel');after=self.next_source('cancel-after-'+str(row['index'])+'-','exports')
        exports.drained(after);result=exports.outcome(after,row['exportId']);need(result['nativeResult']['detail']==dict(status='cancelled',hasError=False))
        row['exportLabel']=self.state['slots'][-1]['label'];row['status']='cancelled';self.save();return self.cancel_result(row)
    def cancel_result(self,row):
        packet=self.packet_original(row['exportLabel']);exports.drained(packet);result=exports.outcome(packet,row['exportId'])
        need(result['nativeResult']['detail']==dict(status='cancelled',hasError=False));return dict(snapshotShareCancellationVersion=1,operationId=row['exportId'],nativeOriginalSha256=digest(packet),wholeFeatureRequired=True)

    @operation
    def select(self,ticket):
        self.guard()
        identifier(ticket)
        if self.state['result'] is not None:need(self.state['selectTicket']==ticket);self.primary.probe(True);return self.proof()
        self.active(ticket,'share-select-owned')
        if self.state['selectTicket'] is None:self.state['selectTicket']=ticket;self.save()
        else:need(self.state['selectTicket']==ticket)
        row=self.op();need(row['status']=='open')
        finish_label='finish-'+str(row['index']);finish_rows=[item for item in self.state['actions'] if item['label']==finish_label]
        finish_issued=bool(finish_rows and self.action(finish_rows[0],True).state['issued'])
        if not finish_issued:
            if self.state['readyReceiver'] is None:
                self.acted('system-select-'+str(row['index']),'system','system-select');self.live('selected-live-')
                self.acted('receive-'+str(row['index']),'receiver','snapshot.share.receive',[
                    ('snapshot.share.run',self.run),('snapshot.share.basename',self.state['capture']['file']['name'])])
                receiver=self.inspect_receiver();query=receiver['queries'][-1]
                if receiver['phase']!='complete' or query['operationAlive'] or not any(event['kind']=='weak-expired' for event in receiver['events']):
                    raise SnapshotSharePending('Actual original resource callback/weak owner remains pending')
                self.state['readyReceiver']=self.state['receiverActions'][-1];self.save()
            self.live('finish-live-');self.acted(finish_label,'receiver','snapshot.share.finish')
        else:self.acted(finish_label,'receiver','snapshot.share.finish')
        receiver=self.receiver_original(self.state['readyReceiver'])
        if not self.state['exportComplete']:
            if self.primary.probe()['process']['foreground'] is False:self.handoff('finish-primary-return','primary')
            after=self.next_source('share-finished-','exports');exports.drained(after);result=exports.outcome(after,row['exportId'])
            need(result['nativeResult']['detail']==dict(status='success',hasError=False));row['exportLabel']=self.state['slots'][-1]['label'];self.state['exportComplete']=True;self.save()
        self.handoff('archive-import','archive');self.acted('archive-import','archive','snapshot.share.archive.import',[('snapshot.share.archive.run',self.run)])
        if self.state['imported'] is None:
            index,raw=self.read_archive('import-original','snapshot-share-'+self.run+'/import-original.json',262144);self.state['imported']=index;self.save()
        if self.state['metadata'] is None:
            index,_raw=self.read_archive('extension-original','snapshot-share-'+self.run+'/original-extension.json',262144);self.state['metadata']=index;self.save()
        imported=decode(self.archive_source(self.state['imported']).decode('utf-8'));metadata=self.archive_source(self.state['metadata'])
        finished=share.imported_metadata(imported,metadata,pid=int(self.archive_binding['processIdentity']),bundle_id=self.archive.target['appId'],receiver_bundle_id=self.archive.artifact['extension']['bundle']['bundleId'])
        share.original(finished,receiver)
        if self.queries.state['receiver']['proof'] is None:self.queries.bind_receiver(self.archive_runtime())
        need(self.queries.receiver()[1]==metadata)
        for offset in range(0,imported['byteCount'],chunks.CHUNK_BYTES):
            prefix='archive-chunk-'+str(offset//chunks.CHUNK_BYTES+1);rows=[item for item in self.state['actions'] if item['label']==prefix]
            nonce=dict(rows[0]['plan']['fields'])['snapshot.share.archive.query'] if rows else 'ios-'+uuid.uuid4().hex
            self.acted(prefix,'archive','snapshot.share.archive.chunk',[('snapshot.share.archive.query',nonce),('snapshot.share.archive.offset',str(offset))])
            index,raw=self.read_archive(prefix,'snapshot-share-chunk.json',chunks.CHUNK_LIMIT);packet=decode(raw.decode('utf-8'),limit=chunks.CHUNK_LIMIT)
            previous=None if not self.state['chunks'] else decode(self.archive_source(self.state['chunks'][-1]).decode('utf-8'),limit=chunks.CHUNK_LIMIT)
            if index in self.state['chunks']:previous=None if offset==0 else decode(self.archive_source(self.state['chunks'][offset//chunks.CHUNK_BYTES-1]).decode('utf-8'),limit=chunks.CHUNK_LIMIT)
            chunks.chunk(packet,nonce,offset,imported,metadata,pid=int(self.archive_binding['processIdentity']),bundle_id=self.archive.target['appId'],receiver_bundle_id=self.archive.artifact['extension']['bundle']['bundleId'],previous=previous)
            if index not in self.state['chunks']:self.state['chunks'].append(index);self.save()
        proof=self.proof();self.handoff('share-client','primary');self.primary.foreground_sources();self.state['result']=proof;row['status']='complete';self.save();return proof
    def proof(self):
        need(self.state['imported'] is not None and self.state['metadata'] is not None and self.state['chunks']);row=self.op()
        imported=decode(self.archive_source(self.state['imported']).decode('utf-8'));metadata=self.archive_source(self.state['metadata']);values=[decode(self.archive_source(index).decode('utf-8'),limit=chunks.CHUNK_LIMIT) for index in self.state['chunks']]
        raw=chunks.original_bytes(values,imported,metadata,pid=int(self.archive_binding['processIdentity']),bundle_id=self.archive.target['appId'],receiver_bundle_id=self.archive.artifact['extension']['bundle']['bundleId'])
        receiver=share.imported_original(imported,metadata,raw,pid=int(self.archive_binding['processIdentity']),bundle_id=self.archive.target['appId'],receiver_bundle_id=self.archive.artifact['extension']['bundle']['bundleId'])
        need(self.queries.receiver()[1]==metadata);_capture,result,_pin,captured=self.capture();original=share.received_original(receiver,self.packet_original(row['exportLabel']),row['exportId'],raw,captured)
        image=inspect_snapshot(raw,mode='still',file_format='png');need(image['sha256']==result['image']['sha256'])
        return dict(iosSnapshotShareTransferVersion=1,sharedOriginal=original,image=image,hostOriginalRetained=True,
            archiveCleanupRequired=True,extensionQuietRequired=True,captureCleanupRequired=True,nativePresentationCleanupRequired=True,wholeFeatureRequired=True)

    def cleanup_state(self):
        state=self.state['cleanup'];exact(state,{'intent','groups','retireNonce','after','result'});need(self.state['result'] is not None
            and type(state['groups']) is list and 1<=len(state['groups'])<=16 and type(state['after']) is list and len(state['after'])<=32)
        need(type(state['retireNonce']) is str and re.fullmatch('ios-[a-f0-9]{32}',state['retireNonce']))
        if state['intent'] is not None:retirement.intent(self.archive_source(state['intent']),decode(self.archive_source(self.state['imported']).decode('utf-8')))
        last=0
        for group in state['groups']:
            need(type(group) is list and len(group)<=3)
            for index in group:
                need(integer(index,last+1,len(self.queries.state['queries'])));last=index;self.cleanup_absent(index)
            if len(group)==3:self.queries.quiet_originals(group)
        for at,row in enumerate(state['after'],1):
            exact(row,{'index','queryIndex','nonce','before','source','qualified'})
            need(type(row['index']) is int and row['index']==at and type(row['nonce']) is str and re.fullmatch('ios-[a-f0-9]{32}',row['nonce'])
                and row['qualified'] in (None,False,True) and (row['qualified'] is None or type(row['qualified']) is bool))
            if row['queryIndex'] is not None:
                need(integer(row['queryIndex'],last+1,len(self.queries.state['queries'])));last=row['queryIndex']
            if row['before'] is not None:host_clock(row['before'])
            if row['source'] is not None:self.archive_source(row['source'])
            if row['qualified'] is True:self.cleanup_qualified(row)
        if state['result'] is not None:need(same(state['result'],self.cleanup_proof()))

    def cleanup_absent(self,index):
        packet=self.queries.qualified(index);extension.absent(packet,self.queries.receiver()[0],self.queries.artifact,self.queries.os_scope['source']);return packet
    def cleanup_fresh(self,index):
        self.cleanup_absent(index);frame,_packet=self.queries.frame(self.queries.state['queries'][index-1]);now=self.queries.stamp();host_clock(now,frame['hostAfter'])
        need(now['monotonicMs']-frame['hostAfter']['monotonicMs']<3000 and now['epochMs']-frame['hostAfter']['epochMs']<3000);return True
    def cleanup_observation(self,row):
        need(row['before'] is not None and row['source'] is not None);raw=self.archive_source(row['source']);value=decode(raw.decode('utf-8'))
        state=self.state['cleanup'];retirement.observation(value,row['nonce'],state['retireNonce'],decode(self.archive_source(self.state['imported']).decode('utf-8')),
            self.archive_source(self.state['metadata']),self.archive_source(self.state['imported']),self.archive_source(state['intent']),
            receiver_bundle_id=self.archive.artifact['extension']['bundle']['bundleId'])
        actions=[item for item in self.state['actions'] if item['label']=='retirement-inspect-'+str(row['index'])];need(len(actions)==1)
        action=actions[0];child=self.action(action,True)
        need(action['journal']==digest(child.previous) and child.state['issued'] and action['plan']['control']=='snapshot.share.archive.retire-inspect'
            and dict(action['plan']['fields'])=={'snapshot.share.archive.query':row['nonce']})
        previous=[item for item in state['after'] if item['index']<row['index'] and item['qualified'] is True]
        if previous:
            old=decode(self.archive_source(previous[-1]['source']).decode('utf-8'));need(same(value['retirement'],old['retirement']))
            share.stamp(value['clockBefore'],old['clockAfter'])
        return value
    def cleanup_qualified(self,row):
        value=self.cleanup_observation(row);retirement.qualified(value);self.cleanup_absent(row['queryIndex'])
        frame=self.archive_frame(row['source']);after=frame['after'];host_clock(frame['before'],row['before']);host_clock(after,row['before'])
        query_frame,_packet=self.queries.frame(self.queries.state['queries'][row['queryIndex']-1]);host_clock(row['before'],query_frame['hostAfter'])
        need(after['monotonicMs']-row['before']['monotonicMs']<5500 and after['epochMs']-row['before']['epochMs']<5500
            and after['monotonicMs']-query_frame['hostAfter']['monotonicMs']<5500
            and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<=after['monotonicMs']-row['before']['monotonicMs']+250);return value
    def cleanup_proof(self):
        state=self.state['cleanup'];qualified=[row for row in state['after'] if row['qualified'] is True];need(len(qualified)>=3)
        selected=qualified[-3:];values=[self.cleanup_qualified(row) for row in selected]
        files=retirement.quiet(values,[dict(before=row['before'],after=self.archive_frame(row['source'])['after']) for row in selected],self.run)
        before=self.queries.quiet_originals(state['groups'][-1]);after=self.queries.quiet_originals([row['queryIndex'] for row in selected])
        need(any(row['label']=='share-retired-client' and row['after'] is not None for row in self.state['handoffs']))
        presentation=[row for row in self.state['slots'] if row['label'].startswith('retirement-presentation-') and row['qualified'] is True];need(presentation)
        packet=self.packet_original(presentation[-1]['label']);exports.drained(packet);need(exports.outcome(packet,self.op()['exportId'])['nativeResult']['detail']==dict(status='success',hasError=False))
        return dict(iosSnapshotShareCleanupVersion=1,runId=self.run,transferSha256=digest(self.proof()),retirementSha256=digest(values[0]['retirement']),
            extensionBefore=before,extensionAfter=after,fileQuiet=files,hostOriginalRetained=True,sourceJournalRetirementRequired=True,
            captureCleanupRequired=True,nativePresentationCleanupRequired=True,wholeFeatureRequired=True)

    @operation
    def cleanup(self):
        self.guard();need(self.state['result'] is not None)
        if self.state['cleanup'] is not None and self.state['cleanup']['result'] is not None:
            self.primary.probe(True);return self.cleanup_proof()
        if self.state['cleanup'] is None:
            self.state['cleanup']=dict(intent=None,groups=[[]],retireNonce='ios-'+uuid.uuid4().hex,after=[],result=None);self.save()
        state=self.state['cleanup'];self.handoff('archive-retirement','archive')
        if state['intent'] is None:
            index,raw=self.read_archive('retirement-import-intent','snapshot-share-'+self.run+'/import-intent.json',262144)
            retirement.intent(raw,decode(self.archive_source(self.state['imported']).decode('utf-8')));state['intent']=index;self.save()
        issued=[row for row in self.state['actions'] if row['label']=='archive-retire']
        if not issued or not self.action(issued[0],True).state['issued']:
            group=state['groups'][-1]
            if len(group)==3:
                try:self.cleanup_fresh(group[-1])
                except NativeUIError:need(len(state['groups'])<16);state['groups'].append([]);group=state['groups'][-1];self.save()
            while len(group)<3:
                if group:self.queries.sleep(1.6)
                rows=self.queries.state['queries'];last=rows[-1] if rows else None
                label=last['label'] if last is not None and last['phase']!='retained' and last['label'].startswith('retire-before-') else 'retire-before-'+str(len(rows)+1)
                self.queries.query(label,retired=True);index=self.queries.state['queries'][-1]['index'];self.cleanup_absent(index);group.append(index);self.save()
            self.queries.quiet_originals(group)
        self.acted('archive-retire','archive','snapshot.share.archive.retire',[('snapshot.share.archive.query',state['retireNonce'])])
        while sum(row['qualified'] is True for row in state['after'])<3:
            rows=state['after']
            if rows and rows[-1]['qualified'] is None:row=rows[-1]
            else:
                if rows:self.queries.sleep(1.6)
                need(len(rows)<32);row=dict(index=len(rows)+1,queryIndex=None,nonce='ios-'+uuid.uuid4().hex,before=None,source=None,qualified=None);rows.append(row);self.save()
            if row['queryIndex'] is None:
                self.queries.query('retire-after-'+str(row['index']),retired=True);row['queryIndex']=self.queries.state['queries'][-1]['index'];self.save()
            existing=[item for item in self.state['actions'] if item['label']=='retirement-inspect-'+str(row['index'])]
            inspection_issued=bool(existing and self.action(existing[0],True).state['issued'])
            if not inspection_issued:
                try:self.cleanup_fresh(row['queryIndex'])
                except NativeUIError:row['qualified']=False;self.save();raise SnapshotSharePending('The actual extension remains present, unknown or stale') from None
            if row['before'] is None:row['before']=self.queries.stamp();self.save()
            self.acted('retirement-inspect-'+str(row['index']),'archive','snapshot.share.archive.retire-inspect',[('snapshot.share.archive.query',row['nonce'])])
            if row['source'] is None:
                index,_raw=self.read_archive('retirement-observation-'+str(row['index']),'snapshot-share-retirement-observation.json',262144);row['source']=index;self.save()
            try:self.cleanup_qualified(row)
            except NativeUIError:row['qualified']=False;self.save();raise SnapshotSharePending('Actual native retirement or file/run absence remains unqualified') from None
            row['qualified']=True;self.save()
        self.handoff('share-retired-client','primary');self.next_source('retirement-presentation-','exports')
        state['result']=self.cleanup_proof();self.save();return deepcopy(state['result'])
