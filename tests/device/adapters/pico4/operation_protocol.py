"""Bounded stdio DTOs for the opt-in original Pico operation host."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import math
import re

VERSION=1
REQUEST_LIMIT=65536
RESPONSE_LIMIT=4*1024*1024
STDERR_LIMIT=65536
PART_LIMIT=65536
FILE_LIMIT=512
BYTE_LIMIT=16*1024*1024
STRIPPED_ENV=('OVERTE_E2E_TABLET_POLICY','OVERTE_E2E_WEB_VIDEO_ROIS',
    'OVERTE_E2E_FEATURE_READER_TOKEN','OVERTE_E2E_FEATURE_IMAGE_POLICY',
    'OVERTE_E2E_SCRIPTS_CONTROL_TOKEN','OVERTE_E2E_CREATE_CONTROL_TOKEN')
FORBIDDEN_KEYS={'expectedFacts','policy','imagePolicy','readerToken','controlToken'}


def need(value):
    if not value:raise ValueError('Pico operation host rejected')


def timeout_for(operation):
    if operation in {'app.install','app.upgrade'}:return 240
    if operation in {'permission.snapshot','permission.set','snapshot.files'}:return 120
    return 60


def dto_bytes(value,limit,*,arguments=False):
    """Bound exact JSON size before allocating the encoded document."""
    count=0;active=set()
    def add(size):
        nonlocal count
        count+=size;need(count+1<=limit)
    def string(value):
        add(2)
        for char in value:
            code=ord(char);need(not 0xD800<=code<=0xDFFF)
            add(2 if char in ('"','\\','\b','\f','\n','\r','\t') else 6 if code<32 else 1 if code<128 else 2 if code<2048 else 3 if code<65536 else 4)
    def walk(item,depth):
        need(depth<=32);kind=type(item)
        if kind in (dict,list):
            need(id(item) not in active);active.add(id(item));add(2)
            if kind is dict:
                for index,(key,value) in enumerate(item.items()):
                    need(type(key) is str and (not arguments or key not in FORBIDDEN_KEYS))
                    if index:add(1)
                    string(key);add(1);walk(value,depth+1)
            else:
                for index,value in enumerate(item):
                    if index:add(1)
                    walk(value,depth+1)
            active.remove(id(item))
        elif kind is str:string(item)
        elif kind is bool:add(4 if item else 5)
        elif item is None:add(4)
        elif kind is int:add(len(str(item)))
        elif kind is float:need(math.isfinite(item));add(len(json.dumps(item,allow_nan=False)))
        else:need(False)
    walk(value,0)
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')+b'\n'
    need(len(raw)==count+1 and len(raw)<=limit);return raw


def decode(raw,limit):
    need(type(raw) is bytes and 0<len(raw)<=limit and raw.endswith(b'\n') and raw.count(b'\n')==1)
    def pairs(items):
        value={}
        for key,item in items:need(key not in value);value[key]=item
        return value
    def invalid(_):need(False)
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    dto_bytes(value,limit);need(type(value) is dict);return value


def request(value):
    need(type(value) is dict and set(value)=={'picoOperationRequestVersion','requestId','operation','arguments','deadlineMonotonic'})
    need(type(value['picoOperationRequestVersion']) is int and value['picoOperationRequestVersion']==VERSION
        and type(value['requestId']) is str and re.fullmatch('[0-9a-f]{32}',value['requestId'])
        and type(value['operation']) is str and re.fullmatch('[a-z][a-z0-9.-]{0,159}',value['operation'])
        and type(value['arguments']) is dict and type(value['deadlineMonotonic']) in (int,float) and math.isfinite(value['deadlineMonotonic']))
    dto_bytes(value['arguments'],REQUEST_LIMIT,arguments=True)
    from contracts import validate_operation_arguments,load_capability_registry
    need(value['operation'] in load_capability_registry())
    validate_operation_arguments(value['operation'],value['arguments']);return value
