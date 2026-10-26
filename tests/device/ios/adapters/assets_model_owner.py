"""Pre-accept native baseline and actual imported UUID ownership.

Loaded wrapper flags are observed separately. Resource origin/consumption,
rendering, peer publication and full resource retirement remain unavailable.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,pack,unpack
from ios.adapters import assets_model_facts as facts
from ios.adapters.assets_budget import operation
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_usage_controls import project as usage_page
from ios.adapters.assets_usage_owner import OwnedAssetsUsage

VERSION=1
SLOT='usage-accept-model'


class OwnedAssetsModel:
    def __init__(self,usage,sources,store,*,lock):
        need(isinstance(usage,OwnedAssetsUsage) and isinstance(sources,AssetsModelSources) and sources.usage is usage and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.usage,self.sources,self.store,self.lock=usage,sources,store,lock;self.monotonic=sources.monotonic;self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.sources.guard();need(all(same(owner.store.read(),owner.previous) for owner in (self,self.usage,self.sources)));return True

    def frame(self,index):need(integer(index,1,len(self.sources._cached)));return self.sources._cached[index-1]
    def native(self,index):return self.frame(index)['originals']['createAfter']

    def input(self):
        entries=[entry for entry in self.usage.state['inputs'] if entry['slot']==SLOT];need(len(entries)==1 and entries[0]['id']=='assets.model.accept');return entries[0]

    def decode(self,value):
        source=self.usage.source;exact(value,{'iosAssetsModelOwnerVersion','binding','runId','role','fileOwnerToken','page','path','payload'})
        need(type(value['iosAssetsModelOwnerVersion']) is int and value['iosAssetsModelOwnerVersion']==VERSION and same(value['binding'],source.binding)
            and value['runId']==source.files.run and value['role']==source.role and value['fileOwnerToken']==source.files.state['token'] and value['page']==source.state['page'] and value['path']==self.usage.path())
        states=unpack(value['payload']);need(len(states)==1);state=states[0];exact(state,{'phase','baseline','observations','creation','geometryObserved'})
        need(state['phase'] in ('reserved','baseline','issued','adopted','geometry-observed') and type(state['observations']) is list and len(state['observations'])<=16
            and state['observations']==sorted(set(state['observations'])))
        if state['baseline'] is not None:
            frame=self.frame(state['baseline']);page=usage_page(frame['originals']['ui'],source.state['page'])
            need(page['model']['visible'] and page['model']['url']==self.usage.url() and page['model']['shapeIndex']==2 and not page['model']['dynamicChecked'])
        else:need(state['phase']=='reserved' and not state['observations'] and state['creation'] is None and state['geometryObserved'] is None)
        if state['phase']!='reserved':need(state['baseline'] is not None)
        for index in state['observations']:need(integer(index,state['baseline']+1,len(self.sources._cached)))
        if state['phase'] in ('issued','adopted','geometry-observed'):need(self.input()['command'] is not None)
        if state['creation'] is not None:
            exact(state['creation'],{'frame','proof'});need(state['creation']['frame'] in state['observations'] and self.input()['resolvedBy'] is not None)
            actual=facts.imported(self.usage,self.native(state['baseline']),self.native(state['creation']['frame']));need(same(actual,state['creation']['proof']))
        if state['phase'] in ('adopted','geometry-observed'):need(state['creation'] is not None)
        if state['geometryObserved'] is not None:
            exact(state['geometryObserved'],{'frame','observation'});need(state['creation'] is not None and state['geometryObserved']['frame'] in state['observations'])
            actual=facts.geometry(self.usage,self.native(state['baseline']),self.native(state['creation']['frame']),self.native(state['geometryObserved']['frame']));need(same(actual,state['geometryObserved']['observation']))
        if state['phase']=='geometry-observed':need(state['geometryObserved'] is not None)
        return state

    def save(self):
        self.guard();source=self.usage.source
        value=dict(iosAssetsModelOwnerVersion=VERSION,binding=source.binding,runId=source.files.run,role=source.role,fileOwnerToken=source.files.state['token'],page=source.state['page'],path=self.usage.path(),payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    @operation
    def reserve(self):
        need(self.state is None and self.usage.state is not None and self.usage.state['clientClosedBy'] is None)
        self.state=dict(phase='reserved',baseline=None,observations=[],creation=None,geometryObserved=None);self.save()

    def capture(self):
        if self.sources.state is None:self.sources.reserve()
        if self.sources.state['pending'] is not None:return self.sources.recover_capture()
        return self.sources.capture(self.sources.epoch_ms())

    @operation
    def start(self):
        need(self.state['phase'] in ('reserved','baseline') and not any(entry['slot']==SLOT for entry in self.usage.state['inputs']))
        opened=[entry for entry in self.usage.state['inputs'] if entry['slot']=='usage-open-model']
        if not opened:self.usage.open_model()
        else:
            need(len(opened)==1)
            if opened[0]['resolvedBy'] is None:self.usage.resolve('usage-open-model')
        self.capture();self.state.update(phase='baseline',baseline=len(self.sources.state['frames']));self.save()
        try:packet=self.usage.accept_model()
        except BaseException as primary:
            matches=[entry for entry in self.usage.state['inputs'] if entry['slot']==SLOT]
            if matches and matches[0]['command'] is not None:
                self.state['phase']='issued'
                try:self.save()
                except BaseException as secondary:primary.add_note('Retaining the issued model parent also failed: '+type(secondary).__name__)
            raise
        self.state['phase']='issued';self.save();return packet

    @operation
    def recover(self):
        need(self.state['phase'] in ('baseline','issued') and self.input()['command'] is not None)
        if self.input()['resolvedBy'] is None:self.usage.resolve(SLOT)
        self.state['phase']='issued';self.save()

    @operation
    def observe(self):
        self.guard();need(self.state['phase'] in ('issued','adopted','geometry-observed') and self.input()['resolvedBy'] is not None and len(self.state['observations'])<16)
        self.capture();index=len(self.sources.state['frames']);need(index not in self.state['observations']);self.state['observations'].append(index);self.save()
        if self.state['creation'] is None:
            proof=facts.imported(self.usage,self.native(self.state['baseline']),self.native(index));self.state.update(phase='adopted',creation=dict(frame=index,proof=proof));self.save()
        before=self.native(self.state['baseline']);created=self.native(self.state['creation']['frame']);current=self.native(index)
        row=next(item for item in current['source']['entities'] if item['id']==self.state['creation']['proof']['entityId']);model=row['model']
        if not (model['present'] and model['loaded'] and model['addedToScene'] and not model['failed']):return None
        observed=facts.geometry(self.usage,before,created,current);self.state.update(phase='geometry-observed',geometryObserved=dict(frame=index,observation=observed));self.save();return deepcopy(observed)
