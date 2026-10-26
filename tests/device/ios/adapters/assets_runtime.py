"""Assets owners on the canonical existing candidate/session/clock transport.

No session is created, no build is installed, and no feature is advertised.
The narrow bundle input/readback owner does not establish oven/model outcomes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.asset_backend_client import AssetsBackendClient
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.asset_fixture import bundle
from feature_journeys.contract import identifier
from ios.adapters.assets_budget import check,operation
from ios.adapters.assets_files import OwnedAssetsFiles
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
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
            check();need(self.assets_guard() is not False)
            if before_send is not None and before_send() is False:return False
            check();need(self.assets_guard() is not False)
        return super()._request(operation,native,before_send=final_guard)


class IOSAssetsRuntime(IOSScriptRuntime):
    def __init__(self,adapter,*,monotonic=time.monotonic):
        super().__init__(adapter);need(callable(monotonic));self.monotonic=monotonic
        self.cleanup_errors=[] # Private diagnostics only; never feature facts.

    def _assets_store(self,selector,run,role,kind):
        identifier(run);need(role in ('primary','actor') and kind in ('files','picker','replies','upload','tree','backend','usage'))
        return PrivateFeatureState(self.state_path(selector).with_name('ios-assets-'+run+'-'+role+'-'+kind+'.json'))

    @operation
    def _assets_sources(self,selector,lock):
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'));lock.assert_held()
        check();sources=super()._sources(selector);check();original_check=sources['check']
        def bound():
            check();lock.assert_held();need(original_check() is not False);check()
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
        files=OwnedAssetsFiles(sources['files'],self._assets_store(selector,run,role,'files'),sources['binding'],run,fixture_url,lock=lock,role=role)
        picker=OwnedAssetsPicker(sources['native'],files,self._assets_store(selector,run,role,'picker'),sources['binding'],lock=lock,
            monotonic=self.monotonic,sleep=sources['observer'].sleep)
        replies=OwnedAssetsReplyReads(sources['replies'],self._assets_store(selector,run,role,'replies'),sources['binding'],run,fixture_url,lock=lock)
        upload=OwnedAssetsUpload(sources['native'],sources['clock_source'],files,picker,replies,self._assets_store(selector,run,role,'upload'),
            sources['binding'],lock=lock,role=role,monotonic=self.monotonic,sleep=sources['observer'].sleep)
        tree=OwnedAssetsTree(upload,self._assets_store(selector,run,role,'tree'),lock=lock)
        usage=OwnedAssetsUsage(upload,self._assets_store(selector,run,role,'usage'),lock=lock)
        sources['check']()
        return dict(sources,owned_files=files,picker=picker,owned_replies=replies,upload=upload,tree=tree,usage=usage)

    @operation
    def _assets_mapping_readback(self,selector,run,role,fixture_url,ticket,lock,*,resource='gltf-bundle/main.gltf'):
        """Ordinary mapping lifecycle only; server/oven/blob cleanup stays owned."""
        parts=self._assets_prepare_upload(selector,run,role,fixture_url,ticket,lock,resource=resource);owner,tree=parts['upload'],parts['tree']
        try:
            self._assets_finish_upload(owner)
            if tree.state is None:tree.reserve()
            if tree.state['phase']=='reserved':tree.browse()
            if tree.state['phase']=='browsed':tree.rename()
            if tree.state['phase']=='renaming':tree.finish_rename()
            if tree.state['phase']=='renamed':tree.delete()
            if tree.state['phase']=='deleting':tree.finish_delete()
            need(tree.state['phase']=='deleted');result=tree.read_proof('tree-deleted');tree.close_clients()
        except BaseException:
            try:tree.close_clients() if tree.state is not None else owner.cleanup(abort=True)
            except BaseException as cleanup_error:self.cleanup_errors.append(cleanup_error)
            raise
        parts['check']();return result

    @operation
    def _assets_upload_readback(self,selector,run,role,fixture_url,ticket,lock,*,resource='gltf-bundle/main.gltf'):
        """Ordinary rendered input and independent reads; no whole-feature verdict."""
        parts=self._assets_prepare_upload(selector,run,role,fixture_url,ticket,lock,resource=resource);owner=parts['upload']
        try:
            self._assets_finish_upload(owner);result=owner.readback_proof(owner.state);owner.cleanup()
        except BaseException:
            # Each issued mutation remains in its own WAL. Cleanup observes
            # those originals and never repeats uncertain input or release.
            try:owner.cleanup(abort=True)
            except BaseException as cleanup_error:self.cleanup_errors.append(cleanup_error)
            raise
        parts['check']();return result

    @operation
    def _assets_mapping_with_backend(self,selector,run,role,fixture_url,ticket,lock,backend_config,*,resource='gltf-bundle/main.gltf'):
        """Ordinary mapping vertical with independently owned backend cleanup.

        This internal source path advertises no feature. Baked model consumers,
        normal bake controls and the complete Assets coordinator remain open.
        """
        parts=self._assets_components(selector,run,role,fixture_url,lock);upload,tree=parts['upload'],parts['tree']
        backend=OwnedAssetsBackend(upload,AssetsBackendClient(backend_config,parts['check']),self._assets_store(selector,run,role,'backend'),lock=lock)
        if backend.state is not None and backend.state['phase']=='restored':
            need(tree.state is not None and tree.state['phase']=='deleted' and tree.state['clientClosedBy'] is not None);parts['check']();return backend.state['restoration']['proof']
        try:
            if backend.state is None or backend.state['phase']=='reserved':
                for _ in range(32):
                    if backend.admit(ticket) is not None:break
                    backend.sleep(.1)
                else:need(False)
            if upload.state is None:self._assets_prepare_upload(selector,run,role,fixture_url,ticket,lock,resource=resource,parts=parts)
            if backend.state['phase']=='baseline':backend.attach()
            if upload.state['phase'] in ('ready','review','destination','starting'):self._assets_finish_upload(upload)
            if upload.state['phase']=='uploaded':
                if backend.state['uploadProof'] is None:
                    self._assets_backend_checkpoint(backend,'uploaded',ticket);backend.uploaded('uploaded')
                if tree.state is None:tree.reserve()
                if tree.state['phase']=='reserved':tree.finish_browse() if tree.state['reads'] else tree.browse()
                if tree.state['phase']=='browsed':tree.rename()
                if tree.state['phase']=='renaming':tree.finish_rename()
                if tree.state['phase']=='renamed':tree.delete()
                if tree.state['phase']=='deleting':tree.finish_delete()
            need(tree.state is not None and tree.state['phase']=='deleted');tree.close_clients()
            first=None
            for index in range(24):
                slot='restoration-'+str(index);packet=self._assets_backend_checkpoint(backend,slot,ticket)
                if backend.quiescent_baseline(packet):
                    if first is not None:
                        proof=backend.restore(first,slot)
                        if proof is not None:parts['check']();return proof
                        # A later already-returned job still interrupts quiet.
                        previous=next(row for row in backend.state['samples'] if row['slot']==first)
                        if backend.packet(previous)['source']['workAfter']['jobs']!=packet['source']['workBefore']['jobs']:first=slot
                    else:first=slot
                else:first=None
                backend.sleep(.2)
            need(False)
        except BaseException:
            try:
                if upload.state is not None:tree.close_clients() if tree.state is not None else upload.cleanup(abort=True)
            except BaseException as cleanup_error:self.cleanup_errors.append(cleanup_error)
            raise

    def _assets_backend_checkpoint(self,backend,slot,ticket):
        for _ in range(32):
            packet=backend.checkpoint(slot,ticket)
            if packet is not None:return packet
            backend.sleep(.1)
        need(False)

    def _assets_finish_upload(self,owner):
        if owner.state['phase']=='ready':owner.review()
        if owner.state['phase']=='review':owner.destination()
        if owner.state['phase']=='destination':owner.start_upload()
        if owner.state['phase']=='starting':owner.uploaded()
        need(owner.state['phase']=='uploaded')

    def _assets_prepare_upload(self,selector,run,role,fixture_url,ticket,lock,*,resource,parts=None):
        bundle(run,ticket,fixture_url,resource);parts=self._assets_components(selector,run,role,fixture_url,lock) if parts is None else parts
        files,picker,replies,owner=parts['owned_files'],parts['picker'],parts['owned_replies'],parts['upload']
        if files.state is None:files.reserve(ticket,resource)
        need(files.state['ticket']==ticket and files.state['resource']==resource)
        if files.state['phase']=='reserved':files.stage()
        elif files.state['phase']=='staging':files.recover_stage()
        need(files.state['phase']=='staged')
        if picker.state is None:picker.reserve()
        if picker.state['phase']=='reserved':picker.open_page()
        if picker.state['phase']=='page-open':picker.open_picker()
        if picker.state['phase']=='picker-open':picker.choose_primary()
        need(picker.state['phase']=='primary-chosen')
        if replies.state is None:replies.reserve(ticket,resource)
        need(replies.state['phase']=='open' and replies.state['ticket']==ticket and replies.state['resource']==resource and replies.state['namespace']=='original')
        if owner.state is None:owner.reserve()
        return parts

    @operation
    def _assets_readback(self,selector,run,role,fixture_url,ticket,lock,*,resource='gltf-bundle/main.gltf',namespace='original'):
        """Actual independent server readback; never an upload success verdict."""
        bundle(run,ticket,fixture_url,resource);components=self._assets_components(selector,run,role,fixture_url,lock);owner=components['owned_replies']
        if owner.state is None:owner.reserve(ticket,resource,namespace)
        need(owner.state['phase']=='open' and owner.state['ticket']==ticket and owner.state['resource']==resource and owner.state['namespace']==namespace)
        try:result=owner.observe_bundle()
        except BaseException:
            # A failed/uncertain read owns its exact issued job. Observe and
            # retire that lease through the ordinary owner, never repeat its
            # start or cancel. A secondary failure cannot hide the primary
            # exception or erase the durable unresolved responsibility.
            try:owner.close()
            except BaseException as cleanup_error:self.cleanup_errors.append(cleanup_error)
            raise
        owner.close();components['check']();return result
