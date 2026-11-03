"""Read-only Background3 admission bill for the existing Lifecycle namespace.

This is deliberately closed over the current producer filenames. Unrecognized
or pending originals prevent another acquisition; they are never ignored,
rewritten, adopted or removed. The bill grants no source or input authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
import re
import stat
from copy import deepcopy

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.chat_journey.source_bundles import decode_parts,logical_bytes
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import exact,integer,need
from adapters.pico4 import lifecycle_world_codec
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES,MAX_RAW

PART=65536
ROOTS={
    'lifecycle-actor-originals.json':('picoLifecycleActorSourceVersion',(1,2)),
    'lifecycle-primary-observation.json':('lifecyclePrimaryObservationVersion',(1,2,3)),
    'lifecycle-primary-operations.json':('lifecyclePrimaryOperationsVersion',(1,2,3)),
    'lifecycle-background-originals.json':('lifecycleBackgroundOriginalsVersion',(1,)),
    'lifecycle-background-owner.json':('lifecycleBackgroundOwnerVersion',(1,3,4)),
    'lifecycle-chat-owner.json':('lifecycleChatOwnerVersion',(1,)),
    'lifecycle-editor-owner.json':('lifecycleEditorOwnerVersion',(1,)),
    'lifecycle-x-join.json':('lifecycleXJoinVersion',(1,)),
    'lifecycle-x-back-owner.json':('lifecycleBackOwnerVersion',(1,)),
    'lifecycle-world-owner.json':('lifecycleWorldOwnerVersion',(1,2)),
    'lifecycle-process-owner.json':('lifecycleProcessOwnerVersion',(1,2)),
    'lifecycle-restore-owner.json':('lifecycleRestoreOwnerVersion',(1,)),
}
METADATA={'lifecycle-actor-worker-exit-diagnostics.json',
    'lifecycle-actor-world-source-diagnostics.json','lifecycle-original-source-worker-config.json'}
LOCKS={'script-sources.lock','lifecycle-x-back-owner.lock'}
WORKER='lifecycle-original-source-worker.py'


def canonical_size(value,limit=MAX_RAW):
    """Exact ASCII-canonical JSON length without constructing the whole DTO."""
    active=set()
    def text(value):
        size=2+len(value)+value.count('"')+value.count('\\')
        for match in re.finditer(r'[\x00-\x1f\x7f-\U0010ffff]',value):
            char=match[0];size+=1 if char in '\b\f\n\r\t' else 11 if ord(char)>65535 else 5
        return size
    def count(item):
        kind=type(item)
        if kind is str:result=text(item)
        elif kind in (dict,list):
            need(id(item) not in active);active.add(id(item))
            if kind is dict:
                need(all(type(key) is str for key in item))
                result=2+max(0,len(item)-1)+sum(text(key)+1+count(child) for key,child in item.items())
            else:result=2+max(0,len(item)-1)+sum(count(child) for child in item)
            active.remove(id(item))
        else:
            need(kind in (int,float,bool,type(None)));result=len(canonical(item))
        need(result<=limit);return result
    return count(value)


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:need(key not in result);result[key]=value
        return result
    def invalid(_value):need(False)
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    need(type(value) is dict and canonical(value)+b'\n'==raw);return value


class LifecycleNamespaceBill:
    """Actual files and all expanded copies, under the original SourceLock.

    A live owner's expanded state is explicitly additive to its stored packed
    representation. Three complete largest-state CAS/projection copies remain
    reserved, along with three full 64KiB atomic metadata files. Range-journal
    files are excluded here and are charged by AudioRawArchive itself.
    """
    def __init__(self,path,lock,*,expanded=lambda:None,mutex_layout=1):
        need(type(mutex_layout) is int and mutex_layout in (1,2))
        self.mutex_layout=self._mutex_layout=mutex_layout
        self.path=self._path=path;self.lock=self._lock=lock;self.expanded=self._expanded=expanded
        self._expanded_guard=self._original_expanded_guard=None
        self._expanded_owner=self._original_expanded_owner=None
        self.directory=OriginalDescriptor(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.last=None;self.maximum=None;self.lease=self._lease=None
        self.mutex_observations=self._mutex_observations=()
        self._mutex_seal=(self._mutex_observations,2)
        self.capacity_bill=self._capacity_bill=None;self._admitted_bill=self._original_budget=None
        self._write=None
        self._mutex_ledger=self._original_mutex_ledger=None
        if mutex_layout==2:
            try:
                from adapters.pico4.lifecycle_mutex_ledger import LifecycleMutexLedger2
                ledger=LifecycleMutexLedger2.__new__(LifecycleMutexLedger2)
                self._mutex_ledger=self._original_mutex_ledger=ledger
                LifecycleMutexLedger2.__init__(ledger,self)
                self.mutex_observations=self._mutex_observations=ledger.view
            except BaseException:
                from adapters.pico4.lifecycle_background_raw_state import close_or_retain
                close_or_retain(path,self);raise

    def mutex_guard(self,*,active=False):
        need(type(self.mutex_layout) is int and self.mutex_layout==self._mutex_layout and self.mutex_layout in (1,2))
        if self.mutex_layout==2:
            need(self._mutex_ledger is self._original_mutex_ledger)
            self._mutex_ledger.active() if active else self._mutex_ledger.require()

    def write_extra(self):return 0 if self._write is None else self._write[4]

    def bind_expanded_guard(self,owner):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
        need(type(owner) is LifecycleSourceRaw4 and owner.namespace is self and owner.source_bill is self
            and owner.lock is self.lock and owner.path.parent==self.path and self.lease is None and self._write is None
            and self._expanded_guard is self._original_expanded_guard is None
            and self._expanded_owner is self._original_expanded_owner is None
            and owner.archive.state['reads']==0 and not owner.archive.state['pending']
            and not owner.archive.state['parts'] and not owner.archive.state['pages'])
        self._expanded_owner=self._original_expanded_owner=owner
        self._expanded_guard=self._original_expanded_guard=owner.require_expanded

    def guard_expanded(self,value,size):
        need(self._expanded_guard is self._original_expanded_guard
            and self._expanded_owner is self._original_expanded_owner)
        if self._expanded_guard is None:need(self._expanded_owner is None)
        else:self._expanded_guard(value,size)

    def begin_write(self,gate,permit,*,parts,stored,decoded,metadata):
        from adapters.pico4.lifecycle_write_gate import LifecycleWriteGate,WritePermit
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4,FamilyPermit4
        need(((type(gate) is LifecycleWriteGate and type(permit) is WritePermit)
            or (type(gate) is LifecycleFamilyGate4 and type(permit) is FamilyPermit4))
            and gate.namespace is self and permit.gate is gate and self._write is None)
        current=self();raw=gate.raw.archive.bill();pending=gate.raw.archive.state['pending']
        need(current['parts']+raw['parts']+sum(row['parts'] for row in pending)+parts<=MAX_FRAMES
            and current['storedBytes']+raw['storedBytes']+sum(row['limit'] for row in pending)+stored<=MAX_RAW
            and current['decodedBytes']+self.capacity_bill()+decoded<=MAX_RAW)
        need(integer(metadata,0,decoded));self._write=(gate,permit,parts,stored,decoded,object(),metadata)

    def spend_metadata(self,gate,permit,count):
        need(self._write is not None and self._write[:2]==(gate,permit)
            and integer(count,0,self._write[6]))
        owner,value,parts,stored,decoded,token,metadata=self._write
        self._write=(owner,value,parts,stored,decoded-count,token,metadata-count)

    def write_guard(self,gate,permit,prepared):
        need(self._write is not None and self._write[:2]==(gate,permit))
        self.lock.assert_held();require_directory(self.directory,self.path)
        need(self.lease is self._lease and self.lease is not None)
        names,pins=self.lease;need(set(self.lease_names())==set(names)|set(prepared))
        updated=[]
        for name,stamp in pins:
            actual=tuple(signature((self.path/name).lstat()))
            if actual!=stamp:self.observe_mutex(name,stamp,actual)
            updated.append((name,actual))
        for name,row in prepared.items():
            need(row['physical'] is not None and row['owner'].closed and not row['owner'].lost
                and tuple(signature((self.path/name).lstat()))==tuple(row['physical'])
                and row['owner'].node==tuple(row['physical'][:2]))
        self.lease=self._lease=(names,tuple(updated))

    def subwrite(self,gate,child,root):
        need(self._write is not None and self._write[:2]==(gate,child))
        self._write=(gate,root,*self._write[2:])

    def resume_child(self,gate,root,child):
        need(self._write is not None and self._write[:2]==(gate,root))
        self._write=(gate,child,*self._write[2:])

    def commit_write(self,gate,permit,root_stamp,prepared):
        need(self._write is not None and self._write[:2]==(gate,permit))
        names,pins=self.lease;root=gate.writer.store.path.name;actual=self.lease_names()
        need(set(actual)==set(names)|set(prepared));updated={}
        for name,stamp in pins:
            current=tuple(signature((self.path/name).lstat()))
            if name==root:need(current==tuple(root_stamp))
            elif current!=stamp:self.observe_mutex(name,stamp,current)
            updated[name]=current
        for name,row in prepared.items():
            need(row['owner'].closed and not row['owner'].lost
                and tuple(signature((self.path/name).lstat()))==tuple(row['physical'])
                and row['owner'].node==tuple(row['physical'][:2]))
            updated[name]=tuple(row['physical'])
        self.lease=self._lease=(actual,tuple(sorted(updated.items())))

    def finish_write(self,gate,permit):
        need(self._write is not None and self._write[:2]==(gate,permit))
        token=self._write[5];self(_write_token=token);self._write=None

    def bind_raw_capacity(self,callback):
        need(self.capacity_bill is None and callable(callback))
        self.capacity_bill=self._capacity_bill=callback

    def metadata_bytes(self):
        self.mutex_guard()
        if self.mutex_layout==2:return self._mutex_ledger.metadata_bytes()
        need(self.mutex_observations is self._mutex_observations is self._mutex_seal[0])
        return self._mutex_seal[1]

    def observe_mutex(self,name,before,after):
        # A zero-byte session mutex has deliberately mutable ctime: the actual
        # existing Session._lock fchmod does this. This does NOT identify the
        # actor which caused a refresh or authorize source/SDK/input facts.
        need(re.fullmatch(r'session-[0-9a-f]{32}\.lock',name) is not None
            and before[:7]==after[:7] and before[5]==0 and before[2]&0o777==0o600
            and before[3]==os.geteuid() and before[4]==1 and after[7]>=before[7])
        if before==after:return
        self.mutex_guard(active=True)
        if self.mutex_layout==2:return self._mutex_ledger.observe(name,before,after)
        need(len(self.mutex_observations)<MAX_FRAMES and self._admitted_bill is self._original_budget
            and self._admitted_bill is not None and self.capacity_bill is self._capacity_bill)
        old=self.metadata_bytes();record=(name,tuple(before),tuple(after))
        size=canonical_size(dict(name=name,before=list(before),after=list(after)))
        new=old+size+(1 if self.mutex_observations else 0)
        budget=dict(self._admitted_bill);raw=self.capacity_bill()
        # Retained ledger, canonical evidence view and old/new append overlap.
        # There is no filesystem ledger/CAS and thus no invented stored file.
        need(budget['decodedBytes']-3*budget['mutexBytes']+3*new+raw<=MAX_RAW)
        self.mutex_observations=self._mutex_observations=(*self._mutex_observations,record)
        self._mutex_seal=(self._mutex_observations,new)

    def lease_names(self):
        names=sorted(os.listdir(self.path));need(len(names)<=4096)
        return tuple(name for name in names if name!='lifecycle-background-raw.json'
            and not name.startswith('lifecycle-background-raw.json.'))

    def guard_lease(self,*,_write_token=None):
        self.mutex_guard(active=True)
        self.lock.assert_held();require_directory(self.directory,self.path)
        need(self._write is None or _write_token is self._write[5])
        need(self.lease is not None and self.lease is self._lease)
        names,pins=self.lease;need(self.lease_names()==names);updated=[]
        for name,stamp in pins:
            actual=tuple(signature((self.path/name).lstat()))
            if actual!=stamp:self.observe_mutex(name,stamp,actual)
            updated.append((name,actual))
        self.lease=self._lease=(names,tuple(updated))
        require_directory(self.directory,self.path)

    def owner_cas(self,store,value):
        # Only the exact Background3 owner's already executed local CAS may
        # update this one metadata pin within its reserved three64KiB overlap.
        self.lock.assert_held();require_directory(self.directory,self.path);need(self._write is None)
        need(store.path==self.path/'lifecycle-background-owner.json'
            and self.lease is not None and self.lease is self._lease)
        need(type(value) is dict and type(value.get('lifecycleBackgroundOwnerVersion')) is int
            and value['lifecycleBackgroundOwnerVersion']==3 and store.read()==value)
        names,pins=self.lease;actual=self.lease_names()
        need(set(actual)==set(names)|{store.path.name})
        for name,stamp in pins:
            if name!=store.path.name:need(tuple(signature((self.path/name).lstat()))==stamp)
        info=store.path.lstat();need(0<info.st_size<=PART and canonical_size(value)+1==info.st_size)
        updated={name:stamp for name,stamp in pins};updated[store.path.name]=tuple(signature(info))
        self.lease=self._lease=(actual,tuple(sorted(updated.items())))

    def phase_writer(self,owner):
        """Only the existing warm Operations writer's actual root/part pins."""
        from adapters.pico4.lifecycle_operations import PicoLifecycleOperations
        need(self._write is None and type(owner) is PicoLifecycleOperations and owner.lock is self.lock
            and owner.store.path==self.path/'lifecycle-primary-operations.json'
            and self.lease is not None and self.lease is self._lease)
        owner.bound(saved=True)
        history=owner.history;need(history.root is owner.store
            and tuple(history.identities)==owner.chunk_identities)
        original={owner.store.path.name:tuple(owner.stamp)}
        for index in range(len(history.identities)):
            need(history.signature(index)==history.identities[index])
            path=history.store(index).path;original[path.name]=tuple(signature(path.lstat()))
        names,pins=self.lease;current=self.lease_names()
        need(set(current)==set(names)|set(original));updated={}
        for name,stamp in pins:
            actual=tuple(signature((self.path/name).lstat()))
            if name in original:
                if name!=owner.store.path.name:need(actual==stamp)
                need(actual==original[name])
            elif actual!=stamp:self.observe_mutex(name,stamp,actual)
            updated[name]=actual
        for name,stamp in original.items():
            need(tuple(signature((self.path/name).lstat()))==stamp);updated[name]=stamp
        owner.bound(saved=True)
        self.lease=self._lease=(current,tuple(sorted(updated.items())))

    def __call__(self,*,_write_token=None):
        self.mutex_guard(active=True)
        need(self.path is self._path and self.lock is self._lock and self.expanded is self._expanded)
        self.lock.assert_held();require_directory(self.directory,self.path)
        need(self._write is None or _write_token is self._write[5])
        if self.lease is not None:self.guard_lease(_write_token=_write_token)
        names=sorted(os.listdir(self.path));need(len(names)<=4096)
        values={};stored=parts=decoded=0;physical={};largest=0;prepaid=set()
        held=0 if self.capacity_bill is None else self.capacity_bill()
        if self._write is not None:
            held-=self.write_extra();held+=self._write[0].finish_bytes(self._write[1])

        # Entire actual namespace first. A late-sorted original is not free
        # space while an earlier packed root is being parsed/decompressed.
        for name in names:
            if name=='lifecycle-background-raw.json' or name.startswith('lifecycle-background-raw.json.'):
                continue
            is_session=re.fullmatch(r'session-[0-9a-f]{32}\.(json|lock)',name) is not None
            is_chunk=re.fullmatch(r'(.+\.json)\.frame-([0-9]{3})\.json',name)
            need(name in ROOTS or name in METADATA or name in LOCKS or name==WORKER or is_session or is_chunk)
            if is_chunk:need(is_chunk[1] in ROOTS)
            info=(self.path/name).lstat()
            need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600
                and info.st_nlink==1 and info.st_uid==os.geteuid() and 0<=info.st_size<=PART)
            if name in LOCKS or name.endswith('.lock'):need(info.st_size==0)
            physical[name]=signature(info);stored+=info.st_size
        need(3*stored+3*PART+held<=MAX_RAW)
        if self.lease is not None:
            need(self.lease is self._lease)
            old=dict(self.lease[1])
            for name,stamp in physical.items():
                if name in old and tuple(stamp)!=old[name] and re.fullmatch(r'session-[0-9a-f]{32}\.lock',name):
                    self.observe_mutex(name,old[name],tuple(stamp))

        def preflight(size):
            need(integer(size,0,MAX_RAW) and 3*stored+decoded+size+3*PART+held<=MAX_RAW)

        def charge(size):
            nonlocal decoded
            preflight(size)
            decoded+=size

        def expand(value):
            if type(value) is dict:
                if set(value)=={'encoding','bytes','sha256','data'}:
                    need(integer(value['bytes'],2,MAX_RAW))
                    # Uncompressed bytes, parsed DTO and canonical validation
                    # may coexist inside the unchanged bounded decoder.
                    preflight((2 if id(value) in prepaid else 3)*value['bytes'])
                    if id(value) not in prepaid:charge(value['bytes'])
                    result=(lifecycle_world_codec.unpack(value,2)
                        if value['encoding']=='xz-base64-json' else unpack(value))
                    expand(result)
                else:
                    for child in value.values():expand(child)
            elif type(value) is list:
                for child in value:expand(child)
            elif type(value) is str and value.startswith(('{','[')):
                # Preflight the parser/canonical-output overlap before parsing.
                # JSON cannot expand its original UTF8 by more than sixfold.
                size=len(value.encode('utf-8'));preflight(6*size)
                try:parsed=json.loads(value)
                except (ValueError,TypeError):return
                charge(len(canonical(parsed)));expand(parsed)

        for name in names:
            if name=='lifecycle-background-raw.json' or name.startswith('lifecycle-background-raw.json.'):
                continue
            is_chunk=re.fullmatch(r'(.+\.json)\.frame-([0-9]{3})\.json',name)
            path=self.path/name;before=physical[name];need(signature(path.lstat())==before)
            info=path.lstat()
            if name in LOCKS or name.endswith('.lock'):
                continue
            owner=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                owner.require(owner.fd);raw=os.pread(owner.fd,PART+1,0);owner.require(owner.fd)
                need(signature(os.fstat(owner.fd))==before==signature(path.lstat()) and len(raw)==info.st_size)
            finally:need(owner.close())
            if name!=WORKER:preflight(5*len(raw))
            value=None if name==WORKER else strict(raw)
            if name==WORKER:continue
            values[name]=value
            if name in ROOTS:
                key,versions=ROOTS[name]
                need(type(value.get(key)) is int and value[key] in versions)
            if is_chunk:parts+=1
            if 'payload' in value:largest=max(largest,value['payload']['bytes'])

        # Complete declared outer decoder/bundle/copy bill precedes the FIRST
        # decompression. A later root or live owner is not future free space.
        def declare(value):
            if type(value) is dict:
                if set(value)=={'encoding','bytes','sha256','data'}:
                    need(integer(value['bytes'],2,MAX_RAW));charge(value['bytes']);prepaid.add(id(value))
                else:
                    for child in value.values():declare(child)
            elif type(value) is list:
                for child in value:declare(child)
        for name,value in values.items():
            declare(value)
            if name in ROOTS:
                if 'bundles' in value:
                    logical_bytes(value['bundles'])
                    for reference in value['bundles']:charge(reference['bytes'])
                if 'decodedSourceBytes' in value:charge(value['decodedSourceBytes'])
        state=self.expanded()
        if state is not None:
            size=canonical_size(state,MAX_RAW-3*stored-decoded-3*PART-held)
            self.guard_expanded(state,size)
            charge(size);largest=max(largest,size)
        else:self.guard_expanded(None,0)
        charge(3*largest);charge(3*self.metadata_bytes())
        for value in values.values():expand(value)

        for name,value in values.items():
            if name not in ROOTS:continue
            manifest=value.get('chunks')
            if manifest is None:continue
            need(type(manifest) is list and len(manifest)<=MAX_FRAMES)
            frames=[];scope=None
            for index,digest in enumerate(manifest):
                child_name=name+f'.frame-{index:03d}.json';need(child_name in values)
                child=values[child_name];exact(child,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
                need(type(child['chatSampleChunkVersion']) is int and child['chatSampleChunkVersion']==1
                    and type(child['index']) is int and child['index']==index and json_digest(child)==digest)
                if scope is None:scope=child['scopeSha256']
                need(child['scopeSha256']==scope)
                frames.extend(unpack(child['transcript']))
            need({child for child in values if child.startswith(name+'.frame-')}
                =={name+f'.frame-{index:03d}.json' for index in range(len(manifest))})
            if 'bundles' in value:
                logical_bytes(value['bundles']);offset=0
                for index,reference in enumerate(value['bundles']):
                    preflight(2*reference['bytes']);count=reference['parts']
                    original,_raw=decode_parts(frames[offset:offset+count],reference,index)
                    offset+=count;expand(original)
                need(offset==len(frames))

        for name in values:
            chunk=re.fullmatch(r'(.+\.json)\.frame-([0-9]{3})\.json',name)
            if chunk:need(chunk[1] in values and 'chunks' in values[chunk[1]])
        if state is not None:
            expand(state)
        # Full stored originals coexist with expanded state and actual CAS
        # projections; no equal-byte deduplication cancels another copy.
        # Disk bytes, read-pass exact bytes and decoded JSON DTOs are separate
        # representations. All packed/chunk/bundle/CAS expansions are additive.
        # No mutable decoded DTO, child-frame or cost cache survives this pass.
        result=dict(parts=parts,storedBytes=stored+3*PART,
            decodedBytes=3*stored+decoded+3*PART,files=len(physical)+3)
        need(result['parts']<=MAX_FRAMES and max(result['storedBytes'],result['decodedBytes'])<=MAX_RAW)
        need(names==sorted(os.listdir(self.path)))
        for name,stamp in physical.items():need(signature((self.path/name).lstat())==stamp)
        require_directory(self.directory,self.path);self.last=deepcopy(result)
        self._admitted_bill=self._original_budget=tuple(sorted({**result,'mutexBytes':self.metadata_bytes()}.items()))
        self.lease=self._lease=(tuple(sorted(physical)),tuple((name,tuple(stamp)) for name,stamp in sorted(physical.items())))
        if self.maximum is None:self.maximum=deepcopy(result)
        else:self.maximum={key:max(self.maximum[key],value) for key,value in result.items()}
        return result

    def close(self):
        sealed=True
        try:self.mutex_guard()
        except BaseException:sealed=False
        closed=self.directory.close()
        return sealed and closed and (self._mutex_layout==1 or self._original_mutex_ledger.close())
