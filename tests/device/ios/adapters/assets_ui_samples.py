"""Original Assets UI screenshots before import, with independent source custody.

Shares the existing Tablet original PNG/WAL mechanics through closed hooks.
Its source grammar is actual Assets UI/Create/UIKit, never WK or imported Model.
Native compilation, device pixels and whole29 qualification remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from adapters.native_feature_observation import need
from ios.adapters.assets_end_metadata import store as metadata_store,checked as metadata_checked
from ios.adapters.assets_ui_source import AssetsUiSource
from ios.adapters.assets_ui_images import IOSAssetsUiImages,AssetsUiScreenArchive
from ios.adapters.assets_ui_measurements import frame,compose
from ios.adapters.tablet_web_samples import TabletWebSamples


class AssetsUiSamples(TabletWebSamples):
    OWNER_KEY='assetsUiSamplesVersion'
    SAMPLE_KEY='assetsUiScreenSampleVersion'
    PREFIX='assets-ui'
    SCREEN_NAMESPACE='assets-ui'
    SCREEN_VERSION='assetsUiScreenImagesVersion'
    FRAME_NAMESPACE='assets-ui-screen-samples'
    FRAME_SCHEMA='assetsUiScreenSample'
    SCREEN_TYPE=IOSAssetsUiImages
    ARCHIVE_TYPE=AssetsUiScreenArchive
    def __init__(self,source,root,policy,client,native_clock,*,historical=False,metadata=None):
        need(isinstance(source,AssetsUiSource) and source.historical==historical and callable(native_clock))
        metadata_checked(metadata);need(metadata is None or historical);self.metadata=metadata
        self.ui_source=source
        runtime=SimpleNamespace(observer=SimpleNamespace(source=source),client=client,native_clock=native_clock,
            tail_source=source.capture,validate_tail_source=source.validate)
        super().__init__(runtime,root,policy,historical=historical)
    def file_guard(self):
        self.lock.assert_held();return super().file_guard()
    def feature_store(self,path):return metadata_store(path,self.metadata)
    def admit_frame(self,value):
        source=self.ui_source
        return frame(value,self.binding,self.run,source.upload.state['page'],source.subject,source.checkpoint)
    def measure(self,ticket,before,after,capture,raw,*,previous=None,changed=False):
        source=self.ui_source;left=source.marker_identity(before);right=source.marker_identity(after);need(left==right)
        return compose(self.run,ticket,self.binding,before,after,capture,raw,self.policy,left,
            page=source.upload.state['page'],subject=source.subject,checkpoint=source.checkpoint,previous=previous,changed=changed)
    def capture(self,ticket,*,before=None):
        # The optional Tablet reuse profile has its own multi-source custody.
        # Assets always acquires its genuine new before original here.
        need(before is None and not self.ui_source.historical)
        return super().capture(ticket)
