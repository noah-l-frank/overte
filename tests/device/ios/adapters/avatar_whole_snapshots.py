"""Private immutable whole-owner snapshots, never independent product facts.

The parent admits each file transition before proceeding. References preserve
original bytes and inode identity instead of nesting unbounded owner histories
inside the small whole-operation journal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from adapters.native_feature_observation import exact,integer,need
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same


class AvatarWholeSnapshots:
    def __init__(self,root,binding,run,role,entries,guard,save):
        self.entries,self.save=entries,save
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage,namespace='avatar-whole-owned',schema_prefix='avatarWholeOwned')

    def storage(self,kind,value):
        need(kind=='original');rows=self.entries();self.originals.original(value);index=value['index']
        if value['phase']=='planned':need(index==len(rows)+1);rows.append(deepcopy(value))
        else:
            need(integer(index,1,len(rows)));old=rows[index-1]
            need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(old['file'],value['file'])))
            rows[index-1]=deepcopy(value)
        self.save()

    def inspect(self,value):
        self.originals.original(value)
        if value['phase']=='planned':return False
        path=self.originals.path(value);fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as stream:
            self.originals.file(path,stream.fileno(),value);raw=stream.read(value['bytes']+1);self.originals.file(path,stream.fileno(),value)
        need(len(raw)<=value['bytes']);complete=len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']
        if value['phase']=='saved':need(complete)
        return complete

    def validate(self):
        rows=self.entries();need(type(rows) is list and len(rows)<=64)
        for index,value in enumerate(rows,1):need(value['index']==index);self.inspect(value)

    def retain(self,value):
        need(type(value) is dict);self.validate()
        for original in self.entries():
            if self.inspect(original) and same(self.originals.read(original),value):
                return dict(index=original['index'],sha256=original['sha256'])
        need(len(self.entries())<64);compact=self.originals.write(len(self.entries())+1,value)
        return {key:compact[key] for key in ('index','sha256')}

    def read(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(self.entries())))
        original=self.entries()[reference['index']-1];need(original['sha256']==reference['sha256'] and self.inspect(original))
        return self.originals.read(original)
