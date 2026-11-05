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



def report_reference(value,path):
    if path in (('beforeUi',),('beforeNative',)):return True
    if len(path)==2 and path[0]=='sources':
        return path[1] in (value['home'],value['quiet'][-1]['sourceIndex'],value['final']['sourceIndex'])
    if path and path[0]=='quiet':
        return path[1]==len(value['quiet'])-1 and (path[2:]==('native',) or path[2:]==('world','ui'))
    if path and path[0]=='finalQuiet':return path[1] in (0,len(value['finalQuiet'])-1)
    return False
_REPORT_REFERENCE=(report_reference,report_reference.__code__)

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
        self.current_capture=self._current_capture=None
        self.capture_hooks=self._capture_hooks={}
        self.runtime_api=self._runtime_api=None
        self.validation_profile=self._validation_profile=None
        self.validation_proof=self._validation_proof=None
        self.capture_choice=self._capture_choice=(owner.quiet_period,)
        self.validation_work=self._validation_work=(0 if owner.quiet_period is None else 5*PART,)
        self.validation_entry=self._validation_entry=None
        self.completed_capture=self._completed_capture=None
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
        if self.capture_choice[0] is None:return
        from adapters.pico4 import lifecycle_capture5 as capture5
        self.capture_api=self._capture_api=capture5.capture_profile()
        self.capture_module=self._capture_module=(capture5,tuple((name,capture5.__dict__[name],capture5.__dict__[name].__code__)
            for name in ('capture_profile','guard_profile','capture_schema','original_owner_capture','capture_method','capture_hook_method','transfer_capture5','api_method','prepare_completed_slot','completed_slot_guard')))
        from adapters.pico4 import lifecycle_validation_work5 as validation5
        self.validation_entry=self._validation_entry=(validation5,tuple((name,validation5.__dict__[name],validation5.__dict__[name].__code__)
            for name in ('profile_proof','require_profile','code_names','decoded_bound')))
        # Existing actual namespace/bank bill sees the complete permanent
        # profile reservation BEFORE constructor tables or snapshots allocate.
        helper_method(self,'preflight')()
        profile=object.__new__(validation5.OriginalValidatorProfile5)
        self.validation_profile=self._validation_profile=profile
        validation5.OriginalValidatorProfile5.__init__(profile,self.owner)
        need(profile.actual_storage is not None)
        self.validation_proof=self._validation_proof=validation5.profile_proof(profile)
        validation5.require_profile(profile,self.validation_proof)


    def guard(self):
        from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
        need(self._fixed is self._original_fixed and self._fixed[0] is self.owner and self._fixed[1] is self.bank
            and self.owner.state5 is self.owner._state5 is self
            and self.bank.background_state5 is self.bank._background_state5 is self
            and self.capture_choice is self._capture_choice and type(self.capture_choice) is tuple and len(self.capture_choice)==1
            and self.capture_choice[0] is self.owner.quiet_period
            and self.current_capture is self._current_capture
            and self.owner.version==5 and self.owner.originals is self.bank
            and self.owner._state_choice is self.owner._original_state_choice and self.owner._state_choice==(5,)
            and self.methods is self._methods and all(a is b for a,b in zip(self.methods,
                (PicoLifecycleBackground._validate_plain,PicoLifecycleBackground._packet_plain,
                    PicoLifecycleBackground._report_plain,PicoLifecycleBackground._before_ui_plain,PicoLifecycleBackground._save_plain)))
            and all(method.__code__ is code for method,code in zip(self.methods,self._codes)))
        from adapters.pico4.lifecycle_quiet_step5 import QuietBook5
        need(self.quiet is self._quiet and type(self.quiet) is QuietBook5)
        self.bank.lock.assert_held()
        namespace=object.__getattribute__(self,'__dict__')
        if 'capture_module' in namespace:
            module,functions=self.capture_module
            need(self.capture_module is self._capture_module and self.capture_api is self._capture_api)
            for name,function,code in functions:
                need(type(function) is FunctionType and module.__dict__.get(name) is function and function.__code__ is code)
            module.guard_profile(self.capture_api)
            need(self.runtime_api is self._runtime_api)
            if self.runtime_api is not None:module.api_method(self.runtime_api,'guard')()
        if self.validation_proof is not None:
            need(self.validation_proof is self._validation_proof and self.validation_profile is self._validation_profile
                and self.validation_entry is self._validation_entry)
            module,functions=self.validation_entry
            for name,function,code in functions:
                need(type(function) is FunctionType and module.__dict__.get(name) is function and function.__code__ is code)
            functions[1][1](self.validation_profile,self.validation_proof)
        else:need((self.capture_choice[0] is None or self.bank.archive.state['reads']==0) and self.runtime_api is None)


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
        need(self.capture_hooks is self._capture_hooks and len(self.capture_hooks)<=5)
        need(self.validation_work is self._validation_work and type(self.validation_work) is tuple
            and len(self.validation_work)==1 and type(self.validation_work[0]) is int and self.validation_work[0]==(0 if self.capture_choice[0] is None else 5*PART))
        fixed_capture=0 if self.capture_choice[0] is None else 4*PART
        total=1024+fixed_capture;work=0
        need(self.completed_capture is self._completed_capture)
        if self.completed_capture is not None:
            from adapters.pico4.lifecycle_capture5 import completed_slot_guard
            completed_slot_guard(self.completed_capture,self)
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
        need(total==self._result_seal[1]+1024+fixed_capture and work==self._result_seal[2])
        # All later audits reserve one largest actual current normalizer/output
        # work window, including before metadata verification allocates it.
        total+=work+self.feature_work[0]+self.validation_work[0]+helper_method(self,'quiet_book')().metadata_bytes()
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
        if self.current_capture is not None:return helper_method(self,'quiet_current')(row,handle,invocation,role)
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

    def bind_capture_runtime(self,world,observer,native):
        from adapters.pico4.lifecycle_capture5 import OriginalApi5,api_method
        helper_method(self,'guard')();need(self.runtime_api is self._runtime_api is None)
        helper_method(self,'preflight')()
        api=object.__new__(OriginalApi5);self.runtime_api=self._runtime_api=api
        try:
            api_method(api,'__init__')(((self.owner,('__init__','capture','fresh','_save_plain','_validate_plain','run_owned','poll_delay','bound')),
                (world,('current','acquire','save','originals','attempts','now','fresh_current')),
                (observer,('read','exchange')),(world.axes,('capture','_capture')),
                (world.avatar,('capture','_capture')),(world.source,('capture','_capture')),
                (native,('read',))),self.capture_api)
        except BaseException:
            self.failed=self.bank.failed=True
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(holder is self for _path,holder in UNRESOLVED):UNRESOLVED.append((self.bank.path.parent,self))
            raise

    def release_completed_capture(self):
        from adapters.pico4.lifecycle_capture5 import completed_slot_guard
        helper_method(self,'guard')() # Whole original/no-finalizer proof FIRST.
        slot=self.completed_capture;need(slot is self._completed_capture)
        if slot is None:return
        completed_slot_guard(slot,self)
        self.completed_capture=self._completed_capture=None
        # The last actual custom references die on return HERE, under the next
        # original capture anchor, before any SDK or input. No close is retried.

    def capture_hook(self,reader,role):
        from adapters.pico4.lifecycle_capture5 import CaptureHook5
        need(role not in self.capture_hooks and len(self.capture_hooks)<5)
        hook=CaptureHook5(self,reader,role);self.capture_hooks[role]=hook
        return hook

    def capture_current(self,invocation,role,*,caller_rows=False):
        from adapters.pico4.lifecycle_capture5 import CaptureIntent5,original_owner_capture
        try:
            helper_method(self,'guard')()
            need(self.current_capture is self._current_capture is None)
            need(type(caller_rows) is bool)
            intent=CaptureIntent5(self,invocation,role,caller_rows)
            return original_owner_capture(self.owner,self.capture_api)(_current=intent)
        except BaseException:
            self.failed=self.bank.failed=True
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(owner is self for _path,owner in UNRESOLVED):UNRESOLVED.append((self.bank.path.parent,self))
            raise

    def begin_capture(self,intent,started,requested):
        from adapters.pico4.lifecycle_capture5 import CaptureAppendPermit5
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        helper_method(self,'guard')()
        need(self.current_capture is self._current_capture is None and self.active is None and self.save_stage is None)
        gate=self.owner.storage_gate
        need(type(gate) is LifecycleFamilyGate4 and gate is self.owner._original_storage_gate
            and gate.role=='background' and gate.root_version==5 and gate.capture is gate._original_capture is None)
        stage=OriginalGraph5(self,intent,0);stage.reserve_before(0)
        self.held.append(stage);self._held_seal=(*self._held_seal,stage)
        permit=object.__new__(CaptureAppendPermit5);stage.graph=permit
        self.current_capture=self._current_capture=permit;gate.capture=gate._original_capture=permit
        try:CaptureAppendPermit5.__init__(permit,self,gate,stage,intent,started,requested)
        except BaseException:
            self.failed=self.bank.failed=True
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(owner is self for _path,owner in UNRESOLVED):UNRESOLVED.append((self.bank.path.parent,self))
            raise
        return permit

    def capture_background(self,observer,result):
        from adapters.pico4.lifecycle_capture5 import capture_method
        permit=self.current_capture;need(permit is self._current_capture and permit is not None)
        capture_method(permit,'bind_background')(observer,result)
        permit.stage.result=None

    def capture_world(self,world):
        from adapters.pico4.lifecycle_capture5 import capture_method
        permit=self.current_capture;need(permit is self._current_capture and permit is not None)
        need(permit.phase=='background-retained');permit.phase='world-reading'
        packets=world.current()
        # Actual return is held before any later guard/clock can reject it.
        permit.stage.result=packets
        capture_method(permit,'bind_drive')(world,packets)
        permit.phase='native-reading';permit.stage.result=None
        return packets

    def capture_row(self,row):
        from adapters.pico4.lifecycle_capture5 import capture_method
        permit=self.current_capture;need(permit is self._current_capture and permit is not None)
        capture_method(permit,'bind_row')(row)

    def capture_checkpoint(self,value,*,caller_rows=False):
        from adapters.pico4.lifecycle_capture5 import capture_method
        from adapters.pico4.lifecycle_back import frame as actual_frame
        permit=self.current_capture;need(permit is self._current_capture and permit is not None)
        need(type(caller_rows) is bool and (not caller_rows or capture_method(permit,'row_selection')() is True))
        if permit.root_confirmed:
            # Same invocation's returned seed: its source was already committed.
            # Preserve the original subsequent quiet checkpoint, without append.
            capture_method(permit,'seed_checkpoint')(value)
            helper_method(self,'save')(value)
            capture_method(permit,'seed_committed')()
        else:
            need(type(value) is dict and type(value['sources']) is list and len(value['sources'])==permit.source_index)
            value['sources'].append(actual_frame(permit.background[1]))
            capture_method(permit,'authorize')(value)
            helper_method(self,'save')(value)
        if permit.drive_consumed:
            rows,last=(capture_method(permit,'confirmed_rows')(value) if caller_rows else (None,None))
            capture_method(permit,'prepare_transfer')()
            if caller_rows:return permit.transfer,rows,last
            return permit.transfer
        need(not caller_rows) # Original unconsumed returned seed stays EXACT.
        return None

    def capture_before_fresh(self):
        from adapters.pico4.lifecycle_capture5 import capture_method
        permit=self.current_capture
        if permit is not None:
            need(permit is self._current_capture)
            if permit.transfer is not None:capture_method(permit,'check_transfer')()
            else:capture_method(permit,'verify_current')()


    def quiet_current(self,row,handle,invocation,role):
        from adapters.pico4.lifecycle_capture5 import capture_method,DRIVE_CANONICAL
        from adapters.pico4 import lifecycle_drive as original_drive
        from adapters.pico4.lifecycle_background import feature_original
        permit=self.current_capture
        need(permit is self._current_capture and permit is not None and permit.row is row
            and permit.intent.invocation is invocation and permit.intent.role==role
            and permit.phase in ('row-bound','root-committed') and json_digest(row)==permit.row_sha)
        # Fresh full-prefix/source verification, never a cached current verdict.
        self.bank.verify();helper_method(self,'guard')();capture_method(permit,'verify_current')()
        value,digest,world,raw,receipt,size=permit.drive
        need(json_digest(value)==digest and canonical_size(value,DRIVE_CANONICAL)==size
            and row['world']['drive']['raw']==raw and row['world']['drive']['sha256']==receipt[3]
            and json_digest(permit.world_row)==permit.world_row_sha and row['world']==permit.world_row)
        original_drive.validate(value,value,self.owner.pid,value['capturedEpochMs'])
        feature_original(row['native'],self.owner.pid)
        request=helper_method(self,'quiet_book')().prepare(row,handle,invocation,role)
        try:
            helper_method(self,'quiet_book')().observe(request,dict(drive=value),row['hostMonotonic'])
            self.bank.verify();helper_method(self,'guard')()
            helper_method(self,'quiet_book')().confirm(request)
            result=helper_method(self,'quiet_book')().finish(request)
            permit.drive_consumed=True
            permit.phase='quiet-consumed'
            return result
        except BaseException:
            capture_method(permit,'fail')();raise

    def no_capture_input(self):
        need(self.current_capture is self._current_capture is None)


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
            selective_report=kind=='report' and self.capture_choice[0] is not None
            need(type(report_reference) is FunctionType and report_reference is _REPORT_REFERENCE[0]
                and report_reference.__code__ is _REPORT_REFERENCE[1])
            maximum_wrapper=0;maximum_literal=0;maximum_decoded_bound=0;binary_bytes=sum(len(raw) for raw in batch.values())
            decoded_max={role:0 for role in ('background','ui','gesture','drive','feature')}
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
                        if selective_report and not report_reference(value,path):continue
                        index=original(item,path);raw=batch[index].decode('utf-8')
                        wrapper_size=canonical_size(frame(raw))
                        expanded+=wrapper_size-canonical_size(item)
                        maximum_wrapper=max(maximum_wrapper,wrapper_size)
                        maximum_literal=max(maximum_literal,len(batch[index]))
                        if kind=='validate' and self.capture_choice[0] is not None:maximum_decoded_bound=max(maximum_decoded_bound,self.validation_entry[1][3][1](batch[index],wrapper_size))
                        literal_bytes+=len(batch[index])
                    else:work.extend((child,(*path,name)) for name,child in item.items())
                elif type(item) is list:work.extend((child,(*path,index)) for index,child in enumerate(item))
            raw=None;work=None;stage.choices=tuple(sorted(choices.values()))
            if kind=='validate' and self.capture_choice[0] is not None:
                # Two parsed-document envelopes are guaranteed BEFORE decode;
                # canonical normalization may expand a short numeric/string
                # spelling. No decoded<=literal assumption is made.
                stage.reserve_before(3*size+binary_bytes+2*maximum_decoded_bound+2*maximum_literal+6*LIMIT+9*PART)
            else:stage.reserve_before(3*size+3*expanded+6*literal_bytes+(binary_bytes if selective_report else 0)+6*LIMIT+8*PART)
            helper_method(self,'preflight')()
            for digest,role,index,command_sha in stage.choices:
                if kind=='validate' and self.capture_choice[0] is not None:
                    from adapters.native_feature_observation import decode
                    packet=decode(batch[index].decode('utf-8'))
                else:packet=json.loads(batch[index])
                request=records[index]['command']
                need(type(packet) is dict and packet.get('processId')==self.owner.pid
                    and packet.get('requestId' if role=='feature' else 'commandId')==request['commandId']
                    and (role=='feature' or packet.get('runId')==self.bank.run))
                if kind=='validate' and self.capture_choice[0] is not None:
                    # Same original strict decoder; not a semantic verdict.
                    decoded_size=canonical_size(packet)
                    need(decoded_size<=maximum_decoded_bound)
                    decoded_max[role]=max(decoded_max[role],decoded_size)
                packet=None
            packet=request=None
            if kind=='validate' and self.capture_choice[0] is not None:
                # The measurement work is dead. Keep the one reconstruction,
                # actual binary batch, and largest sequential framing work.
                semantic_documents=12*sum(decoded_max.values())
                scalar_work=3*max(maximum_wrapper,*decoded_max.values())
                reconstruction=expanded+binary_bytes+3*maximum_wrapper
                semantic=expanded+semantic_documents+scalar_work
                # ONE original admission covers these consecutive pure phases.
                # Retain the larger guaranteed reservation until BOTH finish.
                stage.reserve_before(3*size+max(reconstruction,semantic)+6*LIMIT+8*PART)
                helper_method(self,'preflight')()
            top=[None];work=[(value,top,0,())]
            while work:
                item,parent,name,path=work.pop();need(len(path)<=12)
                if type(item) is dict:
                    if set(item)==REFERENCE or set(item)=={'raw','sha256'}:
                        parent[name]=(deepcopy(item) if selective_report and not report_reference(value,path)
                            else frame(batch[original(item,path)].decode('utf-8')))
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
            work=top=target=parent=item=path=name=raw=None
            if kind=='validate' and self.capture_choice[0] is not None:
                # Explicitly terminate ALL batch and resolver closure aliases
                # before invoking the unchanged full semantic validator.
                original=None;stage.batch=None;batch=records=view=choices=None
                # No query, input, write, arbitrary callback or new allocation
                # window intervenes. The actual prebooked MAX above remains
                # held; no second full audit or verdict reuse is needed here.
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
            if self.capture_choice[0] is not None:
                module,functions=self.capture_module
                need(self.capture_module is self._capture_module and self.capture_api is self._capture_api)
                for name,function,code in functions:
                    need(type(function) is FunctionType and module.__dict__.get(name) is function and function.__code__ is code)
                module.guard_profile(self.capture_api)
                need(self.runtime_api is self._runtime_api)
                if self.runtime_api is not None:module.api_method(self.runtime_api,'guard')()
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
    'read_feature_original','preflight','save','call','selected_reference','close_host',
    'capture_hook','capture_current','begin_capture','capture_background','capture_world','capture_row','capture_checkpoint','quiet_current',
    'no_capture_input','capture_before_fresh','bind_capture_runtime','release_completed_capture')
_HELPER_FUNCTIONS=tuple((name,dict(_HELPER_RAW)[name],dict(_HELPER_RAW)[name].__code__) for name in _HELPER_METHODS)
_HELPER_DEFAULTS=tuple((function,function.__defaults__,function.__kwdefaults__,
    None if function.__kwdefaults__ is None else tuple(function.__kwdefaults__.items())) for _name,function,_code in _HELPER_FUNCTIONS)
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
    for function,defaults,keywords,items in _HELPER_DEFAULTS:
        need(function.__defaults__ is defaults and function.__kwdefaults__ is keywords)
        if keywords is not None:
            need(type(keywords) is dict and len(keywords)==len(items)
                and all(type(key) is str for key in keywords) and all(keywords.get(key) is value for key,value in items))
    for key,function,code in _HELPER_FUNCTIONS:
        bound=object.__getattribute__(helper,key)
        need(type(bound) is MethodType and bound.__self__ is helper and bound.__func__ is function)
    need(type(name) is str and name in _HELPER_METHODS)
    return object.__getattribute__(helper,name)
