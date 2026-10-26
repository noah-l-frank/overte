"""Original baking/import QML with explicit Qt/API/service boundary models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.fixtures import pinned_resource
from ios.adapters import assets_usage_controls as usage
from ios.adapters.assets_controls import project
from ios.self_tests import assets_tree_fixture as tree,assets_picker_fixture as picker

RUN,TICKET,URL,BINDING=tree.RUN,tree.TICKET,tree.URL,tree.BINDING


class Boundary(tree.Boundary):
    host_extra=(*tree.Boundary.host_extra,'usage')
    def __init__(self,directory):
        self.usage_instance=picker.uid();self.usage_sequence=0;self.usage_seen=0
        self.usage_ids={key:picker.uid() for key in ('apiId','clientNodeId','baking','importButtonId','uploadedImportButtonId','dialog','url','shape','dynamic')}
        super().__init__(directory)
    def exchange(self,value):
        result=super().exchange(value);events=result.get('bundleInfo',{}).get('serviceEvents',[])
        for event in events[self.usage_seen:]:
            if event['kind']=='baking-completed':
                for path in event['paths']:self.reads.status[path]=(event['status'],event['error'])
        self.usage_seen=len(events);return result
    def usage_page(self):
        source=self.tree_page();value={key:deepcopy(source[key]) for key in ('rootId','windowId','componentSource','treeId','modelId','treeRevision','selectedPaths','currentPath','currentUrl','canWrite','busy')}
        value.update(deepcopy(self.host_state['usageInfo']));value.update({key:self.usage_ids[key] for key in ('apiId','clientNodeId','importButtonId','uploadedImportButtonId')},domainId=self.reads.binding['domainId'])
        value['baking']['id']=self.usage_ids['baking'];value['model'].update(id=self.usage_ids['dialog'],urlId=self.usage_ids['url'],shapeId=self.usage_ids['shape'],dynamicId=self.usage_ids['dynamic'])
        return value
    def control_metadata(self,identifier,item,role):
        if not usage.control_id(identifier):return super().control_metadata(identifier,item,role)
        current=self.usage_page();return usage.metadata(dict(assetControlVersion=4,role='page',rootId=self.page,ownerRootId=self.page,windowId=self.window,
            componentSource=current['componentSource'],controlId=identifier,inputReady=usage.input_ready(current,identifier),usage=current))
    def extensions(self,ui):
        value=super().extensions(ui);self.usage_sequence+=1
        value.update(assetUsageControlsVersion=1,assetUsageInventory=dict(iosAssetsUsageUiVersion=1,instance=self.usage_instance,sequence=self.usage_sequence,
            processId=42,capturedEpochMs=self.clock(),available=True,complete=True,pages=[self.usage_page()] if self.host_state['pageAlive'] else []));return value


class Fixture(tree.Fixture):
    boundary_type=Boundary
    def seeded_fbx_page(self):
        path='/e2e-'+RUN+'/stand.fbx';raw=pinned_resource('asset-stand.fbx');self.boundary.reads.resource='asset-stand.fbx'
        self.boundary.reads.data={path:raw};self.boundary.reads.status[path]=(1,'')
        self.boundary.configure(serverRows=[dict(path=path,base64=base64.b64encode(raw).decode(),status=1)])
        # This isolated control source starts with an existing server asset.
        # Open the actual browser normally; no local upload is claimed here.
        store=PrivateFeatureState(self.boundary.directory/'usage-browser-open-intents.json');previous=None;commands=[]
        def intent(command):
            nonlocal previous
            commands.append(deepcopy(command));value=dict(commands=commands);store.write(value,previous);previous=deepcopy(value);return True
        for identifier in ('assets.menu','assets.open'):
            self.input.assets_input(identifier,'activate',reference=project(self.input.capture()),before_send=intent)
        self.replies.reserve(TICKET,'asset-stand.fbx')
