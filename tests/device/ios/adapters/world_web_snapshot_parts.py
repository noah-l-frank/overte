"""One retained actual Snapshot carrier, closed references to its originals.

Projected references retain no requested effects. The native resultJSON bytes,
selected original ordinal and exact command come from the original parent. A
round can reuse decoding only after actually reading and hashing that parent;
unchanged private file identity guards every subsequent use and round exit.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import os
import re
import stat
from adapters.original_frame_store import OriginalFrameStore
from adapters.native_feature_observation import exact,integer,need,decode
from adapters.native_clock_join import digest
from adapters.script_feature.history import canonical,same
from ios.adapters import world_web_snapshot as snapshot
from ios.adapters import world_web_whole_snapshot as whole_snapshot
from ios.adapters.world_web_json_pair import clone_pair

CHUNK=512*1024
NAMES=frozenset(snapshot.ACTIONS)|frozenset(whole_snapshot.ACTIONS)


def decoder(value):
    version=value.get('iosWorldWebSnapshotVersion');need(type(version) is int and version in (1,2))
    return snapshot if version==1 else whole_snapshot


_COPY_PAIR=clone_pair
_COPY_PAIR_CODE=clone_pair.__code__
_COPY_PAIR_DEFAULTS=clone_pair.__defaults__


def _detached_original(value):
    """Copy only this process's exact JSON graph; never reuse a verdict.

    All existing parent reads and inode/ordinal checks precede this call. The
    already qualified pair copier preserves mutable aliases and cycles; using
    its first detached copy adds no borrowed outward reference. Unsupported or
    changed copying semantics retain the literal deepcopy call.
    """
    clone,copier=clone_pair,deepcopy
    def literal():
        return (clone_pair is clone and clone is _COPY_PAIR
            and clone.__code__ is _COPY_PAIR_CODE and clone.__defaults__ is _COPY_PAIR_DEFAULTS
            and clone.__kwdefaults__ is None and deepcopy is copier)
    if literal():
        pair=clone(value,copier)
        if pair is not None and literal():return pair[0]
    return deepcopy(value)


class WorldWebSnapshotParts:
    def __init__(self,owner):self.owner=owner;self._store=None;self._round=None
    def store(self):
        owner=self.owner;role='primary' if owner.role=='primary' else 'actor';code={'primary':'p','actor':'a','actor-primary':'ap'}[owner.role]
        if self._store is None:
            self._store=OriginalFrameStore(owner.store.path.parent,owner.binding,owner.run,role,owner.guard,
                lambda kind,value:owner.snapshot_storage_intent(kind,value),namespace='world-web-'+code+'-snapshot',schema_prefix='worldWebSnapshotPart',monotonic=owner.monotonic)
        value=self._store
        need(value.root==owner.store.path.parent and value.binding==owner.binding and value.run==owner.run and value.role==role
            and value.guard is owner.guard and value.monotonic is owner.monotonic and value.namespace=='world-web-'+code+'-snapshot'
            and value.schema_prefix=='worldWebSnapshotPart' and value.kind=='sources')
        return value
    def validate(self,value):
        exact(value,{'worldWebSnapshotPartsVersion','index','acquisitionId','bytes','sha256','chunks'})
        need(type(value['worldWebSnapshotPartsVersion']) is int and value['worldWebSnapshotPartsVersion']==1 and integer(value['index'],1,256)
            and type(value['acquisitionId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['acquisitionId'])
            and integer(value['bytes'],2,snapshot.LIMIT) and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256'])
            and type(value['chunks']) is list and len(value['chunks'])==(value['bytes']+CHUNK-1)//CHUNK)
        for offset,reference in enumerate(value['chunks']):
            self.store().expand(reference);need(reference['index']==(value['index']-1)*4+offset+1)
        return value
    def paths(self,value):
        self.validate(value);store=self.store();return [store.path(store.expand(reference)) for reference in value['chunks']]
    @staticmethod
    def signature(path):
        row=path.lstat();need(stat.S_ISREG(row.st_mode) and row.st_nlink==1 and row.st_uid==os.geteuid() and stat.S_IMODE(row.st_mode)==0o600)
        return (row.st_dev,row.st_ino,row.st_mode,row.st_uid,row.st_gid,row.st_nlink,row.st_size,row.st_mtime_ns,row.st_ctime_ns)
    def read_bytes(self,value):
        self.validate(value);store=self.store();raw=bytearray()
        for reference in value['chunks']:
            frame=store.read(store.expand(reference));exact(frame,{'sourceIndex','acquisitionId','offset','bytes','data'})
            need(type(frame['sourceIndex']) is int and frame['sourceIndex']==value['index'] and frame['acquisitionId']==value['acquisitionId']
                and type(frame['offset']) is int and frame['offset']==len(raw) and type(frame['bytes']) is int and frame['bytes']==value['bytes'] and type(frame['data']) is str)
            chunk=base64.b64decode(frame['data'],validate=True);need(base64.b64encode(chunk).decode('ascii')==frame['data'] and len(chunk)==min(CHUNK,value['bytes']-len(raw)));raw.extend(chunk)
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']);return bytes(raw)
    def write(self,index,value):
        need(integer(index,1,256));owner=self.owner;acquisition=owner.state['pending']['start']['nativeBefore']['requestId']
        module=decoder(value);need(value['iosWorldWebSnapshotVersion']==(2 if getattr(owner,'version',4)==5 else 1))
        module.validate(value,dict(schemaVersion=1,commandId=value['commandId'],action=module.ACTION,runId=owner.run,fixtureUrl=owner.phase.fixture_url),owner.pid)
        need(value['status']=='ready');raw=canonical(value);need(2<=len(raw)<=snapshot.LIMIT);store=self.store();chunks=[]
        for offset in range(0,len(raw),CHUNK):
            frame=dict(sourceIndex=index,acquisitionId=acquisition,offset=offset,bytes=len(raw),data=base64.b64encode(raw[offset:offset+CHUNK]).decode('ascii'))
            chunks.append(store.write((index-1)*4+len(chunks)+1,frame))
        ref=dict(worldWebSnapshotPartsVersion=1,index=index,acquisitionId=acquisition,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),chunks=chunks)
        need(self.read_bytes(ref)==raw);return deepcopy(ref)
    def guard(self,pins):
        for path,signature in pins.items():need(self.signature(path)==signature)
    @contextmanager
    def validation_round(self):
        if self._round is not None:yield;return
        self._round={}
        try:
            with snapshot.validation_round(),whole_snapshot.validation_round():yield
        finally:
            try:
                for _value,_original,_body,_parts,pins in self._round.values():self.guard(pins)
            finally:self._round=None
    def _original(self,reference):
        self.validate(reference);key=digest(reference)
        if self._round is not None and key in self._round:
            old,value,body,parts,pins=self._round[key];owner=self.owner
            need(old==reference and value['processId']==owner.pid and value['runId']==owner.run and value['fixtureUrl']==owner.phase.fixture_url
                and value['iosWorldWebSnapshotVersion']==(2 if getattr(owner,'version',4)==5 else 1))
            self.guard(pins)
            from adapters.original_file_reads import active,scope
            if active():
                with scope() as reads:
                    if not all(path in reads for path in pins):need(self.read_bytes(reference)==canonical(value))
            self.guard(pins);return value,body,parts
        paths=self.paths(reference);pins={path:self.signature(path) for path in paths};raw=self.read_bytes(reference)
        value=decode(raw.decode('utf-8'),limit=snapshot.LIMIT);need(canonical(value)==raw)
        owner=self.owner;module=decoder(value);need(value['iosWorldWebSnapshotVersion']==(2 if getattr(owner,'version',4)==5 else 1))
        module.validate(value,dict(schemaVersion=1,commandId=value['commandId'],action=module.ACTION,runId=owner.run,fixtureUrl=owner.phase.fixture_url),owner.pid)
        need(value['status']=='ready');body,parts=module._validated_body(value);self.guard(pins)
        if self._round is not None:
            need(len(self._round)<256);self._round[key]=(deepcopy(reference),value,body,parts,pins)
        return value,body,parts
    def original(self,reference):
        value,_body,parts=self._original(reference);return deepcopy(value),deepcopy(parts)
    def packet(self,reference):
        value,_body,_parts=self._original(reference);return deepcopy(value)
    def matches(self,reference,parts):
        _value,_body,originals=self._original(reference);need(same(originals,parts))
    def project(self,reference):
        value,body,_parts=self._original(reference);module=decoder(value);version=value['iosWorldWebSnapshotVersion']
        return {name:dict(worldWebSnapshotProjectionVersion=version,name=name,index=reference['index'],acquisitionId=reference['acquisitionId'],parent=deepcopy(reference),ordinal=body['originals'][name]) for name in module.ACTIONS}
    def projection(self,value):
        exact(value,{'worldWebSnapshotProjectionVersion','name','index','acquisitionId','parent','ordinal'})
        version=value['worldWebSnapshotProjectionVersion'];need(type(version) is int and version in (1,2)
            and value['name'] in (snapshot.ACTIONS if version==1 else whole_snapshot.ACTIONS))
        self.validate(value['parent']);need(type(value['index']) is int and value['index']==value['parent']['index'] and value['acquisitionId']==value['parent']['acquisitionId']
            and (value['ordinal'] is None and value['name']=='document' or integer(value['ordinal'],1,64)))
        return value
    def read(self,value):
        self.projection(value);_parent,body,parts=self._original(value['parent'])
        need(value['worldWebSnapshotProjectionVersion']==_parent['iosWorldWebSnapshotVersion']
            and value['ordinal']==body['originals'][value['name']]);return _detached_original(parts[value['name']])
    def verify_projection(self,value):
        """Verify actual original ownership without copying its decoded DTO.

        The first use still reads/hashes the entire actual parent. Reuse is
        confined to the explicit round with its current file identity checks;
        this method never supplies an outward mutable original or fresh fact.
        """
        self.projection(value);_parent,body,_parts=self._original(value['parent'])
        need(value['worldWebSnapshotProjectionVersion']==_parent['iosWorldWebSnapshotVersion'] and value['ordinal']==body['originals'][value['name']])
