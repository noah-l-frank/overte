"""The same fourteen normal Audio stages with an independently armed PC owner.

Digital recorder retirement is scoped separately. Product history, Qt/native
capacity, physical acoustics and complete Common16 cleanup remain unqualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_pc_actor import PicoAudioPCActor,original,require_original
from adapters.pico4.audio_recipe import PicoAudioRecipe,INPUTS
from feature_journeys.contract import arguments

VERSION=1


class PicoAudioPCStartCoordinator:
    def __init__(self,recipe,actor):
        need(type(recipe) is PicoAudioRecipe and type(actor) is PicoAudioPCActor and actor.recipe is recipe)
        self.recipe,self.actor,self.lock=recipe,actor,recipe.lock
        self.store=PrivateFeatureState(recipe.store.path.with_name('audio-recipe-pc-start.json'))
        self.host=host_identity();self.disk=self.pin=self.state=None
        self.scope=dict(audioPCStartCoordinatorVersion=VERSION,runId=recipe.run,binding=deepcopy(recipe.binding),
            fixtureUrl=recipe.source.fixture_url,recipe=str(recipe.store.path),actorHeader=deepcopy(actor.header_ref),hostProcessIdentity=self.host)
        self.scope_sha=json_digest(self.scope)
        with self.lock.held():
            need(self.store.read() is None and recipe.disk is None and recipe.state is None)
            self.save(dict(phase='new',completed=[],pending=None,digitalRetired=False))
        recipe.bind_record_owner(self)

    def bound(self):
        self.lock.assert_held()
        need(host_identity()==self.host and json_digest(self.scope)==self.scope_sha and self.store.read()==self.disk
            and original(self.store)==self.pin and json_digest(self.state)==self.state_sha
            and require_original(self.scope['actorHeader'])==self.actor.scope
            and self.scope['actorHeader']==self.actor.header_ref
            and self.recipe.record_owner is self and self.recipe.record_callback is self.recipe._record_callback)
        self.actor.authority()

    def save(self,state):
        self.lock.assert_held();need(self.store.read()==self.disk and (self.pin is None or original(self.store)==self.pin))
        body=dict(audioPCStartCoordinatorVersion=VERSION,scope=deepcopy(self.scope),state=deepcopy(state))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.pin=original(self.store);self.state=deepcopy(state);self.state_sha=json_digest(self.state)

    def prepare(self):
        self.actor.unlocked()
        with self.lock.held():
            self.bound();need(self.state['phase']=='new');value=deepcopy(self.state);value['phase']='prepare-issued';self.save(value)
        self.recipe.prepare()
        with self.lock.held():
            self.bound();need(self.recipe.state['baseline'] is not None and self.recipe.state['cursor']==0)
            value=deepcopy(self.state);value['phase']='ready';self.save(value)
        # Independent originals, not the normal Page owner's accepted values.
        return self.actor.observe()

    def record_reply(self,action,value):
        self.lock.assert_held();self.bound();need(self.state['pending'] is not None and self.state['phase']=='acting')
        state=deepcopy(self.state);rows=state['pending']['pcReplies'];need(len(rows)<16)
        rows.append(dict(action=action,value=deepcopy(value)));self.save(state)

    def record_guard(self,command,phase):
        self.bound();pending=self.state['pending']
        need(self.state['phase']=='acting' and pending is not None and pending['call']['verb']=='record-start'
            and pending['ready'] is not None and self.recipe.matches(pending['call'],phase)
            and self.actor.state['pending'] is self.actor.state['publication'] is None
            and command['controlId']=='audio.record' and command['action']=='activate')
        call=deepcopy(pending['call']);ready=deepcopy(pending['ready'])
        # The Actor source rechecks its actual recorder and route. Its returned
        # bytes are durably retained before even their schema can be accepted.
        self.actor.check_ready(ready,self.record_reply)
        self.bound();need(self.state['pending']['call']==call and self.state['pending']['ready']==ready)

    def act(self,call):
        self.actor.unlocked();call=deepcopy(arguments('feature.audio.act',call))
        need(call['runId']==self.recipe.run and call['fixtureUrl']==self.recipe.source.fixture_url)
        with self.lock.held():
            self.bound();need(self.state['phase'] in ('ready','waiting-pc','acting','partial-complete'))
            need(self.actor.state['pending'] is self.actor.state['publication'] is None)
            if self.state['completed'] and self.state['completed'][-1]['ticket']==call['ticket']:
                need(self.state['completed'][-1]['call']==call);self.recipe.act(call);return self.report()
            pending=self.state['pending']
            if pending is None:
                self.recipe.load();index=self.recipe.state['cursor'];need(integer(index,0,len(INPUTS)-1)
                    and (call['verb'],call['inputs'])==INPUTS[index])
                phase=self.recipe.source.status(self.recipe.state['lastPhase']);need(phase['active'] and self.recipe.matches(call,phase))
                value=deepcopy(self.state);value['phase']='waiting-pc' if call['verb']=='record-start' else 'acting'
                value['pending']=dict(call=deepcopy(call),beforeCursor=index,phase=phase,ready=None,pcReplies=[]);self.save(value)
            else:need(pending['call']==call)
            waiting=self.state['phase']=='waiting-pc'
        if waiting:
            # No Parent or independent-role lock spans a receive, future wait,
            # worker startup or sleep. The normal command does not yet exist.
            frame=self.actor.observe();seconds=3.25 if frame['actual']['muted'] else 8
            reference=self.actor.arm(call['ticket'],seconds)
            with self.lock.held():
                self.bound();need(self.state['phase']=='waiting-pc' and self.state['pending']['call']==call)
                phase=self.recipe.source.status();need(self.recipe.matches(call,phase)
                    and phase['activations']==self.state['pending']['phase']['activations'])
                value=deepcopy(self.state);value['pending']['ready']=reference;value['phase']='acting';self.save(value)
        if call['verb']=='close':
            for row in tuple(self.actor.state['jobs']):self.actor.wait_saved(row['ticket'])
        result=self.recipe.act(call)
        # Completion consumes the independently retained ORIGINAL Start capture,
        # never the later await-completion ticket or a new receive operation.
        if call['verb']=='await-completion' and self.recipe.state['cursor']>=8:
            ticket=self.recipe.state['steps'][6]['source']['activations'][-1]['ticket']
            self.actor.wait_saved(ticket);self.recipe.join_completed_preview(self.actor.peer())
        with self.lock.held():
            self.bound();pending=self.state['pending'];need(pending['call']==call and self.recipe.state['pending'] is None
                and self.recipe.state['cursor']==pending['beforeCursor']+1)
            value=deepcopy(self.state);value['completed'].append(dict(ticket=call['ticket'],call=call,
                cursor=self.recipe.state['cursor'],stepSha256=json_digest(self.recipe.state['steps'][-1])))
            value['pending']=None;value['phase']='partial-complete' if self.recipe.state['cursor']==14 else 'ready';self.save(value)
            self.bound();return self.report()

    def report(self):
        return dict(normalStagesDispatched=len(self.state['completed']),normalRecipeStages=14,
            pending=None if self.state['pending'] is None else self.state['pending']['call']['ticket'],
            digitalRecorderRetired=self.state['digitalRetired'],independentOriginalRole=True,
            physicalAcousticObserved=False,fullAudioQualified=False,journalsRetained=True)

    def retire_digital(self):
        self.actor.unlocked()
        with self.lock.held():
            self.bound();need(self.state['phase'] in ('partial-complete','retiring','digital-retired')
                and len(self.state['completed'])==14 and self.state['pending'] is None)
            self.recipe.load();self.recipe.resources();need(self.recipe.state['cursor']==14 and self.recipe.state['pending'] is None)
            if self.state['phase']!='digital-retired':
                value=deepcopy(self.state);value['phase']='retiring';self.save(value)
        self.actor.retire_recorders();self.actor.quiet()
        with self.lock.held():
            self.bound();self.recipe.load();self.recipe.resources()
            value=deepcopy(self.state);value.update(phase='digital-retired',digitalRetired=True);self.save(value);self.bound();return self.report()
