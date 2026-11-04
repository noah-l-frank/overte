"""Private exact-reader seal and explicit successful memory handback.

Derived from the original-callable/code/default custody used by the private
Emote ReplayCodecIdentity. No Emote schemas or release policy are imported.
Default False preserves conservative SUM. Selected success handback retains
all original Reader roots and never grants fresh observation or source authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import FunctionType, BuiltinFunctionType
import copy
import json
import sys
from adapters import native_feature_observation as native
from adapters import recorded_preview_history as voice
from adapters import native_account_observation as account
from adapters import native_animation_history as animation
from adapters import audio_preview_lifetime as lifetime
from adapters.pico4 import audio_settings_source as settings
from adapters.pico4 import audio_pages as pages
from adapters.pico4 import navigation
from adapters.pico4 import lifecycle_namespace_bill as sizing
from adapters.script_journey import history
from adapters.pico4 import audio_cleanup_io as cleanup_io
from adapters.pico4 import audio_cleanup_snapshot as cleanup_snapshot
from adapters.pico4 import audio_cleanup_profile as cleanup_profile
from adapters.native_feature_observation import need

MODULES=(native,voice,account,animation,lifetime,settings,pages,navigation,sizing,history,
         json,json.decoder,json.encoder,json.scanner,copy,cleanup_io,cleanup_snapshot,cleanup_profile)
CLASSES=(native.NativeFeatureObservation,settings.PicoAudioSettings,pages.PicoAudioPages,
         json.JSONDecoder,json.JSONEncoder,cleanup_io.PicoAudioCleanupIO1,
         cleanup_snapshot.AudioCleanupSnapshot1,cleanup_profile.AudioCleanupBudget1)
NATIVE_FIELDS=frozenset(('send','original','clock_ms','guard','pid','before_io','ios','monotonic','sleep',
    'instance','sequence','rig','rig_sequence','lifecycle','voice_event_sequence','voice_history',
    'animation_history','account_history'))
SETTINGS_FIELDS=frozenset(('send','original','clock_ms','guard','pid','monotonic','sleep','source_lock',
    'previous','last_raw','last_sha256'))
META_SCRATCH=131072
META_FIXED=16384

PAGES_FIELDS=frozenset(('read','clock_ms','guard','pid','bridge','source_lock','monotonic','sleep',
    'previous','last_raw','last_sha256'))


def callable_entries():
    result=[]
    for module in (*MODULES,sys.modules[__name__]):
        need(len(vars(module))<=512)
        for name,value in sorted(vars(module).items()):
            if type(value) in (FunctionType,BuiltinFunctionType,type):
                result.append((module,name,value))
    for cls in (*CLASSES,ClosedAudioReaderSeal):
        need(len(vars(cls))<=512)
        for name,value in sorted(vars(cls).items()):
            if type(value) is FunctionType:result.append((cls,name,value))
    result.append((sys,'getsizeof',sys.getsizeof))
    need(len(result)<=512)
    return tuple(result)


def default_shape(value):
    if any(type(value) is cls for cls in (type(None),int,float,bool,str,bytes)):return (type(value),value)
    if type(value) is list:
        need(not value);return (type(value),id(value))
    if type(value) is dict:
        # stdlib json.decoder.py_scanstring owns its documented BACKSLASH
        # mapping as a nonempty default. Pin original object AND exact bounded
        # primitive contents; no opaque mutable defaults are accepted.
        need(len(value)<=64 and all(type(k) is str and len(k)<=512
            and any(type(v) is cls for cls in (str,int,bool,type(None))) and (type(v) is not str or len(v)<=512)
            for k,v in value.items()))
        return ('primitive-mapping',id(value),tuple((k,type(v),v) for k,v in sorted(value.items())))
    need(callable(value));return ('callable',id(value))


def function_state(value):
    if type(value) is type:return (None,None,None)
    defaults=getattr(value,'__defaults__',None)
    keywords=getattr(value,'__kwdefaults__',None)
    return (getattr(value,'__code__',None),
        None if defaults is None else tuple(default_shape(v) for v in defaults),
        None if keywords is None else tuple((k,default_shape(v)) for k,v in sorted(keywords.items())))


def metadata_preflight(entries,credit):
    """Before state/default copies: fixed-profile incremental metadata bound.

    Count original callable/module/code/default payloads as aliases to their
    already existing source objects; only new reference/shape tables are
    constructed. The complete retained decoded Reader roots have their separate
    original decoder budget. No per-node identity map or full DTO is allocated.
    """
    need(type(entries) is tuple and len(entries)<=512 and type(credit) is int)
    pointer=sys.getsizeof((None,))-sys.getsizeof(())
    base=sys.getsizeof(())
    def tuple_size(count):
        need(type(count) is int and 0<=count<=512)
        return base+pointer*count
    id_size=sys.getsizeof(id(entries))
    def shape_size(value):
        kind=type(value)
        if any(kind is cls for cls in (type(None),int,float,bool,str,bytes)):return tuple_size(2)
        if kind is list:
            need(not value);return tuple_size(2)+id_size
        if kind is dict:
            need(len(value)<=64 and all(type(k) is str and len(k)<=512
                and any(type(v) is cls for cls in (str,int,bool,type(None))) and (type(v) is not str or len(v)<=512)
                for k,v in value.items()))
            return tuple_size(3)+id_size+tuple_size(len(value))+len(value)*tuple_size(3)
        need(callable(value));return tuple_size(2)+id_size
    # entry triple + state triple + strong-default-holder pair, top-level
    # arrays, fixed Reader/closure/protocol/control/dictionary metadata.
    count=len(entries)
    resident=META_FIXED+3*tuple_size(count)+count*(2*tuple_size(3)+tuple_size(2))
    maximum_signature=0
    for _owner,_name,fn in entries:
        if type(fn) is type:
            resident+=tuple_size(0)
            continue
        defaults=getattr(fn,'__defaults__',None)
        keywords=getattr(fn,'__kwdefaults__',None)
        need(defaults is None or type(defaults) is tuple and len(defaults)<=64)
        need(keywords is None or type(keywords) is dict and len(keywords)<=64
            and all(type(k) is str for k in keywords))
        extra=0
        if defaults is not None:extra+=tuple_size(len(defaults))+sum(shape_size(v) for v in defaults)
        if keywords is not None:extra+=tuple_size(len(keywords))+sum(tuple_size(2)+shape_size(v) for v in keywords.values())
        resident+=extra+tuple_size(0 if keywords is None else len(keywords))
        maximum_signature=max(maximum_signature,tuple_size(3)+extra)
    # A fresh require() entry table, sorted module/class dictionaries, current
    # signature temporaries and the bounded walk/control stack coexist with
    # the retained tables. No freed-canonical-buffer loan is assumed.
    fresh_table=tuple_size(count)+count*tuple_size(3)
    need(fresh_table+maximum_signature+65536<=META_SCRATCH)
    bound=resident+META_SCRATCH
    need(bound<=credit)
    return bound


class ClosedAudioReaderSeal:
    def __init__(self,sampler):
        self.sampler=self._sampler=sampler;self.io=self._io=sampler.io
        self.handback=self._handback=sampler.budget.decode_handback
        self.preserve_other=self._preserve_other=sampler.budget.preserve_other_decode
        self.retained=self._retained=0
        self.active=self._active=None;self.staged=self._staged=None
        self.readers=self._readers=(sampler.native,sampler.settings,sampler.pages)
        self.catalog=self._catalog=self.io.source_sets
        need(len(self.catalog)==(1 if sampler.epoch=='old' else 4))
        matches=tuple(row for row in self.catalog if row[0]==sampler.epoch and row[1]==sampler.role
            and row[4] is sampler.native and row[6] is sampler.settings and row[7] is sampler.pages)
        need(len(matches)==1)
        self.source_set=self._source_set=matches[0]
        if sampler.epoch=='new':
            need(self.preserve_other and sampler.native.sequence==0
                and sampler.settings.previous is None and sampler.pages.previous is None)
        self.entries=self._entries=callable_entries()
        self.metadata_bound=self._metadata_bound=metadata_preflight(self.entries,sampler.budget.decode_seal_metadata)
        # Strong default originals prevent id recycling. 512 entries and all
        # bounded scalar/default/closure/root metadata occupy a booked domain.
        self.states=self._states=tuple(function_state(row[2]) for row in self.entries)
        self.defaults=self._defaults=tuple((None,()) if type(row[2]) is type else
            (getattr(row[2],'__defaults__',None),tuple((getattr(row[2],'__kwdefaults__',None) or {}).values()))
            for row in self.entries)
        self.copy_dispatch=self._copy_dispatch=tuple(copy._deepcopy_dispatch.items())
        self.callbacks=self._callbacks=self.current_callbacks()
        self.callback_states=self._callback_states=tuple(function_state(v) for v in self.callbacks)
        self.closures=self._closures=tuple(tuple(cell.cell_contents for cell in (v.__closure__ or ()))
            for v in self.callbacks)
        self.protocol=self._protocol=(MODULES,CLASSES,NATIVE_FIELDS,SETTINGS_FIELDS,PAGES_FIELDS,META_SCRATCH,META_FIXED)
        self.io_clocks=self._io_clocks=(self.io.monotonic,self.io.sleep)
        self.allowed_codes=self._allowed_codes=tuple(c for c in self.io.sources.__func__.__code__.co_consts
            if type(c).__name__=='code')
        self.require()

    def current_callbacks(self):
        n,s,p=self.readers
        return (n.send,n.original,n.clock_ms,n.guard,s.send,s.original,s.clock_ms,s.guard,
                p.read,p.clock_ms,p.guard)

    def require(self):
        sampler=self._sampler;io=self._io
        need(type(self.handback) is bool and self.handback is self._handback is sampler.budget.decode_handback
            and type(self.preserve_other) is bool
            and self.preserve_other is self._preserve_other is sampler.budget.preserve_other_decode
            and type(self.retained) is int and self.retained==self._retained
            and 0<=self.retained<=16*1024*1024 and self.active is self._active and self.staged is self._staged)
        need(self.sampler is sampler and self.io is io and sampler.io is io
            and self.readers is self._readers and self.readers==(sampler.native,sampler.settings,sampler.pages)
            and self.entries is self._entries and self.states is self._states
            and self.defaults is self._defaults and self.copy_dispatch is self._copy_dispatch
            and self.callbacks is self._callbacks and self.callback_states is self._callback_states
            and self.closures is self._closures and self.allowed_codes is self._allowed_codes)
        need(self.protocol is self._protocol and all(a is b for a,b in zip(
            (MODULES,CLASSES,NATIVE_FIELDS,SETTINGS_FIELDS,PAGES_FIELDS,META_SCRATCH,META_FIXED),self.protocol))
            and type(self.metadata_bound) is int and self.metadata_bound==self._metadata_bound
            and self.metadata_bound<=sampler.budget.decode_seal_metadata
            and self.io_clocks is self._io_clocks and io.monotonic is self.io_clocks[0]
            and io.sleep is self.io_clocks[1])
        need(self.catalog is self._catalog is io.source_sets
            and len(self.catalog)==(1 if sampler.epoch=='old' else 4)
            and self.source_set is self._source_set
            and any(row is self.source_set for row in self.catalog)
            and self.source_set[4] is sampler.native and self.source_set[6] is sampler.settings
            and self.source_set[7] is sampler.pages)
        n,s,p=self.readers
        need(type(n) is native.NativeFeatureObservation and type(s) is settings.PicoAudioSettings
            and type(p) is pages.PicoAudioPages and set(vars(n))==NATIVE_FIELDS
            and set(vars(s))==SETTINGS_FIELDS and set(vars(p))==PAGES_FIELDS
            and n.before_io is None and n.ios is False and n.pid==s.pid==p.pid
            and s.source_lock is p.source_lock is sampler.budget.lock
            and p.bridge==sampler.binding['sessionId'])
        for reader in self.readers:
            need(reader.monotonic is io.monotonic and reader.sleep is io.sleep)
        current=callable_entries();need(len(current)==len(self.entries))
        for actual,original,state in zip(current,self.entries,self.states):
            need(actual[0] is original[0] and actual[1]==original[1] and actual[2] is original[2]
                and (type(actual[2]) is type or getattr(actual[2],'__code__',None) is state[0])
                and function_state(actual[2])==state)
        dispatch=tuple(copy._deepcopy_dispatch.items())
        need(len(dispatch)==len(self.copy_dispatch) and all(a is b and c is d
            for (a,c),(b,d) in zip(dispatch,self.copy_dispatch)))
        current=self.current_callbacks();need(len(current)==len(self.callbacks))
        for actual,original,state,cells in zip(current,self.callbacks,self.callback_states,self.closures):
            need(type(actual) is FunctionType and actual is original
                and actual.__code__ is state[0] and function_state(actual)==state
                and any(actual.__code__ is code for code in self.allowed_codes))
            closure=actual.__closure__ or ();need(len(closure)==len(cells))
            need(all(cell.cell_contents is old for cell,old in zip(closure,cells)))
            names=actual.__code__.co_freevars;need(set(names)<= {'self','identity'} and 'self' in names)
            for name,cell in zip(names,closure):
                need(cell.cell_contents is io if name=='self' else
                    type(cell.cell_contents) is str and cell.cell_contents==sampler.binding['processIdentity'])
        return True

    def retained_size(self):
        self.require();n,s,p=self.readers
        # Aliases only: no full decoded DTO or serialized projection is copied.
        roots=dict(native=dict(lifecycle=n.lifecycle,voice=n.voice_history,animation=n.animation_history,
            account=n.account_history,instance=n.instance,sequence=n.sequence,rig=n.rig,
            rigSequence=n.rig_sequence,voiceEventSequence=n.voice_event_sequence),
            settings=dict(previous=s.previous,raw=s.last_raw,sha=s.last_sha256),
            pages=dict(previous=p.previous,raw=p.last_raw,sha=p.last_sha256))
        size=sizing.canonical_size(roots,16*1024*1024)
        self.require()
        return size

    def begin(self):
        self.require();s=self.sampler;b=s.budget
        need(self.handback and not b.failed and self.active is None and self.staged is None
            and s.reading and s.partial_output is None and self.io.query is None
            and (b.decode_hold>=self.retained if self.preserve_other else b.decode_hold==self.retained))
        self.active=self._active=(b.decode_hold,len(self.io.references),s.sequence)

    def stage(self,encoded):
        self.require();s=self.sampler;b=s.budget
        need(self.handback and not b.failed and self.active is not None and self.staged is None
            and s.reading and type(encoded) is bytes and encoded is s.partial_output and len(encoded)<=16384
            and type(self.io.query) is tuple and len(self.io.query)==2)
        old,start,sequence=self.active
        need(sequence==s.sequence and b.decode_hold>old and len(self.io.references)==start+3
            and self.io.pending is None and not self.io.acquired)
        filenames=(native.FILE,settings.FILE,pages.FILE)
        for row,filename in zip(self.io.references[start:],filenames):
            association=row['association']
            need(association['epoch']==s.epoch and association['role']==s.role
                and association['processIdentity']==s.binding['processIdentity']
                and association['filename']==filename)
        # All decoder SUM still coexists with prior retained roots here. This
        # bounded read-only walk adds aliases, never a full DTO/blob copy.
        next_retained=64*self.retained_size()+3*65536
        next_total=old-self.retained+next_retained if self.preserve_other else next_retained
        need(0<=next_retained<=next_total<=b.decode_hold)
        self.staged=self._staged=(encoded,self.io.query,next_retained,b.decode_hold)

    def commit(self,encoded):
        self.require();s=self.sampler;b=s.budget
        need(self.handback and not b.failed and self.active is not None and self.staged is not None
            and self.staged[0] is encoded is s.partial_output and s.reading
            and self.io.query is None and b.decode_hold==self.staged[3])
        query=self.staged[1];now=self.io.monotonic()
        need(native.number(now,query[0],query[0]+1.5)
            and native.number(now,b.value['startedMonotonic'],b.value['deadlineMonotonic']))
        # Successful callback-free handback only. The local decoder frame has
        # returned, final original global/IO/clock guards have all succeeded,
        # and only immutable output bytes cross the exact pinned boundary.
        # Retained Reader roots stay charged; failure before here keeps fullSUM.
        retained=self.staged[2]
        combined=self.active[0]-self.retained+retained if self.preserve_other else retained
        # Every unrelated prior charge survives. Only this exact reader set
        # replaces its own old roots and successful local decoder work.
        b.decode_hold=combined;b._cost_seal=(b.row_slots,combined)
        self.retained=self._retained=retained
        self.active=self._active=None;self.staged=self._staged=None
