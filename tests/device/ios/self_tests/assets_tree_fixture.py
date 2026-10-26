"""Original tree/rename/delete QML with declared native/service models.

The model is built from independently maintained publication bytes, never
adapter-expected rows. Binary read replies observe changes separately. No Qt,
native compiler, server, device or installed candidate executes here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import assets_tree_controls as controls
from ios.adapters.assets_controls import SUFFIXES
from ios.self_tests import assets_upload_fixture as upload
from ios.self_tests import assets_picker_fixture as picker
from feature_journeys.asset_fixture import BUNDLES
from feature_journeys.fixtures import companion

RUN,TICKET,URL,BINDING=upload.RUN,upload.TICKET,upload.URL,upload.BINDING


class Boundary(upload.Boundary):
    host_extra=(str(picker.ROOT/'interface/resources/qml/hifi/dialogs/NativeModelTree.qml'),)
    def __init__(self,directory):
        self.tree_instance=picker.uid();self.tree_sequence=0;self.tree_id=picker.uid();self.rename=picker.uid();self.remove=picker.uid();self.mapping_seen=0
        super().__init__(directory)

    def exchange(self,value):
        result=super().exchange(value);events=result.get('bundleInfo',{}).get('serviceEvents',[])
        for event in events[self.mapping_seen:]:
            if event['kind']!='mapping-completed' or event['error']:continue
            for change in event['changes']:
                raw=base64.b64decode(change['base64'],validate=True);need(self.reads.data.get(change['from'])==raw)
                self.reads.data.pop(change['from'])
                if change['to'] is not None:self.reads.data[change['to']]=raw
        self.mapping_seen=len(events);return result

    def tree_page(self):
        return dict(deepcopy(self.host_state['treeInfo']),rootId=self.page,windowId=self.window,treeId=self.tree_id,modelId=self.model,
            componentSource='qrc:'+SUFFIXES['page'],renameId=self.rename,deleteId=self.remove)

    def ui(self):
        result=super().ui();data=self.host_state['treeInfo']
        for root in result['roots']:
            if root['role']=='page' and root['alive']:root.update(selectedPath=data['currentPath'],selectedUrl=data['currentUrl'],modelRevision=data['treeRevision'],canWrite=data['canWrite'])
        return result

    def control_metadata(self,identifier,item,role):
        if not controls.control_id(identifier):return super().control_metadata(identifier,item,role)
        data=self.tree_page();match=controls.ROW.fullmatch(identifier);row=data['rows'][int(match[1])] if match else None
        for key in ('rows','modelRows','filterText'):data.pop(key)
        return controls.metadata(dict(data,assetControlVersion=3,role='page',ownerRootId=self.page,controlId=identifier,row=row))

    def extensions(self,ui):
        result=super().extensions(ui);self.tree_sequence+=1
        result.update(assetTreeControlsVersion=1,assetTreeInventory=dict(iosAssetsTreeUiVersion=1,instance=self.tree_instance,sequence=self.tree_sequence,
            processId=42,capturedEpochMs=self.clock(),available=True,complete=True,pages=[self.tree_page()] if self.host_state['pageAlive'] else []))
        return result


class Fixture(upload.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        super().__init__(directory);self.tree_store=PrivateFeatureState(Path(directory)/'assets-tree.json')

    def uploaded(self):
        self.start();owner=self.owner();owner.reserve();owner.review();owner.destination();owner.start_upload();owner.uploaded();return owner

    def seeded_page(self):
        # Explicit independent server boundary inputs, not observed adapter
        # output. The original QML builds its own hierarchy and selection.
        prefix='/e2e-'+RUN+'/'
        self.boundary.reads.data={prefix+name:companion('gltf-bundle/'+name) for name in BUNDLES['gltf-bundle/main.gltf'][1]}
        self.boundary.configure(serverRows=[dict(path=path,base64=base64.b64encode(raw).decode()) for path,raw in self.boundary.reads.data.items()])
        self.files.reserve(TICKET);self.files.stage();self.picker.reserve();self.picker.open_page();self.replies.reserve(TICKET)

    def tree_owner(self,owner):
        from ios.adapters.assets_tree_owner import OwnedAssetsTree
        return OwnedAssetsTree(owner,self.tree_store,lock=self.lock)
