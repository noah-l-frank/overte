"""Versioned complete World history bytes; no source or lifetime authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import json
import lzma
import re

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUIError
from adapters.script_journey import history as legacy

VERSION=2
READS=(1,2)
MEMORY_LIMIT=16*1024*1024


def plain(value):
    pending=[value];seen=set()
    while pending:
        item=pending.pop();kind=type(item)
        if kind in (dict,list):
            if id(item) in seen:continue
            seen.add(id(item))
            if kind is dict:
                need(all(type(key) is str for key in item));pending.extend(item.values())
            else:pending.extend(item)
        else:need(kind in (str,int,float,bool,type(None)))


def pack(frames,version):
    need(type(version) is int and version in READS)
    if version==1:return legacy.pack(frames)
    try:
        plain(frames);need(type(frames) is list and len(frames)<=legacy.MAX_FRAMES)
        raw=legacy.canonical(frames);need(len(raw)<=legacy.MAX_RAW)
        encoded=base64.b64encode(lzma.compress(raw,format=lzma.FORMAT_XZ,preset=3)).decode('ascii')
        need(len(encoded)<=legacy.MAX_PACKED)
        return dict(encoding='xz-base64-json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),data=encoded)
    except NativeUIError:raise
    except Exception:raise NativeUIError('Lifecycle World history cannot be encoded') from None


def unpack(value,version):
    need(type(version) is int and version in READS)
    if version==1:return legacy.unpack(value)
    try:
        plain(value);exact(value,{'encoding','bytes','sha256','data'})
        need(value['encoding']=='xz-base64-json' and integer(value['bytes'],2,legacy.MAX_RAW)
            and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None
            and type(value['data']) is str and 0<len(value['data'])<=legacy.MAX_PACKED)
        compressed=base64.b64decode(value['data'],validate=True)
        need(base64.b64encode(compressed).decode('ascii')==value['data'])
        decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=MEMORY_LIMIT)
        raw=decoder.decompress(compressed,max_length=value['bytes']+1)
        need(len(raw)==value['bytes'] and decoder.eof and not decoder.unused_data
            and hashlib.sha256(raw).hexdigest()==value['sha256'])
        def pairs(items):
            result={}
            for key,item in items:need(key not in result);result[key]=item
            return result
        def invalid(_value):need(False)
        frames=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
        need(type(frames) is list and len(frames)<=legacy.MAX_FRAMES and legacy.canonical(frames)==raw)
        return frames
    except NativeUIError:raise
    except Exception:raise NativeUIError('Lifecycle World history cannot be decoded') from None


def owner_payload(disk):
    return unpack(disk['payload'],disk['lifecycleWorldOwnerVersion'])
