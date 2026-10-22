"""Real actor sources and credentialed loopback fixture; no device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_emote_role
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_emote_actor import PhoneEmoteActor
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_script_history import pack,unpack
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class EmoteActorTests(unittest.TestCase):
    setUp=test_emote_role.EmoteRoleTests.setUp
    owner=test_emote_role.EmoteRoleTests.owner
    prepared=test_emote_role.EmoteRoleTests.prepared
    publication_server=test_emote_role.EmoteRoleTests.publication_server
    actor_run=test_emote_role.EmoteRoleTests.actor_run

    def start(self):
        self.server,self.reader,self.client=self.publication_server()
        call=self.model.call
        def bound_call(*args,**kwargs):
            value=call(*args,**kwargs);value['fixtureUrl']=self.client.url+'/runs/'+RUN+'/';return value
        self.model.call=bound_call;self.primary=self.prepared()
        return PhoneEmoteActor(self.actor_run(self.client),POLICY)

    def test_actual_independent_native_source_publishes_outside_lock_and_backend_entry_is_required(self):
        flow=self.start();m=self.model;request=self.client.request;posts=[]
        def outside(path,*args,**kwargs):
            if path.endswith('/samples') or path=='/runs/'+RUN:
                with self.assertRaises(NativeUIError):flow.run.lock.assert_held()
                if path.endswith('/samples'):posts.append(deepcopy(args[0]))
            return request(path,*args,**kwargs)
        with patch.object(self.client,'request',side_effect=outside):self.assertFalse(flow.step())
        rows=self.reader.request('/runs/'+RUN)['entries'];self.assertEqual(1,len(rows));self.assertEqual(1,len(posts))
        self.assertEqual(rows[0],flow.state['last']['receipt']['body']);self.assertIsNone(flow.state['pending'])
        self.assertEqual('watching',flow.state['phase']);self.assertEqual([],m.controls.input_requests)
        with flow.run.lock.held():
            flow.run.load();actor=PhoneEmoteRole(flow.run,'actor',POLICY);original=actor.stored(1)
            self.assertEqual(original['public']['capturedEpochMs'],posts[0]['capturedEpochMs']);self.assertEqual('actor',original['sourceHeader']['role'])
        self.assertEqual(0,self.server.internal_errors)

    def test_successful_http_ack_with_no_actual_backend_entry_stays_owned_and_cannot_retire(self):
        flow=self.start();request=self.client.request
        def ignored(path,*args,**kwargs):return {} if path.endswith('/samples') else request(path,*args,**kwargs)
        with patch.object(self.client,'request',side_effect=ignored),self.assertRaises(NativeUIError):flow.step()
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries']);self.assertIsNone(flow.state['last'])
        self.assertTrue(flow.state['pending']['issued']);self.assertEqual('publishing',flow.state['phase'])
        before=self.model.calls[:];flow=PhoneEmoteActor(self.actor_run(self.client),POLICY)
        with self.assertRaises(NativeUIError):flow.step()
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries']);self.assertTrue(flow.state['pending']['issued'])
        self.assertTrue(all(call=='phase-read' for call in self.model.calls[len(before):]))

    def test_lost_http_return_reconciles_actual_journal_entry_without_replaying_post(self):
        flow=self.start();request=self.client.request;posts=[]
        def lost(path,*args,**kwargs):
            result=request(path,*args,**kwargs)
            if path.endswith('/samples'):posts.append(deepcopy(args[0]));raise ValueError('Synthetic lost publication return')
            return result
        with patch.object(self.client,'request',side_effect=lost):self.assertFalse(flow.step())
        self.assertEqual(1,len(posts));self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))
        self.assertEqual(posts[0],flow.state['last']['sample']);self.assertEqual('journal',flow.state['last']['receipt']['kind'])

    def test_lost_final_actor_commit_reuses_the_same_original_entry_without_native_query_or_post(self):
        flow=self.start();save=flow.save
        def lost():
            if flow.state['last'] is not None:raise NativeUIError('Synthetic lost actor publication commit')
            return save()
        with patch.object(flow,'save',side_effect=lost),self.assertRaises(NativeUIError):flow.step()
        record=flow.store.read();pending=unpack(record['payload'])[0]['pending'];self.assertTrue(pending['issued'])
        before=self.model.calls[:];request=self.client.request;posts=[]
        def tracked(path,*args,**kwargs):
            if path.endswith('/samples'):posts.append(path)
            return request(path,*args,**kwargs)
        flow=PhoneEmoteActor(self.actor_run(self.client),POLICY)
        with patch.object(self.client,'request',side_effect=tracked):self.assertFalse(flow.step())
        self.assertEqual([],posts);self.assertEqual(pending['sample'],flow.state['last']['sample'])
        self.assertTrue(all(call=='phase-read' for call in self.model.calls[len(before):]))
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))

    def test_changed_or_foreign_backend_entry_cannot_acknowledge_this_original(self):
        flow=self.start();request=self.client.request
        def foreign(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if path=='/runs/'+RUN and value['entries']:value['entries'][0]['facts']['poseProgress']=.75
            return value
        with patch.object(self.client,'request',side_effect=foreign),self.assertRaises(NativeUIError):flow.step()
        self.assertIsNone(flow.state['last']);self.assertTrue(flow.state['pending']['issued'])

    def test_reader_credential_cannot_publish_even_when_all_native_facts_are_valid(self):
        self.start();flow=PhoneEmoteActor(self.actor_run(self.reader),POLICY)
        with self.assertRaises(ValueError):flow.step()
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries']);self.assertIsNone(flow.state['last'])
        self.assertIsNotNone(flow.store.read());self.assertTrue(flow.state['pending']['issued'])

    def test_pending_or_background_parent_never_constructs_a_foreground_native_getter(self):
        flow=self.start();m=self.model
        with self.primary.lock.held():
            self.primary.state['phase']='acting';self.primary.state['call']=m.call('background-resume');self.primary.save()
        with patch.object(m,'_native_feature_observer',side_effect=AssertionError('Forbidden native getter during OS recovery')):
            self.assertFalse(flow.step())
        self.assertIsNone(flow.store.read())

    def test_real_source_phase_race_is_retained_and_next_step_waits_for_matching_primary_call(self):
        flow=self.start();m=self.model;send=m.native_send;fired=False
        def cross(request):
            nonlocal fired
            value=send(request)
            if not fired:fired=True;m.journal.activate(RUN,'f'*32,'open',{})
            return value
        with patch.object(m,'native_send',side_effect=cross):self.assertFalse(flow.step())
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries'])
        with flow.run.lock.held():
            flow.run.load();failure=PhoneEmoteFailures(flow.run);rows=failure.originals.restore(failure.state['manifests'],1)
            self.assertEqual('phase',rows[0]['kind']);self.assertEqual(2,rows[0]['archive']['emoteRolePhaseRetirementVersion'])
        self.assertFalse(flow.step());self.primary.act(m.call('open'));self.assertFalse(flow.step())
        rows=self.reader.request('/runs/'+RUN)['entries'];self.assertEqual(1,len(rows));self.assertEqual(1,rows[0]['actorSequence'])

    def test_cleanup_requires_own_three_second_work_window_then_fresh_actor_entry(self):
        flow=self.start();m=self.model;self.assertFalse(flow.step());m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));before=len(m.work_commands)
        self.assertFalse(flow.step());self.assertEqual('drained',flow.state['phase']);self.assertIsNotNone(flow.state['quiet'])
        self.assertIsNone(flow.state['pending']);self.assertGreater(len(m.work_commands),before)
        quiet=unpack(flow.state['quiet']['header']['payload'])[0];self.assertEqual('complete',quiet['phase'])
        self.assertGreaterEqual(quiet['window']['elapsedMs'],3000)
        self.assertEqual('actor',flow.state['quiet']['header']['role']);self.assertEqual('a'*32,flow.state['last']['sample']['ticket'])
        self.assertFalse((m.root/'phone-emote-actor-lifetime.json').exists());self.assertIsNotNone(flow.store.read())
        self.assertEqual(flow.state['last']['receipt']['body'],self.reader.request('/runs/'+RUN)['entries'][-1])
        before=len(m.work_commands);self.reader.request('/runs/'+RUN,method='DELETE')
        self.assertTrue(PhoneEmoteActor(self.actor_run(self.client),POLICY).step())
        self.assertEqual(before,len(m.work_commands));self.assertIsNotNone(self.primary.store.read())

    def test_slow_pending_commit_cannot_publish_an_old_sample_with_frozen_external_clocks(self):
        flow=self.start();save=flow.save;m=self.model
        def slow():
            save()
            if flow.state['pending'] is not None and not flow.state['pending']['issued']:m.clock+=2
        with patch.object(flow,'save',side_effect=slow):self.assertFalse(flow.step())
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries']);self.assertEqual('expired-before-send',flow.state['dropped'][-1]['reason'])
        self.assertIsNone(flow.state['pending']);self.assertEqual('watching',flow.state['phase'])

    def test_unknown_actor_control_or_changed_image_policy_cannot_be_adopted(self):
        flow=self.start();flow.step();header=deepcopy(flow.previous);header['emoteActorVersion']=99;flow.store.write(header,flow.previous)
        with self.assertRaises(NativeUIError):PhoneEmoteActor(self.actor_run(self.client),POLICY).step()
        flow.store.write(flow.previous,header);changed=deepcopy(POLICY);changed['subject'][0]+=1
        with self.assertRaises(NativeUIError):PhoneEmoteActor(self.actor_run(self.client),changed).step()

    def test_namespace_acknowledgment_uses_own_idle_source_before_new_play_publication(self):
        flow=self.start();m=self.model;flow.step();self.primary.act(m.call('open'));self.primary.act(m.call('close'));call=m.call('play',dict(name='Crying'))
        self.primary.request_switch(call);self.assertFalse(flow.step());self.primary.acknowledge_switch('primary')
        self.assertEqual(1,self.primary.advance_switch());self.assertFalse(flow.step())
        self.primary.act(call);self.assertFalse(flow.step());row=self.reader.request('/runs/'+RUN)['entries'][-1]
        self.assertEqual(call['ticket'],row['ticket']);self.assertEqual('Crying',row['facts']['animation'])
        with flow.run.lock.held():
            flow.run.load();role=PhoneEmoteRole(flow.run,'actor',POLICY)
            self.assertEqual(1,role.state['segment']);self.assertEqual(1,role.state['index']);self.assertEqual(2,role.state['sequence'])

    def test_ignored_normal_input_never_publishes_the_requested_animation(self):
        flow=self.start();m=self.model;m.ignore_native=True;self.primary.act(m.call('play',dict(name='Crying')))
        with self.assertRaises(NativeUIError):flow.step()
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries'])
        with flow.run.lock.held():
            flow.run.load();role=PhoneEmoteRole(flow.run,'actor',POLICY)
            self.assertEqual(0,role.state['sequence']);self.assertEqual('acquiring',role.state['phase'])

    def test_normal_input_history_cannot_borrow_absent_baseline_input_context(self):
        from overte_phone_emote_inputs import PhoneEmoteInputs
        from overte_phone_emote_effects import PhoneEmoteEffects
        flow=self.start();m=self.model;flow.step();self.primary.act(m.call('open'))
        with flow.run.lock.held():
            flow.run.load();primary=flow.run.source();actor=flow.run.source('actor')
            effects=PhoneEmoteEffects(PhoneEmoteInputs(primary),current_source=actor)
            with self.assertRaises(NativeUIError):effects._archive_context(None,primary.previous,actor.previous)

    def test_old_backend_sample_cannot_be_relabelled_as_actor_cleanup_retirement(self):
        flow=self.start();m=self.model;flow.step();baseline=deepcopy(flow.state['last'])
        m.journal.activate(RUN,'a'*32,'cleanup',{});self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step()
        self.reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(flow.step())
        header=deepcopy(flow.previous);state=unpack(header['payload'])[0];state['last']=baseline;header['payload']=pack([state])
        flow.store.write(header,flow.previous)
        with self.assertRaises(NativeUIError):PhoneEmoteActor(self.actor_run(self.client),POLICY).step()
        self.assertEqual(header,flow.store.read())

    def test_retired_actor_still_rejects_unaccounted_scope_metadata(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));self.assertFalse(flow.step())
        self.reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(flow.step())
        unknown=PrivateFeatureState(m.root/'phone-emote-actor-observation-777.json');unknown.write(dict(unaccounted=True),None)
        with self.assertRaises(NativeUIError):PhoneEmoteActor(self.actor_run(self.client),POLICY).step()
        self.assertEqual(dict(unaccounted=True),unknown.read())

    def test_lost_quiet_retention_return_reuses_original_window_without_work_query_or_redating(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));save=flow.save
        def lost():
            save()
            if flow.state['quiet'] is not None:raise NativeUIError('Synthetic lost durable quiet retention return')
        with patch.object(flow,'save',side_effect=lost),self.assertRaises(NativeUIError):flow.step()
        header=flow.store.read();quiet=unpack(header['payload'])[0]['quiet'];self.assertIsNotNone(quiet)
        before=len(m.work_commands);flow=PhoneEmoteActor(self.actor_run(self.client),POLICY);self.assertFalse(flow.step())
        self.assertEqual(before,len(m.work_commands));self.assertEqual(quiet,flow.state['quiet'])
        self.assertFalse((m.root/'phone-emote-actor-lifetime.json').exists())

    def test_phase_change_during_post_drops_only_the_old_publication_intent(self):
        flow=self.start();m=self.model;request=self.client.request
        def crossed(path,*args,**kwargs):
            if path.endswith('/samples'):m.call('open')
            return request(path,*args,**kwargs)
        with patch.object(self.client,'request',side_effect=crossed):self.assertFalse(flow.step())
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries']);self.assertIsNone(flow.state['last'])
        self.assertIsNone(flow.state['pending']);self.assertEqual('phase-changed',flow.state['dropped'][-1]['reason'])
        self.assertEqual([],m.controls.input_requests)
        with flow.run.lock.held():
            flow.run.load();self.assertEqual(1,PhoneEmoteRole(flow.run,'actor',POLICY).state['sequence'])

    def test_actual_actor_cancel_image_race_retires_native_scope_before_any_new_publication(self):
        flow=self.start();m=self.model;self.primary.act(m.call('sit'));flow.step()
        self.primary.act(m.call('override',dict(name='Crying')));flow.step();self.primary.act(m.call('cancel'))
        with patch.object(m,'on_capture',lambda:m.call('close')):self.assertFalse(flow.step())
        rows=self.reader.request('/runs/'+RUN)['entries'];self.assertEqual(2,len(rows))
        with flow.run.lock.held():
            flow.run.load();failure=PhoneEmoteFailures(flow.run);proof=failure.originals.restore(failure.state['manifests'],1)[0]['archive']
            self.assertFalse(proof['scope']['archive']['childRetirement']['cleanup']['retirement']['memory']['present'])
            self.assertEqual(2,PhoneEmoteRole(flow.run,'actor',POLICY).state['sequence'])
        self.assertFalse((m.world_root/'world-actor.json').exists());self.assertIsNone(flow.state['pending'])
        self.primary.act(m.call('close'));self.assertFalse(flow.step());self.assertEqual(3,len(self.reader.request('/runs/'+RUN)['entries']))

    def test_missing_cleanup_peer_entry_cannot_finish_even_with_real_quiet_window(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));request=self.client.request
        def ignored(path,*args,**kwargs):return {} if path.endswith('/samples') else request(path,*args,**kwargs)
        with patch.object(self.client,'request',side_effect=ignored),self.assertRaises(NativeUIError):flow.step()
        self.assertIsNotNone(flow.state['quiet']);self.assertNotEqual('retired',flow.state['phase'])
        self.assertIsNone(flow.state['last']);self.assertEqual([],self.reader.request('/runs/'+RUN)['entries'])

    def test_real_appium_factory_defers_native_sources_and_rejects_foreign_run(self):
        from appium_adapter import PhoneAppiumAdapter
        from overte_phone_emote_run import PhoneEmoteRun
        flow=self.start();m=self.model;before=m.calls[:]
        adapter=SimpleNamespace(candidate=object(),target=lambda _:dict(appId='io.github.noah_be.overte.phone'),
            controlled_android_client=lambda _:True,emote_feature_store=lambda _:self.primary.store,state_path=m.state_path)
        made=PhoneAppiumAdapter._emote_actor(adapter,'synthetic-selector',RUN,client=self.client,image_policy=POLICY)
        self.assertIsInstance(made,PhoneEmoteActor);self.assertIsInstance(made.run,PhoneEmoteRun);self.assertEqual(before,m.calls)
        with self.assertRaises(ValueError):PhoneAppiumAdapter._emote_actor(adapter,'synthetic-selector','e'*32,client=self.client,image_policy=POLICY)
        adapter.controlled_android_client=lambda _:False
        with self.assertRaises(ValueError):PhoneAppiumAdapter._emote_actor(adapter,'synthetic-selector',RUN,client=self.client,image_policy=POLICY)
        self.assertEqual(before,m.calls)

    def test_observer_loop_deadline_includes_the_last_step(self):
        import script_observer
        flow=self.start();m=self.model
        def late():m.clock+=31;return True
        adapter=SimpleNamespace(emote_feature_store=lambda _:self.primary.store,_emote_actor=lambda *args,**kwargs:SimpleNamespace(step=late))
        config=dict(area='emotes',target='owned',fixtureUrl=self.client.url,actorToken=self.client.token,durationSeconds=30,imagePolicy=POLICY)
        with self.assertRaises(NativeUIError):script_observer.run(adapter,config,monotonic=lambda:m.clock,sleep=m.sleep)

    def test_background_intent_between_measurement_and_delivery_defers_all_native_factories(self):
        flow=self.start();m=self.model;deliver=flow.deliver
        def interrupted():
            with self.primary.lock.held():
                self.primary.state.update(phase='acting',call=m.call('background-resume'));self.primary.save()
            with patch.object(m,'_native_feature_observer',side_effect=AssertionError('Forbidden getter after background intent')):
                return deliver()
        with patch.object(flow,'deliver',side_effect=interrupted):self.assertFalse(flow.step())
        self.assertIsNotNone(flow.state['pending']);self.assertFalse(flow.state['pending']['issued'])
        self.assertEqual([],self.reader.request('/runs/'+RUN)['entries'])

    def test_background_intent_before_ack_commit_preserves_pending_without_foreground_getter(self):
        flow=self.start();m=self.model;request=self.client.request;blocked=False
        def interrupted(path,*args,**kwargs):
            nonlocal blocked
            value=request(path,*args,**kwargs)
            if path=='/runs/'+RUN and value['entries'] and not blocked:
                blocked=True
                with self.primary.lock.held():
                    self.primary.state.update(phase='acting',call=m.call('background-resume'));self.primary.save()
            return value
        getter=m._native_feature_observer
        def guarded(*args,**kwargs):
            if blocked:raise AssertionError('Forbidden getter after background intent')
            return getter(*args,**kwargs)
        with patch.object(self.client,'request',side_effect=interrupted),patch.object(m,'_native_feature_observer',side_effect=guarded):self.assertFalse(flow.step())
        self.assertTrue(blocked);self.assertTrue(flow.state['pending']['issued']);self.assertIsNone(flow.state['last'])
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))

    def test_aged_cleanup_ack_requires_a_new_fresh_sample_before_worker_retirement(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));save=flow.save
        def lost():
            if flow.state['last'] is not None:raise NativeUIError('Synthetic lost cleanup ack commit')
            return save()
        with patch.object(flow,'save',side_effect=lost),self.assertRaises(NativeUIError):flow.step()
        original=unpack(flow.store.read()['payload'])[0]['pending']['sample'];m.sleep(2)
        flow=PhoneEmoteActor(self.actor_run(self.client),POLICY);self.assertFalse(flow.step())
        self.assertEqual(original,flow.state['last']['sample']);self.assertEqual('watching',flow.state['phase'])
        self.assertFalse(flow.step());self.assertEqual('drained',flow.state['phase']);current=flow.state['last']['sample']
        self.assertGreater(current['actorSequence'],original['actorSequence']);self.assertGreater(current['capturedEpochMs'],original['capturedEpochMs'])
        self.assertEqual(2,len(self.reader.request('/runs/'+RUN)['entries']))

    def test_closing_fixture_during_source_read_retains_failed_source_and_role_before_terminal(self):
        flow=self.start();m=self.model;flow.step();m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));self.assertFalse(flow.step())
        send=m.native_send;closed=False
        def close(request):
            nonlocal closed
            result=send(request)
            if not closed:self.reader.request('/runs/'+RUN,method='DELETE');closed=True
            return result
        with patch.object(m,'native_send',side_effect=close):self.assertTrue(flow.step())
        self.assertTrue(closed);self.assertEqual('retired',flow.state['phase'])
        self.assertFalse(flow.state['providerRetirement']['active'])
        with flow.run.lock.held():
            flow.run.load();owner=PhoneEmoteFailures(flow.run);rows=owner.originals.restore(owner.state['manifests'],owner.state['count'])
            self.assertEqual(['admission','source','role'],[row['kind'] for row in rows])
            self.assertEqual([2,2],[row['archive'][key] for row,key in zip(rows[1:],('emoteSourceFailureArchiveVersion','emoteRoleFailureArchiveVersion'))])
            self.assertEqual('ready',PhoneEmoteRole(flow.run,'actor',POLICY).state['phase'])
            for row in rows:owner.record(row,row['index'])

    def test_legacy_terminal_actor_is_only_drained_until_actual_fixture_retirement(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step()
        header=deepcopy(flow.previous);header['emoteActorVersion']=1;state=unpack(header['payload'])[0]
        state.pop('providerRetirement');state['phase']='retired';header['payload']=pack([state]);flow.store.write(header,flow.previous)
        flow=PhoneEmoteActor(self.actor_run(self.client),POLICY)
        with flow.run.lock.held():
            flow.run.load();flow.load();self.assertEqual('drained',flow.state['phase']);self.assertEqual(header,flow.store.read())
        self.assertFalse(flow.step());self.assertEqual(3,flow.previous['emoteActorVersion'])
        self.reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(flow.step())

    def test_closing_fixture_during_each_role_original_stage_retains_partial_attempt(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved'):
            with self.subTest(boundary=boundary):
                self.setUp();flow=self.start();m=self.model;flow.step();m.journal.activate(RUN,'a'*32,'cleanup',{})
                self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step()
                intent=PhoneEmoteRole.storage_intent;closed=False
                def close(role,kind,value):
                    nonlocal closed
                    intent(role,kind,value)
                    if not closed and kind+'-'+value['phase']==boundary:
                        closed=True;self.reader.request('/runs/'+RUN,method='DELETE')
                        raise NativeUIError('Synthetic lost role write at actual fixture retirement')
                with patch.object(PhoneEmoteRole,'storage_intent',close):self.assertTrue(flow.step())
                self.assertTrue(closed);self.assertEqual('retired',flow.state['phase'])
                with flow.run.lock.held():
                    flow.run.load();owner=PhoneEmoteFailures(flow.run)
                    rows=owner.originals.restore(owner.state['manifests'],owner.state['count']);failed=rows[-1]
                    self.assertEqual('role',failed['kind']);self.assertEqual(2,failed['archive']['emoteRoleFailureArchiveVersion'])
                    self.assertIsNone(failed['archive']['scope']);self.assertFalse(failed['archive']['cleanup']['active'])
                    self.assertEqual(2,PhoneEmoteRole(flow.run,'actor',POLICY).state['sequence']);owner.record(failed,failed['index'])

    def test_closed_transfer_mode_cannot_release_a_source_while_fixture_is_active(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step()
        with flow.run.lock.held():
            flow.run.load();source=flow.run.source('actor')
            with patch.object(source.phase,'read',side_effect=ValueError('Synthetic lost phase read')),self.assertRaises(ValueError):source.read()
            header=deepcopy(source.previous)
            with self.assertRaises(NativeUIError):source.transfer_failed(lambda proof:None,provider_retired=True)
            self.assertEqual(header,source.store.read());self.assertEqual('reading',source.state['phase'])

    def test_terminal_reconstruction_keeps_original_provider_packet_and_all_journal_bytes(self):
        flow=self.start();m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step()
        self.reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(flow.step());header=deepcopy(flow.previous)
        flow=PhoneEmoteActor(self.actor_run(self.client),POLICY);self.assertTrue(flow.step())
        self.assertEqual(header,flow.store.read());self.assertEqual(header,flow.previous)

    def test_missing_cleanup_peer_and_quiet_proof_cannot_end_when_fixture_closes(self):
        flow=self.start();m=self.model;flow.step();m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));self.reader.request('/runs/'+RUN,method='DELETE')
        with self.assertRaises(NativeUIError):flow.step()
        self.assertIsNone(flow.state['providerRetirement']);self.assertEqual('watching',flow.state['phase'])
        self.assertNotEqual('a'*32,flow.state['last']['sample']['ticket'])

    def test_closed_failure_archive_and_parent_completion_resume_without_new_native_reads(self):
        for boundary in ('original-opened','manifest-saved','final'):
            with self.subTest(boundary=boundary):
                self.setUp();flow=self.start();m=self.model;flow.step();m.journal.activate(RUN,'a'*32,'cleanup',{})
                self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step()
                native=m.native_send;closed=False;intent=PhoneEmoteFailures.storage_intent;save=PhoneEmoteFailures.save
                def close(request):
                    nonlocal closed
                    result=native(request)
                    if not closed:self.reader.request('/runs/'+RUN,method='DELETE');closed=True
                    return result
                def interrupted(owner,kind,value):
                    intent(owner,kind,value)
                    if closed and kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost closed failure archive write')
                def final(owner):
                    if closed and boundary=='final' and owner.state['pending'] is None:raise NativeUIError('Synthetic lost closed failure completion')
                    return save(owner)
                with patch.object(m,'native_send',side_effect=close),patch.object(PhoneEmoteFailures,'storage_intent',interrupted),patch.object(PhoneEmoteFailures,'save',final),self.assertRaises(NativeUIError):flow.step()
                self.assertTrue(closed);before=m.calls[:];flow=PhoneEmoteActor(self.actor_run(self.client),POLICY)
                self.assertTrue(flow.step());self.assertTrue(all(call=='phase-read' for call in m.calls[len(before):]))
                with flow.run.lock.held():
                    flow.run.load();owner=PhoneEmoteFailures(flow.run);rows=owner.originals.restore(owner.state['manifests'],owner.state['count'])
                    self.assertEqual(['admission','source','role'],[row['kind'] for row in rows]);self.assertIsNone(owner.state['pending'])
                    for row in rows:owner.record(row,row['index'])

    def test_foreign_closed_provider_or_old_record_version_cannot_adopt_closed_read_proof(self):
        flow=self.start();m=self.model;flow.step();m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));flow.step();send=m.native_send;closed=False
        def close(request):
            nonlocal closed
            value=send(request)
            if not closed:self.reader.request('/runs/'+RUN,method='DELETE');closed=True
            return value
        with patch.object(m,'native_send',side_effect=close):self.assertTrue(flow.step())
        with flow.run.lock.held():
            flow.run.load();owner=PhoneEmoteFailures(flow.run);rows=owner.originals.restore(owner.state['manifests'],owner.state['count'])
            for row in rows[1:]:
                old=deepcopy(row);old['emoteFailureRecordVersion']=6
                with self.assertRaises(NativeUIError):owner.record(old,old['index'])
                for fault in ('active','birth','ticket'):
                    changed=deepcopy(row);status=changed['archive']['cleanup']
                    if fault=='active':status['active']=True;status['retiredEpochMs']=None
                    elif fault=='birth':status['instance']='e'*32
                    else:status['activations'][-1]['ticket']='e'*32
                    with self.subTest(kind=row['kind'],fault=fault),self.assertRaises((NativeUIError,ValueError)):owner.record(changed,changed['index'])

    def test_actor_configuration_and_existing_observer_entry_point_preserve_separate_client(self):
        import script_observer
        flow=self.start();m=self.model;path=m.root/'actor-config.json';store=PrivateFeatureState(path)
        value=dict(featureObserverVersion=3,area='emotes',target='owned',candidateArguments=['--record','placeholder'],
            fixtureUrl=self.client.url,actorToken=self.client.token,durationSeconds=30,imagePolicy=POLICY)
        store.write(value,None);self.assertEqual(value,script_observer.configuration(path))
        for edit in (dict(featureObserverVersion=2),dict(featureObserverVersion=True),dict(readerToken='x'*64),dict(imagePolicy={})):
            candidate=value|edit;store.write(candidate,store.read())
            with self.subTest(fields=list(edit)),self.assertRaises((NativeUIError,ValueError)):script_observer.configuration(path)
        for area in ('scripts','authentication','graphics'):
            legacy={key:item for key,item in value.items() if key!='imagePolicy'}
            legacy.update(area=area,fixtureUrl='https://accounts.overte.test/feature-fixture/v1')
            store.write(legacy,store.read());self.assertEqual(legacy,script_observer.configuration(path))
        m.journal.activate(RUN,'a'*32,'cleanup',{});self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN))
        made=[]
        def factory(selector,run,*,client,image_policy):
            self.assertEqual(('owned',RUN,self.client.token),(selector,run,client.token));self.assertEqual(POLICY,image_policy)
            made.append(PhoneEmoteActor(self.actor_run(client),image_policy));return made[-1]
        adapter=SimpleNamespace(emote_feature_store=lambda _:self.primary.store,_emote_actor=factory)
        published=[];closed=False
        def caller_window(seconds):
            nonlocal closed
            m.sleep(seconds)
            if not made or made[0].state is None or made[0].state['phase']!='drained' or closed:return
            rows=self.reader.request('/runs/'+RUN)['entries'];published[:]=rows
            if len(rows)>=3 and rows[-1]['capturedEpochMs']-rows[0]['capturedEpochMs']>=3000:
                self.reader.request('/runs/'+RUN,method='DELETE');closed=True
        self.assertEqual(0,script_observer.run(adapter,value,monotonic=lambda:m.clock,sleep=caller_window))
        self.assertTrue(closed);self.assertGreaterEqual(len(published),3)
        self.assertGreaterEqual(published[-1]['capturedEpochMs']-published[0]['capturedEpochMs'],3000)
        self.assertEqual(1,len(made));self.assertEqual('retired',made[0].state['phase'])


if __name__=='__main__':unittest.main()
