"""Frozen actual Result2 decoder membership, never live SDK replacement facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import stat
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import collect as collect_reads
from adapters.script_feature.history import same
from ios.adapters.snapshot_combined_photos_journey import SnapshotCombinedPhotosJourney
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive

ZERO='0'*64
MAX_PINS=16384


def node(path):
    row=path.lstat()
    return [row.st_dev,row.st_ino,row.st_mode,row.st_uid,row.st_gid,row.st_nlink,row.st_size,row.st_mtime_ns,row.st_ctime_ns]


def original_pin(path):
    path=Path(path);before=node(path);need(stat.S_ISREG(before[2]) and before[5]==1 and before[6]<=2**32)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as stream:
        actual=os.fstat(stream.fileno());need([actual.st_dev,actual.st_ino]==before[:2])
        sha=hashlib.sha256()
        for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
        need(node(path)==before and actual.st_size==before[6])
    return dict(stat=before,sha256=sha.hexdigest())


class SnapshotPhotosEndGraph:
    def __init__(self,journey):
        need(type(journey) is SnapshotCombinedPhotosJourney and type(journey.photos) is SnapshotPhotosArchive)
        self.journey=journey;self.photos=journey.photos;returned=journey.journey.returned;share=returned.end.share
        need(returned.historical and returned.end.historical and share.historical and journey.journey.backend.historical
            and journey.journey.backend.native.historical and self.photos.historical)
        self.roots=dict(main=returned.root,photos=self.photos.companion_root,archive=share.archive_root)
        need(len(set(self.roots.values()))==3)
        self.locks=(returned.lock,self.photos.companion_lock,share.archive_lock)
        self.artifacts=(Path(self.photos.companion.artifact_path),Path(returned.end.archive['artifactPath']))
        self.store=PrivateFeatureState(self.roots['photos']/'photos-sdk-end-graph.json');self.previous=self.store.read()
        if self.previous is not None:self.validate(self.previous)
    def locked(self):
        for lock in self.locks:lock.assert_held()
        for root in self.roots.values():PrivateFeatureState(root/'photos-graph-boundary')._parent()
        return True
    def scope(self):
        self.locked()
        return dict(binding=deepcopy(self.photos.binding),companionBinding=deepcopy(self.photos.companion_binding),
            runId=self.photos.run,fixtureUrl=self.photos.fixture_url,roots={key:str(value) for key,value in self.roots.items()},
            artifactPaths=[str(value) for value in self.artifacts],primaryBundle=self.photos.primary.target['appId'])
    def row_store(self,index):
        need(integer(index,1,MAX_PINS));return PrivateFeatureState(self.store.path.with_name('photos-sdk-end-graph-pin-'+format(index,'05d')+'.json'))
    def locate(self,path):
        selected=[(key,path.name) for key,root in self.roots.items() if path.parent==root]
        if not selected:
            selected=[('artifact'+str(index),path.name) for index,value in enumerate(self.artifacts) if path==value]
        need(len(selected)==1);return selected[0]
    def path(self,location,name):
        need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,255}',name) and name not in ('.','..'))
        if location in self.roots:path=self.roots[location]/name
        else:
            need(location in ('artifact0','artifact1'));path=self.artifacts[int(location[-1])];need(path.name==name)
        need(path.is_absolute() and path.parent.resolve(strict=True)==path.parent);return path
    def lease(self):
        self.locked();result={}
        for root in self.roots.values():
            rows=list(root.iterdir());need(len(rows)<=8192)
            for path in rows:result[path]=node(path)
        for path in self.artifacts:result[path]=node(path)
        return result
    def proof_originals(self):
        # Reconstruct the Photos reader from its actual stores. The remaining
        # base graph is explicitly historical and all its normal guards remain.
        photos=self.photos
        fresh=SnapshotPhotosArchive.history(photos.store,photos.lock,photos.companion_lock,photos.binding,photos.companion_binding,
            photos.run,photos.fixture_url,photos.companion.artifact_path,photos.admission.store,photos.primary.target['appId'])
        need(same(fresh.previous,photos.previous))
        value=SnapshotCombinedPhotosJourney(self.journey.journey,fresh).proof()
        capture,_fact,artifact,_raw=fresh.capture();artifact.read()
        host=artifact.store.path.parent/artifact.state['name']
        need(value['snapshotCombinedJourneyResultVersion']==2 and value['photosDestinationCompositionRequired'] is False
            and value['photosSDKRetirementRequired'] is True and capture.historical)
        return value,host
    def freeze(self):
        self.locked();before=self.lease()
        from ios.adapters.snapshot_photos_end_round import scope as decode_round
        with decode_round(self):
            with collect_reads() as reads:value,host=self.proof_originals()
        paths=set(reads)|{host,*self.artifacts};need(1<=len(paths)<=MAX_PINS)
        rows=[];tail=ZERO
        for index,path in enumerate(sorted(paths,key=str),1):
            location,name=self.locate(path);pin=original_pin(path);need(path in before and pin['stat']==before[path])
            row=dict(snapshotPhotosEndGraphPinVersion=1,index=index,previousSha256=tail,location=location,name=name,original=pin)
            rows.append(row);tail=digest(row)
        value=dict(snapshotPhotosEndGraphVersion=1,scope=self.scope(),rootIdentities={key:node(root)[:6] for key,root in self.roots.items()},
            originalResult2=value,fileCount=len(rows),tailSha256=tail)
        if self.previous is not None:need(same(value,self.previous));self.verify();return deepcopy(value)
        missing=sum(not self.row_store(row['index']).path.exists() for row in rows)
        need(len(list(self.roots['photos'].iterdir()))+missing+2<8192)
        for row in rows:
            store=self.row_store(row['index']);old=store.read()
            if old is None:store.write(row,None)
            else:need(same(old,row))
        self.store.write(value,None);self.previous=self.store.read();need(same(value,self.previous));self.verify();return deepcopy(value)
    def validate(self,value):
        exact(value,{'snapshotPhotosEndGraphVersion','scope','rootIdentities','originalResult2','fileCount','tailSha256'})
        need(type(value['snapshotPhotosEndGraphVersion']) is int and value['snapshotPhotosEndGraphVersion']==1
            and same(value['scope'],self.scope()) and integer(value['fileCount'],1,MAX_PINS)
            and set(value['rootIdentities'])==set(self.roots) and type(value['tailSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['tailSha256'])
            and value['originalResult2']['snapshotCombinedJourneyResultVersion']==2)
        return value
    def verify(self):
        from ios.adapters.snapshot_photos_end_round import verified_paths
        reused=verified_paths(self)
        if reused is not None:return reused
        self.locked();need(self.previous is not None and same(self.store.read(),self.previous));value=self.validate(self.previous)
        for key,root in self.roots.items():need(node(root)[:6]==value['rootIdentities'][key])
        tail=ZERO;paths=set()
        for index in range(1,value['fileCount']+1):
            row=self.row_store(index).read();exact(row,{'snapshotPhotosEndGraphPinVersion','index','previousSha256','location','name','original'})
            need(type(row['snapshotPhotosEndGraphPinVersion']) is int and row['snapshotPhotosEndGraphPinVersion']==1 and type(row['index']) is int
                and row['index']==index and row['previousSha256']==tail)
            path=self.path(row['location'],row['name']);need(path not in paths and same(original_pin(path),row['original']));paths.add(path);tail=digest(row)
        expected={self.row_store(index).path for index in range(1,value['fileCount']+1)}
        actual={path for path in self.roots['photos'].iterdir() if path.name.startswith('photos-sdk-end-graph-pin-')}
        need(actual==expected and tail==value['tailSha256']);return paths
    def replay(self,position):
        from ios.adapters.snapshot_photos_end_position import SnapshotPhotosRetiredSDKPosition
        from ios.adapters.snapshot_photos_end_round import scope as decode_round
        need(type(position) is SnapshotPhotosRetiredSDKPosition)
        with decode_round(self):
            position.check(self);paths=self.verify()
            with collect_reads() as reads:value,host=self.proof_originals()
            need(paths==set(reads)|{host,*self.artifacts} and same(value,self.previous['originalResult2']))
            self.verify();position.check(self)
        return deepcopy(value)
