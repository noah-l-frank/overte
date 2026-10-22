"""Snapshot immutable evidence storage over the existing original file engines.

These files retain bytes and provenance. They never establish capture, Save,
receiver consumption or upload success without their independent source joins.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import context
from feature_journeys.contract import identifier
from overte_phone_assets_evidence import AssetsOriginals
from overte_phone_create_evidence import CreateImages
from overte_phone_script_history import canonical
from snapshot_observation import MAX_BYTES,inspect_snapshot


class SnapshotsOriginals(AssetsOriginals):
    KINDS=frozenset({'snapshots','snapshots-input','snapshots-retirement'})

    def clone_frame(self,body,raw):
        # The actual immutable file has just passed every inode/hash/header
        # check, including the existing canonical/schema parse cache. Parse
        # those exact bytes into a new graph instead of recursively copying
        # the cached graph in Python. Neither graph can alias a later read.
        return json.loads(raw)['frame']


class SnapshotsImages(CreateImages):
    KIND='snapshots'


class SnapshotsBinary(CreateImages):
    """Retain a separately acquired original body, with its own exact inode.

    The existing native capture owner retires its intermediate host copies.
    This immutable transcript remains independently auditable afterwards.
    """
    KIND='snapshots-file'
    LIMIT=MAX_BYTES
    SOURCES=frozenset({'snapshot-capture-original','snapshot-saved-original','snapshot-receiver-original','snapshot-upload-original','snapshot-document-original'})

    @classmethod
    def valid_stage(cls,stage):return integer(stage,1,256)

    @classmethod
    def record(cls,value):
        exact(value,{'snapshotsBinaryVersion','binding','runId','role','stage','ticket','acquisition','name','phase','file'})
        need(type(value['snapshotsBinaryVersion']) is int and value['snapshotsBinaryVersion']==1 and value['role'] in ('primary','actor')
            and cls.valid_stage(value['stage']) and value['phase'] in ('planned','opened','saved'))
        context(value['binding']);identifier(value['runId']);identifier(value['ticket']);source=value['acquisition']
        need(type(source) is dict and len(canonical(source))<=65536 and source.get('source') in cls.SOURCES
            and integer(source.get('bytes'),1,MAX_BYTES) and integer(source.get('capturedEpochMs'),1)
            and type(source.get('sha256')) is str and len(source['sha256'])==64 and all(c in '0123456789abcdef' for c in source['sha256']))
        identity=hashlib.sha256(canonical(source)).hexdigest()[:32]
        need(value['name']=='snapshots-file-'+value['runId']+'-'+value['role']+'-'+str(value['stage'])+'-'+identity+'.bin')
        if value['phase']=='planned':need(value['file'] is None)
        else:
            exact(value['file'],{'device','inode'});need(integer(value['file']['device']) and integer(value['file']['inode'],1))
        return value

    def value(self,ticket,source):
        identity=hashlib.sha256(canonical(source)).hexdigest()[:32]
        return dict(snapshotsBinaryVersion=1,binding=deepcopy(self.binding),runId=self.run,role=self.role,stage=self.stage,ticket=ticket,
            acquisition=deepcopy(source),name='snapshots-file-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+identity+'.bin',phase='planned',file=None)

    def content(self,value,raw):
        source=value['acquisition'];need(type(raw) is bytes and len(raw)==source['bytes'] and hashlib.sha256(raw).hexdigest()==source['sha256'])
        # The closed extended journey captures one still PNG. Other format
        # qualification remains the existing independent five-format foundation.
        try:inspect_snapshot(raw,mode='still',file_format='png')
        except (OSError,ValueError):need(False)


class HistoricalSnapshotsBinary(SnapshotsBinary):
    """Share only a PNG decode within one bounded historical validation pass.

    Every read still verifies its original record, file identity and actual
    bytes against its own source. The memo contains exact immutable bytes,
    never a source verdict, and is discarded by the caller after that pass.
    """
    def __init__(self,*args,decoded_pngs,**kwargs):
        need(type(decoded_pngs) is set)
        self.decoded_pngs=decoded_pngs
        super().__init__(*args,**kwargs)

    def content(self,value,raw):
        source=value['acquisition']
        need(type(raw) is bytes and len(raw)==source['bytes']
            and hashlib.sha256(raw).hexdigest()==source['sha256'])
        if raw in self.decoded_pngs:return
        super().content(value,raw)
        # Large or diverse histories remain fully checked without retaining
        # unbounded bodies. This changes no file/decode acceptance limit.
        if len(self.decoded_pngs)<256 and sum(map(len,self.decoded_pngs))+len(raw)<=16*1024*1024:
            self.decoded_pngs.add(raw)
