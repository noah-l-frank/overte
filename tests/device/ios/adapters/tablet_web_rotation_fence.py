"""Unintegrated Source3 rotating-head metadata, never native authority.

The only state this codec can produce is blocked/rotating. Runtime selection,
literal native prefix validation and segment completion are deliberately not
implemented here. An immutable copy has its own actual file identity; its old
mutable-head signature is observed provenance, not a current native fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import stat
import zlib

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import LIMIT,MAX_FRAMES
from adapters.script_feature.history import canonical,same
from feature_journeys.contract import identifier

VERSION=3
LEGACY=(1,2)
MAX_HEAD_BYTES=65536
COPY_KEY='tabletWebClosedHeaderOriginalVersion'


class TabletHeaderRotating(NativeUIError):
    """A fenced head cannot authorize source acquisition or legacy fallback."""


def scope(binding,run,role,fixture_url,pid):
    context(binding);identifier(run)
    need(role in ('primary','actor') and type(pid) is int and pid>0 and binding['processIdentity']==str(pid)
        and type(fixture_url) is str and 0<len(fixture_url)<=4096)
    return dict(binding=deepcopy(binding),runId=run,role=role,fixtureUrl=fixture_url,processId=pid)


def _scope(value):
    exact(value,{'binding','runId','role','fixtureUrl','processId'})
    return scope(value['binding'],value['runId'],value['role'],value['fixtureUrl'],value['processId'])


def _signature(value,size):
    exact(value,{'device','inode','mode','uid','gid','nlink','bytes','mtimeNs','ctimeNs'})
    need(all(type(item) is int and item>=0 for item in value.values()) and value['inode']>0
        and stat.S_ISREG(value['mode']) and stat.S_IMODE(value['mode'])==0o600
        and value['nlink']==1 and value['bytes']==size)


def _legacy(raw,expected):
    need(type(raw) is bytes and 0<len(raw)<=MAX_HEAD_BYTES)
    def pairs(items):
        result={}
        for key,value in items:need(key not in result);result[key]=value
        return result
    def invalid(_value):raise NativeUIError('Non-finite old header is unavailable')
    try:value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    except (ValueError,UnicodeError):raise NativeUIError('Old header bytes are unavailable') from None
    need(type(value) is dict)
    version=value.get('tabletWebSourceOwnerVersion');need(type(version) is int and version in LEGACY)
    exact(value,({'reconciled'} if version==2 else set())|{'tabletWebSourceOwnerVersion','binding','runId','role','fixtureUrl','processId',
        'apps','records','pending','intent','inspection','appIntent','appPending','appInspection'})
    need(all(same(value[key],expected[key]) for key in expected)
        and type(value['apps']) is list and len(value['apps'])<=32
        and type(value['records']) is list and len(value['records'])<=128
        and all(value[key] is None for key in ('pending','intent','inspection','appIntent','appPending','appInspection')))
    if version==2:need(type(value['reconciled']) is list and len(value['reconciled'])<=128)
    # This is metadata grammar only. Opaque original references and native
    # continuation must still pass their full literal readers before use.
    return value


def make(raw,signature,expected):
    expected=_scope(expected);old=_legacy(raw,expected);_signature(signature,len(raw))
    prior=dict(encoding='zlib-base64-bytes',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
        signature=deepcopy(signature),data=base64.b64encode(zlib.compress(raw,9)).decode('ascii'))
    result=dict(tabletWebSourceOwnerVersion=VERSION,phase='rotating',scope=expected,
        legacyVersion=old['tabletWebSourceOwnerVersion'],previousHeader=prior,copyIntent=None)
    # PrivateFeatureState adds a newline. Admit the complete actual file size,
    # without extending its unchanged 64-KiB reader/writer boundary.
    need(len(canonical(result))+1<=MAX_HEAD_BYTES);return result


def _copy(value,expected):
    exact(value,{COPY_KEY,'kind','binding','runId','role','index','sha256','bytes','phase','file'})
    need(type(value[COPY_KEY]) is int and value[COPY_KEY]==1 and value['kind']=='sources'
        and same(value['binding'],expected['binding']) and value['runId']==expected['runId'] and value['role']==expected['role']
        and type(value['index']) is int and 1<=value['index']<=MAX_FRAMES
        and type(value['bytes']) is int and 2<=value['bytes']<=LIMIT
        and type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256'])
        and value['phase'] in ('planned','opened','saved'))
    if value['phase']=='planned':need(value['file'] is None)
    else:
        exact(value['file'],{'device','inode'})
        need(all(type(item) is int and item>=0 for item in value['file'].values()) and value['file']['inode']>0)


def decode(value,expected):
    expected=_scope(expected)
    exact(value,{'tabletWebSourceOwnerVersion','phase','scope','legacyVersion','previousHeader','copyIntent'})
    need(type(value['tabletWebSourceOwnerVersion']) is int and value['tabletWebSourceOwnerVersion']==VERSION
        and value['phase']=='rotating' and same(value['scope'],expected)
        and type(value['legacyVersion']) is int and value['legacyVersion'] in LEGACY)
    prior=value['previousHeader'];exact(prior,{'encoding','bytes','sha256','signature','data'})
    need(prior['encoding']=='zlib-base64-bytes' and type(prior['bytes']) is int and 1<=prior['bytes']<=MAX_HEAD_BYTES
        and type(prior['data']) is str and 0<len(prior['data'])<=MAX_HEAD_BYTES)
    try:
        packed=base64.b64decode(prior['data'],validate=True);need(base64.b64encode(packed).decode('ascii')==prior['data'])
        decoder=zlib.decompressobj();raw=decoder.decompress(packed,prior['bytes']+1)
    except (ValueError,zlib.error):raise NativeUIError('Old header capsule is unavailable') from None
    need(len(raw)==prior['bytes'] and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
        and hashlib.sha256(raw).hexdigest()==prior['sha256'])
    _signature(prior['signature'],len(raw));old=_legacy(raw,expected)
    need(old['tabletWebSourceOwnerVersion']==value['legacyVersion'] and len(canonical(value))+1<=MAX_HEAD_BYTES)
    if value['copyIntent'] is not None:_copy(value['copyIntent'],expected)
    return raw


def copy_body(value,expected):
    decode(value,expected)
    return dict(tabletWebClosedHeaderBodyVersion=1,scope=deepcopy(value['scope']),
        legacyVersion=value['legacyVersion'],previousHeader=deepcopy(value['previousHeader']))


def with_copy_intent(value,kind,intent,expected):
    decode(value,expected);need(kind=='original');_copy(intent,expected);previous=value['copyIntent']
    if previous is None:need(intent['phase']=='planned')
    else:
        order={'planned':'opened','opened':'saved'}
        need(order.get(previous['phase'])==intent['phase']
            and all(same(previous[key],intent[key]) for key in intent if key not in ('phase','file')))
        if previous['file'] is not None:need(same(previous['file'],intent['file']))
    result=deepcopy(value);result['copyIntent']=deepcopy(intent);decode(result,expected);return result


def read_barrier(value,expected):
    """Isolated future entry hook; not wired into the runtime in this packet."""
    need(type(value) is dict);version=value.get('tabletWebSourceOwnerVersion')
    if type(version) is int and version in LEGACY:return value  # Literal route, not validation/normalization.
    decode(value,expected)
    raise TabletHeaderRotating('Original Tablet header remains fenced during rotation')
