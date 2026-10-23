"""Historical browser Actor graph, with original files and no live Actor.

The export is created only by a successfully returned warm retirement owner.
Its reader has no target, fixture client, native observer or input operation.
It does not qualify process absence, Parent consumption or whole cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import stat

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.evidence_archive import LIMIT_BYTES,LIMIT_FILES
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_script_observation import original_history
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.host_process_identity import host_identity
from adapters.observer_return import parent_node,physical,raw_file,state
from adapters.pico4.browser_actor_retirement import validate_original_frame
from adapters.pico4.browser_history import PicoBrowserHistory
from adapters.pico4.browser_quiet import validate as quiet_packet
from adapters.pico4.browser_quiet_journal import PicoBrowserQuietJournal
from adapters.pico4.browser_sample_grammar import validate_owner,validate_sample
from adapters.pico4.browser_stereo import original_name
from adapters.pico4.browser_vm_grammar import validate_frame,window
from adapters.script_journey.history import canonical,same,unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.stereo_browser_evidence import archive_sources

VERSION=1
STORES={'owner','role','history','vm','quiet','retirement'}
EXPECTED={'runId','fixtureUrl','foreignFixtureUrl','artifactRoot','sceneUrl','binding','ownerToken',
    'producerHostProcessIdentity','originalRequestId'}


def original(path,expected=None):
    """A bounded complete read of an explicitly named closed original."""
    path=Path(path);PrivateFeatureState(path)._parent()
    owner=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    descriptor=owner.fd
    try:
        info=os.fstat(descriptor);stamp=signature(info)
        need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
            and info.st_nlink==1 and 0<info.st_size<=LIMIT_BYTES and signature(path.lstat())==stamp
            and (expected is None or stamp==expected))
        raw=os.pread(descriptor,info.st_size+1,0);owner.require(descriptor)
        need(len(raw)==info.st_size and signature(os.fstat(descriptor))==signature(path.lstat())==stamp)
        return raw,stamp
    finally:need(OriginalDescriptor.close(owner) is True)


class BrowserOriginalVm:
    """Read-only historical DTO; never constructs or restores native readers."""
    def __init__(self,root,frames,pid):
        self.scope={key:value for key,value in root.items() if key not in ('phase','revision','chunks','quiet')}
        self.frames=deepcopy(frames);self.origin=None
        for index,frame in enumerate(self.frames):
            self.origin,_facts=validate_frame(frame,self.frames[index-1:index],self.origin,self.scope['scriptUrl'],pid)
        original_history([frame['scripts'] for frame in self.frames],pid)
        self.windows=deepcopy(root['quiet'])
        need(type(self.windows) is list and len(self.windows)<=16 and root['phase']=='ready'
            and type(root['revision']) is int and root['revision']==2*len(frames)+len(self.windows))
        for entry in self.windows:
            exact(entry,{'first','last','afterEpochMs'})
            need(window(len(frames),self.frame,entry['first'],entry['last'],entry['afterEpochMs'],self.origin,self.scope['scriptUrl'],pid))
        self.sealed=json_digest(dict(scope=self.scope,frames=self.frames,origin=self.origin,windows=self.windows))
    @property
    def frame_count(self):return len(self.frames)
    def frame(self,index):return deepcopy(self.frames[index])
    def frame_hash(self,index):return json_digest(self.frames[index])
    def verify(self):need(json_digest(dict(scope=self.scope,frames=self.frames,origin=self.origin,windows=self.windows))==self.sealed)


class PicoBrowserActorGraph:
    """Original typed graph admission only; not a process-return receipt."""
    def __init__(self,raw,source_stamp,export_store,stores,lock,expected):
        need(type(raw) is bytes and 0<len(raw)<=65536 and type(export_store) is PrivateFeatureState
            and type(stores) is dict and set(stores)==STORES and type(lock) is ScriptSourceLock
            and all(type(value) is PrivateFeatureState and value.path.parent==export_store.path.parent for value in stores.values())
            and len({export_store.path,*[value.path for value in stores.values()]})==len(stores)+1)
        lock.assert_held();exact(expected,EXPECTED);json_digest(expected);physical(source_stamp)
        context(expected['binding']);identifier(expected['runId']);identifier(expected['ownerToken']);identifier(expected['originalRequestId'])
        self.expected=deepcopy(expected);self.export,self.stores,self.lock=export_store,dict(stores),lock
        self.raw,self.source_stamp=raw,deepcopy(source_stamp);self.root=json.loads(raw);json_digest(self.root)
        self.parent=parent_node(export_store);self.artifacts=Path(expected['artifactRoot'])
        self.artifact_parent=parent_node(PrivateFeatureState(self.artifacts/'boundary.json'))
        self.scope=dict(picoBrowserActorExportVersion=VERSION,**deepcopy(expected))
        exact(self.root,set(self.scope)|{'phase','chunks','chunkStamps'})
        need(raw==canonical(self.root)+b'\n' and self.root['phase']=='ready'
            and all(same(self.root[key],value) for key,value in self.scope.items())
            and state(export_store)==(self.root,raw,source_stamp))
        self.export_chunks=ChatSourceChunks(export_store,self.scope)
        rows=self.export_chunks.load(self.root['chunks']);self.manifest=[]
        need(type(self.root['chunkStamps']) is list and len(self.root['chunkStamps'])==len(rows))
        for index,row in enumerate(rows):
            exact(row,{'originals'});need(type(row['originals']) is list and 1<=len(row['originals'])<=32)
            need(signature(self.export_chunks.store(index).path.lstat())==self.root['chunkStamps'][index])
            self.manifest.extend(row['originals'])
        need(1<=len(self.manifest)<=LIMIT_FILES);self.files={};self.used=set();self.chunks={};self.images={}
        total=0
        for row in self.manifest:
            exact(row,{'location','name','sha256','stamp'});physical(row['stamp'])
            need(row['location'] in ('state','artifact') and type(row['name']) is str
                and row['name'] not in ('','.','..') and '/' not in row['name'] and '\\' not in row['name'])
            key=(row['location'],row['name']);need(key not in self.files);self.files[key]=deepcopy(row)
            total+=row['stamp'][5];need(total<=LIMIT_BYTES)
        self.load();need(self.used==set(self.files));self.sealed=self.cache_digest();self.failed=False;self.verify()

    def file(self,path):
        location='state' if path.parent==self.export.path.parent else 'artifact'
        need(path.parent==(self.export.path.parent if location=='state' else self.artifacts))
        key=(location,path.name);row=self.files[key];self.used.add(key)
        raw,_stamp=original(path,row['stamp']);need(hashlib.sha256(raw).hexdigest()==row['sha256']);return raw

    def root_value(self,key):
        store=self.stores[key];raw=self.file(store.path);value=store.read()
        need(raw==canonical(value)+b'\n');return value

    def record(self,key,kind):
        value=self.root_value(key);expected=self.expected
        exact(value,{'picoTabletWebFeatureVersion','kind','runId','fixtureUrl','artifactRoot','foreignFixtureUrl','payload'})
        need(type(value['picoTabletWebFeatureVersion']) is int and value['picoTabletWebFeatureVersion']==3
            and value['kind']==kind and all(same(value[field],expected[field]) for field in ('runId','fixtureUrl','artifactRoot'))
            and value['foreignFixtureUrl']==expected['foreignFixtureUrl'].rsplit('/runs/',1)[0])
        rows=unpack(value['payload']);need(len(rows)==1);json_digest(rows[0]);return rows[0]

    def history(self,key,scope,remove):
        root=self.root_value(key);exact(root,set(scope)|set(remove))
        need(root['phase']=='ready' and all(same(root[name],value) for name,value in scope.items()))
        reader=ChatSourceChunks(self.stores[key],scope);rows=reader.load(root['chunks']);self.chunks[key]=reader
        for index in range(len(rows)):self.file(reader.store(index).path)
        return root,rows

    def load(self):
        e=self.expected;run,url=e['runId'],e['fixtureUrl'];pid=int(e['binding']['processIdentity'].split(':',1)[0])
        self.owner=self.record('owner','owner');validate_owner(self.owner,run,url)
        need(self.owner['phase']=='cleaned' and self.owner['scriptUrl'] is not None
            and same(self.owner['binding'],e['binding']) and self.owner['ownerToken']==e['ownerToken'])
        self.role=self.record('role','actor')
        exact(self.role,{'sequence','native','runtime','browser','lifecycle','last','quiet','retired','images','publication','phase'})
        need(integer(self.role['sequence'],1) and type(self.role['images']) is list and len(self.role['images'])<=256)
        vm_scope=dict(picoBrowserVmVersion=1,runId=run,fixtureUrl=url,scriptUrl=self.owner['scriptUrl'],role='actor',binding=e['binding'])
        vm_root,vm_frames=self.history('vm',vm_scope,('phase','revision','chunks','quiet'))
        self.vm=BrowserOriginalVm(vm_root,vm_frames,pid)
        cleanup_epoch=math.ceil(self.role['phase']['activations'][-1]['activatedEpochMs'])
        need(any(entry['afterEpochMs']==cleanup_epoch for entry in self.vm.windows))
        for image in self.role['images']:
            exact(image,{'journalId','ticket','phase','metadata'});identifier(image['journalId']);identifier(image['ticket'])
            need(image['phase']=='saved');name=original_name(run,'actor',image['journalId']);raw=self.file(self.artifacts/name)
            expected=image['metadata'];info=(self.artifacts/name).lstat()
            need(same(expected,dict(device=info.st_dev,inode=info.st_ino,bytes=len(raw),mtimeNs=info.st_mtime_ns,
                ctimeNs=info.st_ctime_ns,sha256=hashlib.sha256(raw).hexdigest())))
            body=json.loads(raw);packed=unpack(body['payload']);need(len(packed)==1 and packed[0]['phase']=='complete')
            png=packed[0]['image'];data=self.file(self.artifacts/png['name'])
            png_stamp=self.files[('artifact',png['name'])]['stamp']
            need((png['file']['device'],png['file']['inode'])==tuple(png_stamp[:2])
                and len(data)==png['bytes'])
            source,_subject,facts=archive_sources(raw,data,run,image['ticket'],e['sceneUrl'],role='actor')
            need(source['binding']==e['binding'] and source['journalId']==image['journalId'] and source['artifactRoot']==e['artifactRoot']
                and source['scope']==dict(fixtureUrl=url,foreignFixtureUrl=e['foreignFixtureUrl'],ownerToken=e['ownerToken'],scriptUrl=self.owner['scriptUrl'])
                and name not in self.images)
            self.images[name]=dict(image=deepcopy(image),png=deepcopy(png),facts=deepcopy(facts),lifecycle=packed[0]['frame']['nativeBefore']['lifecycle'])
        history_scope=dict(binding=e['binding'],ownerToken=e['ownerToken'],runId=run,fixtureUrl=url,
            foreignFixtureUrl=e['foreignFixtureUrl'],artifactRoot=e['artifactRoot'],role='actor',sceneUrl=e['sceneUrl'])
        history_root,rows=self.history('history',dict(picoBrowserHistoryVersion=1,**history_scope),('phase','revision','chunks','intent'))
        self.source_history=PicoBrowserHistory(self.stores['history'],self.lock,history_scope,
            lambda frame,previous:validate_sample(frame,previous,owner=self.owner,run=run,fixture_url=url,
                foreign_url=e['foreignFixtureUrl'],vm=self.vm,image=lambda name:self.images[name]))
        self.source_history.matches(self.role);need(rows and self.role['publication']['phase']=='accepted')
        referenced={item['name'] for row in rows if row['event']=='sample' for item in row['original']['sample']['artifacts'] if item['kind']=='file'}
        need(referenced==set(self.images))
        quiet_scope=dict(picoBrowserQuietJournalVersion=1,runId=run,fixtureUrl=url,ownerToken=e['ownerToken'],binding=e['binding'])
        self.history('quiet',quiet_scope,('phase','revision','chunks'))
        self.quiet=PicoBrowserQuietJournal(self.stores['quiet'],self.lock,run,url,e['ownerToken'],e['binding'],self.owner['cleanupProof'])
        need(self.quiet.value['complete']);quiet_packet(self.role['quiet'],run,url,e['ownerToken'],pid,retired=True)
        need(self.role['quiet']['complete'])
        retirement_scope=dict(picoBrowserActorRetirementVersion=1,runId=run,role='actor',fixtureUrl=url,binding=e['binding'],
            ownerToken=e['ownerToken'],parentSha256=digest(self.stores['owner'].read()),roleSha256=digest(self.stores['role'].read()),
            historySha256=digest(history_root),vmSha256=digest(vm_root))
        self.retirement,frames=self.history('retirement',retirement_scope,('phase','chunks'));need(len(frames)==1 and self.vm.frame_count>0)
        self.inactive=deepcopy(frames[0]);validate_original_frame(self.inactive,self.owner,self.role,self.vm.frame(-1),self.vm.origin,
            self.source_history.last,run=run,fixture_url=url)
        original_history([frame['scripts'] for frame in self.vm.frames]+[self.inactive['scripts']],pid)

    def cache_digest(self):
        return json_digest(dict(expected=self.expected,root=self.root,manifest=self.manifest,owner=self.owner,role=self.role,
            images=self.images,inactive=self.inactive,retirement=self.retirement,files=[dict(key=list(key),value=value) for key,value in self.files.items()],
            vm=dict(scope=self.vm.scope,frames=self.vm.frames,origin=self.vm.origin,windows=self.vm.windows),
            history=dict(scope=self.source_history.scope,rows=self.source_history.rows),quiet=self.quiet.value,
            paths={key:str(store.path) for key,store in self.stores.items()},export=str(self.export.path),
            artifacts=str(self.artifacts),lock=str(self.lock.path)))

    def verify(self):
        self.lock.assert_held()
        try:
            need(not self.failed and self.cache_digest()==self.sealed and parent_node(self.export)==self.parent
                and parent_node(PrivateFeatureState(self.artifacts/'boundary.json'))==self.artifact_parent
                and state(self.export)==(self.root,self.raw,self.source_stamp))
            self.export_chunks.verify()
            for index,expected in enumerate(self.root['chunkStamps']):need(signature(self.export_chunks.store(index).path.lstat())==expected)
            for row in self.manifest:
                path=(self.export.path.parent if row['location']=='state' else self.artifacts)/row['name'];self.file(path)
            self.vm.verify();self.source_history.matches(self.role);self.quiet.verify()
            for reader in self.chunks.values():reader.verify()
            need(parent_node(self.export)==self.parent
                and parent_node(PrivateFeatureState(self.artifacts/'boundary.json'))==self.artifact_parent)
        except Exception:self.failed=True;raise


class PicoBrowserActorExport:
    """One immutable export from the actual successful warm retirement."""
    def __init__(self,retirement,original_request):
        from adapters.pico4.browser_actor_retirement import PicoBrowserActorRetirement
        need(type(retirement) is PicoBrowserActorRetirement and retirement.completed and not retirement.failed)
        identifier(original_request);need(getattr(retirement,'export_owner',None) is None)
        retirement.export_owner=self;self.retirement=retirement;flow=retirement.flow
        self.flow=flow;self.stores=dict(owner=flow.store,role=flow.role_store,history=retirement.history.store,
            vm=retirement.vm.store,retirement=retirement.store)
        self.store=PrivateFeatureState(flow.store.path.with_name('pico-tablet-web-actor-export.json'))
        self.failed=False;self.previous=None;self.graph=None;self.sender=None
        retirement.receipt()
        with flow.lock.held():
            need(self.store.read() is None);self.stores['quiet']=flow.cleanup_window(retirement.owner).store
            self.expected=dict(runId=flow.run,fixtureUrl=flow.fixture_url,foreignFixtureUrl=flow.foreign_url,
                artifactRoot=str(flow.artifact_root),sceneUrl=flow.adapter.scene_url,binding=deepcopy(retirement.owner['binding']),
                ownerToken=retirement.owner['ownerToken'],producerHostProcessIdentity=host_identity(),originalRequestId=original_request)
            self.scope=dict(picoBrowserActorExportVersion=VERSION,**self.expected)
            self.chunks=ChatSourceChunks(self.store,self.scope);self.chunks.inventory(0);manifest=[];names=set()
            def add(path):
                key=('state' if path.parent==self.store.path.parent else 'artifact',path.name)
                need(key not in names);names.add(key);raw,stamp=original(path)
                manifest.append(dict(location=key[0],name=key[1],sha256=hashlib.sha256(raw).hexdigest(),stamp=stamp))
            for key,store in self.stores.items():
                add(store.path);value=store.read()
                if key not in ('owner','role'):
                    for index in range(len(value['chunks'])):add(ChatSourceChunks(store,{}).store(index).path)
            for image in retirement.state['images']:
                name=original_name(flow.run,'actor',image['journalId']);add(flow.artifact_root/name)
                rows=unpack(json.loads(flow.metadata(name,image['metadata']))['payload']);need(len(rows)==1)
                add(flow.artifact_root/rows[0]['image']['name'])
            retirement.originals();need(len(manifest)<=LIMIT_FILES and sum(row['stamp'][5] for row in manifest)<=LIMIT_BYTES)
            self.write('reading',[],[])
            for start in range(0,len(manifest),32):
                chunks=self.chunks.append(dict(originals=manifest[start:start+32]),self.previous['chunks'])
                stamps=[signature(self.chunks.store(index).path.lstat()) for index in range(len(chunks))]
                self.write('reading',chunks,stamps)
            self.write('ready',self.previous['chunks'],self.previous['chunkStamps']);self.raw,self.source_stamp=raw_file(self.store)
            self.graph=PicoBrowserActorGraph(self.raw,self.source_stamp,self.store,self.stores,flow.lock,self.expected)
            retirement.originals();self.graph.verify()

    def write(self,phase,chunks,stamps):
        value={**self.scope,'phase':phase,'chunks':deepcopy(chunks),'chunkStamps':deepcopy(stamps)}
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def verify(self):
        need(not self.failed and self.graph is not None)
        try:
            with self.flow.lock.held():self.retirement.originals();self.graph.verify()
            return True
        except Exception:self.failed=True;raise

    def publish_return(self):
        """Only unchanged literal export bytes; no native query after closure."""
        from adapters.observer_return import ObserverReturnSender
        need(self.sender is None and self.verify())
        self.sender=ObserverReturnSender(
            PrivateFeatureState(self.store.path.with_name('pico-tablet-web-actor-return.json')),
            PrivateFeatureState(self.store.path.with_name('pico-tablet-web-actor-consumption.json')),
            {key:self.expected[key] for key in ('runId','producerHostProcessIdentity','originalRequestId')}|{'family':'pico-browser-actor'},
            self.raw,self.source_stamp,guard=self.verify)
        return self.sender.publish()

    def consume_return(self):
        need(self.sender is not None and self.verify());return self.sender.consume()
