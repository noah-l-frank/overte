"""Assets owners on the canonical existing candidate/session/clock transport.

No session is created, no build is installed, and no feature is advertised.
Successful upload still needs its real review/destination normal input route.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.asset_fixture import bundle
from feature_journeys.contract import identifier
from ios.adapters.assets_budget import check,operation
from ios.adapters.assets_files import OwnedAssetsFiles
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.normal_input import NativeInput
from ios.adapters.script_runtime import IOSScriptRuntime


class AssetsNativeInput(NativeInput):
    """Same original native input channel, with final candidate/budget guards."""
    @classmethod
    def from_original(cls,original,guard):
        need(isinstance(original,NativeInput) and callable(guard))
        value=object.__new__(cls);value.__dict__=original.__dict__;value.assets_guard=guard;return value

    def _request(self,operation,native=None,*,before_send=None):
        def final_guard():
            check();self.assets_guard()
            if before_send is not None and before_send() is False:return False
            check();self.assets_guard()
        return super()._request(operation,native,before_send=final_guard)


class IOSAssetsRuntime(IOSScriptRuntime):
    def __init__(self,adapter,*,monotonic=time.monotonic):
        super().__init__(adapter);need(callable(monotonic));self.monotonic=monotonic

    def _assets_store(self,selector,run,role,kind):
        identifier(run);need(role in ('primary','actor') and kind in ('files','picker','replies'))
        return PrivateFeatureState(self.state_path(selector).with_name('ios-assets-'+run+'-'+role+'-'+kind+'.json'))

    @operation
    def _assets_sources(self,selector,lock):
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'));lock.assert_held()
        check();sources=super()._sources(selector);check();original_check=sources['check']
        def bound():
            check();lock.assert_held();original_check();check()
        def guarded_process():bound();return sources['process']()
        observer=sources['observer'];clock=sources['clock_source'];clock_transport=getattr(clock.send,'__self__',None)
        need(isinstance(observer,FeatureObservation) and isinstance(clock_transport,FeatureObservation))
        for transport in (observer,clock_transport):
            previous=getattr(transport,'before_send',None)
            def final(previous=previous):
                bound()
                if previous is not None:need(callable(previous) and previous() is not False)
                bound()
            transport.before_send=final;transport.observe_process=guarded_process
        native=AssetsNativeInput.from_original(sources['native'],bound);native.observe_process=guarded_process
        bound()
        return dict(sources,check=bound,native=native,files=observer.assets_files(clock),replies=observer.assets_replies(clock))

    @operation
    def _assets_components(self,selector,run,role,fixture_url,lock):
        identifier(run);need(role in ('primary','actor'));sources=self._assets_sources(selector,lock)
        files=OwnedAssetsFiles(sources['files'],self._assets_store(selector,run,role,'files'),sources['binding'],run,fixture_url,lock=lock)
        picker=OwnedAssetsPicker(sources['native'],files,self._assets_store(selector,run,role,'picker'),sources['binding'],lock=lock,
            monotonic=self.monotonic,sleep=sources['observer'].sleep)
        replies=OwnedAssetsReplyReads(sources['replies'],self._assets_store(selector,run,role,'replies'),sources['binding'],run,fixture_url,lock=lock)
        sources['check']()
        return dict(sources,owned_files=files,picker=picker,owned_replies=replies)

    @operation
    def _assets_readback(self,selector,run,role,fixture_url,ticket,lock,*,resource='gltf-bundle/main.gltf',namespace='original'):
        """Actual independent server readback; never an upload success verdict."""
        bundle(run,ticket,fixture_url,resource);components=self._assets_components(selector,run,role,fixture_url,lock);owner=components['owned_replies']
        if owner.state is None:owner.reserve(ticket,resource,namespace)
        need(owner.state['phase']=='open' and owner.state['ticket']==ticket and owner.state['resource']==resource and owner.state['namespace']==namespace)
        result=owner.observe_bundle();owner.close();components['check']();return result
