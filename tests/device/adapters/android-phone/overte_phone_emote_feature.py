"""Public Emote operations composed from the existing original-bound owners.

Capability registration remains separate. No acknowledged input supplies an
observation, and finalization waits for the independently credentialed actor.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,result
from overte_phone_emote_actor import PhoneEmoteActor,image_policy
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_namespaces import PhoneEmoteNamespaces
from overte_phone_emote_retirement import PhoneEmoteRetirement
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_emote_run import PhoneEmoteRun
from overte_phone_script_history import same


class PhoneEmoteFeature:
    def __init__(self,run,policy):
        need(isinstance(run,PhoneEmoteRun))
        self.run,self.policy=run,image_policy(policy)
        need(run.policy is not None and same(run.image_policy,self.policy))

    def call(self,kind,value):
        value=deepcopy(arguments('feature.emotes.'+kind,value))
        need(value['runId']==self.run.run)
        if kind=='act':need(value['fixtureUrl']==self.run.fixture_url)
        return value

    def prepare(self):
        with self.run.lock.held():
            self.run.load()
            # Private legacy owners lack a durable public image configuration.
            # They may be cleaned up, but cannot authorize new public inputs.
            need(self.run.previous is None or same(self.run.previous.get('imagePolicy'),self.policy))
        return self.run.prepare()

    def rotation_needed(self,call):
        """Reserve headroom only at an idle play/Sit boundary, never per play."""
        self.run.lock.assert_held()
        if self.run.state['phase']=='switching':return True
        if call['verb'] not in ('play','sit') or self.run.state['phase']=='acting':return False
        if same(self.run.state['call'],call):return False
        primary=self.run.source();inputs=PhoneEmoteInputs(primary)
        if len(inputs.state['history'])>=128:return True
        for role in ('primary','actor'):
            observer=PhoneEmoteRole(self.run,role,self.policy)
            need(observer.state['phase']=='ready')
            if len(observer.source.frames)>=512 or observer.state['index']>=128:return True
        return False

    def rotate(self,call):
        with self.run.lock.held():
            self.run.load()
            if self.run.state['phase']=='switching':
                lease=PhoneEmoteNamespaces(self.run.source())
                if lease.state['current']==self.run.state['segment']+1:
                    self.run.advance_switch();return
        self.run.request_switch(call);self.run.acknowledge_switch('primary')
        started=previous=self.run.monotonic()
        for attempt in range(81):
            now=self.run.monotonic();need(number(now,previous,started+20));previous=now
            with self.run.lock.held():
                self.run.load();need(self.run.state['phase']=='switching' and same(self.run.state['call'],call))
                lease=PhoneEmoteNamespaces(self.run.source())
                # The actor alone freezes its original source. Never borrow the
                # primary's proof or wait while holding the shared source lock.
                need(lease.state['pending'] is not None)
                if all(
                        lease.state['pending']['roles'][role] is not None for role in ('primary','actor')):
                    self.run.advance_switch();return
            need(attempt<80 and now-started<20);self.run.sleep(.25)
        raise NativeUIError('Independent Emote namespace acknowledgment timed out')

    def act(self,value):
        call=self.call('act',value)
        with self.run.lock.held():
            self.run.load();need(self.run.state is not None and same(self.run.previous.get('imagePolicy'),self.policy))
            rotate=self.rotation_needed(call)
        if rotate:self.rotate(call)
        return self.run.act(call)

    def observe(self,value):
        call=self.call('observe',value)
        with self.run.lock.held():
            self.run.load();prepare=self.run.state is None or self.run.state['phase']=='preparing'
        if prepare:self.prepare()
        with self.run.lock.held():
            self.run.load();need(self.run.state is not None and same(self.run.previous.get('imagePolicy'),self.policy))
            observer=PhoneEmoteRole(self.run,'primary',self.policy)
            if observer.state['phase']!='ready':observer.recover()
            measured=observer.read(call['afterSequence'])
            need(measured['runId']==self.run.run and measured['sequence']>call['afterSequence'])
            return result('feature.emotes.observe',measured)

    def cleanup(self,value):
        call=self.call('cleanup',value)
        self.run.cleanup_resources(call)
        with self.run.lock.held():
            self.run.load();unissued=self.run.state['setup']==dict(view='unissued',scene='unissued')
        if not unissued:self.run.cleanup_quiet('primary')
        # This acknowledges restoration of owned resources only. Common cleanup
        # obtains its own fresh observations and peer evidence afterwards.
        return {'performed':True}

    def finalize(self):
        """Retire only after fixture closure and actual actor termination."""
        started=previous=self.run.monotonic()
        parent=PrivateFeatureState(self.run.store.path.with_name('phone-emote-retirement.json'))
        for attempt in range(241):
            now=self.run.monotonic();need(number(now,previous,started+60));previous=now
            with self.run.lock.held():
                self.run.load();metadata=parent.read()
                if metadata is not None:
                    # Parent reopens exact originals after any child/run prune;
                    # no missing actor control is interpreted as termination.
                    return PhoneEmoteRetirement(self.run,self.policy,deadline=started+60).finalize()
                need(self.run.state is not None and self.run.state['phase']=='resources-restored')
                status=self.run.phase.status();need(status['active'] is False)
                actor=PhoneEmoteActor(self.run,self.policy);actor.load()
                if actor.state['phase'] in ('retired','unadmitted'):
                    return PhoneEmoteRetirement(self.run,self.policy,deadline=started+60).finalize()
            need(attempt<240 and now-started<60);self.run.sleep(.25)
        raise NativeUIError('Independent Emote actor termination timed out')
