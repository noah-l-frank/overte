"""Two independent in-memory copies of exact builtin JSON container graphs.

Only values, exact types and the mutable alias/cycle graph are preserved by
this optional fast path. Immutable Python object identities are not promised.
Unsupported data or changed copying semantics return None. The helper never
invokes the caller's copier; its original assignment order stays with its owner. No stored file, DTO verdict or native observation is deserialized. The caller
retains its existing ownership lock over the input graph throughout copying.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy as _copy
import marshal as _marshal
import sys as _sys
from math import isfinite as _finite
from types import FunctionType

_MAX_NODES=262144
_MAX_DEPTH=128
_MAX_BYTES=32*1024*1024
_MISSING=object()
_SUPPORTED=_sys.implementation.name=='cpython' and _sys.version_info[:2]>=(3,13)
_JSON=(dict,list,str,int,float,bool,type(None))
_ATOMIC=(str,int,float,bool,type(None))
_DUMPS=_marshal.dumps
_LOADS=_marshal.loads


def _dispatch_values(table):
    if type(table) is not dict or any(type(key) is not type for key in table):return None
    # Identity comparisons never invoke a registered foreign metaclass's
    # equality/hash methods. Only the seven exact JSON dispatch slots matter.
    return tuple(next((value for key,value in table.items() if key is kind),_MISSING) for kind in _JSON)


def _atomic_flags(value):
    if value is _MISSING:return ()
    if (type(value) is not set and type(value) is not frozenset) or any(type(item) is not type for item in value):return None
    return tuple(any(item is kind for item in value) for kind in _JSON)


_DEEPCOPY=_copy.deepcopy
_DISPATCH=_copy._deepcopy_dispatch
_DISPATCH_VALUES=_dispatch_values(_DISPATCH)
_ATOMIC_SET=vars(_copy).get('_atomic_types',_MISSING)
_ATOMIC_FLAGS=_atomic_flags(_ATOMIC_SET)
_FUNCTIONS=tuple((name,value,value.__code__,value.__defaults__,value.__kwdefaults__,value.__closure__)
    for name in ('deepcopy','_deepcopy_list','_deepcopy_dict','_keep_alive','_deepcopy_atomic')
    if type(value:=vars(_copy).get(name)) is FunctionType)
_DEFAULTS=getattr(_DEEPCOPY,'__defaults__',None)
_NIL=_DEFAULTS[1] if type(_DEFAULTS) is tuple and len(_DEFAULTS)==2 else _MISSING


def _same_copy_impl(copier):
    if not _SUPPORTED:return False
    if copier is not _DEEPCOPY or vars(_copy).get('deepcopy') is not _DEEPCOPY:return False
    if vars(_copy).get('_deepcopy_dispatch') is not _DISPATCH or _DISPATCH_VALUES is None:return False
    current=_dispatch_values(_DISPATCH)
    if current is None or any(actual is not expected for actual,expected in zip(current,_DISPATCH_VALUES)):return False
    atomic=vars(_copy).get('_atomic_types',_MISSING)
    if atomic is not _ATOMIC_SET or _ATOMIC_FLAGS is None or _atomic_flags(atomic)!=_ATOMIC_FLAGS:return False
    for name,function,code,defaults,kwdefaults,closure in _FUNCTIONS:
        if (vars(_copy).get(name) is not function or function.__code__ is not code
            or function.__defaults__ is not defaults or function.__kwdefaults__ is not kwdefaults
            or function.__closure__ is not closure):return False
    defaults=_DEEPCOPY.__defaults__
    if (type(defaults) is not tuple or len(defaults)!=2 or defaults[0] is not None
        or defaults[1] is not _NIL or type(_NIL) is not list or len(_NIL)!=0):return False
    # These two builtins are reached by deepcopy and _keep_alive; no dynamic
    # module-global override may gain a different literal copying behavior.
    if vars(_copy).get('type',type) is not type or vars(_copy).get('id',id) is not id:return False
    return vars(_marshal).get('dumps') is _DUMPS and vars(_marshal).get('loads') is _LOADS


def _same_copy(copier):
    try:return _same_copy_impl(copier)
    except (AttributeError,TypeError,RuntimeError):return False


def _scan_json_graph(value):
    """Visit exact builtin containers iteratively, without user callbacks."""
    dict_type,list_type,text_type,int_type,float_type,bool_type,none_type=_JSON
    pending=[(value,0)];containers={};nodes=0
    while pending:
        item,depth=pending.pop();nodes+=1
        if nodes>_MAX_NODES or depth>_MAX_DEPTH:return None
        kind=type(item)
        if kind is text_type or kind is int_type or kind is bool_type or kind is none_type:continue
        if kind is float_type:
            if not _finite(item):return None
            continue
        if kind is not dict_type and kind is not list_type:return None
        identity=id(item)
        if identity in containers:
            if containers[identity] is not item:return None
            continue
        containers[identity]=item
        if kind is dict_type:
            for key,child in item.items():
                if type(key) is not text_type:return None
                nodes+=1
                if nodes>_MAX_NODES:return None
                pending.append((child,depth+1))
                if nodes+len(pending)>_MAX_NODES:return None
        else:
            for child in item:
                pending.append((child,depth+1))
                if nodes+len(pending)>_MAX_NODES:return None
    # Strong references protect visited container identities until copying
    # ends. This map is call-local and supplies no later observation/verdict.
    return containers


def _roundtrip(value,copier,allowed):
    # These bytes come only from this process's just-scanned own graph.
    # No file/caller bytes/code object enter the marshal reader.
    raw=_DUMPS(value,4,allow_code=False)
    if type(raw) is not bytes or len(raw)>_MAX_BYTES:raise ValueError('JSON clone resource budget')
    if not allowed():return False,None
    cached=_LOADS(raw,allow_code=False)
    if not allowed():return False,None
    outward=_LOADS(raw,allow_code=False)
    return True,(cached,outward)


def _helper_epoch(expected):
    namespace,missing,functions,values=expected
    # The dictionary itself and the immutable expected tuple are bound in the
    # public function's import-time default, not taken from current globals.
    for name,function,code,defaults,kwdefaults,closure in functions:
        actual=namespace.get(name,missing)
        if (actual is not function or function.__code__ is not code
            or function.__defaults__ is not defaults or function.__kwdefaults__ is not kwdefaults
            or function.__closure__ is not closure):return False
    for name,value in values:
        if namespace.get(name,missing) is not value:return False
    return True


_HELPER_FUNCTIONS=tuple((name,function,function.__code__,function.__defaults__,function.__kwdefaults__,function.__closure__)
    for name in ('_dispatch_values','_atomic_flags','_same_copy_impl','_same_copy','_scan_json_graph','_roundtrip')
    for function in (globals()[name],))
_HELPER_VALUES=tuple((name,globals()[name]) for name in (
    '_MAX_NODES','_MAX_DEPTH','_MAX_BYTES','_MISSING','_SUPPORTED','_JSON','_ATOMIC','_DUMPS','_LOADS',
    '_copy','_marshal','_sys','_finite','FunctionType','_DEEPCOPY','_DISPATCH','_DISPATCH_VALUES',
    '_ATOMIC_SET','_ATOMIC_FLAGS','_FUNCTIONS','_DEFAULTS','_NIL'))
# No module-global override of a builtin called by the closed helper graph
# may run before the epoch check. These names are normally absent here.
_HELPER_VALUES+=tuple((name,_MISSING) for name in ('type','id','len','any','next','zip','tuple','vars','getattr','dict','list','str','int','float','bool','set','frozenset') if name not in globals())
_HELPER_EXPECTED=(globals(),_MISSING,_HELPER_FUNCTIONS,_HELPER_VALUES)


def clone_pair(value,copier,_literal=(_helper_epoch,_helper_epoch.__code__,_HELPER_EXPECTED)):
    def allowed():
        epoch=_helper_epoch
        return (epoch is _literal[0] and epoch.__code__ is _literal[1]
            and epoch(_literal[2]) and _same_copy(copier))
    if not allowed():return None
    try:containers=_scan_json_graph(value)
    except (RuntimeError,RecursionError,MemoryError):containers=None
    if containers is None or not allowed():return None
    failed=False
    try:complete,result=_roundtrip(value,copier,allowed)
    except Exception:
        # Marshal audit/policy errors also disable this pure optimization.
        # KeyboardInterrupt/SystemExit/GeneratorExit remain uncaught.
        failed=True
    if failed:
        containers=None
        return None
    if not complete or not allowed():return None
    return result
