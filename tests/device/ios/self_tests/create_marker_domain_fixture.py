"""Create-specific native DTOs around the reviewed host Script UI/Node model.

The actual staged Create JS/companion runs in Node. Qt/native/SDK/Web renderer
remain modeled. No device, compiler, installed Overte VM or camera setter runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import uuid
from unittest.mock import patch

from ios.self_tests import emote_marker_domain_fixture as shared
from ios.self_tests.test_ios_create_state import packet,version2,SESSION


class RunningDomain(shared.RunningDomain):
    def __init__(self,scope):
        super().__init__(scope);self.sequences['create']=0
        scope.create=SimpleNamespace(last=None,read=self.create)
        self.original_request=self.files.request
        self.files.last_packet=None;self.file_sequence=0
        self.files.request=self.file_request
    def attach(self,scope):
        super().attach(scope);scope.create=SimpleNamespace(last=deepcopy(scope.frames[-1]['create']),read=self.create)
    def start(self):
        view=self.world_template['source']['view'];camera=dict(position=dict(zip('xyz',view['position'])),orientation=dict(zip('xyzw',view['rotation'])))
        program=shared.PROGRAM.replace('MyAvatar:{','Camera:'+json.dumps(camera)+',MyAvatar:{')
        with patch.object(shared,'PROGRAM',program):super().start()
    def world(self,run):
        value=super().world(run)
        # The native Emote domain DTO intentionally filters only Emote markers;
        # its complete EntityTree and Script originals still include Create.
        value['source']['markers']=[]
        value['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(SESSION).bytes).hexdigest()
        return value
    def create(self,run):
        sequence=self.tick('create');value=version2(packet());value.update(iosCreateStateVersion=3,runId=run,processId=31,instance='6'*32,
            requestId='ios-'+format(7000+sequence,'032x'),sequence=sequence)
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=self.epoch(),monotonicMs=round(self.time*1000))
        source=value['source'];domain=self.world_template['source'];source.update(domainId=domain['domain']['domainId'],localSessionId=SESSION)
        source['view'].update({key:deepcopy(domain['view'][key]) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')})
        source['entities']=[];tree=source['tree'];tree.update(treeInstance=domain['tree']['treeInstance'],revisionBefore=1 if self.worker is None else 2 if self.running else 3,
            revisionAfter=1 if self.worker is None else 2 if self.running else 3,totalEntities=0,entities=[])
        if self.running:
            row=deepcopy(self.marker);stamp=row['lastEditedEpochUs']
            row.update(createdEpochUs=stamp,name=self.marker['name'],shape='',modelURL='',textures='',lastEditedBy=SESSION,locked=False,model={},voxels={})
            source['entities']=[row];tree.update(totalEntities=1,entities=[dict(id=row['id'],hostType=row['hostType'],ready=True,createdEpochUs=stamp,
                lastEditedEpochUs=stamp,lastEditedAfterEpochUs=stamp,semanticBytes=100,semanticSha256='d'*64)])
        self.scope.create.last=deepcopy(value);return value
    def widgets(self):
        value=super().widgets();value.update(createControlsVersion=2,createGeneration=str(uuid.UUID('4'*32)))
        return value
    def manager(self):
        manager=super().manager();manager.store.path=manager.store.path.with_name('ios-create-'+self.scope.role+'-marker-script.json')
        # Construct the real manager directly at its Create ownership path.
        from adapters.normal_script_manager import NormalScriptManager
        return NormalScriptManager(manager.ui,manager.observe,manager.store,self.scope.binding,source_kind='script-file-bundle',file_owner=self.scope.files,
            file_picker=manager.file_picker,monotonic=lambda:self.time,sleep=self.io.sleep)
    def paint(self):
        super().paint();self.context['descriptor']['identitySha256']=hashlib.sha256(('web-entity:'+self.marker['id']).encode()).hexdigest()
    def file_request(self,operation,run,owner,files=None):
        result=self.original_request(operation,run,owner,files);self.file_sequence+=1
        self.files.last_packet=dict(schemaVersion=1,requestId='ios-'+uuid.uuid4().hex,instance='9'*32,sequence=self.file_sequence,
            requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),processId=31,runId=run,operation=operation,source=deepcopy(result))
        return result
