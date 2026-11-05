"""Cold Pending3 receipt for the actual original Session state replacement.

No Session writer is replaced. Only a known successful stage return can
confirm this one original old/new inode lineage. No source or input authority.
"""
import json,os,re
from types import FunctionType,MethodType
from adapters.native_feature_observation import need
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.chat_journey.archive_file import signature
from adapters.script_journey.history import canonical
from adapters.pico4.lifecycle_descriptor_close import pin,guard as descriptor_guard,close_original
from openxr_input.adapter_session import PicoOpenXrAdapterSession

_NAMES=('stage','_save','_save_path','_load','_lock','_wait_for_ack')
_SESSION=tuple((name,PicoOpenXrAdapterSession.__dict__[name],PicoOpenXrAdapterSession.__dict__[name].__code__) for name in _NAMES)
_LIMIT=4096

class SessionTransition1:
    def __init__(self,owner):
        self.owner=owner;self.session=owner.world.session;self.gate=owner.storage_gate
        self.raw=owner.originals;self.namespace=self.raw.namespace
        self.old=self.new=None;self.before=self.after=None;self.old_raw=self.new_raw=None;self.value=None
        self.error=None;self.committed=False;self.close_receipts=None
        # Exact acquired/partial resources remain owned before any operation.
        need(owner.session_transitions is owner._session_transitions and len(owner.session_transitions)<2)
        owner.session_transitions.append(self)
        try:
            self.guard();self.gate.identity();self.namespace.guard_lease()
            current=self.raw.other_bill();raw=self.raw.archive.bill()
            need(current['decodedBytes']+raw['decodedBytes']<=16777216)
            self.close_proof=pin();self.path=self.session.state_path
            need(self.path.parent==self.namespace.path and re.fullmatch(r'session-[0-9a-f]{32}\.json',self.path.name))
            self.old=object.__new__(OriginalDescriptor)
            OriginalDescriptor.__init__(self.old,self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            descriptor_guard(self.old,self.close_proof);self.old.require(self.old.fd)
            self.before=tuple(signature(os.fstat(self.old.fd)))
            self.old_raw=os.pread(self.old.fd,_LIMIT+1,0)
            need(0<len(self.old_raw)<=_LIMIT and len(self.old_raw)==self.before[5]
                and tuple(signature(self.path.lstat()))==self.before
                and dict(self.namespace.lease[1])[self.path.name]==self.before)
            self.value=json.loads(self.old_raw);need(self.session._load()==self.value and canonical(self.value)+b'\n'==self.old_raw
                and self.value['processIdentity']==owner.binding['processIdentity'] and self.value['nextSequence']<0xffffffff)
        except BaseException as error:self.fail(error);raise

    def guard(self):
        from adapters.pico4.lifecycle_pending import PicoLifecyclePending
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        need(type(self.owner) is PicoLifecyclePending and self.owner.session_receipts is self.owner._session_receipts is True
            and self.owner.world.session is self.session and type(self.session) is PicoOpenXrAdapterSession
            and type(self.gate) is LifecycleFamilyGate4 and self.gate is self.owner.storage_gate
            and self.gate.writer is self.owner and self.gate.raw is self.raw and self.namespace is self.gate.namespace)
        self.owner.lock.assert_held()
        for name,function,code in _SESSION:
            current=PicoOpenXrAdapterSession.__dict__.get(name)
            need(type(current) is FunctionType and current is function and current.__code__ is code)
            bound=object.__getattribute__(self.session,name)
            need(type(bound) is MethodType and bound.__func__ is function and bound.__self__ is self.session)

    def confirm(self):
        try:
            self.guard();self.gate.identity();namespace=self.namespace
            require_directory(namespace.directory,namespace.path)
            need(not self.committed and self.error is None and namespace._write is None
                and namespace.lease is namespace._lease and namespace.lease is not None)
            names,pins=namespace.lease
            need(namespace.lease_names()==names and dict(pins)[self.path.name]==self.before)
            self.new=object.__new__(OriginalDescriptor)
            OriginalDescriptor.__init__(self.new,self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            descriptor_guard(self.new,self.close_proof);self.new.require(self.new.fd)
            self.after=tuple(signature(os.fstat(self.new.fd)));self.new_raw=os.pread(self.new.fd,_LIMIT+1,0)
            expected=dict(self.value,nextSequence=self.value['nextSequence']+1)
            need(0<len(self.new_raw)<=_LIMIT and self.new_raw==canonical(expected)+b'\n'
                and self.after[5]==len(self.new_raw) and tuple(signature(self.path.lstat()))==self.after
                and self.session._load()==expected and self.after[:2]!=self.before[:2])
            descriptor_guard(self.old,self.close_proof);self.old.require(self.old.fd)
            old=tuple(signature(os.fstat(self.old.fd)))
            need(old[:4]==self.before[:4] and old[4]==0 and old[5:7]==self.before[5:7]
                and old[7]>=self.before[7] and os.pread(self.old.fd,_LIMIT+1,0)==self.old_raw)
            updated=[]
            for name,stamp in pins:
                actual=tuple(signature((namespace.path/name).lstat()))
                if name==self.path.name:need(actual==self.after)
                elif actual!=stamp:namespace.observe_mutex(name,stamp,actual)
                updated.append((name,actual))
            need(namespace.lease_names()==names and tuple(signature(os.fstat(self.new.fd)))==self.after)
            # Both actual known pairs close once; later numeric FD reuse is irrelevant.
            self.close_receipts=(close_original(self.old,self.close_proof),close_original(self.new,self.close_proof))
            need(tuple(signature(self.path.lstat()))==self.after)
            namespace.lease=namespace._lease=(names,tuple(updated))
            namespace.guard_lease();namespace()
            self.committed=True
        except BaseException as error:self.fail(error);raise

    def fail(self,error):
        if self.error is None:self.error=(error,error.__traceback__)
        self.gate.poisoned=True;self.raw.failed=True;self.raw.archive.stopped=True
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        if not any(holder is self for _path,holder in UNRESOLVED):UNRESOLVED.append((self.namespace.path,self))


def metadata_guard(owner):
    """Resource-only bounds also hold for incomplete or failed transitions."""
    from adapters.pico4.lifecycle_namespace_bill import canonical_size
    need(owner.session_transitions is owner._session_transitions and type(owner.session_transitions) is list
        and len(owner.session_transitions)<=2)
    for transition in owner.session_transitions:
        need(type(transition) is SessionTransition1 and transition.owner is owner)
        for raw in (transition.old_raw,transition.new_raw):
            need(raw is None or type(raw) is bytes and len(raw)<=_LIMIT)
        need(transition.value is None or type(transition.value) is dict and canonical_size(transition.value,_LIMIT)<=_LIMIT)
