"""Actual native/model/widget samplers and immutable postlogout source files.

Native product packets are explicit producers. Host source ownership, HTTP/AFC
widget transport and historical validation use the implementation under test.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_scripts,avatar_social_http,people_model,normal_input,world_web_keys
from ios.adapters.native_geometry import OriginalGeometry
from ios.self_tests.test_ios_world_web_keys import QtKeys
from ios.adapters.avatar_code import pins
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from feature_journeys.witness import Client
from ios.self_tests import test_ios_avatar_postlogout_reads as fixture
from ios.self_tests.test_ios_avatar_ui_inventory import row as root_row


class AvatarPostLogoutTailTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarPostLogoutReadsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.store=PrivateFeatureState(self.f.root/'ios-avatar-actor-primary-postlogout-tail.json');self.roots=[];self.channel_calls=[];self.lost=False;self.keys=QtKeys();self.geometry_sequence=0;self.geometry_value=None;self.keyboard=False;self.inset=0
        f=self.f.f;worker=f.prototypes['scripts']['source']['workers'][0];worker['avatar']['events']=[]
        worker['avatar']['code']=[dict(sequence=index,url='qrc:/scripts'+suffix,submittedEpochMs=1700000000000+index,
            encoding='utf-16le-code-units',**pin) for index,(suffix,pin) in enumerate(pins().items(),1)]
        worker['uiWork']=dict(avatarUiWorkVersion=1,instance='f'*32,complete=True,timers=[])
        self.baseline={name:f.reader(name,kind).read(f.run) for name,kind in dict(scripts=avatar_scripts.IOSAvatarScripts,http=avatar_social_http.IOSAvatarSocialHttp).items()}
        owned=self.f.owned
        def admit(query):
            raw=self.store.read()
            if raw is not None:
                p=__import__('adapters.script_feature.history',fromlist=['unpack']).unpack(raw['payload'])[0]['pending']
                if p is not None and query in [row['query'] for row in p['nativeQueries']]:return
            owned(query)
        self.f.owned=admit
        widget=f.widget;widget.shown=False;observed=widget.observed
        def snapshot():
            raw=observed();raw.update(sampleEpochMs=f.now(),elapsedMs=round(f.clock*1000),avatarInventory=dict(iosAvatarUiInventoryVersion=1,complete=True,roots=deepcopy(self.roots)))
            return raw
        widget.observed=snapshot;post=widget.post
        def transport(request,timeout):
            q=json.loads(request.data);p=__import__('adapters.script_feature.history',fromlist=['unpack']).unpack(self.store.read()['payload'])[0]['pending']
            self.assertEqual(q,p['widgetsQuery']);self.assertEqual('observe',q['operation']);return post(request,timeout)
        boundary=patch.object(normal_input,'urlopen',transport);boundary.start();self.addCleanup(boundary.stop)

    def factory(self):
        f=self.f.f;_native,clock=self.f.native_parts()
        def reader(name,kind,given):
            self.assertIs(clock,given);r=f.reader(name,kind);r.clock_ms=lambda:clock.read(clock.sequence)['capturedEpochMs'];send=r.send
            def sending(q):
                p=__import__('adapters.script_feature.history',fromlist=['unpack']).unpack(self.store.read()['payload'])[0]['pending'];self.assertEqual(q,p['queries'][name])
                self.channel_calls.append(deepcopy(q));send(q)
                if self.lost:raise OSError('Lost original passive Pal/Avatar source return')
            r.send=sending;return r
        def key_source(given):
            self.assertIs(clock,given)
            def tick():f.tick();self.keys.epoch=100000+round(f.clock*1000);return self.keys.epoch
            self.keys.tick=tick
            def send(q):
                p=__import__('adapters.script_feature.history',fromlist=['unpack']).unpack(self.store.read()['payload'])[0]['pending']
                self.assertEqual(q,p['queries']['keys']);self.channel_calls.append(deepcopy(q));packet=self.keys.packet()
                def actual(value):
                    if type(value) is dict:return {k:v+1699999900000 if (k.endswith('EpochMs') or k=='epochMs') and type(v) is int and v else actual(v) for k,v in value.items()}
                    if type(value) is list:return [actual(v) for v in value]
                    return value
                packet=actual(packet)
                packet.update(requestId=q['commandId'],runId=q['runId']);self.keys_value=packet
            return world_web_keys.IOSWorldWebKeys(send,lambda:json.dumps(self.keys_value),lambda:clock.read(clock.sequence)['capturedEpochMs'],lambda:True,42,
                monotonic=lambda:f.clock,sleep=f.sleep)
        def geometry_source():
            def send(q):
                p=__import__('adapters.script_feature.history',fromlist=['unpack']).unpack(self.store.read()['payload'])[0]['pending']
                self.assertEqual(q,p['geometryQuery']);f.tick();self.geometry_sequence+=1
                self.geometry_value=dict(schemaVersion=1,commandId=q['commandId'],observation=dict(schemaVersion=1,sampleEpochMs=f.now(),sampleSequence=self.geometry_sequence,
                    nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20,
                        keyboardVisible=self.keyboard,imeInsetBottom=self.inset),window=dict(width=1024,height=728)))
            return OriginalGeometry(send,lambda:json.dumps(self.geometry_value),lambda:clock.read(clock.sequence)['capturedEpochMs'],lambda:True,
                monotonic=lambda:f.clock,sleep=f.sleep)
        observer=SimpleNamespace(world_web_keys=key_source,geometry=geometry_source,avatar_scripts=lambda given:reader('scripts',avatar_scripts.IOSAvatarScripts,given),
            avatar_social_http=lambda given:reader('http',avatar_social_http.IOSAvatarSocialHttp,given),
            people_model=lambda given:reader('people',people_model.IOSPeopleModel,given))
        widgets=normal_input.NativeInput(f.widget,'owned-session',f.widget.target,f.widget.process,
            native_epoch_ms=lambda:clock.read(clock.sequence)['capturedEpochMs'],monotonic=lambda:f.clock,sleep=f.sleep)
        return dict(binding=fixture.BINDING,clock_source=clock,observer=observer,native=widgets)

    def owner(self,kind=IOSAvatarPostLogoutTail):
        f=self.f
        return kind(self.store,f.artifacts,fixture.BINDING,f.f.run,'actor','primary',f.lock,lambda:True,self.factory,
            child_run=f.child,fixture_url='https://controlled.invalid/feature-fixture/v1/runs/'+f.child+'/',ticket=f.ticket,
            baseline=self.baseline,logout_before=f.logout_before,epoch_ms=f.f.host,monotonic=lambda:f.f.clock)

    def archive(self,owner):
        f=self.f
        return IOSAvatarPostLogoutTail.archive(owner.previous,store=self.store,root=f.artifacts,binding=fixture.BINDING,run=f.f.run,role='actor',subject='primary',
            lock=f.lock,child_run=f.child,fixture_url='https://controlled.invalid/feature-fixture/v1/runs/'+f.child+'/',ticket=f.ticket,
            baseline=self.baseline,logout_before=f.logout_before)

    def test_closed_postlogout_sources_keep_actual_queries_and_pure_historical_proof(self):
        owner=self.owner();row=owner.capture();proof=owner.proof(row);requests=deepcopy(self.f.calls);channels=deepcopy(self.channel_calls)
        archived=self.archive(owner);self.assertEqual(proof,archived.proof(archived.state['rows'][0]))
        for action in (archived.capture,archived.recover,archived.save):
            with self.assertRaises(NativeUIError):action()
        self.assertEqual(requests,self.f.calls);self.assertEqual(channels,self.channel_calls)
        self.assertGreaterEqual(len(owner.record(row['reference'])['nativeQueries']),9)

    def test_unknown_source_is_abandoned_before_distinct_passive_query_without_input(self):
        owner=self.owner();self.lost=True
        with self.assertRaises(NativeUIError):owner.capture()
        before=deepcopy(self.channel_calls);self.lost=False;again=self.owner();again.recover();self.assertEqual(before,self.channel_calls)
        row=again.capture();self.assertNotEqual(before[0]['commandId'],again.record(row['reference'])['queries']['scripts']['commandId'])
        self.assertEqual(1,self.channel_calls.count(before[0]))

    def test_actual_retained_hidden_root_blocks_proof_but_original_remains_before_later_distinct_read(self):
        self.roots=[root_row()];owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture()
        original=deepcopy(owner.state['rows'][0]);raw=owner.file(1).path.read_bytes();self.roots=[];again=self.owner();later=again.capture();again.proof(later)
        with self.assertRaises(NativeUIError):again.proof(again.state['rows'][0])
        self.assertEqual(raw,owner.file(1).path.read_bytes());self.assertNotEqual(original['reference'],later['reference'])

    def test_completed_and_abandoned_widgets_keep_actual_elapsed_input_and_read_prefixes(self):
        owner=self.owner();row=owner.capture();prior=owner.record(row['reference'])
        actual=self.f.f.widget;observed=actual.observed
        def widgets():
            value=observed();value.update(placesControlsVersion=1,placesSourceSequence=value['avatarSourceSequence'],
                navigationDialogControlsVersion=1,navigationDialogSourceSequence=value['avatarSourceSequence'])
            return value
        actual.observed=widgets
        # Losing the bracket return after the original widget response leaves
        # that exact response durably owned by an abandoned acquisition.
        write=self.store.write;lost=[]
        def saving(value,previous):
            write(value,previous);p=owner.state['pending']
            if p is not None and p['widgetsReceipt'] is not None and not lost:
                lost.append(True);raise OSError('Lost durable widget response return')
        with patch.object(self.store,'write',side_effect=saving),self.assertRaises(OSError):owner.capture()
        again=self.owner();again.recover();partial=again.state['rows'][-1]['partial'];before=deepcopy(self.channel_calls)
        actual.sequence+=2;next_row=again.capture();current=again.record(next_row['reference'])
        self.assertNotEqual(partial['widgetsQuery']['commandId'],current['widgetsQuery']['commandId'])
        self.assertEqual(before,self.channel_calls[:len(before)])
        for key in ('elapsedMs','lastSequence','avatarSourceSequence','placesSourceSequence','navigationDialogSourceSequence'):
            altered=deepcopy(current);altered['widgetsReceipt']['observation'][key]=partial['widgetsReceipt']['observation'][key]-(1 if key in ('elapsedMs','lastSequence') else 0)
            with self.subTest(key=key),self.assertRaises(NativeUIError):again.floors(partial,altered)
        for key in ('elapsedMs','lastSequence','avatarSourceSequence'):
            altered=deepcopy(current);altered['widgetsReceipt']['observation'][key]=prior['widgetsReceipt']['observation'][key]-(1 if key in ('elapsedMs','lastSequence') else 0)
            with self.subTest(completed=key),self.assertRaises(NativeUIError):again.widget_prefix(prior['widgetsReceipt']['observation'],altered['widgetsReceipt']['observation'])

    def test_writer2_actual_held_key_and_unreturned_release_block_until_original_finally(self):
        owner=self.owner();first=owner.capture();self.assertEqual(2,owner.proof(first)['iosAvatarPostLogoutTailProofVersion'])
        self.keys.finish(self.keys.enter('key-press'))
        with self.assertRaises(NativeUIError):owner.capture()
        held=deepcopy(owner.state['rows'][-1]);release=self.keys.enter('key-release')
        with self.assertRaises(NativeUIError):owner.capture()
        self.keys.finish(release);row=owner.capture();self.assertEqual([],owner.proof(row)['keys']['down'])
        with self.assertRaises(NativeUIError):owner.proof(held)

    def test_actual_uikit_keyboard_visibility_and_ime_inset_are_separate_from_empty_key_arguments(self):
        owner=self.owner();self.keyboard=True
        with self.assertRaises(NativeUIError):owner.capture()
        old=deepcopy(owner.state['rows'][-1]);self.keyboard=False;self.inset=200
        with self.assertRaises(NativeUIError):owner.capture()
        self.inset=0;row=owner.capture();owner.proof(row)
        with self.assertRaises(NativeUIError):owner.proof(old)

    def test_large_original_key_carrier_is_private_raw_file_without_raising_metadata_limits(self):
        actual=self.factory();actual['observer'].world_web_keys(actual['clock_source'])
        for _ in range(240):self.keys.finish(self.keys.enter('key-press'));self.keys.finish(self.keys.enter('key-release'))
        owner=self.owner();row=owner.capture();record=owner.record(row['reference']);raw=owner.key_raw(record['keys'])
        self.assertGreater(len(raw['raw'].encode()),400000);self.assertEqual(480,len(owner.proof(row)['keys']['dispatches']))
        self.assertLess(self.store.path.stat().st_size,65536);self.assertLess(owner.file(row['index']).path.stat().st_size,65536)

    def test_actual_three_channel_legacy_original_stays_byte_exact_and_never_claims_keyboard(self):
        from ios.self_tests.avatar_postlogout_tail_v1_producer import Tail1Producer
        legacy=self.owner(Tail1Producer);first=legacy.capture();metadata=self.store.path.read_bytes();original=legacy.file(1).path.read_bytes()
        self.assertEqual(1,legacy.previous['iosAvatarPostLogoutTailVersion'])
        archived=self.archive(legacy);proof=archived.proof(archived.state['rows'][0])
        self.assertEqual(1,proof['iosAvatarPostLogoutTailProofVersion']);self.assertNotIn('keys',proof)
        self.assertEqual(metadata,self.store.path.read_bytes());self.assertEqual(original,legacy.file(1).path.read_bytes())
        current=self.owner();second=current.capture();self.assertEqual(2,current.previous['iosAvatarPostLogoutTailVersion'])
        self.assertEqual(2,current.proof(second)['iosAvatarPostLogoutTailProofVersion'])
        self.assertEqual(1,current.proof(first)['iosAvatarPostLogoutTailProofVersion'])
        self.assertEqual(original,legacy.file(1).path.read_bytes())

    def test_exhausted_raw_carrier_capacity_fails_before_any_next_native_query(self):
        owner=self.owner();queries=deepcopy(self.f.calls)
        with patch.object(owner,'next_key_index',return_value=1024),self.assertRaises(NativeUIError):owner.capture()
        self.assertIsNone(owner.state['pending']);self.assertEqual(queries,self.f.calls);self.assertEqual([],self.channel_calls)

    def test_unsafe_legacy_fixed_file_never_creates_a_host_raw_artifact_or_resends(self):
        from ios.self_tests.test_ios_world_web_keys import LegacyQtKeys
        self.keys=LegacyQtKeys();self.keys.finish(self.keys.enter('input-method',commit='fixture-private-login-example'))
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture()
        original=deepcopy(owner.state['pending']['queries']['keys'])
        self.assertEqual([],owner.state['pending']['keyRaws']);self.assertEqual([],list(self.f.artifacts.glob('avatar-primary-keys-frame-*.json')))
        self.assertNotIn('fixture-private-login-example',self.store.path.read_text())
        self.keys=QtKeys();again=self.owner();before=deepcopy(self.channel_calls);again.recover();self.assertEqual(before,self.channel_calls)
        row=again.capture();self.assertEqual(2,again.proof(row)['keys']['iosWorldWebKeySourceVersion'])
        self.assertEqual(1,self.channel_calls.count(original));self.assertNotEqual(original['commandId'],again.record(row['reference'])['queries']['keys']['commandId'])

    def test_lost_saved_key_original_never_resends_and_remains_an_actual_source_floor(self):
        owner=self.owner();callback=owner.key_originals.originals.intent;lost=[]
        def saved(kind,value):
            callback(kind,value)
            if value['phase']=='saved' and not lost:lost.append(True);raise OSError('Lost immutable key carrier return')
        owner.key_originals.originals.intent=saved
        with self.assertRaises(NativeUIError):owner.capture()
        before=deepcopy(self.channel_calls);again=self.owner();again.recover();self.assertEqual(before,self.channel_calls)
        self.keys.sequence=0
        with self.assertRaises(NativeUIError):again.capture()
        again=self.owner();again.recover();self.keys.sequence=max(1,self.keys.sequence);row=again.capture();again.proof(row)
        original=before[-1];self.assertEqual(world_web_keys.ACTION,original['action']);self.assertEqual(1,self.channel_calls.count(original))
        self.assertNotEqual(original['commandId'],again.record(row['reference'])['queries']['keys']['commandId'])

    def test_actual_runtime_factory_keeps_sdk_binding_and_existing_passive_transports(self):
        fixture=self
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,_selector):return fixture.f.root/'session.json'
            def _sources(_self,_selector):
                actual=fixture.factory();actual.update(check=lambda:True,target=dict(testBuild=dict(launchEnvironment=dict(HIFI_METAVERSE_URL='https://controlled.invalid'))))
                return actual
        runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True));f=self.f
        owner=runtime._avatar_postlogout_tail('target',Client('https://controlled.invalid/feature-fixture/v1','r'*64),f.f.run,'actor','primary',f.artifacts,f.lock,
            child_run=f.child,ticket=f.ticket,baseline=self.baseline,logout_before=f.logout_before,epoch_ms=f.f.host,monotonic=lambda:f.f.clock)
        self.assertEqual([],owner.proof(owner.capture())['ownedHttp'])

    def test_slow_final_metadata_save_preserves_history_but_cannot_freshly_return_it(self):
        owner=self.owner();write=self.store.write
        def slow(value,previous):
            write(value,previous)
            if owner.state['rows'] and owner.state['pending'] is None:self.f.f.clock+=1.501
        with patch.object(self.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.capture()
        before=deepcopy(self.channel_calls);archive=self.archive(self.owner());archive.proof(archive.state['rows'][0]);self.assertEqual(before,self.channel_calls)

    def test_lost_completed_local_record_return_is_adopted_without_a_source_request(self):
        owner=self.owner();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            write(store,value,previous)
            if store.path==owner.file(1).path and not lost:lost.append(True);raise OSError('Lost immutable tail original return')
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):owner.capture()
        requests=deepcopy(self.f.calls);channels=deepcopy(self.channel_calls);again=self.owner();row=again.recover();again.proof(row)
        self.assertEqual(requests,self.f.calls);self.assertEqual(channels,self.channel_calls)


if __name__=='__main__':unittest.main()
