"""Separate normal FBX actions for shared upload18/off19/on20/import21.

All effects still belong to the existing normal child WALs and independent
backend/geometry originals. This mixin never advances a shared journey phase,
imports during an image checkpoint, retires a page, or claims whole completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from adapters.native_feature_observation import need
from ios.adapters.assets_action_owners import ActionAssetsBaking,ActionAssetsParsed
from ios.adapters.assets_baked_tree import fresh_baseline
from ios.adapters.assets_budget import operation
from ios.adapters.assets_files import original_bytes
from ios.adapters.assets_usage_controls import project as usage_controls


class AssetsStageRecipes:
    def _assets_stage_upload_components(self,*args,**kwargs):return self._assets_baking_components(*args,**kwargs)
    def _assets_stage_select(self,parts):
        usage=parts['usage']
        if usage.state is None:usage.reserve()
        leaf=[entry for entry in usage.state['inputs'] if entry['slot']=='usage-select-1']
        if leaf:
            need(len(leaf)==1)
            if leaf[0]['resolvedBy'] is None:usage.resolve('usage-select-1')
        else:
            roots=[entry for entry in usage.state['inputs'] if entry['slot']=='usage-select-0']
            if roots and roots[0]['resolvedBy'] is None:usage.resolve('usage-select-0')
            usage.select()
        return usage
    @operation
    def _assets_stage_fbx_upload(self,selector,run,role,fixture_url,ticket,lock,backend_config,*,parts=None):
        parts=self._assets_stage_upload_components(selector,run,role,fixture_url,lock,backend_config) if parts is None else parts
        upload,backend,usage=(parts[key] for key in ('upload','backend','usage'));parts['check']()
        need(usage.state is None and ('model' not in parts or parts['model'].state is None))
        if backend.state is None or backend.state['phase']=='reserved':
            for _ in range(32):
                if backend.admit(ticket) is not None:break
                backend.sleep(.1)
            else:need(False)
        if upload.state is None:self._assets_prepare_upload(selector,run,role,fixture_url,ticket,lock,resource='asset-stand.fbx',parts=parts)
        need(upload.files.state['resource']=='asset-stand.fbx' and upload.files.state['ticket']==ticket)
        if backend.state['phase']=='baseline':backend.attach()
        if upload.state['phase'] in ('ready','review','destination'):
            digest=hashlib.sha256(original_bytes(next(iter(upload.files.state['files'].values())))).hexdigest()
            fresh_baseline(backend.packet(backend.state['samples'][backend.state['baseline']-1]),digest)
        if upload.state['phase'] in ('ready','review','destination','starting'):self._assets_finish_upload(upload)
        need(upload.state['phase']=='uploaded')
        if backend.state['uploadProof'] is None:self._assets_backend_checkpoint(backend,'uploaded-model-input',ticket);backend.uploaded('uploaded-model-input')
        parts['check']();return parts
    @operation
    def _assets_stage_baking_off(self,parts):
        parts['check']();usage=self._assets_stage_select(parts);need('model' not in parts or parts['model'].state is None)
        need(not any(entry['slot']=='usage-bake-on' for entry in usage.state['inputs']))
        off=[entry for entry in usage.state['inputs'] if entry['slot']=='usage-bake-off']
        if off:
            need(len(off)==1)
            if off[0]['resolvedBy'] is None:usage.resolve('usage-bake-off')
        else:
            current=usage_controls(usage.capture(),parts['upload'].state['page'])
            if current['baking']['checked']:usage.baking(False)
        current=usage_controls(usage.capture(),parts['upload'].state['page'])
        need(current['baking']['enabled'] and not current['baking']['checked'] and not current['model']['visible'])
        parts['check']();return current
    @operation
    def _assets_stage_baking_on(self,parts,ticket):
        parts['check']();usage,backend=parts['usage'],parts['backend'];need(usage.state is not None and ('model' not in parts or parts['model'].state is None))
        old=parts['baking']
        if not isinstance(old,ActionAssetsBaking):
            need(old.state is None and old.store.read() is None)
            parts['baking']=ActionAssetsBaking(usage,backend,old.store,lock=old.lock,action_ticket=ticket)
        baking=parts['baking'];need(baking.ticket()==ticket)
        issued=any(entry['slot']=='usage-bake-on' and entry['command'] is not None for entry in usage.state['inputs'])
        if not issued:
            current=usage_controls(usage.capture(),parts['upload'].state['page'])
            need(current['baking']['enabled'] and not current['baking']['checked'] and not current['model']['visible'])
        if baking.state is None:baking.reserve()
        if baking.state['phase'] in ('reserved','baseline'):
            if issued:baking.recover()
            else:
                for _ in range(8):
                    if baking.start() is not None:break
                    backend.sleep(.1)
                else:need(False)
        if baking.state['phase']=='issued':baking.recover()
        for _ in range(16):
            result=baking.qualify()
            if result is not None:break
            backend.sleep(.1)
        else:need(False)
        current=usage_controls(usage.capture(),parts['upload'].state['page'])
        need(current['baking']['enabled'] and current['baking']['checked'] and not current['model']['visible'])
        parts['check']();return result
    @operation
    def _assets_stage_import_baked(self,parts,ticket):
        parts['check']();need(isinstance(parts['baking'],ActionAssetsBaking) and parts['baking'].state['phase']=='qualified')
        model=parts['model'];old=parts['parsed']
        if not isinstance(old,ActionAssetsParsed):
            need(old.state is None and old.store.read() is None)
            parts['parsed']=ActionAssetsParsed(old.sources,parts['baking'],old.store,lock=old.lock,action_ticket=ticket)
        parsed=parts['parsed'];need(parsed.ticket()==ticket and parsed.baking is parts['baking'] and parsed.model is model)
        if model.state is None:model.reserve()
        if model.state['phase'] in ('reserved','baseline'):
            accepted=any(entry['slot']=='usage-accept-model' and entry['command'] is not None for entry in parts['usage'].state['inputs'])
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
