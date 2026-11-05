"""Prospective cold profile for the unchanged Background5 semantic graph.

This explicit cold profile conveys no original-read,
publication, input, currentness or retirement authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import FunctionType,ModuleType,CodeType,MethodType
from importlib import import_module
import sys
from adapters.native_feature_observation import need,LIMIT

PART=65536
PROFILE_RESERVE=5*PART
# Explicitly include lazy optional Native branches before any Native IO.
SOURCES=(
 ('adapters.pico4.lifecycle_background',('bytes_packet','original','source_original','feature_original','status','compact_quiet','same_editor','chat_current','advanced','validate_return')),
 ('adapters.pico4.lifecycle_background_source',('command','validate','accept')),
 ('adapters.pico4.lifecycle_source',('nonce','editors','validate','summary','validate_summary','accept','current_editor')),
 ('adapters.pico4.lifecycle_field_binding',('validate','advance')),
 ('adapters.pico4.lifecycle_gesture',('sample','known','nonzero','stream','validate','accept','consumed')),
 ('adapters.pico4.lifecycle_drive',('vector','quaternion','validate','continuity')),
 ('adapters.pico4.lifecycle_process',('identity','native','settings')),
 ('adapters.pico4.lifecycle_world',('neutral',)),
 ('adapters.native_feature_observation',('decode','validate','need','exact','number','integer','fresh')),
 ('adapters.native_chat_view',('entity_id','vr_keyboard','measured_keyboard')),
 ('adapters.recorded_preview_history',('phases','validate_history')),
 ('adapters.native_account_observation',('validate',)),
 ('adapters.native_animation_history',('original_origin','clip','validate')),
 ('adapters.native_animation_caller',('validate',)),
 ('adapters.native_animation_source',('nonce','digest','model','validate')),
 ('adapters.native_script_membership',('validate',)),
 ('adapters.native_script_observation',('text','validate_code')),
 ('adapters.native_script_compilations',('compilation',)),
 ('adapters.normal_feature_state',('context',)),
 ('feature_journeys.fixtures',('context',)),
 ('feature_journeys.contract',('identifier','typed_equal')),
 ('openxr_input.android_transport',('validate_native_status',)),
 ('adapters.pico4.lifecycle_back',('frame',)),
 ('adapters.pico4.lifecycle_namespace_bill',('canonical_size',)),
 ('adapters.chat_journey.source_chunks',('json_digest',)),
 ('adapters.script_journey.history',('canonical',)),
 ('copy',('deepcopy',)),('json',('loads','dumps')),
)


def decoded_bound(literal,wrapper_size):
    """Preparse canonical envelope over exact already-durable original bytes.

    Every JSON number contains an ASCII digit-run. Count runs even inside
    strings/escapes, deliberately overcounting. The canonical raw wrapper
    already bounds strings/keys/containers and integer spelling; each finite
    binary64 normalization needs at most32 additional characters per number.
    This is a byte walk, not a parser or an accepted/current fact.
    """
    need(type(literal) is bytes and len(literal)<=LIMIT
        and type(wrapper_size) is int and wrapper_size>=0)
    runs=0;previous=False
    for byte in literal:
        digit=48<=byte<=57
        if digit and not previous:runs+=1
        previous=digit
    return wrapper_size+32*runs+64


def code_names(code):
    pending=[code];names=set()
    while pending:
        item=pending.pop();names.update(item.co_names)
        pending.extend(value for value in item.co_consts if type(value) is CodeType)
    return names


class OriginalValidatorProfile5:
    """Budgeted cold identity/default/constant graph, never a cached verdict.

    The actual helper must strongly own this preallocated object and reserve
    PROFILE_RESERVE before calling its constructor. Constructor failures keep
    the partial object and the original reservation; no retry is admitted.
    """
    def __init__(self,owner):
        self.owner=owner;self.ready=False;self.spent=0
        self.bindings=[];self.functions=[];self.classes=[];self.objects=[];self.storage=[]
        self.todo=[];self.seen_functions=set();self.seen_bindings=set()
        self.seen_classes=set();self.modules={};self.self_profile=None
        need(sys.float_info.mant_dig==53 and sys.float_info.max_exp==1024 and sys.float_info.max_10_exp==308)
        self.function(decoded_bound)
        for module_name,names in SOURCES:
            module=import_module(module_name);need(type(module) is ModuleType)
            self.modules[module_name]=module;namespace=ModuleType.__getattribute__(module,'__dict__')
            self.binding(sys.modules,module_name)
            parent,leaf=module_name.rsplit('.',1) if '.' in module_name else ('',module_name)
            if parent:self.binding(import_module(parent).__dict__,leaf)
            for name in names:self.binding(namespace,name)
        self.class_profile(type(owner),('_validate_plain','_packet_plain','packet','evidence'))
        drive=self.modules['adapters.pico4.lifecycle_drive'].__dict__
        for name in ('AvatarDisplacement','AvatarReleaseWindow'):self.class_profile(drive[name])
        json=import_module('json');decoder=import_module('json.decoder');encoder=import_module('json.encoder')
        self.class_profile(decoder.JSONDecoder);self.class_profile(encoder.JSONEncoder)
        # Default decoder state/scanner are actual loaded originals. No new
        # scanner/library is substituted and no executable attribute is set.
        default=json.__dict__['_default_decoder']
        self.objects.append((default,type(default),self.snapshot(object.__getattribute__(default,'__dict__'))))
        copy=import_module('copy')
        for name in ('_deepcopy_dispatch','_keep_alive'):
            self.binding(copy.__dict__,name)
        if '_atomic_types' in copy.__dict__:self.binding(copy.__dict__,'_atomic_types')
        for module,names in ((decoder,('JSONObject','JSONArray','scanstring')),
                (encoder,('_make_iterencode','encode_basestring_ascii','c_make_encoder'))):
            for name in names:
                if name in module.__dict__:self.binding(module.__dict__,name)
        while self.todo:
            function=self.todo.pop();namespace=function.__globals__
            # The original wrapper's layout5 branch is unreachable while the
            # SAME unchanged validator runs with _plain5=True. Its helper entry
            # identity/code/default is pinned, but no alternate capture/IO
            # implementation is treated as part of this pure validator graph.
            if namespace.get('__name__')=='adapters.pico4.lifecycle_background_state5' and function.__name__=='helper_method':continue
            names=code_names(function.__code__)
            for name in names:
                if name in namespace:self.binding(namespace,name)
            # E.g. json.loads/math.sqrt/re.fullmatch/copy.deepcopy. Only
            # physically present module attributes are read, no __getattr__.
            for name in names:
                module=namespace.get(name)
                if type(module) is ModuleType:
                    attributes=ModuleType.__getattribute__(module,'__dict__')
                    for field in names:
                        if field in attributes:self.binding(attributes,field)
        self.todo=self.seen_functions=self.seen_bindings=self.seen_classes=None
        # These exact STORAGE leaves prove the already-reviewed data alias/
        # lifetime shape. Do not pretend their IO graph is semantic decoding.
        # They are class/MRO/raw-entry/code/default pinned, never invoked here.
        for module_name,class_name,names in (
                ('adapters.pico4.lifecycle_source_raw','LifecycleSourceRaw4',('_verify',)),
                ('adapters.pico4.lifecycle_background_raw','LifecycleBackgroundRaw3',('verify','verify_before_batch')),
                ('adapters.pico4.audio_raw_archive','AudioRawArchive',('verify','_verify')),
                ('adapters.chat_journey.archive_file','ClosedOriginalFile',('read',))):
            module=import_module(module_name);cls=module.__dict__[class_name];need(type(cls) is type)
            raw=type.__getattribute__(cls,'__dict__');entries=tuple(raw.items());functions=[]
            self.charge(256+128*len(entries))
            for name in names:
                function=raw.get(name);need(type(function) is FunctionType);self.charge(256)
                functions.append((name,function,function.__code__,function.__defaults__,self.snapshot(function.__defaults__),
                    function.__kwdefaults__,self.snapshot(function.__kwdefaults__)))
            self.storage.append((module,class_name,cls,type.__getattribute__(cls,'__mro__'),entries,tuple(functions)))
        module=import_module('adapters.pico4.lifecycle_raw_ranges');functions=[]
        for name in ('verified_ranges','record_literal'):
            function=module.__dict__[name];need(type(function) is FunctionType);self.charge(256)
            functions.append((name,function,function.__code__,function.__defaults__,self.snapshot(function.__defaults__),
                function.__kwdefaults__,self.snapshot(function.__kwdefaults__)))
        self.storage.append((module,None,None,None,None,tuple(functions)))
        self.storage=tuple(self.storage)
        fields=object.__getattribute__(owner,'__dict__')
        self.actual_storage=None
        if 'originals' in fields:
            bank=fields['originals'];need(type(bank) is self.storage[0][2])
            archive=object.__getattribute__(bank,'archive');need(type(archive) is self.storage[2][2])
            self.actual_storage=(bank,archive,object.__getattribute__(archive,'closed'))
        self.bindings=tuple(self.bindings);self.functions=tuple(self.functions)
        self.classes=tuple(self.classes);self.objects=tuple(self.objects)
        self.lengths=(len(self.bindings),len(self.functions),len(self.classes),len(self.objects))
        self.ready=True

    def charge(self,size):
        need(type(size) is int and 0<=size<=PROFILE_RESERVE and self.spent+size<=PROFILE_RESERVE)
        self.spent+=size

    def snapshot(self,value,depth=0):
        need(depth<=64);kind=type(value);self.charge(128)
        if kind is FunctionType:
            self.function(value);return ('identity',value)
        if kind is dict:
            self.charge(64*len(value))
            return ('dict',value,tuple((self.snapshot(key,depth+1),self.snapshot(child,depth+1)) for key,child in value.items()))
        if kind is list or kind is tuple:
            self.charge(32*len(value));return ('sequence',value,kind,tuple(self.snapshot(child,depth+1) for child in value))
        if kind is set or kind is frozenset:
            self.charge(64*len(value));return ('set',value,kind,frozenset(id(child) for child in value))
        if kind is str or kind is bytes:self.charge(4*len(value));return ('scalar',value,kind)
        if kind is int or kind is float or kind is bool or kind is type(None):return ('scalar',value,kind)
        return ('identity',value)

    def function(self,function):
        marker=id(function)
        if marker in self.seen_functions:return
        self.charge(256);self.seen_functions.add(marker)
        # Source-grammar functions are traversed transitively. The selected
        # actual stdlib function/code/C identities and JSON/deepcopy tables
        # are explicit; mutable regex caches are not grammar or data verdicts.
        name=function.__globals__.get('__name__','')
        if type(name) is str and (name.startswith(('adapters.','feature_journeys.','openxr_input.','json.')) or name in ('json','copy')):self.todo.append(function)
        self.functions.append((function,function.__code__,function.__defaults__,self.snapshot(function.__defaults__),
            function.__kwdefaults__,self.snapshot(function.__kwdefaults__)))

    def binding(self,namespace,name):
        marker=(id(namespace),name)
        if marker in self.seen_bindings:return
        self.charge(256+4*len(name));self.seen_bindings.add(marker)
        need(name in namespace);value=namespace[name]
        self.bindings.append((namespace,name,value,self.snapshot(value)))

    def class_profile(self,cls,names=None):
        need(type(cls) is type)
        if id(cls) in self.seen_classes:return
        self.charge(256);self.seen_classes.add(id(cls))
        raw=type.__getattribute__(cls,'__dict__')
        self.classes.append((cls,type.__getattribute__(cls,'__mro__'),tuple((name,value) for name,value in raw.items())))
        for name,value in raw.items():
            if type(value) is FunctionType and (names is None or name in names):self.binding(raw,name)

    @staticmethod
    def matches(value,sealed):
        label=sealed[0]
        if label=='identity':return value is sealed[1]
        if label=='scalar':return type(value) is sealed[2] and (value is sealed[1] or value==sealed[1])
        if value is not sealed[1]:return False
        if label=='dict':
            if type(value) is not dict or len(value)!=len(sealed[2]):return False
            return all(OriginalValidatorProfile5.matches(key,a) and OriginalValidatorProfile5.matches(child,b)
                for (key,child),(a,b) in zip(value.items(),sealed[2]))
        if label=='sequence':
            return type(value) is sealed[2] and len(value)==len(sealed[3]) and all(
                OriginalValidatorProfile5.matches(child,fixed) for child,fixed in zip(value,sealed[3]))
        return type(value) is sealed[2] and frozenset(id(child) for child in value)==sealed[3]

    def guard(self):
        need(self.ready is True and self.lengths==(len(self.bindings),len(self.functions),len(self.classes),len(self.objects)))
        for namespace,name,value,sealed in self.bindings:
            need(namespace.get(name) is value and self.matches(value,sealed))
        for function,code,defaults,default_seal,keywords,keyword_seal in self.functions:
            need(type(function) is FunctionType and function.__code__ is code
                and function.__defaults__ is defaults and self.matches(defaults,default_seal)
                and function.__kwdefaults__ is keywords and self.matches(keywords,keyword_seal))
        for cls,mro,entries in self.classes:
            raw=type.__getattribute__(cls,'__dict__')
            need(type.__getattribute__(cls,'__mro__') is mro and len(raw)==len(entries)
                and all(raw.get(name) is value for name,value in entries))
        for value,cls,sealed in self.objects:
            need(type(value) is cls and self.matches(object.__getattribute__(value,'__dict__'),sealed))
        for module,name,cls,mro,entries,functions in self.storage:
            if cls is not None:
                need(module.__dict__.get(name) is cls and type.__getattribute__(cls,'__mro__') is mro)
                raw=type.__getattribute__(cls,'__dict__')
                need(len(raw)==len(entries) and all(raw.get(key) is value for key,value in entries))
            else:raw=module.__dict__
            for name,function,code,defaults,sealed,keywords,keyword_seal in functions:
                need(raw.get(name) is function and type(function) is FunctionType and function.__code__ is code
                    and function.__defaults__ is defaults and self.matches(defaults,sealed)
                    and function.__kwdefaults__ is keywords and self.matches(keywords,keyword_seal))


        if self.actual_storage is not None:
            bank,archive,closed=self.actual_storage
            need(type(bank) is self.storage[0][2] and type(archive) is self.storage[2][2]
                and object.__getattribute__(bank,'archive') is archive
                and object.__getattribute__(archive,'closed') is closed and type(closed) is dict and len(closed)<=512)
            for instance,index,names in ((bank,0,('_verify',)),(bank,1,('verify','verify_before_batch')),
                    (archive,2,('verify','_verify'))):
                entries=self.storage[index][5]
                for name in names:
                    function=next(row[1] for row in entries if row[0]==name)
                    bound=object.__getattribute__(instance,name)
                    need(type(bound) is MethodType and bound.__self__ is instance and bound.__func__ is function)
            function=self.storage[3][5][0][1]
            for file in closed.values():
                need(type(file) is self.storage[3][2])
                bound=object.__getattribute__(file,'read')
                need(type(bound) is MethodType and bound.__self__ is file and bound.__func__ is function)


def profile_proof(profile):
    need(type(profile) is OriginalValidatorProfile5 and profile.ready is True)
    cls=OriginalValidatorProfile5;raw=type.__getattribute__(cls,'__dict__')
    entries=tuple(raw.items());functions=[]
    for name,value in entries:
        function=value.__func__ if type(value) is staticmethod else value
        if type(function) is FunctionType:functions.append((name,value,function,function.__code__))
    return (cls,type.__getattribute__(cls,'__mro__'),entries,tuple(functions),profile,
        profile.bindings,profile.functions,profile.classes,profile.objects,profile.lengths,profile.storage,profile.actual_storage)


def require_profile(profile,proof):
    # Raw class/code proof precedes any instance descriptor or method binding.
    need(type(proof) is tuple and len(proof)==12 and OriginalValidatorProfile5 is proof[0]
        and type(profile) is proof[0] and profile is proof[4])
    cls=proof[0];raw=type.__getattribute__(cls,'__dict__')
    need(type.__getattribute__(cls,'__mro__') is proof[1] and len(raw)==len(proof[2])
        and all(raw.get(name) is value for name,value in proof[2]))
    for name,value,function,code in proof[3]:
        need(raw.get(name) is value and type(function) is FunctionType and function.__code__ is code)
    fields=object.__getattribute__(profile,'__dict__')
    need(not any(name in fields for name,_value in proof[2]))
    need(profile.bindings is proof[5] and profile.functions is proof[6]
        and profile.classes is proof[7] and profile.objects is proof[8] and profile.lengths is proof[9] and profile.storage is proof[10] and profile.actual_storage is proof[11])
    function=raw['guard'];bound=object.__getattribute__(profile,'guard')
    need(type(bound) is MethodType and bound.__self__ is profile and bound.__func__ is function)
    function(profile)
