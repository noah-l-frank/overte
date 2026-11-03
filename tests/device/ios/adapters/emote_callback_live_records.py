"""Existing AvatarRecordCache shared only by an explicit CallbackLive2 owner.

Historical rows keep their original measurement and clocks. Every hit retains
actual original file signatures/read membership; every outer Live decode keeps
its complete immutable inventory, row order, pending and orphan checks. Current
State/native admission, new acquisitions and resource cleanup never enter it.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from importlib import import_module
from types import FunctionType,ModuleType,BuiltinFunctionType,CodeType,MethodType
from contextvars import ContextVar
import re,sys,enum,__future__,socket,functools
from _collections import _tuplegetter
from pathlib import PurePath,Path
import hashlib,json,math
from PIL import Image,ImageChops,ImageStat,ImageFile,PngImagePlugin,ImageMode,_binary
import zlib
from adapters.native_feature_observation import need
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical,same
from ios.adapters.avatar_record_cache import AvatarRecordCache

# The actual source modules on the complete retained747 graph decode. Bind
# their full parser/class namespaces, including aliases and policy constants;
# a new/unsupported dependency takes the unchanged literal decoder.
PARSER_MODULES=('adapters.emote_rig_measurements', 'adapters.emote_source_profile', 'adapters.graphics_subject_geometry', 'adapters.native_animation_caller', 'adapters.native_animation_history', 'adapters.native_avatar_receive', 'adapters.native_clock_join', 'adapters.native_completed_frame', 'adapters.native_feature_observation', 'adapters.native_graphics_subject', 'adapters.native_script_files', 'adapters.native_script_loads', 'adapters.native_script_membership', 'adapters.native_script_observation', 'adapters.native_script_roots', 'adapters.native_script_terminal', 'adapters.native_script_work', 'adapters.native_vulkan_world_frame', 'adapters.normal_feature_state', 'adapters.original_file_reads', 'adapters.original_frame_store', 'adapters.original_key_packets', 'adapters.original_marker_clock_queries', 'adapters.original_marker_entities', 'adapters.original_marker_file_receipts', 'adapters.original_marker_holders', 'adapters.original_marker_pointers', 'adapters.original_marker_restoration_frames', 'adapters.original_marker_restoration_image', 'adapters.original_marker_scope', 'adapters.owned_vulkan_world_frame', 'adapters.phase_witness_publisher', 'adapters.pure_original_validation', 'adapters.render_view', 'adapters.script_feature.history', 'adapters.script_feature.lock', 'adapters.script_manager_status', 'adapters.script_ui_inventory', 'adapters.script_ui_root_ownership', 'adapters.token_emote_ui', 'adapters.token_script_file_ui', 'feature_journeys.contract', 'feature_journeys.evidence', 'feature_journeys.fixtures', 'feature_journeys.navigation_scene', 'feature_journeys.phase_fixture', 'feature_journeys.retirement_receipts', 'feature_journeys.scenarios', 'feature_journeys.terminal', 'ios.adapters.avatar_marker_scope', 'ios.adapters.avatar_record_cache', 'ios.adapters.avatar_renderers', 'ios.adapters.avatar_state', 'ios.adapters.create_entities', 'ios.adapters.create_state', 'ios.adapters.emote_actions', 'ios.adapters.emote_archive_round', 'ios.adapters.emote_callback_archive', 'ios.adapters.emote_callback_current_state', 'ios.adapters.emote_callback_drain_originals', 'ios.adapters.emote_callback_live', 'ios.adapters.emote_callback_retirement', 'ios.adapters.emote_callback_samples', 'ios.adapters.emote_callback_scene', 'ios.adapters.emote_cleanup', 'ios.adapters.emote_controls', 'ios.adapters.emote_held_marker_scope', 'ios.adapters.emote_images', 'ios.adapters.emote_keyed_retirement', 'ios.adapters.emote_keys', 'ios.adapters.emote_marker_disposition', 'ios.adapters.emote_marker_files', 'ios.adapters.emote_marker_measurements', 'ios.adapters.emote_native_prefix', 'ios.adapters.emote_observation', 'ios.adapters.emote_original_lease', 'ios.adapters.emote_originals', 'ios.adapters.emote_peer', 'ios.adapters.emote_rendered_retirement', 'ios.adapters.emote_retirement', 'ios.adapters.emote_rooted_live', 'ios.adapters.emote_rooted_marker_scope', 'ios.adapters.emote_rooted_retirement', 'ios.adapters.emote_rooted_scene_retirement', 'ios.adapters.emote_samples', 'ios.adapters.emote_sources', 'ios.adapters.emote_ui_inventory', 'ios.adapters.emote_world', 'ios.adapters.graphics_history', 'ios.adapters.login_source', 'ios.adapters.native_geometry', 'ios.adapters.normal_input', 'ios.adapters.places_model', 'ios.adapters.pointer_state', 'ios.adapters.scene_inventory', 'ios.adapters.script_dialogs', 'ios.adapters.viewport', 'ios.adapters.web_closures', 'ios.adapters.world_web_keys')


class _Unsupported(Exception):
    def __init__(self,kind=None,reason='unsupported-type'):
        self.kind=None if kind is None else (kind.__module__,kind.__qualname__)
        self.reason=reason


def _token(value,refs,active,depth=0):
    if depth>32:raise _Unsupported(type(value),'depth')
    kind=type(value)
    if kind in (str,bytes,int,bool,type(None)):return (kind.__name__,value)
    if kind is float:return ('float',value.hex())
    refs.append(value);identity=id(value)
    if identity in active:return ('recursive',identity)
    active=active|{identity}
    def token(item):return _token(item,refs,active,depth+1)
    # The sole supported plain object is this actual stdlib default sentinel.
    # Its current module binding is separately part of EXTERNAL_READERS below.
    if kind is object and value is socket._GLOBAL_DEFAULT_TIMEOUT:return ('socket-default-timeout',identity)
    if kind is FunctionType:
        refs.append(value.__code__) # Mutable function binding cannot permit old-code ID reuse.
        closure=() if value.__closure__ is None else tuple(token(cell.cell_contents) for cell in value.__closure__)
        return ('function',identity,id(value.__code__),token(value.__defaults__),token(value.__kwdefaults__),closure)
    if kind is CodeType:return ('code',identity)
    if value is int.__repr__ or value is float.__repr__:return ('json-number-repr',identity)
    if kind is json.JSONDecoder:
        fields=('object_hook','parse_float','parse_int','parse_constant','strict','object_pairs_hook','parse_object','parse_array','parse_string','memo','scan_once')
        if set(vars(value))!=set(fields):raise _Unsupported(kind,'json-decoder-state')
        return ('json-decoder',identity,tuple((name,token(getattr(value,name))) for name in fields))
    if kind is json.JSONEncoder:
        required={'skipkeys','ensure_ascii','check_circular','allow_nan','sort_keys','indent'}
        if not required<=set(vars(value))<=required|{'item_separator','key_separator','default'}:raise _Unsupported(kind,'json-encoder-state')
        return ('json-encoder',identity,token(vars(value)))
    if json.scanner.c_make_scanner is not None and kind is json.scanner.c_make_scanner:
        fields=('strict','object_hook','object_pairs_hook','parse_float','parse_int','parse_constant')
        return ('json-c-scanner',identity,tuple((name,token(getattr(value,name))) for name in fields))
    if kind is functools.cached_property:
        # Exact stdlib descriptor state only, not arbitrary __get__ objects.
        if set(vars(value))!={'func','attrname','__doc__','__module__'}:raise _Unsupported(kind,'cached-property-state')
        return ('cached-property',identity,token(value.func),token(value.attrname),token(value.__doc__),token(value.__module__))
    if kind is type(json.decoder.WHITESPACE.match):
        # Python3.14's native regex bound-method type differs from the ordinary
        # builtin function/method type. Only the actual immutable Pattern.match
        # receiver/name/descriptor is supported; no arbitrary native receiver.
        receiver=getattr(value,'__self__',None);name=getattr(value,'__name__',None)
        if type(receiver) is not re.Pattern or name!='match':raise _Unsupported(kind,'regex-bound-method')
        descriptor=vars(re.Pattern)['match'];refs.append(descriptor)
        return ('regex-match',identity,token(receiver),id(descriptor))
    if kind is BuiltinFunctionType:return ('builtin',identity)
    if kind is ModuleType:return ('module',identity)
    if isinstance(value,PurePath):return ('path',kind.__module__,kind.__qualname__,str(value))
    if isinstance(value,enum.Enum):return ('enum',id(kind),value.name,token(value.value))
    if kind is __future__._Feature:return ('future-feature',value.optional,value.mandatory,value.compiler_flag)
    if kind is partial:
        # Exact stdlib partial only. Its actual function/arguments/keyword
        # mapping all participate; keyword mutation cannot reuse an old row.
        # Unsupported nested values still force the unchanged literal parser.
        return ('partial',identity,token(value.func),token(value.args),token(value.keywords))
    if kind.__module__=='functools' and hasattr(value,'__wrapped__'):
        return ('stdlib-wrapper',identity,token(value.__wrapped__))
    if kind is ContextVar:return ('contextvar',identity) # No current validator-scope result is cached.
    if kind is re.Pattern:return ('pattern',identity,value.pattern,value.flags)
    if kind in (list,tuple):return (kind.__name__,tuple(token(item) for item in value))
    if kind in (set,frozenset):
        unsupported=next((type(item) for item in value if type(item) not in (str,int)),None)
        if unsupported is not None:raise _Unsupported(unsupported,'set-member')
        return (kind.__name__,tuple(sorted(token(item) for item in value)))
    if kind is dict:
        # Only exact str/int keys. Preserve the type in the canonical order:
        # integer1 and string'1' cannot alias, and bool/float/object keys refuse.
        unsupported=next((type(key) for key in value if type(key) not in (str,int)),None)
        if unsupported is not None:raise _Unsupported(unsupported,'mapping-key')
        entries=((token(key),token(item)) for key,item in value.items())
        return ('dict',tuple(sorted(entries,key=lambda row:row[0])))
    if kind in (staticmethod,classmethod):return (kind.__name__,token(value.__func__))
    if kind is property:return ('property',token(value.fget),token(value.fset),token(value.fdel))
    if kind is type:
        # External standard-library types are bindings, not project policies.
        if not value.__module__.startswith(('adapters.','ios.adapters.','feature_journeys.')):
            return ('external-type',identity)
        attributes=[]
        for name,item in sorted(vars(value).items()):
            if name.startswith('__') and name not in ('__init__','__enter__','__exit__','__call__'):continue
            attributes.append((name,token(item)))
        refs.append(value.__bases__) # Keep former bases alive if a class binding changes.
        return ('class',identity,tuple(id(base) for base in value.__bases__),tuple(attributes))
    raise _Unsupported(kind)


# External byte/JSON/PNG/parser entrypoints used by these actual decoders.
# External module identity alone cannot qualify a changed parser function.
EXTERNAL_READERS=((socket,'_GLOBAL_DEFAULT_TIMEOUT'),(json,'loads'),(json,'dumps'),(hashlib,'sha256'),(re,'fullmatch'),(re,'match'),(re,'compile'),
    (math,'isfinite'),(Image,'open'),(Image,'frombytes'),(ImageChops,'difference'),
    (Image.Image,'load'),(Image.Image,'convert'),(Image.Image,'crop'),(Image.Image,'getdata'),(Image.Image,'getpixel'))


# Explicit closed dependencies called by actual JSON and original RGBA PNG
# decoding. No external arbitrary instance/buffer or custom PNG decoder is
# accepted. Mutable registry bindings and same-function code changes participate.
EXTERNAL_READERS+=((json,'JSONDecoder'),(json,'JSONEncoder'),(json,'_default_decoder'),(json,'_default_encoder'),
    (json,'detect_encoding'),(json.decoder,'JSONObject'),(json.decoder,'JSONArray'),(json.decoder,'scanstring'),
    (json.decoder,'py_scanstring'),(json.decoder,'_decode_uXXXX'),(json.decoder,'_CONSTANTS'),
    (json.decoder,'BACKSLASH'),(json.decoder,'WHITESPACE'),(json.decoder,'WHITESPACE_STR'),(json.decoder,'STRINGCHUNK'),
    (json.decoder,'HEXDIGITS'),(json.scanner,'make_scanner'),(json.scanner,'c_make_scanner'),
    (json.scanner,'py_make_scanner'),(json.scanner,'NUMBER_RE'),(json.encoder,'c_make_encoder'),
    (json.encoder,'_make_iterencode'),(json.encoder,'encode_basestring'),(json.encoder,'encode_basestring_ascii'),
    (json.encoder,'py_encode_basestring'),(json.encoder,'py_encode_basestring_ascii'),(json.encoder,'ESCAPE_DCT'),
    (json.encoder,'ESCAPE'),(json.encoder,'ESCAPE_ASCII'),(json.encoder,'INFINITY'),
    (json.JSONDecoder,'__init__'),(json.JSONDecoder,'decode'),(json.JSONDecoder,'raw_decode'),
    (json.JSONEncoder,'__init__'),(json.JSONEncoder,'encode'),(json.JSONEncoder,'iterencode'),
    (json.JSONEncoder,'default'),(json.JSONEncoder,'item_separator'),(json.JSONEncoder,'key_separator'),
    (Image,'_getdecoder'),(Image,'_decompression_bomb_check'),(Image,'MAX_IMAGE_PIXELS'),(Image,'ID'),
    (Image,'core'),(Image.core,'zip_decoder'),(Image.core,'raw_decoder'),(Image.core,'new'),
    (Image,'getmodebase'),(Image,'getmodebands'),(Image,'preinit'),(Image,'init'),(ImageMode,'getmode'),
    (ImageFile,'_safe_read'),(ImageFile,'_tilesort'),(ImageFile,'LOAD_TRUNCATED_IMAGES'),
    (ImageFile,'MAXBLOCK'),(ImageFile,'SAFEBLOCK'),(ImageFile._Tile,'__new__'),
    (PngImagePlugin,'_accept'),(PngImagePlugin,'_MAGIC'),(PngImagePlugin,'MAX_TEXT_CHUNK'),
    (PngImagePlugin,'MAX_TEXT_MEMORY'),(PngImagePlugin,'_crc32'),(PngImagePlugin,'_safe_zlib_decompress'),
    (PngImagePlugin,'i16'),(PngImagePlugin,'i32'),(PngImagePlugin,'o8'),(PngImagePlugin,'o16'),(PngImagePlugin,'o32'),
    (_binary,'pack'),(_binary,'unpack_from'),(zlib,'crc32'),(zlib,'decompressobj'))
EXTERNAL_READERS+=((json,'decoder'),(json,'encoder'),(json.decoder,'scanner'),(json.decoder,'c_scanstring'),
    (Image,'_getencoder'),(Image,'Image'),(Image,'ImageMode'),(ImageMode,'ModeDescriptor'),(ImageMode,'sys'),(sys,'byteorder'),
    (Image.core,'raw_encoder'),(Image.core,'fill'),(Image.core,'blend'),(ImageFile,'Image'),(ImageFile,'_Tile'),
    (PngImagePlugin,'Image'),(PngImagePlugin,'ImageFile'),(PngImagePlugin,'zlib'),
    (_binary,'i32le'),(ImageStat,'Stat'),(ImageStat,'Image'),(ImageStat,'math'),(math,'sqrt'),
    (ImageChops,'Image'),(ImageChops,'lighter'),(functools,'cached_property'),
    (functools.cached_property,'__get__'),(functools.cached_property,'__set_name__'))
_PNG_CLASSES=(Image.Image,ImageFile.ImageFile,PngImagePlugin.PngImageFile,PngImagePlugin.PngStream,PngImagePlugin.ChunkStream,ImageStat.Stat,json.JSONDecoder,json.JSONEncoder,functools.cached_property)


def _parser_global_bindings(function,references):
    # Only actual referenced global aliases of these closed dispatch probes and
    # generated namedtuple constructors. No all-globals/opaque object admission.
    if type(function) is not FunctionType:raise _Unsupported(type(function),'parser-function')
    return tuple((name,_token(function.__globals__[name],references,set()))
        for name in sorted(set(function.__code__.co_names)&function.__globals__.keys())
        if name!='__builtins__')


def _namedtuple_policy(cls,fields,references):
    if cls._fields!=fields:raise _Unsupported(type(cls),'namedtuple-fields')
    refs=[]
    for name in fields:
        descriptor=vars(cls).get(name)
        if type(descriptor) is not _tuplegetter:raise _Unsupported(type(descriptor),'namedtuple-field')
        references.append(descriptor);refs.append((name,id(descriptor)))
    references.append(cls.__bases__)
    # Exact namespace membership catches new call/attribute overrides too;
    # existing generated method code and field descriptor identity are retained.
    methods=tuple((name,_token(value,references,set())) for name,value in sorted(vars(cls).items())
        if name not in ('__annotations__','__annotate__','__annotate_func__','__annotations_cache__')
        and type(value) in (FunctionType,staticmethod,classmethod,property))
    return (tuple(sorted(vars(cls))),tuple(id(base) for base in cls.__bases__),methods,_token(cls,references,set()),_token(cls.__new__,references,set()),
        _parser_global_bindings(cls.__new__,references),_token(cls._field_defaults,references,set()),tuple(refs))


def _png_policy(references):
    def token(value):return _token(value,references,set())
    # The real native original codec requires RGBA PNG. The known PNG opener
    # and C zip decoder remain the only cached dispatch, never a custom decoder.
    entry=Image.OPEN.get('PNG')
    if type(entry) is not tuple or len(entry)!=2 or entry[0] is not PngImagePlugin.PngImageFile:
        raise _Unsupported(type(entry),'png-opener')
    if any(name in Image.DECODERS for name in ('zip','raw')):raise _Unsupported(dict,'png-custom-decoder')
    if 'raw' in Image.ENCODERS:raise _Unsupported(type(Image.ENCODERS['raw']),'png-custom-encoder')
    probes=[]
    if type(Image.ID) is not list or 'PNG' not in Image.ID:raise _Unsupported(type(Image.ID),'png-dispatch-order')
    for format_name in Image.ID[:Image.ID.index('PNG')+1]:
        if type(format_name) is not str:raise _Unsupported(type(format_name),'png-dispatch-format')
        probe=Image.OPEN.get(format_name)
        if type(probe) is not tuple or len(probe)!=2 or type(probe[1]) is not FunctionType:
            raise _Unsupported(type(probe),'png-dispatch-probe')
        probes.append((format_name,token(probe),_parser_global_bindings(probe[1],references)))
    # cached_property's sentinel is bound by identity and retained, never
    # admitted as a general object policy value.
    references.append(functools._NOT_FOUND)
    descriptor_sentinel=(id(functools._NOT_FOUND),type(functools._NOT_FOUND).__module__,type(functools._NOT_FOUND).__qualname__)
    namedtuples=(_namedtuple_policy(ImageMode.ModeDescriptor,('mode','bands','basemode','basetype','typestr'),references),
        _namedtuple_policy(ImageFile._Tile,('codec_name','extents','offset','args'),references))
    classes=[]
    for cls in _PNG_CLASSES:
        references.append(cls);references.append(cls.__bases__);members=[]
        for name,value in sorted(vars(cls).items()):
            # All names participate, including newly added Python call/lookup
            # overrides. Only inherent instance dictionary/weakref descriptors
            # use exact retained identity, never arbitrary descriptor admission.
            if name in ('__annotations__','__annotate__','__annotate_func__','__annotations_cache__'):
                # The actual PNG/JSON decode graph never reads annotations.
                # Keep namespace membership, without evaluating or traversing
                # typing's inert lazy closures/ForwardRefs. Runtime behavior
                # methods and added call/lookup overrides still bind fully.
                members.append((name,('inert-annotation-metadata',)))
            elif name in ('__dict__','__weakref__'):
                references.append(value);members.append((name,('inherent-descriptor',id(value),type(value).__module__,type(value).__qualname__)))
            else:members.append((name,token(value)))
        classes.append((id(cls),tuple(id(base) for base in cls.__bases__),tuple(members)))
    modes=PngImagePlugin._MODES
    if type(modes) is not dict or any(type(key) is not tuple or len(key)!=2 or any(type(item) is not int for item in key) for key in modes):
        raise _Unsupported(type(modes),'png-mode-table')
    return token(entry),tuple(probes),tuple(classes),namedtuples,descriptor_sentinel,tuple((key,token(modes[key])) for key in sorted(modes))


class CallbackLiveRecords:
    """Feature-local reuse of byte-proved historical rows, never current facts."""
    def __init__(self):
        self.cache=AvatarRecordCache();loaded=tuple(import_module(name) for name in PARSER_MODULES)
        files={module.__file__ for module in loaded}|{__file__}
        # Own _token/function globals/PARSER_MODULES/EXTERNAL_READERS are policy
        # too. The helper has no global cache instance or mutable result rows.
        # Some shared contracts have both existing package and top-level aliases.
        # Bind every actual alias for the same reviewed parser sources too.
        self.modules=tuple(module for _name,module in sorted(sys.modules.items())
            if type(module) is ModuleType and vars(module).get('__file__') in files)
        self.module_names=tuple((module.__name__,module) for module in self.modules)
        self.references=[];self.unsupported=None;self.policy=self.signature(self.references)

    def signature(self,references):
        result=[];location=None
        try:
            if any(sys.modules.get(name) is not module for name,module in self.module_names):return None
            for module in self.modules:
                members=[]
                for name,value in sorted(vars(module).items()):
                    if name.startswith('__'):continue
                    # Module aliases and full callable/class policy are part of
                    # admission, even when a decoder imports the same function
                    # under another name. Mutable original rows live on owners,
                    # never in these source-module namespaces.
                    location=(module.__name__,name);members.append((name,_token(value,references,set())))
                result.append((module.__name__,id(module),tuple(members)))
            external=tuple((id(container),name,_token(getattr(container,name),references,set())) for container,name in EXTERNAL_READERS)
            location=('PIL.PNG','closed-policy');png=_png_policy(references)
            return tuple(result),external,png
        except (AttributeError,TypeError,ValueError,RecursionError,_Unsupported):
            self.unsupported=location;return None

    def unsupported_members(self):
        # Diagnostic only: use the SAME closed tokenizer without granting any
        # policy/cache admission. Report module/member/type/reason, never values,
        # function locals, owner contents or a substituted decoder result.
        output=[]
        for module in self.modules:
            if sys.modules.get(module.__name__) is not module:
                output.append(dict(module=module.__name__,member=None,type=None,reason='namespace-rebound'));continue
            for name,value in sorted(vars(module).items()):
                if name.startswith('__'):continue
                try:_token(value,[],set())
                except _Unsupported as error:output.append(dict(module=module.__name__,member=name,type=error.kind,reason=error.reason))
                except (AttributeError,TypeError,ValueError,RecursionError) as error:
                    output.append(dict(module=module.__name__,member=name,type=(type(error).__module__,type(error).__qualname__),reason='token-error'))
        for container,name in EXTERNAL_READERS:
            try:_token(getattr(container,name),[],set())
            except _Unsupported as error:output.append(dict(module=container.__name__,member=name,type=error.kind,reason=error.reason))
            except (AttributeError,TypeError,ValueError,RecursionError) as error:
                output.append(dict(module=container.__name__,member=name,type=(type(error).__module__,type(error).__qualname__),reason='token-error'))
        try:_png_policy([])
        except _Unsupported as error:output.append(dict(module='PIL.PNG',member='closed-policy',type=error.kind,reason=error.reason))
        except (AttributeError,TypeError,ValueError,RecursionError) as error:
            output.append(dict(module='PIL.PNG',member='closed-policy',type=(type(error).__module__,type(error).__qualname__),reason='token-error'))
        return output

    def literal(self):
        return self.policy is not None and self.signature([])==self.policy

    def read(self,owner,reference,decode):
        from ios.adapters.emote_callback_live import IOSEmoteCallbackLive
        if type(owner) is not IOSEmoteCallbackLive or not self.literal():return decode()
        owner.file_guard()
        need(owner._historical_rows is self and type(self.cache) is AvatarRecordCache)
        def header():
            need(owner._historical_rows is self and type(self.cache) is AvatarRecordCache)
            original=owner.originals
            need(type(original) is OriginalFrameStore and original.root==owner.root
                and same(original.binding,owner.binding) and original.run==owner.run and original.role==owner.role
                and original.namespace=='emote-rooted-live' and original.schema_prefix=='iosEmoteRootedLive' and original.kind=='inputs'
                and type(original.guard) is MethodType and original.guard.__self__ is owner and original.guard.__func__ is owner.file_guard.__func__
                and type(original.intent) is MethodType and original.intent.__self__ is owner and original.intent.__func__ is owner.intent.__func__)
            return dict(formatVersion=owner.FORMAT_VERSION,binding=owner.binding,primaryBinding=owner.primary_binding,runId=owner.run,role=owner.role,
                root=str(owner.root),store=str(owner.store.path),sourceLock=str(owner.lock.path),primaryLock=str(owner.primary_lock.path),
                fixtureUrl=owner.fixture_url,phaseInstance=owner.phase_instance,imagePolicy=owner.policy,
                original=dict(root=str(owner.originals.root),namespace=owner.originals.namespace,
                    schema=owner.originals.schema_prefix,kind=owner.originals.kind))
        context=deepcopy(header());before=canonical(context);key=dict(emoteCallbackLiveHistoricalRowVersion=1,context=context,reference=reference)
        encoded=canonical(key)
        def checked():
            owner.file_guard();need(self.literal() and canonical(key)==encoded and canonical(header())==before)
            result=decode()
            owner.file_guard();need(self.literal() and canonical(key)==encoded and canonical(header())==before)
            return result
        if encoded not in self.cache.rows and len(self.cache.rows)>=512:return decode()
        result=self.cache.read(key,checked)
        owner.file_guard();need(self.literal() and canonical(key)==encoded and canonical(header())==before)
        return result
