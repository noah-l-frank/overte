"""Immutable private original frames; manifests never replace a fresh query."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import os
import stat

from adapters.native_feature_observation import exact, need, integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import canonical, pack, unpack, MAX_FRAMES, MAX_RAW, same

VERSION=1


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def json_digest(value):
    """Cache only exact JSON DTO types, including original dictionary keys.

    JSON encoding alone aliases tuples/lists, subclasses and integer/string
    keys. A digest hit must not bypass the original closed DTO validators.
    This changes no persisted source/manifest format or ordinary digest.
    """
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
    # The ordinary canonical encoder still checks finite values and cycles.
    return digest(value)


class ChatSourceChunks:
    """Fixed numbered children, one complete original source bundle per file.

    The root's reading intent MUST already exist before append. Lost child/root
    writes remain reading, and orphan files forbid acquisition by a new owner.
    No discard, truncation, adoption or overwrite operation is provided.
    """
    def __init__(self,store,scope):
        need(isinstance(store,PrivateFeatureState))
        self.root=store;self.scope=digest(scope);self.raw_bytes=2;self.identities=[]
        self.root_path=store.path;self.prefix=store.path.name+'.frame-'
        self.names=tuple(self.prefix+f'{index:03d}.json' for index in range(MAX_FRAMES));self.paths={}

    def _path(self,index):
        need(integer(index,0,MAX_FRAMES-1) and self.root.path==self.root_path)
        if index not in self.paths:self.paths[index]=self.root_path.with_name(self.names[index])
        return self.paths[index]

    def store(self,index):return PrivateFeatureState(self._path(index))

    def inventory(self,count):
        need(integer(count,0,MAX_FRAMES) and self.root.path==self.root_path);self.root._parent()
        expected=set(self.names[:count])
        with os.scandir(self.root_path.parent) as entries:
            actual={entry.name for entry in entries if entry.name.startswith(self.prefix)}
        need(actual==expected)

    def signature(self,index):
        info=self._path(index).lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=65536
            and (os.name=='nt' or info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600))
        return (info.st_dev,info.st_ino,info.st_size,info.st_uid,info.st_mode,info.st_nlink,info.st_mtime_ns,info.st_ctime_ns)

    def verify(self):
        self.inventory(len(self.identities))
        need(all(self.signature(index)==original for index,original in enumerate(self.identities)))

    def load(self,manifest):
        need(type(manifest) is list and len(manifest)<=MAX_FRAMES
            and all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in manifest))
        self.inventory(len(manifest));frames=[];identities=[];total=2
        for index,expected in enumerate(manifest):
            before=self.signature(index);value=self.store(index).read();need(self.signature(index)==before);identities.append(before)
            exact(value,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
            need(value['chatSampleChunkVersion']==VERSION and type(value['chatSampleChunkVersion']) is int
                and value['scopeSha256']==self.scope and type(value['index']) is int and value['index']==index and digest(value)==expected)
            frame=unpack(value['transcript']);need(len(frame)==1)
            total+=value['transcript']['bytes']-2+(1 if index else 0);need(total<=MAX_RAW)
            frames.extend(frame)
        self.raw_bytes=total;self.identities=identities;self.verify()
        return frames

    def append(self,frame,manifest):
        need(type(manifest) is list and len(manifest)<MAX_FRAMES)
        self.verify();need(len(self.identities)==len(manifest))
        root=self.root.read();need(root is not None and root.get('phase')=='reading' and same(root.get('chunks'),manifest))
        transcript=pack([deepcopy(frame)])
        total=self.raw_bytes+transcript['bytes']-2+(1 if manifest else 0);need(total<=MAX_RAW)
        value=dict(chatSampleChunkVersion=VERSION,scopeSha256=self.scope,index=len(manifest),transcript=transcript)
        child=self.store(len(manifest));need(child.read() is None)
        child.write(value,None);before=self.signature(len(manifest));need(same(child.read(),value) and self.signature(len(manifest))==before)
        self.identities.append(before);self.verify()
        self.raw_bytes=total
        return manifest+[digest(value)]
