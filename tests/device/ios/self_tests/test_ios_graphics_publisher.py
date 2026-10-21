"""Original actor publication on real loopback journals and synthetic iOS SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack
from ios.adapters.graphics_fixture import GraphicsPhasePending
from ios.adapters.graphics_observer import IOSGraphicsObserver
from ios.adapters.graphics_publisher import IOSGraphicsPublisher
from ios.self_tests.test_ios_graphics_observer import ObserverHarness
from ios.self_tests.test_ios_graphics_scene import RUN
from ios.self_tests.test_ios_graphics_samples import POLICY


class GraphicsPublisherTests(ObserverHarness, unittest.TestCase):
    def publisher(self):return IOSGraphicsPublisher(self.observer('actor'))
    def posts(self, method):
        original = self.actor_client.request; calls = []
        def request(path, value=None, *args, **kwargs):
            if path.endswith('/samples'):
                calls.append(deepcopy(value)); return method(original, path, value, args, kwargs)
            return original(path, value, *args, **kwargs)
        return calls, request
    def passed(self, original, path, value, args, kwargs):return original(path, value, *args, **kwargs)

    def test_original_frame_is_independently_read_back_from_server_before_publication_completes(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher(); calls, request = self.posts(self.passed)
            with patch.object(self.actor_client, 'request', side_effect=request):sequence = publisher.publish(0)
            self.assertEqual(1, sequence); self.assertEqual(1, len(calls)); self.assertIsNone(publisher.state['pending'])
            row = publisher.load(publisher.state['records'][0]); entry = self.client.observe()['entries'][-1]
            self.assertEqual(entry, row['entry']); self.assertEqual('published', row['mode'])
            self.assertEqual(calls[0], row['intent']['body']); self.assertEqual(entry, row['journal']['entries'][-1])
            self.assertEqual(row['intent']['value']['capturedEpochMs'], entry['capturedEpochMs'])

    def test_lost_committed_post_is_resolved_by_original_journal_without_post_or_capture_redelivery(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher()
            def lost(original, path, value, args, kwargs):
                original(path, value, *args, **kwargs); raise OSError('Synthetic lost committed POST return')
            calls, request = self.posts(lost)
            with patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            packet = deepcopy(publisher.state['pending']); self.assertEqual('issued', packet['phase'])
            captures = len(self.gpu.commands); recovered = self.publisher()
            calls2, request2 = self.posts(self.passed)
            with patch.object(self.actor_client, 'request', side_effect=request2):self.assertTrue(recovered.resolve())
            self.assertEqual(1, len(calls)); self.assertEqual([], calls2); self.assertEqual(captures, len(self.gpu.commands))
            self.assertEqual(packet, recovered.load(recovered.state['records'][0])['intent'])
            self.assertIsNone(recovered.state['pending'])

    def test_lost_uncommitted_post_remains_issued_and_blocks_all_same_phase_capture_or_redelivery(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher()
            def lost(*_args):raise OSError('Synthetic POST not delivered')
            calls, request = self.posts(lost)
            with patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            captures = len(self.gpu.commands); pending = deepcopy(publisher.state['pending'])
            recovered = self.publisher(); calls2, request2 = self.posts(self.passed)
            with patch.object(self.actor_client, 'request', side_effect=request2), self.assertRaises(GraphicsPhasePending):recovered.publish(0)
            self.assertEqual(1, len(calls)); self.assertEqual([], calls2); self.assertEqual(captures, len(self.gpu.commands))
            self.assertEqual(pending, recovered.state['pending']); self.assertEqual([], self.client.observe()['entries'])

    def test_ack_without_actual_journal_entry_cannot_complete_publication(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher(); calls, request = self.posts(lambda *_:dict(performed=True))
            with patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(GraphicsPhasePending):publisher.publish(0)
            self.assertEqual(1, len(calls)); self.assertEqual([], publisher.state['records'])
            self.assertEqual('issued', publisher.state['pending']['phase'])

    def test_phase_crossing_retires_uncertain_publication_without_publishing_old_facts(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher()
            def lost(*_args):raise OSError('Synthetic uncommitted POST')
            calls, request = self.posts(lost)
            with patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            old = deepcopy(publisher.state['pending']); self.client.activate('f'*32, 'cleanup', {}); self.gpu.marker = 'f'*32
            recovered = self.publisher(); before = len(self.gpu.commands); self.assertTrue(recovered.resolve())
            row = recovered.load(recovered.state['records'][0]); self.assertEqual('phase-retired', row['mode'])
            self.assertIsNone(row['entry']); self.assertEqual(old, row['intent']); self.assertEqual(before, len(self.gpu.commands))
            self.assertEqual([], self.client.observe()['entries']); self.assertEqual(1, len(calls))

    def test_failed_issue_intent_can_retire_only_on_real_later_phase_and_never_sends_post(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher(); actual = publisher.save
            def failed_issue():
                if publisher.state['pending'] is not None and publisher.state['pending']['phase'] == 'issued':
                    raise OSError('Synthetic issue intent not committed')
                return actual()
            calls, request = self.posts(self.passed)
            with patch.object(publisher, 'save', side_effect=failed_issue), patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            self.assertEqual([], calls); recovered = self.publisher(); self.assertEqual('planned', recovered.state['pending']['phase'])
            self.client.activate('e'*32, 'cleanup', {}); self.gpu.marker = 'e'*32
            self.assertTrue(recovered.resolve()); self.assertEqual('phase-retired', recovered.load(recovered.state['records'][0])['mode'])
            self.assertEqual([], self.client.observe()['entries'])

    def test_lost_committed_receipt_return_adopts_original_record_without_second_post_or_journal_read(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher(); actual = publisher.store_record
            def lost(row):
                actual(row); raise OSError('Synthetic lost publication receipt return')
            calls, request = self.posts(self.passed)
            with patch.object(publisher, 'store_record', side_effect=lost), patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            captures = len(self.gpu.commands); recovered = self.publisher()
            with patch.object(self.actor_client, 'observe', side_effect=AssertionError('No second journal read')):self.assertTrue(recovered.resolve())
            self.assertEqual(1, len(calls)); self.assertEqual(captures, len(self.gpu.commands)); self.assertEqual(1, len(recovered.state['records']))

    def test_changed_requested_facts_in_private_intent_are_rejected_from_original_pixels_and_state(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher()
            def lost(*_args):raise OSError('Synthetic uncommitted POST')
            calls, request = self.posts(lost)
            with patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            value = deepcopy(publisher.previous); state = unpack(value['payload'])[0]
            state['pending']['body']['facts']['resolution'] = .5; value['payload'] = pack([state])
            publisher.store.write(value, publisher.previous); captures = len(self.gpu.commands)
            with self.assertRaises(NativeUIError):self.publisher()
            self.assertEqual(captures, len(self.gpu.commands)); self.assertEqual(1, len(calls))

    def test_foreign_or_stale_journal_receipt_cannot_resolve_original_post(self):
        with self.lock.held():
            self.prepare(); publisher = self.publisher()
            def lost(original, path, value, args, kwargs):
                original(path, value, *args, **kwargs); raise OSError('Synthetic lost committed POST')
            calls, request = self.posts(lost)
            with patch.object(self.actor_client, 'request', side_effect=request), self.assertRaises(OSError):publisher.publish(0)
            actual = self.actor_client.observe
            for fault in ('foreign', 'stale', 'facts'):
                journal = deepcopy(actual())
                if fault == 'foreign':journal['runId'] = 'd'*32
                elif fault == 'stale':journal['sampleEpochMs'] -= 10000
                else:journal['entries'][-1]['facts']['haze'] = True
                recovered = self.publisher()
                with self.subTest(fault=fault), patch.object(self.actor_client, 'observe', return_value=journal), self.assertRaises(NativeUIError):recovered.resolve()
                self.assertIsNotNone(recovered.state['pending']); self.assertFalse(recovered.state['records'])

    def test_changed_provider_or_slow_receipt_lookup_keeps_the_issued_post_owned(self):
        with self.lock.held():
            self.prepare();publisher=self.publisher()
            def lost(original,path,value,args,kwargs):
                original(path,value,*args,**kwargs);raise OSError('Synthetic lost committed POST')
            _calls,request=self.posts(lost)
            with patch.object(self.actor_client,'request',side_effect=request),self.assertRaises(OSError):publisher.publish(0)
            recovered=self.publisher();actual=self.actor_client.observe
            def slow():
                value=actual();self.sdk.clock+=1.6;return value
            with patch.object(self.actor_client,'observe',side_effect=slow),self.assertRaises(NativeUIError):recovered.resolve()
            self.assertIsNotNone(recovered.state['pending']);self.assertFalse(recovered.state['records'])
            recovered=self.publisher();status=self.actor_client.graphics_status
            def foreign(*args,**kwargs):
                value=status(*args,**kwargs);value['instance']='f'*32;return value
            with patch.object(self.actor_client,'graphics_status',side_effect=foreign),self.assertRaises((NativeUIError,ValueError)):recovered.resolve()
            self.assertIsNotNone(recovered.state['pending']);self.assertFalse(recovered.state['records'])

    def test_publication_archive_remains_historical_after_runtime_metadata_and_sdk_retirement(self):
        with self.lock.held():
            self.prepare();publisher=self.publisher();publisher.publish(0)
            value,observed=deepcopy(publisher.previous),deepcopy(publisher.observer.previous)
            publisher.store.discard(value);publisher.observer.store.discard(observed);self.sdk.clock+=100
            with patch.object(self.adapter,'normal_feature_runtime',side_effect=AssertionError('No live SDK')):
                saved=IOSGraphicsPublisher.archive(value,observed,path=publisher.observer.store.path,run=RUN,
                    fixture_url=self.client.url,provider_instance=publisher.source.instance,role='actor',lock=self.lock,
                    artifact_root=self.root/'pixels',image_policy=POLICY)
            self.assertEqual(publisher.state,saved);self.assertIsNone(publisher.store.read())
            self.assertIsNone(publisher.observer.store.read());self.assertIsNone(saved['pending'])
            self.assertLess(publisher.load(saved['records'][0])['journal']['sampleEpochMs'],self.sdk.host_epoch())

    def test_observer_archive_validates_original_bytes_after_metadata_removal_without_live_sdk(self):
        with self.lock.held():
            self.prepare(); observer = self.observer('actor'); observer.read(0, 0); original = deepcopy(observer.previous)
            args = dict(path=observer.store.path, run=RUN, fixture_url=self.client.url, provider_instance=observer.source.instance,
                        role='actor', lock=self.lock, artifact_root=self.root/'pixels', image_policy=POLICY)
            observer.store.discard(observer.previous)
            with patch.object(self.adapter, 'normal_feature_runtime', side_effect=AssertionError('No live SDK')):
                saved = IOSGraphicsObserver.archive(original, **args)
            self.assertEqual(observer.state, saved); self.assertIsNone(observer.store.read())
            ref = saved['last']; self.sdk.clock += 100
            self.assertEqual(saved, IOSGraphicsObserver.archive(original, **args))
            scope = IOSGraphicsObserver._archive_scope(original, **args)
            with self.assertRaises(NativeUIError):scope.save()
            frame, _raw, _actual, name = scope.frame(ref, saved['binding']); path = self.root/'pixels'/name
            path.write_bytes(b'Changed original PNG')
            with self.assertRaises(NativeUIError):IOSGraphicsObserver.archive(original, **args)


if __name__ == '__main__':unittest.main()
