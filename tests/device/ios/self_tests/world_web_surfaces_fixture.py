"""Host cache/weak-object model, not execution of the native Qt source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
import weakref


class Surface:
    def __init__(self):self.root=Root()
class Root:pass
class Lease:pass


class CacheOriginals:
    def __init__(self):
        self.sequence=0;self.now=20000;self.events=[];self.surfaces=[];self.leases=[];self.cache=[]
        self.instance=uuid.uuid4().hex
    def event(self,kind,surface,lease=''):
        self.now+=1;self.events.append(dict(sequence=len(self.events)+1,kind=kind,surfaceBirth=surface['birth'],
            rootBirth=surface['rootBirth'],leaseBirth=lease,epochMs=self.now,monotonicMs=self.now-20000))
    def reserve(self,root_source='qrc:/qml/World.qml'):
        surface=Surface();row=dict(birth=uuid.uuid4().hex,rootSource=root_source,rootBirth='',weak=weakref.ref(surface),root=weakref.ref(surface.root),cached=False)
        self.surfaces.append(row);self.event('built',row)
        row['rootBirth']=uuid.uuid4().hex;self.event('root-created',row)
        self.cache.append(surface);row['cached']=True;self.event('reserved',row);return row['birth']
    def acquire(self,entity,source):
        surface=self.cache.pop(0);row=next(row for row in self.surfaces if row['weak']() is surface)
        row['cached']=False;self.event('acquired',row);lease=Lease()
        original=dict(birth=uuid.uuid4().hex,surfaceBirth=row['birth'],entityId=entity,sourceUrl=source,weak=weakref.ref(lease))
        self.leases.append(original);self.event('renderer-acquired',row,original['birth'])
        return dict(surface=surface,lease=lease)
    def release(self,renderer):
        surface=renderer.pop('surface');renderer['lease']=None
        row=next(row for row in self.surfaces if row['weak']() is surface);self.cache.append(surface)
        row['cached']=True;self.event('released',row)
    def read(self):
        self.sequence+=1;self.now+=1
        surfaces=[{key:value for key,value in row.items() if key not in ('weak','root')}|dict(surfaceAlive=row['weak']() is not None,rootAlive=row['root']() is not None) for row in self.surfaces]
        leases=[{key:value for key,value in row.items() if key!='weak'}|dict(alive=row['weak']() is not None) for row in self.leases]
        return dict(iosWebSurfaceOwnershipVersion=1,instance=self.instance,sequence=self.sequence,processId=42,capturedEpochMs=self.now,
            monotonicMs=self.now-20000,complete=True,eventSequence=len(self.events),events=deepcopy(self.events),surfaces=surfaces,leases=leases)
