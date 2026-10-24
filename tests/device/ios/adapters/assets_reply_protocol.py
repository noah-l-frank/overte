"""Original AssetClient wire payloads and exact native result bytes.

Parsed mapping statuses are server reports, never oven or model-consumer facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import re
import struct
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import same


def text(value,limit=4096):
    need(type(value) is str and len(value.encode('utf-8'))<=limit);return value


def sha(value):need(type(value) is str and re.fullmatch('[a-f0-9]{64}',value));return value


def original(value,maximum=160000):
    need(type(value) is str and len(value)<=4*((maximum+2)//3))
    raw=base64.b64decode(value,validate=True)
    need(len(raw)<=maximum and base64.b64encode(raw).decode('ascii')==value);return raw


def body(value,*,required=False):
    exact(value,{'bytes','sha256','retained','base64'});need(integer(value['bytes'],0,2**31-1) and type(value['retained']) is bool);sha(value['sha256'])
    if not value['retained']:
        need(not required and value['base64'] is None and value['bytes']>65536);return None
    raw=original(value['base64'],65536);need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']);return raw


def path(value):
    text(value);need(value.startswith('/') and not value.endswith('/') and '//' not in value and '\x00' not in value);return value


class Cursor:
    def __init__(self,raw):need(type(raw) is bytes and len(raw)<=65536);self.raw=raw;self.offset=0
    def take(self,count):
        need(integer(count,0,65536) and self.offset+count<=len(self.raw));data=self.raw[self.offset:self.offset+count];self.offset+=count;return data
    def u32(self):return struct.unpack('<I',self.take(4))[0]
    def i32(self):return struct.unpack('<i',self.take(4))[0]
    def string(self,maximum=4096):
        size=self.u32();need(size<=maximum);return text(self.take(size).decode('utf-8','strict'),maximum)
    def end(self):need(self.offset==len(self.raw))


def inventory(raw):
    cursor=Cursor(raw);count=cursor.u32();need(count<=256);rows=[];seen=set()
    for _ in range(count):
        name=path(cursor.string());need(name not in seen);seen.add(name)
        digest=cursor.take(32).hex();status=cursor.i32();need(0<=status<=5)
        rows.append(dict(path=name,hash=digest,status=status,bakingErrors=cursor.string(8192) if status==5 else ''))
    cursor.end();need(rows==sorted(rows,key=lambda row:row['path'].encode('utf-16be')));return rows


def mapping(raw):
    cursor=Cursor(raw);digest=cursor.take(32).hex();redirect=cursor.take(1)[0];need(redirect in (0,1))
    destination=path(cursor.string()) if redirect else '';cursor.end();return dict(hash=digest,redirected=bool(redirect),redirectedPath=destination)


def result(value,kind):
    need(type(value) is dict)
    if kind=='inventory':
        exact(value,{'error','complete','mappings'});need(integer(value['error'],0,6) and type(value['complete']) is bool
            and type(value['mappings']) is list and len(value['mappings'])<=256)
        names=[]
        for row in value['mappings']:
            exact(row,{'path','hash','status','bakingErrors'});text(row['path']);text(row['hash'],64);text(row['bakingErrors'],8192)
            need(re.fullmatch('[a-f0-9]{0,64}',row['hash']) and integer(row['status'],-2**31,2**31-1));names.append(row['path'])
        need(len(names)==len(set(names)) and names==sorted(names,key=lambda item:item.encode('utf-16be')))
    elif kind=='mapping':
        exact(value,{'error','hash','redirected','redirectedPath'});need(integer(value['error'],0,6) and type(value['redirected']) is bool)
        text(value['hash'],64);need(re.fullmatch('[a-f0-9]{0,64}',value['hash']));text(value['redirectedPath'])
    elif kind=='info':
        exact(value,{'responseReceived','serverError','hash','size'});need(type(value['responseReceived']) is bool and integer(value['serverError'],0,255))
        need(type(value['size']) is str and re.fullmatch('-?(?:0|[1-9][0-9]{0,19})',value['size']) and -2**63<=int(value['size'])<2**63)
        text(value['hash'],64);need(re.fullmatch('[a-f0-9]{0,64}',value['hash']))
    else:
        need(kind=='raw-server');exact(value,{'responseReceived','serverError','body'})
        need(type(value['responseReceived']) is bool and integer(value['serverError'],0,255));body(value['body'])
    return value


def exact_result(encoded,value,kind):
    raw=original(encoded);need(raw and same(decode(raw.decode('utf-8')),value));result(value,kind);return raw
