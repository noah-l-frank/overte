"""Original QML multi-picker producer; native/Qt/file boundaries are models.

Weak roots are born on the actual JS picker false-to-true transition, before
any fresh observation/control metadata. A dead earlier picker never revives.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_controls import SUFFIXES
from ios.adapters.assets_episodes import AssetsEpisodes
from ios.adapters.assets_selected_profile import EpisodeAssetsFiles
from ios.adapters.assets_page_lease import OwnedAssetsPageLease
from ios.adapters.assets_page_picker import PageLeasePicker
from ios.self_tests.assets_picker_fixture import Boundary as OriginalBoundary,uid,BINDING,RUN,URL
from ios.self_tests.test_ios_assets_selected_end_profile import AssetsSelectedEndProfileTests


class Boundary(OriginalBoundary):
    def exchange(self,value):
        before=getattr(self,'host_state',{}).get('pickerAlive',False)
        result=super().exchange(value)
        if result['pickerAlive'] and not before:self.picker=uid()
        return result
    def ui(self):
        state=self.exchange(dict(op='snapshot'));self.ui_sequence+=1
        for role,alive,identity in (('page',state['pageAlive'],self.page),('picker',state['pickerAlive'],self.picker)):
            if alive and not any(row['rootId']==identity for row in self.roots):
                self.roots.append(dict(rootId=identity,role=role,componentSource='qrc:'+SUFFIXES[role],ownerRootId=self.page,
                    firstObservedEpochMs=self.clock(),alive=True))
        result=deepcopy(self.roots)
        for row in result:
            row['alive']=state[row['role']+'Alive'] and row['rootId']==(self.page if row['role']=='page' else self.picker)
            if not row['alive']:continue
            row.update(windowId=self.window,visible=True)
            if row['role']=='picker':row.update(deepcopy(state['ui']))
            else:row.update(deepcopy(state['page']),canWrite=True,selectedPath='',selectedUrl='',modelId=self.model,modelRevision=1)
        return dict(iosAssetUiInventoryVersion=1,available=True,complete=True,instance=self.ui_instance,sequence=self.ui_sequence,
            capturedEpochMs=self.clock(),processId=42,roots=result)


class Fixture:
    boundary_type=Boundary
    def __init__(self,test):
        self.h=AssetsSelectedEndProfileTests();self.h.setUp();test.addCleanup(self.h.doCleanups)
        self.selected=self.h.archive();self.selected.select();self.episodes=AssetsEpisodes(self.selected,self.h.locks)
        self.boundary=self.boundary_type(self.h.roots['primary']);test.addCleanup(self.boundary.close)
        self.page=OwnedAssetsPageLease(self.episodes,PrivateFeatureState(self.h.roots['primary']/('ios-assets-page-lease-'+RUN+'-primary.json')),
            self.h.locks['primary'],monotonic=self.boundary.monotonic);self.page.reserve()
        self.scopes=[];self.pickers={}
    def begin(self,index,ticket):
        scope=self.episodes.begin(index,ticket);self.scopes.append(scope);return scope
    def picker(self,scope):
        root=Path(scope.descriptor['directories']['primary']['stateRoot']['path']);lock=scope.locks['primary']
        files=EpisodeAssetsFiles(self.boundary.files_native(),PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-files.json')),
            BINDING,RUN,URL,lock=lock,selection=self.selected,episode=scope)
        files.reserve(scope.descriptor['ticket'],scope.descriptor['resource']);files.stage()
        picker=PageLeasePicker(self.boundary.native_input(),files,PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-picker.json')),
            BINDING,lock=lock,monotonic=self.boundary.monotonic,sleep=self.boundary.sleep,page_lease=self.page,episode=scope)
        picker.reserve();self.pickers[scope.index]=picker;return picker
