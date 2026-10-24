"""Private Lifecycle normal-operation prefix over the unchanged v16 recipe.

No peer, artifact, cleanup, public capability or cold input replay is granted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_input_fence import PhaseInputFence
from feature_journeys.contract import arguments,result,typed_equal,VERSION as CONTRACT
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhaseFixtureReader,validate
from feature_journeys.scenarios import SCENARIOS,expand

VERSION=1


def phase(owner):
    """Only the exact live coordinator may add an optional owner fence."""
    value=getattr(owner,'phase_fence',None)
    if value is not None:need(type(value) is LifecycleInputFence and value.owns(owner))
    return value


class LifecycleInputFence(PhaseInputFence):
    def __init__(self,owner):
        need(type(owner) is PicoLifecycleOperations)
        self.owner=owner
        super().__init__(owner.phases)

    def owns(self,owner):
        return owner is self.owner.source.editor or owner is self.owner.source.world or owner is self.owner.source.restore.joined.back

    def original(self):
        self.owner.bound(saved=True);need(not self.owner.failed and self.owner.state['steps'])
        row=self.owner.state['steps'][-1];need(row['phase']=='issued')
        return self.owner.original(row['before'])

    def read(self,expected):
        packet,now,epoch=super().read(expected)
        self.owner.archive(packet)
        # The original phase cannot age unnoticed during its durable write.
        completed=self.source.monotonic();final=self.source.epoch_ms()
        need(0<=completed-now<=1.5 and 0<=final-epoch<=1500)
        validate(packet,run=self.source.run,area=self.source.area,request=packet['requestId'],epoch=final,previous=expected)
        return packet,completed,final


class PicoLifecycleOperations:
    """One live primary graph; first four ordinary recipe actions only.

    This deliberately has no execute/witness or cleanup substitute. Retained
    parent intent makes a failed call terminal; it never resends that input.
    """
    def __init__(self,source,phases,path):
        from adapters.pico4.lifecycle_observation import PicoLifecycleObservation
        need(type(source) is PicoLifecycleObservation and source.version==3
            and type(phases) is PhaseFixtureReader and phases.area=='lifecycle-input' and phases.run==source.run)
        self.source,self.phases,self.lock=source,phases,source.lock
        self.original_phases=phases
        self.store=PrivateFeatureState(path)
        need(self.store.path==source.world.store.path.with_name('lifecycle-primary-operations.json'))
        self.scope=dict(lifecyclePrimaryOperationsVersion=VERSION,contractVersion=CONTRACT,runId=source.run,
            binding=deepcopy(source.binding),fixtureUrl=phases.fixture_url)
        self.disk=None;self.failed=False
        self.state=dict(**self.scope,phase='reading',chunks=[],bundles=[],baseline=None,steps=[])
        self.history=ChatSourceChunks(self.store,self.scope)
        with self.lock.held():
            need(self.store.read() is None)
            # Missing parent plus retained children is unresolved ownership.
            self.history.load([])
            self.save()
            self.fence=LifecycleInputFence(self)
            for owner in (source.editor,source.world,source.restore.joined.back):
                need(getattr(owner,'phase_fence',None) is None)

    def bound(self,*,saved=False):
        self.lock.assert_held();need(not self.failed and not self.source.failed
            and self.source.run==self.scope['runId'] and typed_equal(self.source.binding,self.scope['binding'])
            and self.source.lock is self.lock and typed_equal(self.store.read(),self.disk)
            and json_digest(self.scope)==self.history.scope and self.phases is self.original_phases
            and self.phases.run==self.source.run and self.phases.area=='lifecycle-input'
            and self.phases.fixture_url==self.scope['fixtureUrl']
            and self.phases.client.url+'/runs/'+self.source.run+'/'==self.scope['fixtureUrl'])
        if saved:need(typed_equal(self.state,self.disk))
        self.history.verify()

    def save(self):
        self.bound();value=deepcopy(self.state)
        self.store.write(value,self.disk);need(typed_equal(self.store.read(),value));self.disk=value

    def archive(self,packet):
        self.bound()
        index,parts=source_bundles.prepare(packet,len(self.state['bundles']),self.state['bundles'])
        for part in parts:
            self.state['chunks']=self.history.append(part,self.state['chunks']);self.save()
        self.state['bundles'].append(index);self.save()
        return len(self.state['bundles'])-1

    def original(self,index):
        self.bound()
        value,_=source_bundles.original(self.history,self.state['chunks'],self.state['bundles'],index)
        return value

    def baseline(self):
        self.bound();need(not self.state['steps'])
        previous=None if self.state['baseline'] is None else self.original(self.state['baseline'])
        current=self.phases.read(previous);packet=current['status']
        need(len(packet['activations'])==1 and current['verb']=='baseline' and current['inputs']=={})
        self.state['baseline']=self.archive(packet);self.save()

    def invoke(self,operation,fields):
        arguments(operation,fields);need(fields['runId']==self.scope['runId'])
        need(operation in ('feature.lifecycle-input.act','feature.lifecycle-input.observe'))
        try:
            with self.lock.held():
                self.bound(saved=True)
                if operation.endswith('.observe'):
                    if not self.state['steps']:
                        self.baseline();previous=self.original(self.state['baseline'])
                    else:
                        need(self.state['steps'][-1]['phase']=='returned')
                        previous=self.original(self.state['steps'][-1]['after'])
                        current=self.phases.read(previous)
                        need(typed_equal(current['status']['activations'],previous['activations']))
                        self.archive(current['status'])
                    observed=self.source.read(after_sequence=fields['afterSequence'])
                    confirmed=self.phases.read(previous)
                    need(typed_equal(confirmed['status']['activations'],previous['activations']))
                    self.archive(confirmed['status']);self.source.fresh()
                    # All physical parent writes precede Source3's final clock
                    # and real lock-exit check; no old packet becomes current.
                else:observed=self.act(fields)
            if operation.endswith('.observe'):self.source.fresh()
            else:
                self.source.bound()
                packet,started,epoch=self.delivery
                completed=self.phases.monotonic();final=self.phases.epoch_ms()
                need(0<=completed-started<=1.5 and 0<=final-epoch<=1500)
                validate(packet,run=self.source.run,area=self.phases.area,request=packet['requestId'],epoch=final)
            return observed
        except Exception:
            self.failed=True
            raise NativeUIError('Lifecycle primary operation unresolved; original intent retained, no input repeated') from None

    def act(self,fields):
        self.bound();index=len(self.state['steps'])
        need(index<4 and self.state['baseline'] is not None and self.source.disk is not None
            and (index==0 or self.state['steps'][-1]['phase']=='returned'))
        expected=SCENARIOS['lifecycle-input']['steps'][index]
        need(fields['verb']==expected['verb'] and typed_equal(fields['inputs'],expand(expected['inputs'],context(self.source.run))))
        previous=self.original(self.state['baseline'] if index==0 else self.state['steps'][-1]['after'])
        current=self.phases.read(previous);packet=current['status']
        need(fields['fixtureUrl']==self.scope['fixtureUrl'] and fields['ticket']==current['ticket']
            and len(packet['activations'])==index+2 and current['verb']==fields['verb']
            and typed_equal(current['inputs'],fields['inputs']))
        before=self.archive(packet)
        self.state['steps'].append(dict(verb=fields['verb'],inputs=deepcopy(fields['inputs']),ticket=current['ticket'],
            phase='issued',before=before,after=None));self.save()
        if index==0:
            self.source.editor.bind_phase_fence(self.fence)
            self.source.world.phase_fence=self.source.restore.joined.back.phase_fence=self.fence
        self.dispatch(index)
        after=self.phases.read(packet)
        need(typed_equal(after['status']['activations'],packet['activations']))
        self.delivery=deepcopy(after['status']),self.phases.monotonic(),self.phases.epoch_ms()
        original=self.archive(after['status'])
        self.state['steps'][-1].update(phase='returned',after=original);self.save()
        return result('feature.lifecycle-input.act',dict(performed=True))

    def dispatch(self,index):
        editor,world,joined=self.source.editor,self.source.world,self.source.restore.joined
        if index==0:
            editor.tablet();editor.open_create();editor.focus_create()
        elif index==1:editor.type_create()
        elif index==2:world.world_input(editor_id=editor.state['originalId']);world.release()
        elif index==3:joined.back_once()
        else:need(False)
