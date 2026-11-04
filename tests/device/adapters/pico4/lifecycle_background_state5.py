"""Typed Background5 temporary original graphs over one original Raw4 bank.

Graph retirement grants no input, fresh source or native release authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import marshal
import math
from adapters.normal_ui import NativeUIError
import json
from dataclasses import dataclass
from types import FunctionType,MethodType

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import LIMIT,need,integer
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.history import MAX_RAW,MAX_FRAMES

PART=65536


# Reuses the reviewed ChatReader3 sorted-marshal2 value-signature pattern.
# This local bounded normalizer has no self-capturing closure, no persisted
# signature/loads, and no source/file/callback/clock authority.
class _SignatureFallback(Exception):pass

def _signature_ordered(item,budget,active,depth):
    if depth>64:raise _SignatureFallback()
    kind=type(item)
    if kind is dict:
        budget[0]-=256+96*len(item)
        if budget[0]<0 or id(item) in active:raise _SignatureFallback()
        if not all(type(key) is str for key in item):raise _SignatureFallback()
        active.add(id(item))
        try:
            result={}
            for key in sorted(item):
                budget[0]-=96+4*len(key)
                if budget[0]<0:raise _SignatureFallback()
                result[key]=_signature_ordered(item[key],budget,active,depth+1)
            return result
        finally:active.remove(id(item))
    if kind is list:
        budget[0]-=64+16*len(item)
        if budget[0]<0 or id(item) in active:raise _SignatureFallback()
        active.add(id(item))
        try:return [_signature_ordered(child,budget,active,depth+1) for child in item]
        finally:active.remove(id(item))
    if kind is str:budget[0]-=96+4*len(item)
    elif kind is int:budget[0]-=64+2*((item.bit_length()+14)//15)
    elif kind is float:
        if not math.isfinite(item):raise _SignatureFallback()
        budget[0]-=32
    elif kind is bool or kind is type(None):budget[0]-=16
    else:raise NativeUIError('Lifecycle metadata has an invalid exact type')
    if budget[0]<0:raise _SignatureFallback()
    return item


def _result_signature(value,size):
    # Initial canonical/grammar admission remains separate. The warm copy and
    # output are bounded by a prospectively charged per-result scratch window.
    try:return marshal.dumps(_signature_ordered(value,[12*size+3*65536],set(),0),2)
    except (_SignatureFallback,ValueError,TypeError,RecursionError):return None


def _feature_reader(reader,proof):
    """Pure raw entry proof before any descriptor binding; no SDK callback."""
    from adapters.native_feature_observation import NativeFeatureObservation
    need(type(proof) is tuple and len(proof)==6)
    need(proof[0] is NativeFeatureObservation and type(reader) is NativeFeatureObservation
        and type.__getattribute__(NativeFeatureObservation,'__mro__') is proof[3])
    namespace=type.__getattribute__(NativeFeatureObservation,'__dict__')
    read=namespace.get('read')
    need(type(read) is FunctionType and read is proof[1] and read.__code__ is proof[2]
        and '__getattribute__' not in namespace and '__getattr__' not in namespace
        and all(name not in namespace for name in ('sequence','instance','pid','ios','send','original','before_io')))
    bound=object.__getattribute__(reader,'read')
    need(type(bound) is MethodType and bound.__self__ is reader and bound.__func__ is read)
    return read


@dataclass(eq=False)
class OriginalGraph5:
    holder:object
    source:object
    reserve:int
    graph:object=None
    batch:object=None
    result:object=None
    failed:bool=False
    choices:object=None
    signature:bytes|None=None
    reserve_seal:object=None

    def reserve_before(self,value):
        need(integer(value,0,MAX_RAW))
        self.reserve=value;self.reserve_seal=(self,value)


class LifecycleBackgroundState5:
    def __init__(self,owner,bank):
        from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
        need(type(owner) is PicoLifecycleBackground and owner.version==5
            and type(bank) is LifecycleSourceRaw4 and owner.originals is bank
            and owner.lock is bank.lock and owner.run==bank.run and owner.binding==bank.binding
            and owner._state_choice is owner._original_state_choice and owner._state_choice==(5,)
            and bank.background_state5 is bank._background_state5 is self
            and owner.state5 is owner._state5 is self and bank.archive.state['reads']==0)
        self.owner,self.bank=owner,bank
        self._fixed=self._original_fixed=(owner,bank)
        self.quiet=self._quiet=None;self.quiet_request=self._quiet_request=None
        self.active=None;self.held=self._held=[];self._held_seal=();self.save_stage=None;self.selection=self._selection=None;self.failed=False
        self.results=self._results=();self._result_seal=self._original_result_seal=(self.results,0,0)
        self.signature_codec=self._original_signature_codec=(marshal.dumps,_result_signature,
            _result_signature.__code__,_signature_ordered,_signature_ordered.__code__,math.isfinite,PART,MAX_RAW)
        self.methods=tuple(getattr(PicoLifecycleBackground,name) for name in
            ('_validate_plain','_packet_plain','_report_plain','_before_ui_plain','_save_plain'))
        self._methods=self.methods;self._codes=tuple(method.__code__ for method in self.methods)
        from adapters.native_feature_observation import NativeFeatureObservation
        read=type.__getattribute__(NativeFeatureObservation,'__dict__')['read']
        need(type(read) is FunctionType)
        self.feature_proof=self._feature_proof=(NativeFeatureObservation,read,read.__code__,
            type.__getattribute__(NativeFeatureObservation,'__mro__'),_feature_reader,_feature_reader.__code__)
        # Chosen before the first source IO. This permanent work reservation
        # covers the bounded current raw/string/DTO projection, including an
        # unknown result, in addition to the existing full archive batch bill.
        self.feature_work=self._feature_work=(6*LIMIT+3*PART,)
        from adapters.pico4.lifecycle_quiet_step5 import QuietBook5,capture_api,guard_api
        self.quiet_api=self._quiet_api=capture_api()
        self.quiet_guard=self._quiet_guard=(guard_api,guard_api.__code__)
        book=object.__new__(QuietBook5);self.quiet=self._quiet=book
        helper_method(self,'quiet_book')().__init__(self)
        helper_method(self,'preflight')()

    def guard(self):
        from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
        need(self._fixed is self._original_fixed and self._fixed[0] is self.owner and self._fixed[1] is self.bank
            and self.owner.state5 is self.owner._state5 is self
            and self.bank.background_state5 is self.bank._background_state5 is self
            and self.owner.version==5 and self.owner.originals is self.bank
            and self.owner._state_choice is self.owner._original_state_choice and self.owner._state_choice==(5,)
            and self.methods is self._methods and all(a is b for a,b in zip(self.methods,
                (PicoLifecycleBackground._validate_plain,PicoLifecycleBackground._packet_plain,
                    PicoLifecycleBackground._report_plain,PicoLifecycleBackground._before_ui_plain,PicoLifecycleBackground._save_plain)))
            and all(method.__code__ is code for method,code in zip(self.methods,self._codes)))
        from adapters.pico4.lifecycle_quiet_step5 import QuietBook5
        need(self.quiet is self._quiet and type(self.quiet) is QuietBook5)
        self.bank.lock.assert_held()

    def metadata_bytes(self):
        # Resource bill remains available after a business failure. Exact graph
        # mutations refuse capacity; neither a mutable cached cost nor a lost
        # local can make a previously acquired object disappear from the bill.
        need(self._result_seal is self._original_result_seal and self.results is self._results is self._result_seal[0])
        codec=self.signature_codec
        need(codec is self._original_signature_codec and marshal.dumps is codec[0]
            and _result_signature is codec[1] and _result_signature.__code__ is codec[2]
            and _signature_ordered is codec[3] and _signature_ordered.__code__ is codec[4]
            and math.isfinite is codec[5] and type(PART) is int and type(MAX_RAW) is int
            and PART==codec[6] and MAX_RAW==codec[7])
        need(self.feature_work is self._feature_work and type(self.feature_work) is tuple
            and len(self.feature_work)==1 and type(self.feature_work[0]) is int
            and self.feature_work[0]==6*LIMIT+3*PART)
        total=1024;work=0
        for value,size,digest,signature in self.results:
            need(type(size) is int and 0<=size<=MAX_RAW and type(digest) is str)
            if signature is not None:
                window=12*size+3*PART
                need(type(signature) is bytes and 0<len(signature)<=window)
                work=max(work,4*window)
                current=_result_signature(value,size)
            else:current=None
            if signature is None or current!=signature:
                # No signature change ever reseals/reinterprets the canonical
                # contract; Unicode/surrogate spelling aliases keep its exact
                # old size/SHA fallback. Changed values/types still fail.
                need(canonical_size(value,size)==size and json_digest(value)==digest)
            current=None # Free the candidate before the next warm audit.
            total+=3*size+256+(0 if signature is None else 3*len(signature))
        need(total==self._result_seal[1]+1024 and work==self._result_seal[2])
        # All later audits reserve one largest actual current normalizer/output
        # work window, including before metadata verification allocates it.
        total+=work+self.feature_work[0]+helper_method(self,'quiet_book')().metadata_bytes()
        need(self.held is self._held and len(self.held)==len(self._held_seal)
            and all(stage is fixed for stage,fixed in zip(self.held,self._held_seal)))
        for stage in self.held:
            need(type(stage) is OriginalGraph5 and stage.holder is self
                and integer(stage.reserve,0,MAX_RAW) and type(stage.reserve_seal) is tuple
                and len(stage.reserve_seal)==2 and stage.reserve_seal[0] is stage
                and type(stage.reserve_seal[1]) is int and stage.reserve==stage.reserve_seal[1])
            total+=stage.reserve
        return total

    def quiet_book(self):
        from adapters.pico4.lifecycle_quiet_step5 import guard_api
        need(self.quiet_api is self._quiet_api and type(self.quiet_guard) is tuple and len(self.quiet_guard)==2
            and self.quiet_guard is self._quiet_guard
            and type(guard_api) is FunctionType and guard_api is self.quiet_guard[0]
            and guard_api.__code__ is self.quiet_guard[1] and self.quiet is self._quiet)
        return self.quiet_guard[0](self.quiet,self.quiet_api)

    def begin_quiet_invocation(self):
        return helper_method(self,'quiet_book')().token()

    def quiet_step(self,row,handle,invocation,role):
        request=helper_method(self,'quiet_book')().prepare(row,handle,invocation,role)
        try:
            need(self.quiet_request is self._quiet_request is None)
            self.quiet_request=self._quiet_request=request
            helper_method(self,'call')(row,'quiet')
            result=helper_method(self,'quiet_book')().finish(request)
            self.quiet_request=self._quiet_request=None
            return result
        except BaseException:
            helper_method(self,'quiet_book')().fail(request);raise

    def read_feature_original(self,reader):
        """One original Native read and its SAME durable raw; no second getter."""
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        from adapters.native_feature_observation import NativeFeatureObservation,decode
        stage=OriginalGraph5(self,reader,0);stage.reserve_before(0)
        self.held.append(stage);self._held_seal=(*self._held_seal,stage)
        try:
            helper_method(self,'guard')();need(not self.failed and not self.bank.failed and not self.bank.frozen
                and self.active is None and self.save_stage is None)
            self.active=stage;proof=self.feature_proof
            need(type(proof) is tuple and len(proof)==6 and proof is self._feature_proof
                and type(_feature_reader) is FunctionType and _feature_reader is proof[4]
                and _feature_reader.__code__ is proof[5])
            read=proof[4](reader,proof)
            self.bank.check_hooks();hook=self.bank.hooks.get('feature')
            need(type(hook) is tuple and len(hook)==8 and hook[0] is reader
                and type(reader.pid) is int and reader.pid==self.owner.pid and reader.ios is False
                and type(reader.sequence) is int and reader.sequence>=0)
            floor=self.bank.archive.state['reads'];sequence=reader.sequence
            helper_method(self,'preflight')() # All fixed work is booked BEFORE Native's SDK callbacks.
            value=proof[1](reader,sequence)
            stage.source=value # Acquired return first, before any later guard/copy.
            need(type(value) is dict and type(reader.pid) is int and reader.pid==self.owner.pid
                and type(value.get('processId')) is int and value['processId']==reader.pid
                and type(reader.instance) is str and type(value.get('instance')) is str
                and value['instance']==reader.instance and type(value.get('requestId')) is str
                and type(reader.sequence) is int and type(value.get('sequence')) is int
                and value['sequence']==reader.sequence and value['sequence']>sequence)
            canonical_size(value,LIMIT);helper_method(self,'preflight')()
            batch,records=self.bank.verify(materialize=True);stage.batch=batch
            index=max((index for index,row in records.items() if row['role']=='feature'),default=-1)
            need(index>=floor and index in records);record=records[index];command=record['command']
            need(record['kind']=='utf8' and type(command) is dict
                and set(command)=={'schemaVersion','commandId','action'}
                and type(command['schemaVersion']) is int and command['schemaVersion']==1
                and command['action']=='feature-native-observe'
                and command['commandId']==value.get('requestId'))
            stage.result=batch[index].decode('utf-8');stage.graph=decode(stage.result)
            need(stage.graph==value and json_digest(stage.graph)==json_digest(value))
            self.bank.verify();helper_method(self,'guard')();self.bank.check_hooks()
            need(type(proof) is tuple and len(proof)==6 and proof is self._feature_proof
                and type(_feature_reader) is FunctionType and _feature_reader is proof[4]
                and _feature_reader.__code__ is proof[5])
            need(proof[4](reader,proof) is read)
            need(self.bank.hooks.get('feature') is hook and type(reader.sequence) is int
                and reader.sequence==value['sequence'] and type(reader.instance) is str
                and reader.instance==value['instance'] and not self.bank.failed and not self.bank.frozen)
            result=value,stage.result
            stage.graph=stage.batch=stage.source=stage.result=None
            batch=records=record=command=None
            need(self.held[-1] is stage and self._held_seal[-1] is stage)
            stage.reserve_seal=None;self.held.pop();self._held_seal=self._held_seal[:-1];self.active=None
            return result
        except BaseException:
            stage.failed=True;self.failed=True;self.bank.failed=True
            if not any(holder is self for _path,holder in UNRESOLVED):UNRESOLVED.append((self.bank.path.parent,self))
            raise

    def preflight(self):
        current=self.bank.other_bill();ours=self.bank.archive.bill()
        need(current['decodedBytes']+ours['decodedBytes']<=MAX_RAW)

    def save(self,value):
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        stage=OriginalGraph5(self,value,0);stage.reserve_before(0)
        self.held.append(stage);self._held_seal=(*self._held_seal,stage)
        try:
            helper_method(self,'guard')();need(self.save_stage is None and self.active is None and not self.failed)
            self.save_stage=stage
            need(self.selection is self._selection is None)
            stage.reserve_before(3*canonical_size(value)+3*PART)
            helper_method(self,'preflight')()
            self.methods[4](self.owner,value)
            need(self.active is None and self.held[-1] is stage and self._held_seal[-1] is stage)
            stage.source=None;stage.reserve_seal=None;self.held.pop();self._held_seal=self._held_seal[:-1];self.save_stage=None
            self.selection=self._selection=None
        except BaseException:
            stage.failed=True;self.failed=True;self.bank.failed=True
            if not any(holder is self for _path,holder in UNRESOLVED):UNRESOLVED.append((self.bank.path.parent,self))
            raise

    def call(self,value,kind):
        from adapters.pico4.lifecycle_source_raw import REFERENCE,key,VIEW_ROLES
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        # The acquired actual input graph is retained before any guard or bill.
        stage=OriginalGraph5(self,value,0);stage.reserve_before(0)
        self.held.append(stage);self._held_seal=(*self._held_seal,stage)
        try:
            helper_method(self,'guard')();need(not self.failed and not self.bank.failed and self.active is None
                and kind in ('validate','packet','report','ui','quiet') and len(self.results)<MAX_FRAMES)
            if kind=='quiet':
                need(self.quiet_request is self._quiet_request is self.quiet.active
                    and self.quiet_request is not None and self.quiet_request.row is value)
            self.active=stage;size=canonical_size(value)
            stage.reserve_before(3*size+6*LIMIT+8*PART);helper_method(self,'preflight')()
            batch,records=self.bank.verify(materialize=True);stage.batch=batch
            latest={}
            for index,record in records.items():
                if record['kind']=='utf8' and record['role'] in VIEW_ROLES['background']:
                    latest[record['role']]=max(latest.get(record['role'],-1),index)
            expanded=size;literal_bytes=0;view=self.bank.view('background');choices={}
            def original(item,path):
                role=self.role_at(kind,path)
                if set(item)==REFERENCE:
                    identity=key(item);need(identity in view.confirmed and identity[0]==role)
                    index=identity[2];need(records[index]['sha256']==identity[3]
                        and records[index]['role']==role)
                else:
                    need(set(item)=={'raw','sha256'} and type(item['raw']) is str)
                    # Historical raw wrappers from the original loop's local
                    # rows must already be confirmed by THIS exact owner view.
                    confirmed=[row for row in view.confirmed if row[0]==role and row[3]==item['sha256']]
                    index=(min(row[2] for row in confirmed) if confirmed else latest.get(role,-1))
                    need(index in records and records[index]['kind']=='utf8'
                        and records[index]['role']==role and records[index]['sha256']==item['sha256']
                        and batch[index]==item['raw'].encode('utf-8'))
                key_choice=(records[index]['sha256'],role)
                choice=(records[index]['sha256'],role,index,json_digest(records[index]['command']))
                need(key_choice not in choices or choices[key_choice]==choice)
                choices[key_choice]=choice
                return index
            # Iterative walks have no self-referential closure which could
            # keep the exact verified bytes alive until a later GC cycle.
            work=[(value,())]
            while work:
                item,path=work.pop();need(len(path)<=12)
                if type(item) is dict:
                    if set(item)==REFERENCE or set(item)=={'raw','sha256'}:
                        index=original(item,path);raw=batch[index].decode('utf-8')
                        expanded+=canonical_size(frame(raw))-canonical_size(item)
                        literal_bytes+=len(batch[index])
                    else:work.extend((child,(*path,name)) for name,child in item.items())
                elif type(item) is list:work.extend((child,(*path,index)) for index,child in enumerate(item))
            raw=None;work=None;stage.choices=tuple(sorted(choices.values()))
            stage.reserve_before(3*size+3*expanded+6*literal_bytes+6*LIMIT+8*PART)
            helper_method(self,'preflight')()
            for digest,role,index,command_sha in stage.choices:
                packet=json.loads(batch[index]);request=records[index]['command']
                need(type(packet) is dict and packet.get('processId')==self.owner.pid
                    and packet.get('requestId' if role=='feature' else 'commandId')==request['commandId']
                    and (role=='feature' or packet.get('runId')==self.bank.run))
            packet=None
            top=[None];work=[(value,top,0,())]
            while work:
                item,parent,name,path=work.pop();need(len(path)<=12)
                if type(item) is dict:
                    if set(item)==REFERENCE or set(item)=={'raw','sha256'}:
                        parent[name]=frame(batch[original(item,path)].decode('utf-8'))
                    else:
                        target={};parent[name]=target
                        work.extend((child,target,key,(*path,key)) for key,child in item.items())
                elif type(item) is list:
                    target=[None]*len(item);parent[name]=target
                    work.extend((child,target,index,(*path,index)) for index,child in enumerate(item))
                else:parent[name]=deepcopy(item)
                if stage.graph is None:stage.graph=top[0]
            stage.graph=top[0];need(canonical_size(stage.graph)==expanded)
            # No local recursive function, work item, container or text alias
            # retains a second complete graph/byte batch across callback return.
            work=top=target=parent=item=None
            before=json_digest(value);old_state=self.owner.state
            self.owner._plain5=True
            try:
                if kind=='report':self.owner.state=stage.graph
                method_kind='packet' if kind=='quiet' else kind
                stage.result=self.methods[('validate','packet','report','ui').index(method_kind)](self.owner,stage.graph) if kind!='report' else self.methods[2](self.owner)
            finally:self.owner.state=old_state;self.owner._plain5=False
            need(json_digest(value)==before);self.bank.verify();helper_method(self,'guard')()
            if kind=='quiet':
                request=self.quiet_request
                helper_method(self,'quiet_book')().observe(request,stage.result,value['hostMonotonic'])
                self.bank.verify();helper_method(self,'guard')();need(json_digest(value)==before)
                helper_method(self,'quiet_book')().confirm(request)
                result=request.complete,request.handle
            elif kind=='validate':
                need(stage.result is None)
                if self.save_stage is not None:
                    need(value is self.save_stage.source and self.selection is self._selection is None)
                    self.selection=self._selection=(value,before,self.bank.archive.state['reads'],stage.choices)
            else:
                need(type(stage.result) is dict)
                result_size=canonical_size(stage.result)
                # Results which can escape into the original Drive/window or
                # caller remain actually retained and charged, without eviction.
                digest=json_digest(stage.result)
                # Pure capacity selection precedes the optional signature.
                # Physical/CAS/guard exceptions never become a cache fallback.
                signature=None;window=12*result_size+3*PART
                added_work=max(0,4*window-self._result_seal[2]);prospective=3*result_size+256+added_work+3*window
                extra_reservation=False
                current=self.bank.other_bill();ours=self.bank.archive.bill()
                if current['decodedBytes']+ours['decodedBytes']+prospective<=MAX_RAW:
                    old_reserve=stage.reserve
                    stage.reserve_before(old_reserve+prospective);helper_method(self,'preflight')();extra_reservation=True
                    stage.signature=_result_signature(stage.result,result_size)
                    signature=stage.signature
                    need(signature is None or type(signature) is bytes and len(signature)<=window)
                    # The exact preallocated stage remains held on any unknown
                    # path; successful optional refusal introduces no new IO.
                self.results=self._results=(*self.results,(stage.result,result_size,digest,signature))
                added=3*result_size+256+(0 if signature is None else 3*len(signature))
                largest=self._result_seal[2] if signature is None else max(self._result_seal[2],4*window)
                self._result_seal=self._original_result_seal=(self.results,self._result_seal[1]+added,largest)
                # Transfer the successful measured signature/work charge to
                # the immutable result seal; do not bill the old provisional
                # reservation and its exact completed representation twice.
                if extra_reservation:stage.reserve_before(old_reserve)
                helper_method(self,'preflight')()
            if kind!='quiet':result=stage.result
            stage.graph=stage.batch=stage.source=stage.result=stage.signature=None
            original=None;batch=records=view=choices=None
            need(self.held[-1] is stage and self._held_seal[-1] is stage)
            stage.reserve_seal=None
            self.held.pop();self._held_seal=self._held_seal[:-1];self.active=None
            return result
        except BaseException:
            stage.failed=True;self.failed=True;self.bank.failed=True
            if not any(holder is self for _path,holder in UNRESOLVED):UNRESOLVED.append((self.bank.path.parent,self))
            raise

    @staticmethod
    def role_at(kind,path):
        if kind=='ui':need(path==());return 'ui'
        if kind in ('validate','report'):
            if path==('beforeUi',):return 'ui'
            if path==('beforeNative',):return 'feature'
            if len(path)==2 and path[0]=='sources' and type(path[1]) is int:return 'background'
            if path and path[0] in ('quiet','finalQuiet'):
                need(len(path)>=3 and type(path[1]) is int);path=path[2:]
            elif path and path[0]=='final':path=path[1:]
            else:need(False)
        if path==('native',):return 'feature'
        need(len(path)==2 and path[0]=='world' and path[1] in ('ui','gesture','drive'))
        return path[1]

    def selected_reference(self,item,value,records):
        from adapters.pico4.lifecycle_source_raw import reference
        helper_method(self,'guard')();need(self.selection is self._selection and self.selection is not None)
        source,digest,reads,choices=self.selection
        need(type(value) is list and len(value)==1 and value[0] is source
            and json_digest(source)==digest and self.bank.archive.state['reads']==reads)
        selected=[row for row in choices if row[0]==item['sha256']]
        need(len(selected)==1)
        sha,role,index,command_sha=selected[0];record=records[index]
        need(record['sha256']==sha and record['role']==role
            and json_digest(record['command'])==command_sha)
        return reference(self.bank.archive.scope_sha,record)

    def close_host(self):
        if self.failed or self.active is not None or self.save_stage is not None:return False
        try:
            known=helper_method(self,'quiet_book')().known_stages()
            need(not any(not any(stage is window for window in known) for stage in self.held))
            helper_method(self,'metadata_bytes')()
            if helper_method(self,'quiet_book')().close_host() is not True:return False
            self.results=self._results=();self._result_seal=self._original_result_seal=(self.results,0,0)
            return True
        except BaseException:return False


_HELPER_CLASS=LifecycleBackgroundState5
_HELPER_MRO=type.__getattribute__(_HELPER_CLASS,'__mro__')
_HELPER_RAW=tuple(type.__getattribute__(_HELPER_CLASS,'__dict__').items())
_HELPER_METHODS=('__init__','guard','metadata_bytes','quiet_book','begin_quiet_invocation','quiet_step',
    'read_feature_original','preflight','save','call','selected_reference','close_host')
_HELPER_FUNCTIONS=tuple((name,dict(_HELPER_RAW)[name],dict(_HELPER_RAW)[name].__code__) for name in _HELPER_METHODS)
_HELPER_STATIC=dict(_HELPER_RAW)['role_at'].__func__
_HELPER_STATIC_CODE=_HELPER_STATIC.__code__
def helper_method(helper,name):
    need(type(helper) is _HELPER_CLASS and LifecycleBackgroundState5 is _HELPER_CLASS
        and type.__getattribute__(_HELPER_CLASS,'__mro__') is _HELPER_MRO)
    raw=type.__getattribute__(_HELPER_CLASS,'__dict__')
    need(len(raw)==len(_HELPER_RAW) and all(raw.get(key) is value for key,value in _HELPER_RAW))
    # Never bind a foreign descriptor or inspect a foreign callable attribute.
    role=raw.get('role_at')
    need(type(role) is staticmethod and role.__func__ is _HELPER_STATIC
        and type(_HELPER_STATIC) is FunctionType and _HELPER_STATIC.__code__ is _HELPER_STATIC_CODE)
    for key,function,code in _HELPER_FUNCTIONS:
        need(type(function) is FunctionType and raw.get(key) is function and function.__code__ is code)
    for key,function,code in _HELPER_FUNCTIONS:
        bound=object.__getattribute__(helper,key)
        need(type(bound) is MethodType and bound.__self__ is helper and bound.__func__ is function)
    need(type(name) is str and name in _HELPER_METHODS)
    return object.__getattribute__(helper,name)
