"""Original consumed world attempt joined to the actual normal Pico X owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_world import PicoLifecycleWorld
from adapters.pico4.lifecycle_back import PicoLifecycleBack,validate_history
from adapters.pico4 import lifecycle_source as ui
from adapters.script_journey.history import pack,unpack

VERSION=1


class PicoLifecycleXJoin:
    def __init__(self,world,back,path):
        need(isinstance(world,PicoLifecycleWorld) and isinstance(back,PicoLifecycleBack)
            and back.source_lock is world.lock and world.run==back.run and world.binding==back.binding and world.pid==back.source.pid)
        self.world,self.back,self.store=world,back,PrivateFeatureState(path)
        need(self.store.path==world.store.path.with_name('lifecycle-x-join.json')
            and back.store.path==world.store.path.with_name('lifecycle-x-back-owner.json'))
        self.disk=self.state=None
        with world.lock.held():self.load()

    def original(self):
        state=self.world.state;need(state is not None and 1<=len(state['attempts'])<=2 and state['attempts'][0]['phase']=='quiet')
        before=self.world.originals(state['frames'][state['attempts'][0]['before']])['ui']
        selected=ui.current_editor(before);need(selected is not None and selected['kind']=='create');return selected['id']

    def validate(self,value):
        LifecycleXHistory(self.world,self.world.session.profile,self.back.store.read()).validate(value)

    def load(self):
        self.world.lock.assert_held();self.world.load();self.world.now();disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecycleXJoinVersion','runId','binding','payload'})
        need(type(disk['lifecycleXJoinVersion']) is int and disk['lifecycleXJoinVersion']==VERSION
            and disk['runId']==self.world.run and disk['binding']==self.world.binding)
        payload=unpack(disk['payload']);need(len(payload)==1);self.validate(payload[0])
        self.disk,self.state=deepcopy(disk),deepcopy(payload[0])

    def save(self,state):
        self.world.lock.assert_held();need(self.store.read()==self.disk)
        self.validate(state)
        disk=dict(lifecycleXJoinVersion=VERSION,runId=self.world.run,binding=self.world.binding,payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)

    def finish(self,reconcile):
        # The normal X owner itself journals its exact physical-button envelope
        # before transport. An existing reservation never creates another press.
        need(self.state is not None)
        if reconcile:
            need(self.back.state is not None and self.back.state['originalId']==self.state['originalId']);self.back.reconcile()
        else:
            need(self.back.state is None);self.back.back(original_id=self.state['originalId'])
        packets=self.world.current();state=deepcopy(self.state)
        state.update(phase='observed',after=deepcopy(self.world.state['frames'][-1]),backOwner=deepcopy(self.back.disk));self.save(state)
        result=self.world.report(packets,len(self.world.attempts(self.world.state,packets['gesture'])))
        row=PicoLifecycleBack.home(packets['ui'],state['originalId'])
        result['back']=dict(routeObserved=True,originalId=state['originalId'],editorRetired=PicoLifecycleBack.retired(packets['ui'],state['originalId']),
            retainedContext=row['contextAlive'])
        self.world.now();self.world.fresh_current();return result

    def back_once(self):
        try:
            with self.world.lock.held():
                self.load();need(self.state is None and len(self.world.state['attempts'])==1);original=self.original();packets=self.world.current()
                self.world.editor_gate(packets['ui'],0);need(ui.current_editor(packets['ui'])['id']==original)
                self.save(dict(phase='reserved',originalId=original,before=deepcopy(self.world.state['frames'][-1]),after=None,backOwner=None))
                self.world.now();self.world.fresh_current();return self.finish(False)
        except Exception:raise NativeUIError('Pico lifecycle X join unresolved; original input ownership retained') from None

    def reconcile(self):
        try:
            with self.world.lock.held():self.load();return self.finish(True)
        except Exception:raise NativeUIError('Pico lifecycle X reconciliation unresolved; no button repeated') from None


class LifecycleXHistory:
    """Original X↔World history validation without live observers or input."""
    original=PicoLifecycleXJoin.original

    def __init__(self,world,profile,back_owner):
        self.world,self.profile,self.back_owner=world,profile,deepcopy(back_owner)

    def validate(self,value):
        exact(value,{'phase','originalId','before','after','backOwner'})
        need(value['phase'] in ('reserved','observed') and ui.nonce(value['originalId']) and value['originalId']==self.original())
        need(sum(row==value['before'] for row in self.world.state['frames'])==1)
        before=self.world.originals(value['before'])['ui'];self.world.editor_gate(before,0)
        need(ui.current_editor(before)['id']==value['originalId'])
        if value['phase']=='reserved':need(value['after'] is None and value['backOwner'] is None);return
        need(sum(row==value['after'] for row in self.world.state['frames'])==1)
        current=self.world.originals(value['after'])['ui']
        back,previous=validate_history(value['backOwner'],self.world.run,self.world.binding,self.world.pid,self.profile)
        need(back['phase'] in ('retained','released') and back['originalId']==value['originalId'])
        from adapters.native_feature_observation import decode
        back_before=decode(back['frames'][0]['raw'])
        ui.accept(ui.summary(before),ui.summary(back_before));ui.accept(previous,ui.summary(current))
        PicoLifecycleBack.home(current,value['originalId'])
        need(value['backOwner']==self.back_owner)
