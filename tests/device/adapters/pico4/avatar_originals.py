"""Bounded immutable original frames for the closed Pico Avatar owners.

The cache saves parsing only; actual descriptor/stamp/byte admission is repeated
at every final input fence. No original is repaired, replaced or adopted warm.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import re
import stat
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_journey.history import pack,unpack,same,canonical

KINDS={'urls':('avatar-urls','avatarUrlFrameVersion'),'favorites':('avatar-favorites','avatarFavoriteFrameVersion')}

class AvatarOriginalFrames:
    def __init__(self,store,binding,run,fixture_url,kind):
        need(kind in KINDS and re.fullmatch('[0-9a-f]{32}',run) is not None)
        prefix,self.schema=KINDS[kind];self.store,self.binding,self.run,self.fixture_url=store,deepcopy(context(binding)),run,fixture_url
        suffix='-'+run+'.json';name=store.path.name;root_prefix=prefix+'-owner-'
        need(name.startswith(root_prefix) and name.endswith(suffix));key=name[len(root_prefix):-len(suffix)]
        need(re.fullmatch('[0-9a-f]{32}',key) is not None);self.frame_prefix=prefix+'-frame-'+key+'-'+run+'-'
        self._frame_references={};self._frame_originals={};self._frame_files={}
    def frame_original(self,reference):
        exact(reference,{self.schema,'name','sha256'})
        need(type(reference[self.schema]) is int and reference[self.schema]==1
            and type(reference['sha256']) is str and len(reference['sha256'])==64 and all(c in '0123456789abcdef' for c in reference['sha256']))
        name=self.frame_prefix+reference['sha256'][:32]+'.json';need(reference['name']==name)
        if reference['sha256'] in self._frame_references:
            need(same(self._frame_references[reference['sha256']],reference));self.verify_frame_file(reference)
            return deepcopy(self._frame_originals[reference['sha256']])
        record=PrivateFeatureState(self.store.path.with_name(name)).read();need(record is not None)
        exact(record,{self.schema,'binding','runId','fixtureUrl','payload'})
        need(type(record[self.schema]) is int and record[self.schema]==1 and same(record['binding'],self.binding)
            and record['runId']==self.run and record['fixtureUrl']==self.fixture_url)
        values=unpack(record['payload']);need(len(values)==1 and hashlib.sha256(canonical(values[0])).hexdigest()==reference['sha256'])
        self.verify_frame_file(reference,canonical(record)+b'\n')
        self._frame_references[reference['sha256']]=deepcopy(reference);self._frame_originals[reference['sha256']]=deepcopy(values[0]);return values[0]
    @staticmethod
    def frame_stamp(info):
        return (info.st_dev,info.st_ino,info.st_uid,info.st_mode,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
    def verify_frame_file(self,reference,original=None):
        # Cache only parsing/decompression. Every admission and final input
        # fence rereads the original bounded descriptor, inode/stamps and bytes.
        store=PrivateFeatureState(self.store.path.with_name(reference['name']));store._parent();before=store.path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=65536
            and (os.name=='nt' or before.st_uid==os.geteuid() and stat.S_IMODE(before.st_mode)==0o600))
        descriptor=os.open(store.path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            opened=os.fstat(stream.fileno());need(self.frame_stamp(before)==self.frame_stamp(opened))
            raw=stream.read(65537);after=os.fstat(stream.fileno());current=store.path.lstat()
        stamp=self.frame_stamp(current);need(stamp==self.frame_stamp(after)==self.frame_stamp(opened) and len(raw)==current.st_size)
        observed=(stamp,hashlib.sha256(raw).hexdigest());digest=reference['sha256']
        if digest in self._frame_files:need(self._frame_files[digest]==observed)
        else:need(original is not None and raw==original);self._frame_files[digest]=observed
    def verify_frames(self,frames):
        need(type(frames) is list and len(frames)<=128)
        for frame in frames:
            digest=hashlib.sha256(canonical(frame)).hexdigest();need(digest in self._frame_references)
            self.verify_frame_file(self._frame_references[digest])
    def frame_reference(self,frame):
        # Fixed Phone5527 content-addressed private blob foundation. An original
        # frame is never truncated to fit the root CAS envelope. Every leaf
        # keeps the existing pack/PrivateFeatureState limits and exact binding.
        digest=hashlib.sha256(canonical(frame)).hexdigest()
        if digest in self._frame_references:
            need(same(self._frame_originals[digest],frame));self.verify_frame_file(self._frame_references[digest]);return deepcopy(self._frame_references[digest])
        name=self.frame_prefix+digest[:32]+'.json';reference={self.schema:1,"name":name,"sha256":digest}
        record={self.schema:1,"binding":self.binding,"runId":self.run,"fixtureUrl":self.fixture_url,"payload":pack([frame])}
        store=PrivateFeatureState(self.store.path.with_name(name));old=store.read()
        if old is None:store.write(record,None)
        else:need(same(old,record))
        need(same(store.read(),record));self.verify_frame_file(reference,canonical(record)+b'\n')
        self._frame_references[digest]=deepcopy(reference);self._frame_originals[digest]=deepcopy(frame);return reference
