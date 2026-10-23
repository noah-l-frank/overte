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


class ChatSourceChunks:
    """Fixed numbered children, one complete original source bundle per file.

    The root's reading intent MUST already exist before append. Lost child/root
    writes remain reading, and orphan files forbid acquisition by a new owner.
    No discard, truncation, adoption or overwrite operation is provided.
    """
    def __init__(self,store,scope):
        need(isinstance(store,PrivateFeatureState))
        self.root=store;self.scope=digest(scope);self.raw_bytes=2;self.identities=[]

    def store(self,index):
        need(integer(index,0,MAX_FRAMES-1))
        return PrivateFeatureState(self.root.path.with_name(self.root.path.name+f'.frame-{index:03d}.json'))

    def inventory(self,count):
        need(integer(count,0,MAX_FRAMES));self.root._parent()
        prefix=self.root.path.name+'.frame-'
        expected={prefix+f'{index:03d}.json' for index in range(count)}
        # Still enumerate the complete actual directory on EVERY check. Avoid
        # constructing a pathlib object for every unrelated entry; inventories
        # compare names only, while signature()/load() retain all file checks.
        with os.scandir(self.root.path.parent) as entries:
            actual={entry.name for entry in entries if entry.name.startswith(prefix)}
        need(actual==expected)

    def signature(self,index):
        info=self.store(index).path.lstat()
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
