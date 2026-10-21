"""Durable original Graphics lifetime on real files/HTTP and synthetic native SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack, unpack
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.witness import Client
from ios.adapters.graphics_fixture import GraphicsFixtureReader
from ios.adapters.graphics_lifetime import IOSGraphicsLifetime, GraphicsLifetimePending
from ios.adapters.web_closures import IOSWebClosures, KINDS, resources_for
from ios.self_tests.test_ios_graphics_scene import SceneHarness, RUN, TICKET
from ios.self_tests.test_ios_graphics_restart import RestartHarness
from ios.adapters.graphics_preferences import IOSGraphicsPreferences


class WebSDK:
    """Original callback/resource counter model, never a normalized adapter result."""
    def __init__(self,sdk):
        self.sdk=sdk;self.query=None;self.commands=[];self.rows=[];self.sequence=0;self.held=None
        self.mutate=None;self.birth='e'*32;self.lost=False;self.after=None;self.last_activity=None
    def send(self,query):
        self.query=deepcopy(query);self.commands.append(deepcopy(query))
        if self.lost:raise OSError('Synthetic lost passive Web request return')
    def original(self):
        marker=next((r for r in self.sdk.scene_rows if r['id']==subject_ids(RUN)['marker']),None)
        now=self.sdk.epoch()
        if marker is not None and not self.rows:
            descriptor=dict(handle=1,creation=1,grant=1,page=1,surface='world-entity',
                identitySha256=hashlib.sha256(('web-entity:'+marker['id']).encode()).hexdigest(),sourceUrl=marker['sourceUrl'])
            transient={'upload-image','native-snapshot-object','vulkan-staging-buffer','vulkan-staging-memory','vulkan-submission'}
            resources={k:dict(created=0 if k=='native-presentation' else 1,retired=1 if k in transient else 0,
                pending=0 if k in transient or k=='native-presentation' else 1) for k in resources_for(5)}
            callbacks={k:dict(created=1 if k in ('snapshot','javascript','notification','rule-list') else 0,
                retired=1 if k in ('snapshot','javascript','rule-list') else 0,pending=1 if k=='notification' else 0) for k in KINDS}
            self.rows=[dict(id=1,descriptor=descriptor,createdEpochMs=now,updatedEpochMs=now,callbacks=callbacks,resources=resources)]
        if marker is None:
            for row in self.rows:
                for collection in ('callbacks','resources'):
                    for k,c in row[collection].items():
                        retired=c['created'] if k!=self.held else max(0,c['created']-1)
                        if retired!=c['retired']:c.update(retired=retired,pending=c['created']-retired);row['updatedEpochMs']=now
        self.sequence+=1
        value=dict(iosWebClosureVersion=5,commandId=self.query['commandId'],runId=RUN,fixtureUrl=self.query['fixtureUrl'],
            instance=self.birth,sequence=self.sequence,processId=self.sdk.pid,capturedEpochMs=now,complete=True,contexts=deepcopy(self.rows))
        if self.mutate:self.mutate(value)
        if self.after:self.after(self)
        return json.dumps(value)
    def reader(self):
        return IOSWebClosures(self.send,self.original,self.sdk.epoch,lambda:self.sdk.running and self.sdk.foreground,self.sdk.pid,
                              monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)


class LifetimeHarness(SceneHarness):
    def setUp(self):
        super().setUp();self.web=WebSDK(self.sdk);self.actor_client=Client(self.client.url,self.server.actor_token)
        self.adapter._web_closure_observer=lambda *_,**__:self.web.reader()
    def lifetime(self,role='primary'):
        source=GraphicsFixtureReader(self.actor_client if role=='actor' else self.client,RUN,epoch_ms=self.sdk.host_epoch)
        return IOSGraphicsLifetime(self.adapter,'owned',source,role,0,self.lock,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def prepare(self,role='primary'):
        owner=self.lifetime(role);scene=self.scene();scene.prepare();original=deepcopy(scene.state['original']['subject'])
        owner.observe_active();return owner,original
    def restore(self):
        self.client.close();self.scene().restore()


class LifetimeTests(LifetimeHarness,unittest.TestCase):
    def test_separate_original_admission_and_three_second_native_host_quiet_after_world_restore(self):
        with self.lock.held():
            owner,original=self.prepare();admitted=owner.load(owner.state['records'][0])
            self.assertTrue(admitted['web']['contexts'][0]['resources']['native-view']['pending'])
            self.assertNotEqual(admitted['providerBefore']['capturedEpochMs'],admitted['web']['capturedEpochMs'])
            self.restore();value=self.lifetime().wait_released(original);archive=IOSGraphicsLifetime.archive(value,path=owner.store.path,
                run=RUN,fixture_url=self.client.url,provider_instance=owner.source.instance,role='primary',stage=0,binding=owner.binding)
            self.assertEqual('released',archive['phase']);self.assertTrue(archive['windows'][-1]['complete'])
            self.assertGreaterEqual(archive['windows'][-1]['elapsedMs'],3000)
            self.assertGreaterEqual(len(archive['windows'][-1]['samples']),3)
            self.assertEqual(1,admitted['web']['contexts'][0]['resources']['native-view']['pending'])
            self.assertIsNotNone(owner.store.read())

    def test_actor_admission_uses_its_own_original_queries_and_private_role_history(self):
        with self.lock.held():
            primary,_original=self.prepare();actor=self.lifetime('actor');actor.observe_active()
            a=primary.load(primary.state['records'][0]);b=actor.load(actor.state['records'][0])
            self.assertNotEqual(primary.store.path,actor.store.path)
            self.assertNotEqual(a['web']['commandId'],b['web']['commandId']);self.assertGreater(b['web']['sequence'],a['web']['sequence'])
            self.assertNotEqual(a['clockJoin']['nativeBefore']['requestId'],b['clockJoin']['nativeBefore']['requestId'])
            self.assertEqual(a['web']['contexts'],b['web']['contexts']);self.assertIs(actor.source.client,self.actor_client)

    def test_fixture_retirement_and_missing_entities_alone_do_not_retire_held_native_resources(self):
        with self.lock.held():
            _owner,original=self.prepare();self.web.held='vulkan-image';self.restore()
            with self.assertRaises(NativeUIError):self.lifetime().wait_released(original)
            owner=self.lifetime();self.assertEqual('releasing',owner.state['phase']);self.assertFalse(owner.state['windows'][-1]['complete'])
            self.web.held=None;owner.wait_released(original);self.assertEqual(2,len(owner.state['windows']))
            self.assertTrue(owner.state['windows'][-1]['complete'])

    def test_new_resource_activity_between_zero_pending_reads_resets_the_quiet_window(self):
        with self.lock.held():
            _owner,original=self.prepare();self.restore();at=self.sdk.clock;changed=[False]
            def activity(source):
                if not changed[0] and self.sdk.clock-at>=1.5:
                    c=source.rows[0]['resources']['vulkan-staging-buffer'];c['created']+=1;c['retired']+=1
                    source.rows[0]['updatedEpochMs']=self.sdk.epoch();changed[0]=True
            self.web.after=activity;owner=self.lifetime();owner.wait_released(original);window=owner.state['windows'][-1]
            self.assertTrue(changed[0]);self.assertGreater(window['start'],0);self.assertGreaterEqual(self.sdk.clock-at,4.5)

    def test_reconstruction_restores_original_source_birth_counter_and_context_prefix_floors(self):
        with self.lock.held():
            owner,_original=self.prepare();count=len(self.web.commands);self.web.birth='f'*32
            with self.assertRaises(NativeUIError):self.lifetime().observe_active()
            self.assertEqual(count+1,len(self.web.commands));self.assertIsNotNone(self.lifetime().state['pending'])

    def test_ignored_marker_resources_do_not_get_filled_from_delivered_fixture_or_expected_values(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();self.web.mutate=lambda v:v.update(contexts=[])
            with self.assertRaises(GraphicsLifetimePending):owner.observe_active()
            self.assertFalse(owner.state['activeProofs']);self.assertIsNotNone(owner.state['pending'])

    def assert_foreign_marker(self,fault):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare()
            self.web.mutate=(lambda v:v['contexts'][0]['descriptor'].update(identitySha256='f'*64)) if fault=='identity' else (
                lambda v:v['contexts'][0]['descriptor'].update(sourceUrl=v['contexts'][0]['descriptor']['sourceUrl'].replace(TICKET,'f'*32)))
            with self.assertRaises(GraphicsLifetimePending):owner.observe_active()
            self.assertFalse(owner.state['activeProofs']);self.assertIsNotNone(owner.state['pending'])

    def test_original_native_entity_identity_is_required_for_resource_admission(self):
        self.assert_foreign_marker('identity')

    def test_original_native_source_url_is_required_for_resource_admission(self):
        self.assert_foreign_marker('url')


class LifetimeRecoveryTests(LifetimeHarness,unittest.TestCase):
    def test_lost_passive_request_keeps_accepted_cursors_then_recovers_without_normal_input(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();actions=len(self.sdk.model.actions);self.web.lost=True
            with self.assertRaises(NativeUIError):owner.observe_active()
            saved=deepcopy(owner.state['cursors']);self.assertIsNotNone(saved['subject']);self.assertIsNone(saved['web'])
            recovered=self.lifetime();self.assertEqual(saved,recovered.state['cursors']);self.web.lost=False
            recovered.observe_active();self.assertEqual(1,len(recovered.state['activeProofs']))
            abandoned=recovered.load(recovered.state['records'][0]);self.assertEqual('abandoned',abandoned['mode'])
            self.assertEqual(saved,abandoned['cursors']);self.assertEqual(actions,len(self.sdk.model.actions))
            self.assertEqual(2,len(self.web.commands));self.assertNotEqual(self.web.commands[0]['commandId'],self.web.commands[1]['commandId'])

    def test_lost_record_write_return_adopts_immutable_original_without_second_native_read(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();write=PrivateFeatureState.write;lost=[False]
            def uncertain(store,value,previous):
                result=write(store,value,previous)
                if value.get('iosGraphicsLifetimeRecordVersion') in (1,2) and not lost[0]:lost[0]=True;raise OSError('Synthetic lost original-record return')
                return result
            with patch.object(PrivateFeatureState,'write',new=uncertain),self.assertRaises(OSError):owner.observe_active()
            count=len(self.web.commands);owner=self.lifetime();reference=owner.observe_active()
            self.assertEqual(count,len(self.web.commands));self.assertEqual(reference,owner.state['records'][0])
            self.assertEqual(1,len(owner.state['activeProofs']));self.assertIsNone(owner.state['pending'])

    def test_lost_state_adoption_return_recovers_through_actual_committed_state(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();write=owner.store.write;lost=[False]
            def uncertain(value,previous):
                result=write(value,previous);data=unpack(value['payload'])[0]
                if data['records'] and data['pending'] is None and not lost[0]:lost[0]=True;raise OSError('Synthetic lost owner adoption return')
                return result
            with patch.object(owner.store,'write',side_effect=uncertain),self.assertRaises(OSError):owner.observe_active()
            count=len(self.web.commands);recovered=self.lifetime();self.assertEqual(count,len(self.web.commands))
            self.assertEqual(1,len(recovered.state['activeProofs']));self.assertIsNone(recovered.state['pending'])
            self.assertEqual('active',recovered.load(recovered.state['records'][0])['mode'])

    def test_lost_adoption_before_state_write_uses_original_record_without_reacquisition(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();write=owner.store.write
            def rejected(value,previous):
                if unpack(value['payload'])[0]['records']:raise OSError('Synthetic state disk failure')
                return write(value,previous)
            with patch.object(owner.store,'write',side_effect=rejected),self.assertRaises(OSError):owner.observe_active()
            count=len(self.web.commands);recovered=self.lifetime();recovered.observe_active()
            self.assertEqual(count,len(self.web.commands));self.assertEqual(1,len(recovered.state['records']))

    def test_actual_pid_change_does_not_rebind_the_old_resource_owner(self):
        with self.lock.held():
            owner,_original=self.prepare();before=owner.store.read();self.sdk.pid=43
            with self.assertRaises(NativeUIError):self.lifetime()
            self.assertEqual(before,owner.store.read())

    def test_foreign_role_metadata_or_altered_immutable_record_fails_before_native_request(self):
        with self.lock.held():
            owner,_original=self.prepare();count=len(self.web.commands)
            other=PrivateFeatureState(owner.store.path.with_name('ios-graphics-actor-0-lifetime.json'))
            other.write(owner.previous,None)
            with self.assertRaises(NativeUIError):self.lifetime('actor')
            self.assertEqual(count,len(self.web.commands))
            store=owner.record_store(1);value=store.read();rows=unpack(value['payload']);rows[0]['web']['capturedEpochMs']-=1
            store.write(value|dict(payload=pack(rows)),value)
            with self.assertRaises(NativeUIError):self.lifetime()
            self.assertEqual(count,len(self.web.commands))

    def test_each_repeated_cleanup_requires_a_new_complete_quiet_window(self):
        with self.lock.held():
            owner,original=self.prepare();self.restore();owner.wait_released(original)
            first=deepcopy(owner.state['windows'][0]);at=self.sdk.clock;self.lifetime().wait_released(original)
            current=self.lifetime();self.assertGreaterEqual(self.sdk.clock-at,3);self.assertEqual(first,current.state['windows'][0])
            self.assertEqual(2,len(current.state['windows']));self.assertTrue(current.state['windows'][1]['complete'])
            forged=deepcopy(current.previous);data=unpack(forged['payload'])[0]
            data['windows'][1]=deepcopy(data['windows'][0]);forged['payload']=pack([data])
            with self.assertRaises(NativeUIError):current.decode(forged)

    def test_archiving_has_no_live_factory_or_clock_and_does_not_mutate_originals(self):
        with self.lock.held():
            owner,original=self.prepare();self.restore();owner.wait_released(original);saved=deepcopy(owner.previous)
            count=len(self.web.commands)
            with patch.object(self.adapter,'normal_feature_runtime',side_effect=AssertionError('No SDK in historical archive')):
                state=IOSGraphicsLifetime.archive(owner.previous,path=owner.store.path,run=RUN,fixture_url=self.client.url,
                    provider_instance=owner.source.instance,role='primary',stage=0,binding=owner.binding)
            self.assertEqual('released',state['phase']);self.assertEqual(saved,owner.previous);self.assertEqual(count,len(self.web.commands))

    def test_immutable_original_mapping_validates_after_record_metadata_retirement(self):
        with self.lock.held():
            owner,original=self.prepare();self.restore();owner.wait_released(original)
            records={r['ordinal']:owner.record_store(r['ordinal']).read() for r in owner.state['records']}
            for n,value in records.items():owner.record_store(n).discard(value)
            self.assertTrue(all(owner.record_store(n).read() is None for n in records))
            args=dict(path=owner.store.path,run=RUN,fixture_url=self.client.url,provider_instance=owner.source.instance,
                      role='primary',stage=0,binding=owner.binding)
            archived=IOSGraphicsLifetime.archive(owner.previous,**args,records=records)
            self.assertEqual('released',archived['phase'])
            for bad in ({},{**records,999:records[1]}):
                with self.assertRaises(NativeUIError):IOSGraphicsLifetime.archive(owner.previous,**args,records=bad)
            changed=deepcopy(records);value=changed[1];rows=unpack(value['payload']);rows[0]['web']['processId']=43
            value['payload']=pack(rows)
            with self.assertRaises(NativeUIError):IOSGraphicsLifetime.archive(owner.previous,**args,records=changed)


    def test_late_passive_acquisition_cannot_return_a_fresh_admission(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare()
            self.web.after=lambda _source:self.sdk.sleep(1.6)
            with self.assertRaises(NativeUIError):owner.observe_active()
            self.assertFalse(owner.state['activeProofs']);self.assertIsNotNone(owner.state['pending'])

    def test_private_intent_failure_prevents_native_source_request(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();count=len(self.web.commands)
            with patch.object(owner.store,'write',side_effect=OSError('Synthetic intent write failure')),self.assertRaises(OSError):owner.observe_active()
            self.assertEqual(count,len(self.web.commands));self.assertIsNone(unpack(owner.previous['payload'])[0]['pending'])


class QuietIntervalTests(LifetimeHarness,unittest.TestCase):
    def test_slow_initial_absence_observation_does_not_count_as_earlier_quiet_time(self):
        with self.lock.held():
            owner,original=self.prepare();self.restore();delayed=[False];started=self.sdk.clock
            def delay(_source):
                if not delayed[0]:self.sdk.sleep(.3);delayed[0]=True
            self.web.after=delay;owner.wait_released(original);window=owner.state['windows'][-1]
            rows=[owner.load(owner.state['records'][n-1]) for n in window['samples'][window['start']:]]
            self.assertGreaterEqual(self.sdk.clock-started,3.3)
            self.assertGreaterEqual(rows[-1]['clockJoin']['hostBeforeMonotonic']-rows[0]['clockJoin']['hostAfterMonotonic'],3)
            self.assertGreaterEqual(rows[-1]['clockJoin']['nativeBefore']['capturedEpochMs']-rows[0]['clockJoin']['nativeAfter']['capturedEpochMs'],3000)

    def test_unseen_background_activation_between_samples_resets_actual_quiet(self):
        with self.lock.held():
            owner,original=self.prepare();self.restore();changed=[False];started=self.sdk.clock
            def transition(_source):
                if not changed[0] and self.sdk.clock-started>=1.5:
                    self.sdk.native_lifecycle['backgrounds']+=1;self.sdk.native_lifecycle['activations']+=1;changed[0]=True
            self.web.after=transition;owner.wait_released(original)
            self.assertTrue(changed[0]);self.assertGreater(owner.state['windows'][-1]['start'],0)
            self.assertGreaterEqual(self.sdk.clock-started,4.5)


    def test_interrupt_after_a_slow_first_sample_keeps_a_decodable_incomplete_window(self):
        with self.lock.held():
            owner,original=self.prepare();self.restore();delayed=[False]
            def delay(_source):
                if not delayed[0]:self.sdk.sleep(.3);delayed[0]=True
            self.web.after=delay
            with patch.object(owner,'sleep',side_effect=OSError('Synthetic interrupted quiet polling')),self.assertRaises(OSError):owner.wait_released(original)
            recovered=self.lifetime();self.assertEqual(0,recovered.state['windows'][-1]['elapsedMs'])
            self.assertFalse(recovered.state['windows'][-1]['complete']);self.web.after=None
            recovered.wait_released(original);self.assertEqual(2,len(recovered.state['windows']))
            self.assertTrue(recovered.state['windows'][-1]['complete'])

    def test_retiring_the_fixture_without_restoring_the_actual_world_does_not_clean_resources(self):
        with self.lock.held():
            owner,original=self.prepare();self.client.close()
            with self.assertRaises(NativeUIError):owner.wait_released(original)
            self.assertEqual(7,len(self.sdk.scene_rows));self.assertEqual('releasing',self.lifetime().state['phase'])


class RestartLifetimeHarness(RestartHarness):
    def setUp(self):
        super().setUp();self.web=WebSDK(self.sdk);self.adapter._web_closure_observer=lambda *_,**__:self.web.reader()
    def lifetime(self,stage):
        source=GraphicsFixtureReader(self.client,RUN,epoch_ms=self.sdk.host_epoch)
        return IOSGraphicsLifetime(self.adapter,'owned',source,'primary',stage,self.lock,
                                   monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def restarted(self):
        old=self.lifetime(0);restart=self.prepare();old.observe_active();original=deepcopy(self.scene().state['original']['subject'])
        restart.act(self.call());self.web=WebSDK(self.sdk);self.web.birth='f'*32
        current=self.lifetime(1);current.observe_active();return old,current,original,restart.state['receipt']
    def restored(self):
        self.client.close();scene=self.scene()
        IOSGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep).cleanup();scene.restore()


class RestartLifetimeTests(RestartLifetimeHarness,unittest.TestCase):
    def test_new_process_uses_new_originals_and_old_process_history_is_never_relabelled(self):
        with self.lock.held():
            old,current,original,receipt=self.restarted();before=deepcopy(old.previous);self.restored()
            current.wait_released(original,restart=receipt)
            self.assertEqual(43,current.pid);self.assertEqual(42,current.state['original']['subject']['processId'])
            self.assertEqual('ESRCH',current.state['original']['restart']['exit']['errorSymbol'])
            self.assertEqual(before,old.previous);self.assertEqual(before,old.store.read())
            historical=IOSGraphicsLifetime.archive(before,path=old.store.path,run=RUN,fixture_url=self.client.url,
                provider_instance=old.source.instance,role='primary',stage=0,binding=old.binding)
            self.assertEqual('ready',historical['phase'])
            oldrow=old.load(old.state['records'][0]);newrow=current.load(current.state['records'][0])
            self.assertNotEqual(oldrow['web']['instance'],newrow['web']['instance'])
            self.assertEqual(42,oldrow['web']['processId']);self.assertEqual(43,newrow['web']['processId'])
            self.assertIn('/tickets/'+TICKET+'/',newrow['web']['contexts'][0]['descriptor']['sourceUrl'])
            self.assertNotEqual(TICKET,newrow['providerAfter']['ticket'])
            self.assertEqual(1,oldrow['web']['contexts'][0]['resources']['native-view']['pending'])
            self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_old_world_original_requires_the_actual_strict_restart_receipt(self):
        with self.lock.held():
            _old,current,original,receipt=self.restarted();self.restored();before=len(self.web.commands)
            with self.assertRaises(NativeUIError):current.wait_released(original)
            bad=deepcopy(receipt);bad['exit']['presence']='present'
            with self.assertRaises(NativeUIError):current.wait_released(original,restart=bad)
            foreign=deepcopy(receipt);foreign['input']['ownerFiles'][0]=str(self.root/'foreign-scene.json')
            with self.assertRaises(NativeUIError):current.wait_released(original,restart=foreign)
            self.assertEqual(before,len(self.web.commands));self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_old_pid_is_not_substituted_with_the_replacement_pid_in_preserved_world_evidence(self):
        with self.lock.held():
            _old,current,original,receipt=self.restarted();self.restored();changed=deepcopy(original)
            changed.update(processId=self.sdk.pid,instance=self.sdk.birth)
            with self.assertRaises(NativeUIError):current.wait_released(changed,restart=receipt)
            self.assertEqual(42,original['processId']);self.assertIsNone(current.state['original'])


if __name__=='__main__':unittest.main()
