"""World Web owners composed on the guarded existing iOS session runtime."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUI
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame,FILE as GPU_FILE,LIMIT as GPU_LIMIT
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.native_script_files import NativeScriptFiles,FILE as FILE_NAME,LIMIT as FILE_LIMIT
from ios.adapters.world_web_input import WorldWebInput
from ios.adapters.world_web_background import WorldWebBackground
from ios.adapters.world_web_actions import WorldWebActions
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.world_web_file_receipts import WorldWebFileReceipts


def sample(runtime,selector,source,request,root):
    source.bound();own=runtime._sources(selector);need(own['binding']==source.binding)
    native=source.native;clock=lambda:native.read(native.sequence)['capturedEpochMs'];remote=own['observer'].remote.rsplit('/',1)[0]+'/'+GPU_FILE
    def reader(intent,receipt):
        return NativeVulkanWorldFrame(own['observer'].send,lambda:own['observer'].original(remote=remote,limit=GPU_LIMIT),clock,own['check'],source.pid,
            intent,receipt=receipt,monotonic=source.monotonic,sleep=source.native.sleep)
    owner=VulkanWorldFrameOwner(PrivateFeatureState(runtime.state_path(selector).with_name('graphics-world-frame-primary-0-'+request[4:]+'.json')),
        root,source.binding,source.run,'primary',0,request,reader,own['check'],source_lock=source.lock,monotonic=source.monotonic,sleep=source.native.sleep)
    return WorldWebSample(runtime._world_web_store(selector,'ios-world-web-primary-'+request[4:]+'-sample.json'),source,owner,source.guard)


def actions(runtime,selector,source,scope,origins,entity):
    source.bound();own=runtime._sources(selector);need(own['binding']==source.binding)
    inputs=WorldWebInput(runtime._world_web_store(selector,'ios-world-web-inputs.json'),source,NativeUI(own['client'],own['session'],own['check']),entity,own['check'],epoch_ms=source.epoch_ms,monotonic=source.monotonic)
    background=WorldWebBackground(runtime,selector,source,runtime._world_web_store(selector,'ios-world-web-background.json'))
    return WorldWebActions(runtime._world_web_store(selector,'ios-world-web-actions.json'),source,inputs,scope,background,origins,own['check'])


def observer(runtime,selector,source,origins,role,*,peer=None,lease=None,sample_resolver=None,setup_scope=None):
    return WorldWebObserver(runtime._world_web_store(selector,'ios-world-web-'+role+'-observer.json'),source,origins,
        source.guard if peer is None else peer.guard,role=role,peer=peer,lease=lease,sample_resolver=sample_resolver,setup_scope=setup_scope)


def file_receipts(runtime,selector,source,root):
    source.bound();own=runtime._sources(selector);need(own['binding']==source.binding)
    # Reuse the actual unbound clock instance that the source owner restores.
    # The common receipt journals every query of this instance before send.
    native=source.native;clock=lambda:native.read(native.sequence)['capturedEpochMs'];remote=own['observer'].remote.rsplit('/',1)[0]+'/'+FILE_NAME
    files=NativeScriptFiles(own['observer'].send,lambda:own['observer'].original(remote=remote,limit=FILE_LIMIT),clock,own['check'],source.pid,ios=True,
        monotonic=source.monotonic,sleep=source.native.sleep)
    return WorldWebFileReceipts(runtime._world_web_store(selector,'ios-world-web-primary-files.json'),root,source.binding,source.run,'primary',source.lock,own['check'],
        native=native,files=files,epoch_ms=source.epoch_ms,monotonic=source.monotonic)
