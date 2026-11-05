"""Cold Background5 capture transaction with original source custody."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from types import FunctionType,MethodType,BuiltinFunctionType
import os,time
from adapters.native_feature_observation import need,integer,LIMIT
from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_fd_owner import OriginalDescriptor
from adapters.pico4.lifecycle_descriptor_close import pin,close_original,guard as descriptor_guard
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.history import canonical
from adapters.pico4.lifecycle_back import frame

PART=65536
BG_CANONICAL=3*PART       # Derived existing Background1 schema upper138996.
DRIVE_CANONICAL=PART//2   # Derived existing Drive1 schema upper28435.
BG_WORK=3*BG_CANONICAL+LIMIT+3*PART
DRIVE_WORK=3*DRIVE_CANONICAL+LIMIT+3*PART
_TIME_DEFAULTS=(time.monotonic,time.sleep)
PHASES=('observing-background','background-retained','world-reading','world-retained',
    'native-reading','row-bound','quiet-consumed','commit-prepared','root-committed','retired','failed')


def _function_proof(function):
    need(type(function) is FunctionType)
    defaults=function.__defaults__;keywords=function.__kwdefaults__
    need(defaults is None or type(defaults) is tuple)
    need(keywords is None or type(keywords) is dict and all(type(key) is str for key in keywords))
    # These admitted schema/API functions have immutable primitive defaults.
    values=(() if defaults is None else defaults)+(() if keywords is None else tuple(keywords.values()))
    need(all(type(value) is int or type(value) is float or type(value) is str
        or type(value) is bool or value is None or type(value) is tuple and not value
        or type(value) is BuiltinFunctionType and any(value is expected for expected in _TIME_DEFAULTS) for value in values))
    return function,function.__code__,defaults,keywords,None if keywords is None else tuple(keywords.items())


def _function_guard(proof):
    function,code,defaults,keywords,items=proof
    need(type(function) is FunctionType and function.__code__ is code
        and function.__defaults__ is defaults and function.__kwdefaults__ is keywords)
    if keywords is not None:
        need(type(keywords) is dict and len(keywords)==len(items)
            and all(type(key) is str for key in keywords)
            and all(keywords.get(key) is value for key,value in items))


class OriginalApi5:
    """Instances bind only to the profile selected before cold runtime."""
    def __init__(self,objects,profile):
        guard_profile(profile)
        self.objects=self._objects=tuple(objects);self.profile=self._profile=profile
        methods=[]
        for owner,names in self.objects:
            cls=type(owner)
            match=[entry for entry in profile if entry[2] is cls]
            need(len(match)==1)
            entry=match[0]
            for name in names:
                proof=next((proof for key,proof in entry[5] if key==name),None)
                need(proof is not None)
                bound=object.__getattribute__(owner,name)
                need(type(bound) is MethodType and bound.__self__ is owner and bound.__func__ is proof[0])
                methods.append((owner,name,proof))
        self.methods=self._methods=tuple(methods)
    def guard(self):
        need(self.objects is self._objects and self.methods is self._methods and self.profile is self._profile)
        guard_profile(self.profile)
        for owner,name,proof in self.methods:
            _function_guard(proof)
            bound=object.__getattribute__(owner,name)
            need(type(bound) is MethodType and bound.__self__ is owner and bound.__func__ is proof[0])



_API_CLASS=OriginalApi5
_API_MRO=type.__getattribute__(_API_CLASS,'__mro__')
_API_RAW=tuple(type.__getattribute__(_API_CLASS,'__dict__').items())
_API_FUNCTIONS=tuple((name,_function_proof(value)) for name,value in _API_RAW if type(value) is FunctionType)
def api_method(api,name):
    need(type(api) is _API_CLASS and OriginalApi5 is _API_CLASS
        and type.__getattribute__(_API_CLASS,'__mro__') is _API_MRO)
    raw=type.__getattribute__(_API_CLASS,'__dict__')
    need(len(raw)==len(_API_RAW) and all(raw.get(key) is value for key,value in _API_RAW))
    for key,proof in _API_FUNCTIONS:
        _function_guard(proof)
        bound=object.__getattribute__(api,key)
        need(type(bound) is MethodType and bound.__self__ is api and bound.__func__ is proof[0])
    need(type(name) is str and any(key==name for key,_proof in _API_FUNCTIONS))
    return object.__getattribute__(api,name)


from adapters.pico4 import lifecycle_drive as _drive,lifecycle_background_source as _background,lifecycle_source as _ui
from adapters import native_feature_observation as _native
_SCHEMA_SPEC=((_drive,('validate','vector','quaternion','integer','number','exact','fresh','nonce')),
    (_background,('validate','command','accept','integer','number','exact','fresh')),
    (_ui,('editors','context','nonce','integer','number','exact','fresh')))
_SCHEMA=tuple((module,name,_function_proof(module.__dict__[name])) for module,names in _SCHEMA_SPEC for name in names)
_SCHEMA_CONSTANTS=tuple((module,name,module.__dict__[name]) for module,names in
    ((_drive,('VERSION',)),(_background,('VERSION',)),(_ui,('READS','IDENTITIES','LIVENESS'))) for name in names)
def capture_schema():
    need(time.monotonic is _TIME_DEFAULTS[0] and time.sleep is _TIME_DEFAULTS[1])
    need(type(PART) is int and PART==65536 and type(LIMIT) is int and LIMIT==262144
        and type(BG_CANONICAL) is int and BG_CANONICAL==3*65536
        and type(DRIVE_CANONICAL) is int and DRIVE_CANONICAL==32768
        and type(BG_WORK) is int and BG_WORK==1048576
        and type(DRIVE_WORK) is int and DRIVE_WORK==557056)
    for module,name,proof in _SCHEMA:
        need(module.__dict__.get(name) is proof[0]);_function_guard(proof)
    for module,name,value in _SCHEMA_CONSTANTS:need(module.__dict__.get(name) is value)
    need(frame is _CALLER_FRAME[0]);_function_guard(_CALLER_FRAME)
    for name,proof in _CALLER_KEY:
        need(_ranges.__dict__.get(name) is proof[0]);_function_guard(proof)
    need(_ranges.REFERENCE is _CALLER_REFERENCE and type(_CALLER_REFERENCE) is set
        and all(type(name) is str for name in _CALLER_REFERENCE)
        and _CALLER_REFERENCE=={'lifecycleSourceRangeVersion','role','source','sha256'}
        and _ranges.SOURCE_ROLES4 is _CALLER_ROLES and _ranges.VERSION is _CALLER_VERSION)

from adapters.pico4 import lifecycle_background_owner as _owner,lifecycle_world as _world,lifecycle_gesture as _gesture
_CLASS_SPEC=((_owner,'PicoLifecycleBackground',('__init__','capture','fresh','_save_plain','_validate_plain','run_owned','poll_delay','bound')),
    (_world,'PicoLifecycleWorld',('current','acquire','save','originals','attempts','now','fresh_current')),
    (_background,'NativeLifecycleBackground',('read','exchange')),
    (_gesture,'PicoLifecycleGesture',('capture','_capture')),(_drive,'PicoLifecycleDrive',('capture','_capture')),
    (_ui,'PicoLifecycleSource',('capture','_capture')),(_native,'NativeFeatureObservation',('read',)))
_CLASS_API=[]
for _module,_name,_names in _CLASS_SPEC:
    _cls=_module.__dict__[_name];_raw=type.__getattribute__(_cls,'__dict__')
    need(len(_raw)<=128 and len(_names)<=16)
    _CLASS_API.append((_module,_name,_cls,type.__getattribute__(_cls,'__mro__'),tuple(_raw.items()),
        tuple((name,_function_proof(_raw[name])) for name in _names)))
_CLASS_API=_ORIGINAL_CLASS_API=tuple(_CLASS_API)
def capture_profile():
    guard_profile(_CLASS_API);return _CLASS_API
def guard_profile(profile):
    need(profile is _CLASS_API is _ORIGINAL_CLASS_API)
    capture_schema()
    for module,name,cls,mro,entries,functions in profile:
        need(module.__dict__.get(name) is cls and type.__getattribute__(cls,'__mro__') is mro)
        raw=type.__getattribute__(cls,'__dict__')
        need(len(raw)==len(entries) and all(raw.get(key) is value for key,value in entries))
        for key,proof in functions:
            need(raw.get(key) is proof[0]);_function_guard(proof)
def original_owner_capture(owner,profile):
    guard_profile(profile);entry=profile[0];need(type(owner) is entry[2])
    proof=next(proof for name,proof in entry[5] if name=='capture')
    bound=object.__getattribute__(owner,'capture')
    need(type(bound) is MethodType and bound.__self__ is owner and bound.__func__ is proof[0])
    return bound

@dataclass(eq=False)
class CaptureIntent5:
    helper:object
    invocation:object
    role:str
    caller_rows:bool=False


class CaptureAppendPermit5:
    """Actual old root plus uncommitted source; no native/sample authority."""
    def __init__(self,helper,gate,stage,intent,started,requested):
        # The caller owns this object/stage BEFORE __init__ can fail.
        self.helper,self.gate,self.stage,self.intent=helper,gate,stage,intent
        self.phase='observing-background';self.failed=False;self.old=None;self.close_receipt=None
        self.root_confirmed=False;self.drive_consumed=False
        self.background=self.drive=self.row=self.authorized=self.family=self.receipt=None
        self.latest={};self._latest=self.latest;self.world_started=None;self.role_commands={}
        self.root_bytes=self.root_stamp=None;self.prefix=None;self.prefix_sha=None
        self.started,self.requested=started,requested
        self.owner=helper.owner;self.raw=helper.bank;self.lock=self.raw.lock
        need(type(intent) is CaptureIntent5 and type(intent.caller_rows) is bool)
        self.caller_rows=self._caller_rows=intent.caller_rows
        self.fixed=self._fixed=(helper,gate,stage,intent,self.owner,self.raw,self.lock,self.caller_rows)
        self.read_floor=self.raw.archive.state['reads'];self.close_proof=pin();self.api=None
        self.hooks=None;self.root_receipt=None;self.transfer=None
        self.closed_family=self.closed_projection=self.seed_receipts=None
        try:
            from adapters.pico4.lifecycle_background_state5 import helper_method
            from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
            need(type(intent) is CaptureIntent5 and intent.helper is helper
                and type(gate) is LifecycleFamilyGate4 and gate is self.owner.storage_gate
                and gate is self.owner._original_storage_gate and gate.writer is self.owner
                and gate.raw is self.raw and gate.role=='background' and gate.root_version==5
                and gate.capture is gate._original_capture is self and gate.pending is None
                and helper.current_capture is helper._current_capture is self
                and stage.holder is helper and stage.graph is self)
            self.lock.assert_held();helper_method(helper,'guard')()
            need(type(self.owner.state) is dict and type(self.owner.state['sources']) is list)
            size=self.owner.disk['payload']['bytes'];need(integer(size,2,16*1024*1024))
            # Old projected graph/root/OFD+both new successful DTO lifetimes are
            # booked before canonical buffers, descriptor open or first query.
            stage.reserve_before(3*size+3*PART+BG_WORK+DRIVE_WORK+(PART if self.caller_rows else 0))
            helper_method(helper,'preflight')()
            capture_schema()
            world,observer,native=self.owner.runtime
            from adapters.pico4.lifecycle_background_state5 import helper_method
            helper_method(helper,'release_completed_capture')()
            self.api=helper.runtime_api;need(self.api is helper._runtime_api and self.api is not None)
            api_method(self.api,'guard')()
            self.hooks=tuple(self.raw.hooks[role] for role in ('background','gesture','drive','ui','feature'))
            self.old_disk=self.owner.disk;self.old_state=self.owner.state
            self.prefix=tuple(self.owner.state['sources']);self.source_index=len(self.prefix)
            self.prefix_sha=json_digest(list(self.prefix));self.old_state_sha=json_digest(self.old_state)
            self.root_bytes=canonical(self.old_disk)+b'\n';need(len(self.root_bytes)<=PART)
            self.root_stamp=tuple(signature(self.owner.store.path.lstat()))
            descriptor=object.__new__(OriginalDescriptor);self.old=descriptor
            OriginalDescriptor.__init__(descriptor,'/proc/self/fd/'+str(self.raw.namespace.directory.fd)+'/'+self.owner.store.path.name,
                os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            capture_method(self,'verify_old')()
        except BaseException:capture_method(self,'fail')();raise
    def row_selection(self):
        need(self.fixed is self._fixed and len(self.fixed)==8
            and type(self.caller_rows) is bool and self.caller_rows is self._caller_rows
            and self.fixed[7] is self.caller_rows and self.intent.caller_rows is self.caller_rows)
        return self.caller_rows
    def verify_old(self):
        capture_method(self,'row_selection')()
        self.lock.assert_held();need(self.old is not None and not self.root_confirmed)
        capture_schema();api_method(self.api,'guard')();self.raw.check_hooks()
        need(all(self.raw.hooks[role] is original for role,original in zip(
            ('background','gesture','drive','ui','feature'),self.hooks)))
        descriptor_guard(self.old,self.close_proof);self.close_proof[2](self.old,self.old.fd)
        need(tuple(signature(os.fstat(self.old.fd)))==self.root_stamp
            and tuple(signature(self.owner.store.path.lstat()))==self.root_stamp
            and os.pread(self.old.fd,PART+1,0)==self.root_bytes
            and self.owner.disk is self.old_disk and self.owner.state is self.old_state
            and json_digest(self.old_state)==self.old_state_sha
            and len(self.owner.state['sources'])==self.source_index
            and all(value is saved for value,saved in zip(self.owner.state['sources'],self.prefix)))
        descriptor_guard(self.old,self.close_proof);self.close_proof[2](self.old,self.old.fd)
    def before_source(self,role,reader,command):
        # Exact wrappers invoke this before SDK send/get, after reserving all
        # ordinary raw-reader work. It never grants input or resets clocks.
        need(not self.failed and self.phase in ('observing-background','world-reading','native-reading'))
        capture_method(self,'verify_old')();need(type(command) is dict and command.get('runId',self.raw.run)==self.raw.run)
        world,observer,native=self.owner.runtime
        allowed={'background':observer,'gesture':world.axes,'drive':world.avatar,'ui':world.source,'feature':native}
        need(role in allowed and reader is allowed[role])
        if role=='background':
            need(self.phase=='observing-background' and command.get('operation')=='observe')
        elif role=='feature':
            need(self.phase=='native-reading' and command.get('action')=='feature-native-observe')
        else:need(self.phase=='world-reading')
        digest=json_digest(command)
        if role in self.role_commands:need(self.role_commands[role]==digest)
        else:
            if role in ('gesture','drive','ui'):
                sequence=[name for name in self.role_commands if name in ('gesture','drive','ui')]
                need(sequence==list(('gesture','drive','ui')[:len(sequence)]) and role==('gesture','drive','ui')[len(sequence)])
            self.role_commands[role]=digest
    def verify_current(self):
        capture_method(self,'row_selection')()
        self.lock.assert_held();need(not self.failed)
        if not self.root_confirmed:return capture_method(self,'verify_old')()
        disk,state,disk_sha,state_sha,stamp=self.root_receipt
        capture_schema();api_method(self.api,'guard')();self.raw.check_hooks()
        need(self.owner.disk is disk and self.owner.state is state and json_digest(disk)==disk_sha
            and json_digest(state)==state_sha and tuple(signature(self.owner.store.path.lstat()))==stamp
            and self.owner.store.read()==disk and self.close_receipt is not None
            and self.gate.capture is self.gate._original_capture is None)

    def require_no_input(self):
        # Capture retirement is resource authority only. Ordinary owned input
        # must not run until the exact pending append/checkpoint is resolved.
        need(self.phase=='retired' and not self.failed)
    def retained(self,role,reader,command,reference,raw):
        # This runs ONLY AFTER existing archive.retain returned durably. It
        # grants no successful exchange/last assignment, clock or input proof.
        need(type(role) is str and role in ('background','gesture','drive','ui','feature')
            and type(raw) is str and type(reference) is dict)
        self.latest[role]=(reader,json_digest(command),reference['read'],reference['sha256'],len(raw.encode('utf-8')))
    def bind_background(self,observer,result):
        need(self.phase=='observing-background' and not self.failed and type(result) is dict)
        row=self.latest.get('background');need(row is not None and row[0] is observer and row[2]>=self.read_floor)
        # The caller's pinned original exchange must have RETURNED normally.
        api_method(self.api,'guard')();capture_schema()
        need(result==observer.last and observer.last_raw is not None
            and observer.last_sha256==row[3] and result['commandId'] is not None)
        size=canonical_size(result,BG_CANONICAL)
        self.background=(observer.last,observer.last_raw,observer.last_sha256,row)
        self.phase='background-retained'
        self.stage.reserve_before(3*self.owner.disk['payload']['bytes']+3*PART+3*size+row[4]+3*PART+DRIVE_WORK)
    def bind_drive(self,world,packets):
        need(self.phase=='world-reading' and type(packets) is dict and type(packets.get('drive')) is dict)
        value=packets['drive'];receipt=self.latest.get('drive')
        need(receipt is not None and receipt[0] is world.avatar and receipt[2]>=self.read_floor
            and value['runId']==self.raw.run and value['processId']==world.pid)
        api_method(self.api,'guard')();capture_schema()
        raw=world.state['frames'][-1]['drive']
        need(raw['sha256']==receipt[3] and raw['raw']==world.avatar.last_raw
            and world.avatar.last_sha256==receipt[3])
        size=canonical_size(value,DRIVE_CANONICAL)
        self.world_row=world.state['frames'][-1];self.world_row_sha=json_digest(self.world_row)
        self.drive=(value,json_digest(value),world,world.state['frames'][-1]['drive']['raw'],receipt,size)
        self.phase='world-retained'
    def bind_row(self,row):
        need(self.phase=='native-reading' and self.drive is not None and self.background is not None
            and type(row) is dict and row['sourceIndex']==self.source_index
            and row['world']==self.world_row and json_digest(self.world_row)==self.world_row_sha)
        self.row=row;self.row_sha=json_digest(row);self.phase='row-bound'
    def authorize(self,value):
        need(type(value) is dict)
        seed=(self.phase=='row-bound' and self.intent.role=='quiet'
            and self.owner.state['phase']=='resume-issued' and value.get('phase')=='returned'
            and type(value.get('quiet')) is list and len(value['quiet'])==1 and value['quiet'][0] is self.row)
        need((self.phase=='quiet-consumed' or seed) and self.authorized is None and type(value) is dict)
        capture_method(self,'verify_old')();sources=value['sources']
        need(type(sources) is list and len(sources)==self.source_index+1
            and all(actual==saved for actual,saved in zip(sources,self.prefix)))
        # New source bytes are exact actual exchange output, not a prior last.
        from adapters.pico4.lifecycle_back import frame
        need(sources[-1]==frame(self.background[1]))
        self.authorized=(value,json_digest(value));self.phase='commit-prepared'
    def attach_family(self,permit):
        need(self.phase=='commit-prepared' and self.family is None and permit.gate is self.gate
            and permit.writer is self.owner and permit.value is self.authorized[0]
            and json_digest(permit.value)==self.authorized[1])
        self.family=permit
    def committed(self,permit,receipt):
        need(self.phase=='commit-prepared' and permit is self.family and permit.committed is True
            and receipt is self.gate.receipts[-1] and self.gate.pending is None
            and self.raw.view('background').pending is None)
        need(json_digest(permit.value)==self.authorized[1]);self.receipt=receipt
        # Verify SAME original old file after the known successful replacement,
        # then use the original close syscall receipt (never numeric EBADF).
        descriptor_guard(self.old,self.close_proof);self.close_proof[2](self.old,self.old.fd);now=tuple(signature(os.fstat(self.old.fd)))
        need(now[:4]==self.root_stamp[:4] and now[4]==0 and now[5:7]==self.root_stamp[5:7]
            and os.pread(self.old.fd,PART+1,0)==self.root_bytes)
        self.close_receipt=close_original(self.old,self.close_proof)
        self.root_receipt=(self.owner.disk,self.owner.state,json_digest(self.owner.disk),json_digest(self.owner.state),
            tuple(signature(self.owner.store.path.lstat())))
        self.root_confirmed=True;self.phase='root-committed'
        need(self.gate.capture is self.gate._original_capture is self)
        self.gate.capture=self.gate._original_capture=None
    def seed_checkpoint(self,value):
        need(self.root_confirmed and self.drive_consumed and self.transfer is None
            and self.intent.role=='quiet' and self.gate.capture is self.gate._original_capture is None
            and type(value) is dict and value['sources']==self.owner.state['sources'])
        capture_method(self,'verify_current')()
        self.authorized=(value,json_digest(value));self.seed_receipts=self.gate.receipts
    def seed_committed(self):
        need(self.root_confirmed and self.drive_consumed and self.authorized is not None
            and len(self.gate.receipts)==len(self.seed_receipts)+1
            and all(a is b for a,b in zip(self.gate.receipts,self.seed_receipts))
            and self.gate.pending is None and self.raw.view('background').pending is None)
        self.receipt=self.gate.receipts[-1]
        self.root_receipt=(self.owner.disk,self.owner.state,json_digest(self.owner.disk),json_digest(self.owner.state),
            tuple(signature(self.owner.store.path.lstat())))
    def confirmed_rows(self,value):
        # Caller opted in BEFORE the original acquisition/first query. The
        # additional PART for bounded list/ref work is already held by stage.
        need(capture_method(self,'row_selection')() is True and self.root_confirmed and self.drive_consumed
            and self.close_receipt is not None and self.authorized is not None
            and self.authorized[0] is value and json_digest(value)==self.authorized[1])
        from adapters.pico4.lifecycle_background_state5 import helper_method
        helper_method(self.helper,'guard')()
        capture_method(self,'verify_current')()
        from adapters.pico4.lifecycle_source_raw import REFERENCE,key
        field=self.intent.role;need(field in ('quiet','finalQuiet'))
        original=value[field];current=self.owner.state[field]
        need(type(original) is type(current) is list and 1<=len(original)==len(current)<=25)
        view=self.raw.view('background');view.guard()
        for before,after in zip(original,current):
            need(type(before) is type(after) is dict and set(before)==set(after)=={'sourceIndex','world','native','hostMonotonic'})
            for name in ('sourceIndex','hostMonotonic'):
                need(type(before[name]) is type(after[name]) and before[name]==after[name])
            a,b=before['world'],after['world']
            need(type(a) is type(b) is dict and set(a)==set(b)=={'ui','gesture','drive','hostMonotonic'}
                and type(a['hostMonotonic']) is type(b['hostMonotonic']) and a['hostMonotonic']==b['hostMonotonic'])
            for role,source,target in (('ui',a['ui'],b['ui']),('gesture',a['gesture'],b['gesture']),
                    ('drive',a['drive'],b['drive']),('feature',before['native'],after['native'])):
                need(type(source) is type(target) is dict and set(target)==REFERENCE)
                identity=key(target);need(identity[0]==role and identity in view.confirmed
                    and identity[1]==self.raw.archive.scope_sha)
                record=self.raw.archive.pages[identity[2]//32]['receipts'][identity[2]%32]
                need(record['role']==role and record['kind']=='utf8' and record['sha256']==identity[3])
                if set(source)==REFERENCE:need(source==target)
                else:need(set(source)=={'raw','sha256'} and frame(source['raw'])==source and source['sha256']==identity[3])
        # Copy ONLY the vector. Its exact row dictionaries remain the actual
        # confirmed owner-state dictionaries. Never append into the owner list.
        rows=list(current);need(rows is not current)
        return rows,rows[-1]
    def prepare_transfer(self):
        need(self.root_confirmed and self.drive_consumed and self.transfer is None
            and not self.failed and self.close_receipt is not None)
        capture_method(self,'verify_current')();self.raw.verify()
        helper=self.helper;stage=self.stage
        need(helper.current_capture is helper._current_capture is self and helper.held is helper._held
            and len(helper.held)==len(helper._held_seal)
            and all(item is saved for item,saved in zip(helper.held,helper._held_seal)))
        indices=[index for index,item in enumerate(helper.held) if item is stage];need(len(indices)==1)
        next_held=list(helper.held);next_held.pop(indices[0]);next_seal=tuple(next_held)
        # Dicts and every allocation are prepared while the original acquisition
        # still owns/bills this stage. No descriptor close or callback is left.
        hd=object.__getattribute__(helper,'__dict__');pd=object.__getattribute__(self,'__dict__')
        sd=object.__getattribute__(stage,'__dict__')
        hooks=tuple(object.__getattribute__(helper.capture_hooks[role],'__dict__')
            for role in ('background','gesture','drive','ui','feature'))
        capture_method(self,'compact_graphs')()
        slot=prepare_completed_slot(self)
        self.transfer=(hd,pd,sd,helper.held,helper._held_seal,next_held,next_seal,hooks,self,stage,slot)
        self.phase='retirement-prepared'
        capture_method(self,'check_transfer')()
    def check_transfer(self):
        need(self.transfer is not None and not self.failed and self.phase=='retirement-prepared')
        capture_method(self,'verify_current')();self.raw.verify()
        hd,pd,sd,old,old_seal,new,new_seal,hooks,permit,stage,slot=self.transfer
        need(permit is self and stage is self.stage and type(hd) is type(pd) is type(sd) is dict
            and hd is object.__getattribute__(self.helper,'__dict__')
            and pd is object.__getattribute__(self,'__dict__') and sd is object.__getattribute__(self.stage,'__dict__')
            and hd['held'] is hd['_held'] is old and hd['_held_seal'] is old_seal
            and hd['current_capture'] is hd['_current_capture'] is self
            and len(old)==len(old_seal) and all(a is b for a,b in zip(old,old_seal))
            and type(new) is list and type(new_seal) is tuple and len(new)==len(new_seal)
            and all(a is b for a,b in zip(new,new_seal)) and len(old)==len(new)+1
            and sd['graph'] is self and sd['holder'] is self.helper
            and hd['completed_capture'] is hd['_completed_capture'] is None)
        completed_slot_guard(slot,self.helper,preparing=True)
        for row in hooks:need(type(row) is dict and row['permit'] is self)

    def compact_graphs(self):
        guard_profile(self.helper.capture_api)
        family=self.family;projection=family.projection
        from adapters.pico4.lifecycle_family_gate import FamilyPermit4
        from adapters.pico4.lifecycle_source_raw import LifecycleRangeProjection
        need(type(family) is FamilyPermit4 and type(projection) is LifecycleRangeProjection
            and family.committed and not family.failed and family.old is None and family.created is None
            and type(family.prepared) is dict and not family.prepared
            and not projection.failed and self.root_confirmed and self.drive_consumed)
        self.closed_family,self.closed_projection=family,projection
        # All these graphs were validated and durably transferred by the actual
        # known root CAS. No custom holder loses its last reference here.
        if family.old_stamp is not None:
            need(type(family.old_stamp) is list and len(family.old_stamp)==8
                and all(type(value) is int for value in family.old_stamp))
            family.old_stamp=tuple(family.old_stamp) # Same actual eight physical values, now immutable.
        family.value=family.root=family.old_raw=None
        projection.value=projection.encoded=None;projection.references=()
        self.background=self.drive=self.row=self.authorized=self.family=None
        self.old_disk=self.old_state=self.prefix=self.root_bytes=self.world_row=None
        self.latest=self._latest=self.role_commands=self.hooks=self.seed_receipts=None

    def fail(self):
        self.failed=True;self.phase='failed';self.helper.failed=True;self.raw.failed=True
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        if not any(owner is self for _path,owner in UNRESOLVED):UNRESOLVED.append((self.raw.path.parent,self))


_CAPTURE_CLASS=CaptureAppendPermit5
_CAPTURE_MRO=type.__getattribute__(_CAPTURE_CLASS,'__mro__')
_CAPTURE_RAW=tuple(type.__getattribute__(_CAPTURE_CLASS,'__dict__').items())
_CAPTURE_FUNCTIONS=tuple((name,_function_proof(value)) for name,value in _CAPTURE_RAW if type(value) is FunctionType)

def capture_method(permit,name):
    need(type(permit) is _CAPTURE_CLASS and CaptureAppendPermit5 is _CAPTURE_CLASS
        and type.__getattribute__(_CAPTURE_CLASS,'__mro__') is _CAPTURE_MRO)
    raw=type.__getattribute__(_CAPTURE_CLASS,'__dict__')
    need(len(raw)==len(_CAPTURE_RAW) and all(raw.get(key) is value for key,value in _CAPTURE_RAW))
    for key,proof in _CAPTURE_FUNCTIONS:_function_guard(proof)
    for key,proof in _CAPTURE_FUNCTIONS:
        bound=object.__getattribute__(permit,key)
        need(type(bound) is MethodType and bound.__self__ is permit and bound.__func__ is proof[0])
    need(type(name) is str and any(key==name for key,_proof in _CAPTURE_FUNCTIONS))
    return object.__getattribute__(permit,name)


class CaptureHook5:
    """One constructor-selected typed wrapper; None remains the old raw path."""
    def __init__(self,helper,reader,role):
        need(type(role) is str and role in ('background','gesture','drive','ui','feature'))
        self.helper,self.reader,self.role=helper,reader,role
        self.fixed=self._fixed=(helper,helper.bank,reader,role)
        self.command_sha=None;self.permit=None
    def before(self,command):
        from adapters.pico4.lifecycle_background_state5 import helper_method
        helper,raw,reader,role=self.fixed
        helper_method(helper,'guard')()
        need(self.fixed is self._fixed and self.helper is helper and helper.bank is raw
            and self.reader is reader and self.role==role
            and helper.current_capture is helper._current_capture)
        permit=helper.current_capture;digest=json_digest(command)
        if digest!=self.command_sha:
            # A new command can select the current already-owned scope ONCE.
            # A get/postguard cannot silently become unscoped or be promoted.
            self.command_sha=digest;self.permit=permit
        else:need(permit is self.permit)
        if self.permit is not None:capture_method(self.permit,'before_source')(role,reader,command)
    def retained(self,command,reference,raw):
        if self.permit is not None:
            capture_method(self.permit,'retained')(self.role,self.reader,command,reference,raw)

_HOOK_CLASS=CaptureHook5
_HOOK_MRO=type.__getattribute__(_HOOK_CLASS,'__mro__')
_HOOK_RAW=tuple(type.__getattribute__(_HOOK_CLASS,'__dict__').items())
_HOOK_FUNCTIONS=tuple((name,_function_proof(value)) for name,value in _HOOK_RAW if type(value) is FunctionType)
def capture_hook_method(hook,name):
    need(type(hook) is _HOOK_CLASS and CaptureHook5 is _HOOK_CLASS
        and type.__getattribute__(_HOOK_CLASS,'__mro__') is _HOOK_MRO)
    raw=type.__getattribute__(_HOOK_CLASS,'__dict__')
    need(len(raw)==len(_HOOK_RAW) and all(raw.get(key) is value for key,value in _HOOK_RAW))
    for key,proof in _HOOK_FUNCTIONS:
        _function_guard(proof);bound=object.__getattribute__(hook,key)
        need(type(bound) is MethodType and bound.__self__ is hook and bound.__func__ is proof[0])
    need(type(name) is str and any(key==name for key,_proof in _HOOK_FUNCTIONS))
    return object.__getattribute__(hook,name)


def transfer_capture5(ticket):
    """Only precomputed built-in pointer transfer after ORIGINAL final fresh."""
    hd,pd,sd,old,old_seal,new,new_seal,hooks,permit,stage,slot=ticket
    if not (type(hd) is type(pd) is type(sd) is dict and hd['current_capture'] is permit
            and hd['_current_capture'] is permit and hd['held'] is hd['_held'] is old
            and hd['_held_seal'] is old_seal and pd['transfer'] is ticket
            and pd['failed'] is False and pd['phase']=='retirement-prepared'
            and pd['root_confirmed'] is True and pd['drive_consumed'] is True
            and pd['close_receipt'] is not None and sd['graph'] is permit):
        raise RuntimeError('Unresolved Capture5 transfer; original holder remains')
    # Each exact hook still references this actual original invocation. Values
    # cleared below are plain DTOs or still-owned runtime objects, not foreign
    # last-reference callbacks. The known close receipt is released, not redone.
    for row in hooks:
        if type(row) is not dict or row['permit'] is not permit:
            raise RuntimeError('Unresolved Capture5 hook; original holder remains')
    dict.__setitem__(hd,'completed_capture',slot);dict.__setitem__(hd,'_completed_capture',slot)
    dict.__setitem__(pd,'root_receipt',None)
    for row in hooks:
        dict.__setitem__(row,'permit',None);dict.__setitem__(row,'command_sha',None)
    for key in ('graph','result','batch','source','reserve_seal'):dict.__setitem__(sd,key,None)
    dict.__setitem__(sd,'reserve',0)
    dict.__setitem__(pd,'phase','completed')
    dict.__setitem__(hd,'held',new);dict.__setitem__(hd,'_held',new);dict.__setitem__(hd,'_held_seal',new_seal)
    dict.__setitem__(hd,'current_capture',None);dict.__setitem__(hd,'_current_capture',None)
    # Drop the old list now that its exact remaining stages have moved. This is
    # an exact list with known actual stage types, checked before the finalclock.
    list.clear(old)
    dict.__setitem__(pd,'transfer',None)


import sys as _sys
from adapters.pico4 import lifecycle_background_state5 as _state5,lifecycle_family_gate as _family,lifecycle_source_raw as _ranges
from adapters import native_fd_owner as _fds
_CALLER_FRAME=_function_proof(frame)
_CALLER_KEY=tuple((name,_function_proof(_ranges.__dict__[name])) for name in ('key','exact','need','integer'))
_CALLER_REFERENCE=_ranges.REFERENCE;_CALLER_ROLES=_ranges.SOURCE_ROLES4;_CALLER_VERSION=_ranges.VERSION
_SELF=_sys.modules[__name__]
_EXTRA_SPEC=((_SELF,'CaptureAppendPermit5',('__init__',)),(_SELF,'CaptureIntent5',('__init__',)),
    (_SELF,'OriginalApi5',('__init__','guard')),(_state5,'OriginalGraph5',('__init__',)),
    (_family,'FamilyPermit4',('__init__',)),(_ranges,'LifecycleRangeProjection',('__init__',)),
    (_fds,'OriginalDescriptor',('__init__','require','close')))
for _module,_name,_names in _EXTRA_SPEC:
    _cls=_module.__dict__[_name];_raw=type.__getattribute__(_cls,'__dict__')
    need('__del__' not in _raw and len(_raw)<=128)
    _CLASS_API=(*_CLASS_API,(_module,_name,_cls,type.__getattribute__(_cls,'__mro__'),tuple(_raw.items()),
        tuple((name,_function_proof(_raw[name])) for name in _names)))
_ORIGINAL_CLASS_API=_CLASS_API
_SIZEOF=_sys.getsizeof
_OBJECT_SIZEOF=object.__sizeof__
_ORIGINAL_SIZEOF=_SIZEOF
_ORIGINAL_OBJECT_SIZEOF=_OBJECT_SIZEOF
_SLOT_CHARGE=65536

# Exact private field schema, not a reflection-based adoption of caller data.
_SLOT_KEYS=(('capture', ('_fixed', '_latest', 'api', 'authorized', 'background', 'close_proof', 'close_receipt', 'caller_rows', '_caller_rows', 'closed_family', 'closed_projection', 'drive', 'drive_consumed', 'failed', 'family', 'fixed', 'gate', 'helper', 'hooks', 'intent', 'latest', 'lock', 'old', 'old_disk', 'old_state', 'old_state_sha', 'owner', 'phase', 'prefix', 'prefix_sha', 'raw', 'read_floor', 'receipt', 'requested', 'role_commands', 'root_bytes', 'root_confirmed', 'root_receipt', 'root_stamp', 'row', 'row_sha', 'seed_receipts', 'source_index', 'stage', 'started', 'transfer', 'world_row', 'world_row_sha', 'world_started')), ('stage', ('holder', 'source', 'reserve', 'graph', 'batch', 'result', 'failed', 'choices', 'signature', 'reserve_seal')), ('intent', ('helper', 'invocation', 'role', 'caller_rows')), ('descriptor', ('fd', 'anchor', 'closed', 'lost', 'node')), ('family', ('gate', 'writer', 'value', 'value_size', 'value_sha', 'projection', 'projection_sha', 'root', 'root_sha', 'old', 'old_raw', 'old_stamp', 'created', 'prepared', 'committed', 'failed')), ('projection', ('view', 'value', 'encoded', 'references', 'peak', 'failed')))

def _slot_objects(permit):
    return (permit,permit.stage,permit.intent,permit.old,permit.closed_family,permit.closed_projection)

def _slot_scalar_work(value,refs):
    # Exact builtin only: sys.getsizeof can never dispatch foreign __sizeof__.
    need(_SIZEOF is _ORIGINAL_SIZEOF and _OBJECT_SIZEOF is _ORIGINAL_OBJECT_SIZEOF
        and _sys.getsizeof is _SIZEOF and object.__sizeof__ is _OBJECT_SIZEOF)
    pending=[(value,0)];nodes=total=0
    while pending:
        need(len(pending)<=32);item,depth=pending.pop();nodes+=1
        need(nodes<=256 and depth<=8)
        if any(item is ref for ref in refs):continue
        kind=type(item)
        need(kind is str or kind is int or kind is float or kind is bool or kind is type(None)
            or kind is tuple or kind is dict)
        total+=_SIZEOF(item);need(total<=16384)
        if kind is str:need(len(item)<=64 and item.isascii())
        elif kind is int:need(-(2**64)<item<2**64)
        elif kind is float:need(_native.number(item,0,1e15))
        elif kind is dict:need(not item)
        elif kind is tuple:
            need(len(item)<=16);pending.extend((child,depth+1) for child in item)
    return total

def prepare_completed_slot(permit):
    helper=permit.helper;guard_profile(helper.capture_api)
    objects=_slot_objects(permit)
    need(type(permit.old) is OriginalDescriptor and permit.old.closed is True and permit.old.fd==permit.old.anchor==-1
        and permit.old.lost is False and permit.api is helper.runtime_api is helper._runtime_api)
    refs=(*objects,helper,permit.gate,permit.owner,permit.raw,permit.lock,permit.api,
        permit.closed_projection.view,permit.intent.invocation,permit.close_proof)
    rows=[];backing=work=scalar=fields=headers=0
    for obj,(_name,keys) in zip(objects,_SLOT_KEYS):
        raw=object.__getattribute__(obj,'__dict__')
        need(type(raw) is dict and len(raw)==len(keys) and all(type(key) is str and key.isascii() and len(key)<=32 for key in raw))
        need(all(key in raw for key in keys));fields+=len(raw);need(fields<=96)
        backing+=_SIZEOF(raw);headers+=_OBJECT_SIZEOF(obj)+16
        need(backing<=8192 and headers<=512)
        expected=dict(raw);work+=_SIZEOF(expected);need(work<=8192)
        if obj is permit:
            expected['phase']='completed';expected['transfer']=expected['root_receipt']=None
        elif obj is permit.stage:
            expected['graph']=expected['source']=expected['result']=expected['batch']=expected['reserve_seal']=None
            expected['reserve']=0
        for key,item in expected.items():
            scalar+=_SIZEOF(key)+_slot_scalar_work(item,refs);need(scalar<=16384)
        entries=tuple(expected.items());rows.append((obj,raw,entries))
    rows=tuple(rows)
    seal_bytes=_SIZEOF(rows)+sum(_SIZEOF(row)+_SIZEOF(row[2])+sum(_SIZEOF(pair) for pair in row[2]) for row in rows)
    need(seal_bytes<=8192)
    # Immutable actual identities/values, not a mutable cached cost/current fact.
    return (permit,rows,refs,backing,headers,scalar,seal_bytes)

def completed_slot_guard(slot,helper,*,preparing=False):
    need(_SIZEOF is _ORIGINAL_SIZEOF and _OBJECT_SIZEOF is _ORIGINAL_OBJECT_SIZEOF)
    need(type(slot) is tuple and len(slot)==7 and type(preparing) is bool)
    permit,rows,refs,backing,headers,scalar,seal_bytes=slot
    need(type(rows) is tuple and len(rows)==6 and type(refs) is tuple and len(refs)<=16
        and all(type(value) is int for value in (backing,headers,scalar,seal_bytes))
        and backing<=8192 and headers<=512 and scalar<=16384 and seal_bytes<=8192)
    need(type(rows[0]) is tuple and len(rows[0])==3)
    pd=rows[0][1];need(type(pd) is dict)
    classes=(CaptureAppendPermit5,_state5.OriginalGraph5,CaptureIntent5,OriginalDescriptor,_family.FamilyPermit4,_ranges.LifecycleRangeProjection)
    size=0
    for index,row in enumerate(rows):
        need(type(row) is tuple and len(row)==3)
        obj,raw,entries=row
        need(type(obj) is classes[index])
        # Stored original dict access is resource-only even if a later class
        # change has removed business/source authority. No descriptor lookup.
        need(type(raw) is dict and type(entries) is tuple and len(raw)==len(entries)
            and all(type(key) is str for key in raw))
        size+=_SIZEOF(raw);need(size<=8192)
        for key,value in entries:
            if preparing and obj is permit and key in ('phase','transfer','root_receipt'):continue
            if preparing and obj is rows[1][0] and key in ('graph','source','result','batch','reserve_seal','reserve'):continue
            current=raw[key];need(current is value)
            if type(value) is dict:need(not value)
    sd=rows[1][1];descriptor=rows[3][1]
    need(permit is rows[0][0] and pd['stage'] is rows[1][0] and pd['intent'] is rows[2][0]
        and pd['old'] is rows[3][0] and pd['closed_family'] is rows[4][0] and pd['closed_projection'] is rows[5][0])
    need(pd['helper'] is helper and pd['api'] is helper.runtime_api is helper._runtime_api
        and pd['root_confirmed'] is True and pd['drive_consumed'] is True
        and pd['failed'] is False and pd['close_receipt'] is not None
        and descriptor['closed'] is True and descriptor['lost'] is False
        and descriptor['fd']==descriptor['anchor']==-1)
    if not preparing:need(pd['phase']=='completed' and sd['graph'] is None)
    return _SLOT_CHARGE
