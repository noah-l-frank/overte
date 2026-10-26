"""Actual bundled FBX loaded-frame metadata for explicitly selected host rigs.

FBXSerializer.cpp builds AnimationCurve.values from KeyValueFloat and allocates
max(1, max(curve.values.size())) frames. This bounded reader follows that rule;
it supplies no Rig pose, animation verdict, expected duration or source clock.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import struct
import zlib
from adapters.native_feature_observation import need
from ios.adapters.emote_original_lease import EmoteOriginalLease

NAMES=('Crying','Surprised','Dancing','Cheering','Waving','Fall','Pointing','Clapping','Sit1','Sit2','Sit3','Love')


def frame_count(raw):
    need(type(raw) is bytes and 27<=len(raw)<=8*1024*1024 and raw[:23]==b'Kaydara FBX Binary  \x00\x1a\x00')
    version=struct.unpack_from('<I',raw,23)[0];need(7000<=version<7500)
    counts=[];visited=0
    def nodes(offset,limit,parents=()):
        nonlocal visited
        need(len(parents)<=64)
        while offset+13<=limit:
            end,number,length,name_length=struct.unpack_from('<IIIB',raw,offset)
            if end==0:
                need(raw[offset:offset+13]==bytes(13));return
            visited+=1;need(visited<=50000 and offset+13+name_length+length<=end<=limit)
            name=raw[offset+13:offset+13+name_length];start=offset+13+name_length
            if name==b'KeyValueFloat' and parents and parents[-1]==b'AnimationCurve':
                need(number==1 and length>=13 and raw[start:start+1]==b'f')
                count,encoding,size=struct.unpack_from('<III',raw,start+1)
                need(1<=count<=1000000 and encoding in (0,1) and length==13+size)
                encoded=raw[start+13:start+13+size];need(len(encoded)==size);expected=count*4
                if encoding:
                    decoder=zlib.decompressobj()
                    try:decoded=decoder.decompress(encoded,expected+1)
                    except zlib.error:need(False)
                    need(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail)
                else:decoded=encoded
                need(len(decoded)==expected);counts.append(count)
            nodes(start+length,end,parents+(name,));offset=end
    nodes(27,len(raw));need(bool(counts));return max(1,max(counts))


def bundled_frames():
    root=Path(__file__).resolve().parents[4]/'scripts/system/assets/animations';result={}
    for name in NAMES:
        path=root/(name+'.fbx');before=path.stat();raw=path.read_bytes()
        need(EmoteOriginalLease.signature(path.stat())==EmoteOriginalLease.signature(before))
        result[name]=frame_count(raw)
    return result
