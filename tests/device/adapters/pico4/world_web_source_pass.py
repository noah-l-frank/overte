"""Original independent World source pass; retained product owners are explicit.

This is a bounded historical source/process join, never Tablet retirement,
World stereo, v16 steps 15–19, a cleanup permit or a public feature result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,need,number
from adapters.native_script_observation import original_history
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnSender,ObserverReturnReceiver,parent_node,raw_file,state,physical as physical_stamp
from adapters.pico4.browser_actor_graph import original
from adapters.pico4.browser_history import PicoBrowserHistory
from adapters.pico4.browser_sample_grammar import validate_sample
from adapters.pico4.browser_vm import reviewed
from adapters.pico4.browser_vm_grammar import validate_frame
from adapters.pico4.world_web_prefix import PicoWorldWebPrefix,validate_owner
from adapters.script_journey.history import canonical,same,unpack
from adapters.script_journey.lock import ScriptSourceLock,ScriptSourceBusy
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhasePending
from fixture.chat_observer_process import LinuxChatObserverProcess,ObserverProcessPresent

VERSION=2
READS=(1,2)
FAMILY='pico-world-web-source-pass'
EXPECTED={'runId','fixtureUrl','foreignFixtureUrl','prefixScope','binding','ownerToken','producerHostProcessIdentity','originalRequestId'}
STORES={'owner':'pico-world-web-prefix.json','history':'pico-world-web-prefix-actor-sources.json','vm':'pico-world-web-actor-vm.json'}
EXPORT='pico-world-web-actor-source-pass.json'
RETURN='pico-world-web-actor-source-pass-return.json'
CONSUMPTION='pico-world-web-actor-source-pass-consumption.json'


class OriginalWorldVm:
    """Cold pure original World grammar, with no live native reader or restore."""
    def __init__(self,root,frames,scope,pid):
        exact(root,set(scope)|{'phase','revision','chunks','quiet'});json_digest(root);json_digest(frames)
        need(all(same(root[key],value) for key,value in scope.items()) and root['phase']=='ready'
            and root['quiet']==[] and type(root['revision']) is int and root['revision']==2*len(frames) and frames)
        self.scope=deepcopy(scope);self.origin=None;self.facts=None
        for index,frame in enumerate(frames):
            self.origin,self.facts=validate_frame(frame,frames[index-1:index],self.origin,scope['scriptUrl'],pid,surface='world')
        original_history([frame['scripts'] for frame in frames],pid)
        self._frames=tuple(canonical(frame) for frame in frames);self._hashes=tuple(digest(frame) for frame in frames)
        self.frame_count=len(frames);self.sealed=self.seal()
    def seal(self):return json_digest(dict(scope=self.scope,frames=list(self._hashes),origin=self.origin,facts=self.facts,count=self.frame_count))
    def frame(self,index):
        self.verify();need(type(index) is int and -len(self._frames)<=index<len(self._frames));return json.loads(self._frames[index])
    def frame_hash(self,index):self.frame(index);return self._hashes[index]
    def verify(self):
        need(type(self._frames) is tuple and type(self._hashes) is tuple and len(self._frames)==len(self._hashes)==self.frame_count
            and all(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==sha for raw,sha in zip(self._frames,self._hashes)) and self.seal()==self.sealed)


class WorldSourceGraph:
    def __init__(self,raw,physical,store,lock,expected):
        physical_stamp(physical)
        need(type(raw) is bytes and len(raw)<=65536 and type(store) is PrivateFeatureState and type(lock) is ScriptSourceLock)
        lock.assert_held();json_digest(expected)
        self.store,self.lock=store,lock;self.expected=deepcopy(expected);self.parent=parent_node(store)
        self.raw,self.physical=raw,deepcopy(physical);self.root=json.loads(raw);json_digest(self.root)
        exact(self.root,{'picoWorldWebSourcePassVersion','scope','files','cursor','retainedResources'})
        version=self.root['picoWorldWebSourcePassVersion'];need(type(version) is int and version in READS)
        self.version=version;exact(expected,EXPECTED|({'stereoScope'} if version==2 else set()))
        need(same(self.root['scope'],expected) and canonical(self.root)+b'\n'==raw and raw_file(store)==(raw,physical))
        self.files={};total=0
        need(type(self.root['files']) is list)
        for row in self.root['files']:
            exact(row,{'name','stamp','sha256'}|({'location'} if self.version==2 else set()));physical_stamp(row['stamp']);name=row['name']
            if self.version==2:need(row['location'] in ('state','artifact'))
            need(type(name) is str and name not in ('','.','..') and '/' not in name and '\\' not in name and name not in self.files)
            self.files[name]=deepcopy(row);total+=row['stamp'][5]
        need(1<=len(self.files)<=512 and total<=16*1024*1024);self.manifest_seal=json_digest(self.files);self.used=set();self.readers=[]
        self.load();need(self.used==set(self.files));self.sealed=json_digest(self.root);self.admitted=self.semantic_seal();self.verify()
    def path(self,name):
        row=self.files[name]
        return (Path(self.expected['stereoScope']['artifactRoot']) if row.get('location')=='artifact' else self.store.path.parent)/name
    def file(self,path):
        row=self.files[path.name];need(path==self.path(path.name));self.used.add(path.name)
        raw,stamp=original(path,row['stamp']);need(hashlib.sha256(raw).hexdigest()==row['sha256']);return raw
    def root_value(self,key):
        store=PrivateFeatureState(self.store.path.with_name(STORES[key]));raw=self.file(store.path);value=store.read()
        need(raw==canonical(value)+b'\n');return store,value
    def chunks(self,store,root,scope):
        reader=ChatSourceChunks(store,scope);rows=reader.load(root['chunks']);self.readers.append(reader)
        for index in range(len(rows)):self.file(reader.store(index).path)
        return rows
    def load(self):
        e=self.expected;run,url=e['runId'],e['fixtureUrl'];scope=e['prefixScope'];json_digest(scope)
        identifier(e['ownerToken']);identifier(e['originalRequestId'])
        owner_store,body=self.root_value('owner');exact(body,{'picoWorldWebPrefixVersion','scope','payload'})
        need(type(body['picoWorldWebPrefixVersion']) is int and body['picoWorldWebPrefixVersion']==3 and same(body['scope'],scope)
            and scope==dict(runId=run,fixtureUrl=url,foreignFixtureUrl=e['foreignFixtureUrl'],sourceLock=str(self.lock.path),
                path=str(owner_store.path),worldCode=reviewed('world')[0]))
        rows=unpack(body['payload']);need(len(rows)==1);self.owner=rows[0];validate_owner(self.owner,run,url)
        need(self.owner['phase']=='source-stopped' and len(self.owner['completed'])==14 and self.owner['ownerToken']==e['ownerToken']
            and same(self.owner['binding'],e['binding']))
        pid=int(e['binding']['processIdentity'].split(':',1)[0])
        vm_store,vm_root=self.root_value('vm');vm_scope=dict(picoWorldBrowserVmVersion=1,runId=run,fixtureUrl=url,
            scriptUrl=self.owner['scriptUrl'],role='actor',binding=e['binding'])
        self.vm=OriginalWorldVm(vm_root,self.chunks(vm_store,vm_root,vm_scope),vm_scope,pid)
        history_store,history_root=self.root_value('history')
        history_scope={**scope,'binding':e['binding'],'ownerToken':e['ownerToken'],'role':'actor'}
        source_scope=dict(picoWorldBrowserHistoryVersion=1,**history_scope)
        self.chunks(history_store,history_root,source_scope)
        self.history=PicoBrowserHistory(history_store,self.lock,history_scope,lambda frame,previous:validate_sample(frame,previous,
            owner=self.owner,run=run,fixture_url=url,foreign_url=e['foreignFixtureUrl'],vm=self.vm,image=lambda name:need(False),area='world-web'),area='world-web')
        frames=[row['original'] for row in self.history.rows if row['event']=='sample'];need(frames)
        activations=self.owner['fixture']['activations'];seen=[]
        for frame in frames:
            phase=frame['phaseBefore'];n=len(phase['activations'])
            need(1<=n<=len(activations) and same(phase['activations'],activations[:n]) and not frame['sample']['artifacts'])
            ticket=phase['activations'][-1]['ticket']
            if not seen or seen[-1]!=ticket:seen.append(ticket)
        need(seen==[row['ticket'] for row in activations] and self.history.publication is not None
            and self.history.publication['phase']=='accepted' and len(self.history.rows)==3*len(frames))
        last=frames[-1];need(same(last['phaseBefore']['activations'],activations)
            and same(self.root['retainedResources'],last['sample']['resources']))
        need(self.root['cursor']==dict(sampleSequence=last['sample']['sequence'],phaseRequestId=last['phaseAfter']['requestId'],
            nativeCommandId=last['native']['commandId'],vm=last['vm']))
        self.images=[]
        if self.version==2:
            from adapters.pico4.world_web_stereo_join import original_join
            stereo=e['stereoScope'];exact(stereo,{'prefixScope','binding','ownerToken','role','artifactRoot','artifactParent','sceneUrl'})
            need(type(stereo['artifactParent']) is list and len(stereo['artifactParent'])==4 and all(type(field) is int for field in stereo['artifactParent'])
                and same(stereo['prefixScope'],scope) and same(stereo['binding'],e['binding'])
                and stereo['ownerToken']==e['ownerToken'] and stereo['role']=='actor'
                and list(parent_node(PrivateFeatureState(Path(stereo['artifactRoot'])/'boundary.json')))==stereo['artifactParent'])
            path=self.store.path.with_name('pico-world-web-actor-stereo.json');raw=self.file(path);body=PrivateFeatureState(path).read()
            need(raw==canonical(body)+b'\n')
            self.images=original_join(body,stereo,self.history,lambda name:(self.file(self.path(name)),self.files[name]['stamp']))
            need([row['original']['ticket'] for row in self.images]==[activations[index]['ticket'] for index in (1,14)])
    def semantic_seal(self):return json_digest(dict(version=self.version,owner=self.owner,images=self.images,vmScope=self.vm.scope,historyScope=self.history.scope))
    def verify_files(self):
        need(self.semantic_seal()==self.admitted and type(self.version) is int and self.version==self.root['picoWorldWebSourcePassVersion'])
        need(json_digest(self.files)==self.manifest_seal and json_digest(self.root)==self.sealed and raw_file(self.store)==(self.raw,self.physical)
            and parent_node(self.store)==self.parent and same(self.root['scope'],self.expected))
        if self.version==2:need(list(parent_node(PrivateFeatureState(Path(self.expected['stereoScope']['artifactRoot'])/'boundary.json')))==self.expected['stereoScope']['artifactParent'])
        for name in self.files:self.file(self.path(name))
        return True
    def verify(self):
        self.lock.assert_held();self.verify_files()
        for reader in self.readers:reader.verify()
        self.history.verify();self.vm.verify()
        return True


class WorldSourcePass:
    """One warm published World source forest; no product retirement permit."""
    def __init__(self,flow,request,*,stereo=None):
        need(type(flow) is PicoWorldWebPrefix and flow.role=='actor' and flow.require_new_actor and flow._actor_started
            and flow._source_pass_export is None and flow.history is not None and flow.vm is not None)
        if stereo is not None:
            from adapters.pico4.world_web_stereo_join import WorldStereoJoin
            need(type(stereo) is WorldStereoJoin and stereo.flow is flow and not stereo.failed and stereo.state['phase']=='ready')
        self.version=1 if stereo is None else 2
        identifier(request);self.flow=flow;self.lock=flow.lock;self.sender=None;self.failed=False;self.graph=None
        self.store=PrivateFeatureState(flow.root/EXPORT)
        with self.lock.held():
            flow.read();flow.control();flow.history.verify();flow.vm.verify()
            need(flow.state['phase']=='source-stopped' and len(flow.state['completed'])==14
                and flow.history.publication is not None and flow.history.publication['phase']=='accepted'
                and self.store.read() is None)
            if stereo is not None:stereo.control()
            flow._source_pass_export=self
            self.expected=dict(runId=flow.run,fixtureUrl=flow.url,foreignFixtureUrl=flow.foreign,prefixScope=deepcopy(flow.scope),
                binding=deepcopy(flow.state['binding']),ownerToken=flow.state['ownerToken'],
                producerHostProcessIdentity=host_identity(),originalRequestId=request)
            if stereo is not None:self.expected['stereoScope']=deepcopy(stereo.scope)
            manifest=[]
            def add(path,location='state'):
                raw,stamp=original(path);row=dict(name=path.name,stamp=stamp,sha256=hashlib.sha256(raw).hexdigest())
                if self.version==2:row['location']=location
                manifest.append(row)
            for key,path in STORES.items():
                store=PrivateFeatureState(flow.root/path);names=[store.path]
                if key!='owner':names.extend(ChatSourceChunks(store,{}).store(index).path for index in range(len(store.read()['chunks'])))
                for path in names:add(path)
            if stereo is not None:
                add(stereo.store.path)
                for row in stereo.state['images']:
                    for field in ('metadata','png'):add(stereo.artifacts/row[field]['name'],'artifact')
            need(len(manifest)<=512 and sum(row['stamp'][5] for row in manifest)<=16*1024*1024)
            last=flow.history.last;value=dict(picoWorldWebSourcePassVersion=self.version,scope=self.expected,files=manifest,
                cursor=dict(sampleSequence=last['sample']['sequence'],phaseRequestId=last['phaseAfter']['requestId'],
                    nativeCommandId=last['native']['commandId'],vm=last['vm']),retainedResources=last['sample']['resources'])
            self.store.write(value,None);self.raw,self.physical=raw_file(self.store)
            self.graph=WorldSourceGraph(self.raw,self.physical,self.store,self.lock,self.expected)
        self.verify()
    def verify(self):
        need(not self.failed and self.graph is not None and self.flow._source_pass_export is self)
        try:
            with self.lock.held():self.graph.verify()
            self.graph.verify_files();return True
        except BaseException:self.failed=True;raise
    def publish_return(self):
        need(self.sender is None and self.verify())
        identity={key:self.expected[key] for key in ('runId','producerHostProcessIdentity','originalRequestId')}|dict(family=FAMILY)
        self.sender=ObserverReturnSender(PrivateFeatureState(self.store.path.with_name(RETURN)),
            PrivateFeatureState(self.store.path.with_name(CONSUMPTION)),identity,self.raw,self.physical,guard=self.verify)
        return self.sender.publish()
    def consume_return(self):need(self.sender is not None and self.verify());return self.sender.consume()


def _receive(process,root,lock,expected):
    """Admit actual original graph before acknowledging its live producer.

    The returned generic receiver retains its own actual consumption/ESRCH
    checks. No method here unlinks a file or qualifies product resource release.
    """
    need(type(process) is LinuxChatObserverProcess and process.process_identity==expected['producerHostProcessIdentity'])
    export=PrivateFeatureState(Path(root)/EXPORT);graphs=[]
    def admit(raw,physical):
        need(not graphs)
        with lock.held():graphs.append(WorldSourceGraph(raw,physical,export,lock,expected))
        return True
    receiver=ObserverReturnReceiver(process,PrivateFeatureState(Path(root)/RETURN),PrivateFeatureState(Path(root)/CONSUMPTION),
        {key:expected[key] for key in ('runId','producerHostProcessIdentity','originalRequestId')}|dict(family=FAMILY),admit=admit)
    return receiver,graphs[0]


class WorldSourceReturnPending(NativeUIError):
    """The actual original producer is not yet consumed/absent."""


class WorldSourceReturn:
    """Typed immutable source forest plus consumed Parent nonce and real ESRCH.

    This retains all native/VM/source files. No cleanup/unlink permission or
    target retirement can be inferred from the observer process disappearing.
    """
    def __init__(self,process,root,lock,expected):
        for method in ('guard','source_files','original_program','require_absent','final_absence','_absent','_arguments','close'):
            need(getattr(getattr(process,method),'__func__',None) is getattr(LinuxChatObserverProcess,method))
        self.receiver,self.graph=_receive(process,root,lock,expected)
        self.lock,self.process=lock,process;self.started=self.complete=self.failed=False
        self.store=PrivateFeatureState(Path(root)/'pico-world-web-actor-source-pass-receipt.json')
        need(self.store.read() is None);self.previous=None;self.previous_stamp=None;self.result=None
        self.scope=dict(picoWorldWebSourceReturnVersion=self.graph.version,scope=deepcopy(expected))
        self.scope_sha=json_digest(self.scope);self.save('prepared');self.verify()
    def verify(self):
        need(not self.failed and json_digest(self.scope)==self.scope_sha and same(self.store.read(),self.previous)
            and (self.previous is None or state(self.store)[2]==self.previous_stamp)
            and self.process is self.receiver.owner)
        with self.lock.held():self.graph.verify()
        self.graph.verify_files();return True
    def save(self,phase,**extra):
        value={**self.scope,'phase':phase,**deepcopy(extra)}
        self.store.write(value,self.previous);observed,_raw,physical=state(self.store)
        need(same(value,observed));self.previous=deepcopy(value);self.previous_stamp=physical
    def acknowledge(self):
        need(not self.started and not self.complete and self.verify());self.started=True;self.save('consumption-issued')
        result=self.receiver.acknowledge();self.verify();return result
    def finish(self):
        need(self.started and not self.complete and self.verify())
        try:
            if self.receiver.store.read().get('phase')=='ready':
                self.receiver.verify_ready();raise WorldSourceReturnPending('Original Parent nonce is not yet consumed')
            try:receipt=self.receiver.receipt()
            except ObserverProcessPresent:raise WorldSourceReturnPending('Original World source observer is still present') from None
            self.verify()
            value=dict(sourceGraphSha256=self.graph.sealed,processReturn=receipt,
                retainedResources=deepcopy(self.graph.root['retainedResources']))
            self.save('complete',result=value);returned=deepcopy(self.previous)
            self.verify();self.process.final_absence(receipt['processAbsence'])
            self.result=canonical(returned);self.complete=True;return returned
        except WorldSourceReturnPending:raise
        except BaseException:self.failed=True;raise
    def receipt(self):
        need(self.complete and self.verify() and self.result==canonical(self.previous))
        need(same(self.receiver.historical_receipt(),self.previous['result']['processReturn']))
        return json.loads(self.result)
    def close_host(self):return self.process.close() is True


def run(flow,request,*,monotonic=time.monotonic,sleep=time.sleep,duration=120,stereo=None):
    """Same original World observer, one source pass, Parent consumption, exit."""
    need(type(flow) is PicoWorldWebPrefix and flow.role=='actor' and flow.require_new_actor)
    if stereo is not None:
        from adapters.pico4.world_web_stereo_join import WorldStereoJoin
        need(type(stereo) is WorldStereoJoin and stereo.flow is flow)
    started=previous=monotonic();need(number(duration,.25,1800));exported=None
    while True:
        now=monotonic();need(number(now,previous,started+duration) and now-started<duration);previous=now
        if exported is None:
            try:
                sample=flow.publish()
                if stereo is not None and flow.state['phase']=='ready' and len(flow.state['completed']) in (1,14) and not any(
                    row['ticket']==flow.state['fixture']['activations'][-1]['ticket'] for row in ([] if stereo.state is None else stereo.state['images'])):
                    stereo.capture(sample)
                if flow.state['phase']=='source-stopped':
                    exported=WorldSourcePass(flow,request,stereo=stereo);exported.publish_return()
            except (PhasePending,ScriptSourceBusy):
                need(not flow.failed and (flow.history is None or not flow.history.failed)
                    and (flow.vm is None or not flow.vm.failed))
        if exported is not None:
            exported.verify();exported.sender.control()
            if exported.sender.ack_store.read() is not None:
                exported.consume_return();return 0
        sleep(.25)
