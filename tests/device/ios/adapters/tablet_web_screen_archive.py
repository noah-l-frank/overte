"""Exact original WDA PNG bytes in bounded private immutable file fragments.

This is byte ownership, not screen/document authority or product retirement.
The enclosing sample durably records every parent/child transition before
continuing. Original native packet/file identities are never relabelled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.native_clock_join import digest
from adapters.original_packet_segments import OriginalPacketSegments,CHUNK_BYTES,LIMIT,sha
from adapters.original_frame_store import MAX_FRAMES
from adapters.script_feature.history import same
from ios.adapters.tablet_web_images import capture_record,pixels,LIMIT as PNG_LIMIT

VERSION=1


def raw_original(value,raw=None):
    exact(value,{'nativeScreenRawVersion','requestId','source','transport','sessionId','processId','bytes','sha256','extent'})
    from feature_journeys.contract import identifier
    need(type(value['nativeScreenRawVersion']) is int and value['nativeScreenRawVersion']==1
        and type(value['requestId']) is str and value['requestId'].startswith('ios-'))
    identifier(value['requestId'][4:])
    need(value['source']=='native-screen' and value['transport']=='webdriveragent-original-png'
        and type(value['sessionId']) is str and 0<len(value['sessionId'])<=160 and integer(value['processId'],1)
        and integer(value['bytes'],1,PNG_LIMIT) and type(value['sha256']) is str and len(value['sha256'])==64
        and all(char in '0123456789abcdef' for char in value['sha256'])
        and type(value['extent']) is list and len(value['extent'])==2
        and all(integer(item,1,4096) for item in value['extent']) and value['extent'][0]*value['extent'][1]<=8388608)
    if raw is not None:need(type(raw) is bytes and len(raw)==value['bytes'] and sha(raw)==value['sha256'] and pixels(raw)==value['extent'])
    return value


def with_capture(raw,capture):
    raw_original(raw);capture_record(capture)
    need(all(same(raw[key],capture[key]) for key in raw if key!='nativeScreenRawVersion'))
    return capture


class TabletScreenParts(OriginalPacketSegments):PROFILE='tabletweb-screen'


class TabletWebScreenArchive:
    def __init__(self,root,binding,run,role,guard,intent,*,monotonic):
        need(role in ('primary','actor') and callable(intent));self.intent=intent;self.writing=None
        self.parts=TabletScreenParts(root,binding,run,role,role,guard,self.transition,monotonic=monotonic)
    def parent(self,value):
        exact(value,{'tabletWebScreenArchiveVersion','raw','bytes','sha256','first','parts','complete'})
        need(type(value['tabletWebScreenArchiveVersion']) is int and value['tabletWebScreenArchiveVersion']==VERSION
            and integer(value['bytes'],1,PNG_LIMIT) and type(value['parts']) is list and len(value['parts'])<=6
            and integer(value['first'],1,MAX_FRAMES) and type(value['complete']) is bool)
        raw_original(value['raw']);need(value['bytes']==value['raw']['bytes'] and value['sha256']==value['raw']['sha256'])
        first=value['first'];total=0
        for index,part in enumerate(value['parts']):
            self.parts.parent(part);need(part['label']=='png' and part['tag']==digest(value['raw'])
                and part['first']==first and part['bytes']==min(LIMIT,value['bytes']-total))
            if index<len(value['parts'])-1:need(part['complete'])
            first+=max(1,(part['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES);total+=part['bytes']
        need(first-1<=MAX_FRAMES)
        if value['complete']:need(total==value['bytes'] and all(row['complete'] for row in value['parts']))
        return value
    def transition(self,part):
        value=self.writing;need(value is not None);self.parts.parent(part)
        if not value['parts'] or part['first']!=value['parts'][-1]['first']:
            need(not value['parts'] or value['parts'][-1]['complete']);value['parts'].append(deepcopy(part))
        else:
            old=value['parts'][-1];need(all(same(old[key],part[key]) for key in old if key not in ('chunks','complete')))
            value['parts'][-1]=deepcopy(part)
        self.parent(value);need(self.intent(deepcopy(value)) is not False)
    def write(self,original,raw,first):
        need(self.writing is None);raw_original(original,raw)
        value=dict(tabletWebScreenArchiveVersion=VERSION,raw=deepcopy(original),bytes=len(raw),sha256=sha(raw),first=first,parts=[],complete=False)
        self.parent(value);need(self.intent(deepcopy(value)) is not False);self.writing=value
        try:
            cursor=first
            for offset in range(0,len(raw),LIMIT):
                part=raw[offset:offset+LIMIT];self.parts.write('png',digest(original),part,cursor)
                cursor+=max(1,(len(part)+CHUNK_BYTES-1)//CHUNK_BYTES)
            value['complete']=True;self.parent(value);need(self.intent(deepcopy(value)) is not False)
            need(self.read(value)==raw);return deepcopy(value)
        finally:self.writing=None
    def inspect(self,value):
        self.parent(value);return [self.parts.inspect(part) for part in value['parts']]
    def retained(self,value):
        """Read complete actual opened bytes without relabelling any phase."""
        self.parent(value);need(len(value['parts'])==(value['bytes']+LIMIT-1)//LIMIT)
        raw=b''.join(self.parts.read(part) for part in value['parts'])
        need(len(raw)==value['bytes'] and sha(raw)==value['sha256']);raw_original(value['raw'],raw);return raw
    def read(self,value):
        self.parent(value);need(value['complete']);return self.retained(value)
