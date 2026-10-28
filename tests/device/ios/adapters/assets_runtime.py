"""Assets owners on the canonical existing candidate/session/clock transport.

No session is created, no build is installed, and no feature is advertised.
The narrow bundle input/readback owner does not establish oven/model outcomes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
import hashlib
import re
from pathlib import Path
from adapters.asset_backend_client import AssetsBackendClient
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.asset_fixture import bundle
from feature_journeys.contract import identifier
from ios.adapters.assets_budget import check,operation
from ios.adapters.assets_files import OwnedAssetsFiles,original_bytes
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_baking_owner import OwnedAssetsBaking
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_parsed_sources import AssetsParsedSources
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters.assets_baked_tree import OwnedAssetsBakedTree,fresh_baseline
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.adapters.assets_peer_owner import OwnedAssetsPeer
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_image_sample import AssetsImageSample
from ios.adapters.create_marker_scope import CreateMarkerScope
from ios.adapters.assets_usage_controls import project as usage_controls
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
    def __init__(self,adapter,*,monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000):
        super().__init__(adapter);need(callable(monotonic) and callable(epoch_ms));self.monotonic,self.epoch_ms=monotonic,epoch_ms
        self.cleanup_errors=[] # Private diagnostics only; never feature facts.

    def _assets_store(self,selector,run,role,kind):
        identifier(run);need(role in ('primary','actor') and kind in ('files','picker','replies','upload','tree','backend','usage','baking','model','model-sources','parsed-sources','parsed','model-removal','baked-tree'))
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
        replies=OwnedAssetsReplyReads(sources['replies'],self._assets_store(selector,run,role,'replies'),sources['binding'],run,fixture_url,lock=lock,role=role)
        upload=OwnedAssetsUpload(sources['native'],sources['clock_source'],files,picker,replies,self._assets_store(selector,run,role,'upload'),
            sources['binding'],lock=lock,role=role,monotonic=self.monotonic,sleep=sources['observer'].sleep)
        tree=OwnedAssetsTree(upload,self._assets_store(selector,run,role,'tree'),lock=lock)
        usage=OwnedAssetsUsage(upload,self._assets_store(selector,run,role,'usage'),lock=lock)
        sources['check']()
        return dict(sources,owned_files=files,picker=picker,owned_replies=replies,upload=upload,tree=tree,usage=usage)

    @operation
    def _assets_baking_components(self,selector,run,role,fixture_url,lock,backend_config,*,parts=None):
        parts=self._assets_components(selector,run,role,fixture_url,lock) if parts is None else parts
        backend=OwnedAssetsBackend(parts['upload'],AssetsBackendClient(backend_config,parts['check']),self._assets_store(selector,run,role,'backend'),lock=lock)
        baking=OwnedAssetsBaking(parts['usage'],backend,self._assets_store(selector,run,role,'baking'),lock=lock)
        parts['check']();return dict(parts,backend=backend,baking=baking)

    @operation
    def _assets_model_components(self,selector,run,role,fixture_url,lock,*,parts=None):
        parts=self._assets_components(selector,run,role,fixture_url,lock) if parts is None else parts
        observer=parts['observer'];clock=parts['upload'].clock
        source=AssetsModelSources(parts['usage'],clock,observer.create_state(clock),observer.create_work(clock),self._assets_store(selector,run,role,'model-sources'),
            lock=lock,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        model=OwnedAssetsModel(parts['usage'],source,self._assets_store(selector,run,role,'model'),lock=lock)
        parts['check']();return dict(parts,model_sources=source,model=model)

    @operation
    def _assets_parsed_components(self,selector,run,role,fixture_url,lock,backend_config,*,parts=None):
        parts=self._assets_model_components(selector,run,role,fixture_url,lock,parts=parts) if parts is None or 'model' not in parts else parts
        if 'baking' not in parts:parts=self._assets_baking_components(selector,run,role,fixture_url,lock,backend_config,parts=parts)
        source=AssetsParsedSources(parts['model'],parts['observer'].assets_model_origin(parts['upload'].clock),self._assets_store(selector,run,role,'parsed-sources'),lock=lock)
        parsed=OwnedAssetsParsedInput(source,parts['baking'],self._assets_store(selector,run,role,'parsed'),lock=lock)
        parts['check']();return dict(parts,parsed_sources=source,parsed=parsed)

    @operation
    def _assets_model_removal_components(self,selector,run,role,fixture_url,lock,backend_config,*,parts=None):
        parts=self._assets_parsed_components(selector,run,role,fixture_url,lock,backend_config) if parts is None else parts
        removal=OwnedAssetsModelRemoval(parts['parsed'],self._assets_store(selector,run,role,'model-removal'),lock=lock)
        parts['check']();return dict(parts,model_removal=removal)

    @operation
    def _assets_baked_tree_components(self,selector,run,role,fixture_url,lock,backend_config,*,parts=None):
        parts=self._assets_parsed_components(selector,run,role,fixture_url,lock,backend_config) if parts is None else parts
        tree=OwnedAssetsBakedTree(parts['parsed'],self._assets_store(selector,run,role,'baked-tree'),lock=lock)
        parts['check']();return dict(parts,baked_tree=tree)

    @operation
    def _assets_scene_source(self,selector,run,role,lock):
        identifier(run);need(role in ('primary','actor','actor-primary'));parts=self._assets_sources(selector,lock)
        observer,clock=parts['observer'],parts['clock_source']
        source=AssetsSceneSources(PrivateFeatureState(self.state_path(selector).with_name('ios-assets-scene-'+run+'-'+role+'.json')),
            parts['binding'],run,role,lock,parts['check'],native=observer.bound_native_observer(clock),state=observer.create_state(clock),
            domain=observer.emote_world(clock),origin=observer.assets_model_origin(clock),epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        parts['check']();return dict(parts,scene=source)

    @operation
    def _assets_image_pool_source(self,selector,run,lock):
        """Construct the existing primary Pool/Storage/Source1 owner only.

        No reserve, capture, removal, pool/cache operation or retirement is
        implicit. The caller must hold this selected SDK's existing lock.
        """
        from ios.adapters.assets_image_pool_sources import AssetsImageReaderPoolSources
        identifier(run);parts=self._assets_sources(selector,lock)
        observer,clock=parts['observer'],parts['clock_source'];parts['check']()
        source=AssetsImageReaderPoolSources(
            PrivateFeatureState(self.state_path(selector).with_name('ios-assets-image-pool-'+run+'.json')),
            parts['binding'],run,lock,parts['check'],native=observer.bound_native_observer(clock),
            pool=observer.assets_image_reader_pool(clock),storage=observer.assets_image_reader_storage(clock),
            image_reader=observer.assets_image_reader(clock),epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        parts['check']();return dict(parts,image_pool_sources=source)

    @operation
    def _assets_peer_components(self,selector,primary_selector,run,fixture_url,lock,primary_lock,backend_config,*,primary_parts=None,primary_scene_parts=None,peer_scene_parts=None):
        primary_parts=self._assets_parsed_components(primary_selector,run,'primary',fixture_url,primary_lock,backend_config) if primary_parts is None else primary_parts
        primary_scene_parts=self._assets_scene_source(primary_selector,run,'actor-primary',primary_lock) if primary_scene_parts is None else primary_scene_parts
        peer_scene_parts=self._assets_scene_source(selector,run,'actor',lock) if peer_scene_parts is None else peer_scene_parts
        for parts in (primary_parts,primary_scene_parts,peer_scene_parts):need(parts['check']() is not False)
        owner=OwnedAssetsPeer(primary_parts['parsed'],primary_scene_parts['scene'],peer_scene_parts['scene'],
            PrivateFeatureState(self.state_path(selector).with_name('ios-assets-peer-'+run+'.json')),lock)
        for parts in (primary_parts,primary_scene_parts,peer_scene_parts):need(parts['check']() is not False)
        return dict(primary=primary_parts,primary_scene=primary_scene_parts,peer_scene=peer_scene_parts,peer=owner)

    @operation
    def _assets_marker_components(self,selector,run,role,fixture_url,ticket,artifact_root,lock):
        identifier(run);identifier(ticket);need(role in ('primary','actor'));parts=self._assets_sources(selector,lock)
        scope=CreateMarkerScope(self,selector,artifact_root,run,role,fixture_url,ticket,lock,namespace='assets',
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=parts['observer'].sleep)
        need(scope.binding==parts['binding']);marker=OwnedAssetsMarker(scope,
            PrivateFeatureState(self.state_path(selector).with_name('ios-assets-marker-'+run+'-'+role+'.json')))
        parts['check']();return dict(parts,marker_scope=scope,marker=marker)

    @operation
    def _assets_image_components(self,selector,run,fixture_url,ticket,artifact_root,lock,backend_config,request_id,*,parts=None,marker_parts=None):
        """Construct one primary image owner; no setup or capture is implicit."""
        identifier(run);identifier(ticket);need(type(request_id) is str and re.fullmatch('ios-[a-f0-9]{32}',request_id))
        root=Path(artifact_root);PrivateFeatureState(root/'assets-image-boundary.json')._parent()
        parts=self._assets_parsed_components(selector,run,'primary',fixture_url,lock,backend_config) if parts is None else parts
        marker_parts=self._assets_marker_components(selector,run,'primary',fixture_url,ticket,root,lock) if marker_parts is None else marker_parts
        need(parts['binding']==marker_parts['binding'] and marker_parts['marker'].scope.root==root)
        observer,clock=parts['observer'],parts['clock_source'];parts['check']();marker_parts['check']()
        frame=VulkanWorldFrameOwner(PrivateFeatureState(self.state_path(selector).with_name('graphics-world-frame-primary-0-'+request_id[4:]+'.json')),
            root,parts['binding'],run,'primary',0,request_id,observer.vulkan_world_frame,parts['check'],source_lock=lock,
            monotonic=self.monotonic,sleep=observer.sleep)
        sample=AssetsImageSample(PrivateFeatureState(self.state_path(selector).with_name('ios-assets-image-'+run+'-primary-'+request_id[4:]+'.json')),
            lock,parts['binding'],run,request_id,parts['check'],parsed=parts['parsed'],marker=marker_parts['marker'],native=observer.bound_native_observer(clock),
            state=observer.create_state(clock),models=observer.assets_model_renderers(clock),avatars=observer.avatar_renderers(clock),frame_owner=frame,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        parts['check']();marker_parts['check']();return dict(parts,image=sample,image_marker=marker_parts['marker'],image_frame=frame)

    @operation
    def _assets_upload_model_bytes(self,selector,run,role,fixture_url,ticket,lock,backend_config,*,parts=None):
        """Fresh ordinary FBX upload through parsed-output observation only.

        All mutating commands belong to the existing child WALs. An uncertain
        command is resolved from originals, never sent again. No Model/page,
        cache, server or full feature retirement is implied by this return.
        """
        parts=self._assets_parsed_components(selector,run,role,fixture_url,lock,backend_config) if parts is None else parts
        upload,backend,usage,baking,model,parsed=(parts[key] for key in ('upload','backend','usage','baking','model','parsed'))
        parts['check']()
        if backend.state is None or backend.state['phase']=='reserved':
            for _ in range(32):
                if backend.admit(ticket) is not None:break
                backend.sleep(.1)
            else:need(False)
        if upload.state is None:self._assets_prepare_upload(selector,run,role,fixture_url,ticket,lock,resource='asset-stand.fbx',parts=parts)
        need(upload.files.state['resource']=='asset-stand.fbx' and upload.files.state['ticket']==ticket)
        if backend.state['phase']=='baseline':backend.attach()
        if upload.state['phase'] in ('ready','review','destination'):
            # Reject already-owned/shared input hashes before the first upload
            # can itself trigger an implicit bake. This original baseline is
            # not a global actor lock or fresh permission proof at later inputs.
            digest=hashlib.sha256(original_bytes(next(iter(upload.files.state['files'].values())))).hexdigest()
            fresh_baseline(backend.packet(backend.state['samples'][backend.state['baseline']-1]),digest)
        if upload.state['phase'] in ('ready','review','destination','starting'):self._assets_finish_upload(upload)
        need(upload.state['phase']=='uploaded')
        if backend.state['uploadProof'] is None:self._assets_backend_checkpoint(backend,'uploaded-model-input',ticket);backend.uploaded('uploaded-model-input')
        if usage.state is None:usage.reserve()
        leaf=[entry for entry in usage.state['inputs'] if entry['slot']=='usage-select-1']
        if leaf:
            need(len(leaf)==1)
            if leaf[0]['resolvedBy'] is None:usage.resolve('usage-select-1')
        else:
            roots=[entry for entry in usage.state['inputs'] if entry['slot']=='usage-select-0']
            if roots and roots[0]['resolvedBy'] is None:usage.resolve('usage-select-0')
            usage.select()
        if baking.state is None or baking.state['phase']=='reserved':
            off=[entry for entry in usage.state['inputs'] if entry['slot']=='usage-bake-off']
            if not off:
                current=usage_controls(usage.capture(),upload.state['page'])
                if current['baking']['checked']:usage.baking(False)
            elif off[0]['resolvedBy'] is None:usage.resolve('usage-bake-off')
        if baking.state is None:baking.reserve()
        if baking.state['phase'] in ('reserved','baseline'):
            issued=any(entry['slot']=='usage-bake-on' and entry['command'] is not None for entry in usage.state['inputs'])
            if issued:baking.recover()
            else:
                for _ in range(8):
                    if baking.start() is not None:break
                    backend.sleep(.1)
                else:need(False)
        if baking.state['phase']=='issued':baking.recover()
        for _ in range(16):
            if baking.qualify() is not None:break
            backend.sleep(.1)
        else:need(False)
        if model.state is None:model.reserve()
        if model.state['phase'] in ('reserved','baseline'):
            accepted=any(entry['slot']=='usage-accept-model' and entry['command'] is not None for entry in usage.state['inputs'])
            model.recover() if accepted else model.start()
        if model.state['phase']=='issued':model.recover()
        if model.state['phase'] in ('issued','adopted'):
            for _ in range(16):
                if model.observe() is not None:break
                model.sources.readers['state'].sleep(.1)
            else:need(False)
        need(model.state['phase']=='geometry-observed')
        if parsed.state is None:parsed.reserve()
        result=parsed.observe();parts['check']();return result

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
