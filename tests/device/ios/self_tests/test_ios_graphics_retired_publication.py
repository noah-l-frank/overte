"""Closed journal authority retires uncertain POST responsibility without outcome."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_graphics_publisher as base


class RetiredPublicationTests(base.ObserverHarness,unittest.TestCase):
    publisher=base.GraphicsPublisherTests.publisher
    posts=base.GraphicsPublisherTests.posts
    def pending(self,committed=False):
        self.prepare();owner=self.publisher()
        def lost(original,path,value,args,kwargs):
            if committed:original(path,value,*args,**kwargs)
            raise OSError('Synthetic lost publication return')
        calls,request=self.posts(lost)
        with patch.object(self.actor_client,'request',side_effect=request),self.assertRaises(OSError):owner.publish(0)
        return owner,calls

    def test_closed_issued_post_keeps_unknown_outcome_and_never_reads_a_deleted_journal(self):
        with self.lock.held():
            owner,calls=self.pending();pending=deepcopy(owner.state['pending']);count=len(self.gpu.commands);self.client.close()
            recovered=self.publisher()
            with patch.object(self.actor_client,'observe',side_effect=AssertionError('No retired journal GET')):
                self.assertTrue(recovered.resolve())
            row=recovered.load(recovered.state['records'][-1]);self.assertEqual('run-retired',row['mode'])
            self.assertEqual(pending,row['intent']);self.assertNotIn('entry',row);self.assertNotIn('journal',row)
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual(1,len(calls));self.assertIsNone(recovered.state['pending'])

    def test_committed_but_lost_post_also_stays_unknown_when_original_journal_was_removed(self):
        with self.lock.held():
            owner,calls=self.pending(True);pending=deepcopy(owner.state['pending']);self.assertEqual(1,len(self.client.observe()['entries']))
            self.client.close();count=len(self.gpu.commands);recovered=self.publisher();self.assertTrue(recovered.retire_run())
            row=recovered.load(recovered.state['records'][-1]);self.assertEqual('run-retired',row['mode']);self.assertEqual(pending,row['intent'])
            self.assertEqual(count,len(self.gpu.commands));self.assertNotIn('entry',row);self.assertEqual(1,len(calls))

    def test_active_same_phase_cannot_authorize_retiring_the_post(self):
        with self.lock.held():
            owner,calls=self.pending();count=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):owner.retire_run()
            self.assertIsNotNone(owner.state['pending']);self.assertEqual(count,len(self.gpu.commands));self.assertEqual(1,len(calls))


    def test_never_issued_planned_post_can_retire_without_ever_sending_it(self):
        with self.lock.held():
            self.prepare();owner=self.publisher();save=owner.save
            def failed():
                if owner.state['pending'] is not None and owner.state['pending']['phase']=='issued':raise OSError('Synthetic uncommitted issue intent')
                return save()
            calls,request=self.posts(lambda original,path,value,args,kwargs:original(path,value,*args,**kwargs))
            with patch.object(owner,'save',side_effect=failed),patch.object(self.actor_client,'request',side_effect=request),self.assertRaises(OSError):owner.publish(0)
            self.assertEqual([],calls);self.client.close();count=len(self.gpu.commands);recovered=self.publisher()
            self.assertEqual('planned',recovered.state['pending']['phase']);self.assertTrue(recovered.retire_run())
            self.assertEqual('planned',recovered.load(recovered.state['records'][-1])['intent']['phase']);self.assertEqual(count,len(self.gpu.commands))

    def test_lost_committed_retirement_record_is_adopted_without_another_authority_or_post_request(self):
        with self.lock.held():
            owner,_calls=self.pending();self.client.close();write=owner.store_record
            def lost(row):write(row);raise OSError('Synthetic lost committed retirement-record return')
            with patch.object(owner,'store_record',side_effect=lost),self.assertRaises(OSError):owner.retire_run()
            pending=deepcopy(owner.state['pending']);count=len(self.gpu.commands);recovered=self.publisher()
            with patch.object(self.actor_client,'request',side_effect=AssertionError('No authority/POST replay on historical adoption')):
                self.assertTrue(recovered.retire_run())
            self.assertEqual(pending,recovered.load(recovered.state['records'][-1])['intent']);self.assertEqual(count,len(self.gpu.commands))

    def test_original_retirement_archive_survives_runtime_metadata_removal_without_native_or_http_reads(self):
        from ios.adapters.graphics_publisher import IOSGraphicsPublisher
        with self.lock.held():
            owner,_calls=self.pending();self.client.close();owner.retire_run()
            value,observer_value=deepcopy(owner.previous),deepcopy(owner.observer.previous)
            owner.store.discard(value);owner.observer.store.discard(observer_value);self.sdk.running=False;self.sdk.clock+=100
            with patch.object(self.actor_client,'request',side_effect=AssertionError('No historical HTTP read')):
                saved=IOSGraphicsPublisher.archive(value,observer_value,path=owner.observer.store.path,run=owner.run,
                    fixture_url=owner.source.client.url,provider_instance=owner.source.instance,role='actor',lock=self.lock,
                    artifact_root=owner.root,image_policy=owner.policy)
            self.assertIsNone(saved['pending']);self.assertEqual(owner.state,saved)


    def test_same_epoch_retired_provider_cannot_be_misread_as_an_old_active_floor_advancing(self):
        with self.lock.held():
            owner,_calls=self.pending();source=owner.source;before=source.status();self.client.close();closed=source.status()
            self.assertEqual(before['capturedEpochMs'],closed['capturedEpochMs']);self.assertTrue(before['active'])
            current=source.status(before);self.assertFalse(current['active']);self.assertFalse(source.previous['active'])
            self.assertTrue(before['active']);self.assertTrue(owner.retire_run())

    def test_version_one_original_published_records_remain_readable_without_rewriting_them(self):
        from adapters.native_clock_join import digest
        with self.lock.held():
            self.prepare();owner=self.publisher();owner.publish(0);ref=owner.state['records'][-1];store=owner.record_store(ref['ordinal'])
            value=store.read();old=deepcopy(value);old['iosGraphicsPublicationRecordVersion']=1;store.write(old,value)
            owner.state['records'][-1]['sha256']=digest(old);owner.save();recovered=self.publisher()
            self.assertEqual('published',recovered.load(recovered.state['records'][-1])['mode'])
            recovered.publish(0);self.assertEqual(old,store.read())
            self.assertEqual(2,recovered.record_store(2).read()['iosGraphicsPublicationRecordVersion'])

    def test_retired_run_record_cannot_be_downgraded_to_old_version_one(self):
        from adapters.native_clock_join import digest
        with self.lock.held():
            owner,_calls=self.pending();self.client.close();owner.retire_run();ref=owner.state['records'][-1]
            store=owner.record_store(ref['ordinal']);value=store.read();changed=deepcopy(value);changed['iosGraphicsPublicationRecordVersion']=1
            store.write(changed,value)
            with self.assertRaises(NativeUIError):owner.load(dict(ordinal=ref['ordinal'],sha256=digest(changed)))


if __name__=='__main__':unittest.main()
