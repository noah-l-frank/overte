"""Real original owners/PNGs and private loopback actor authority; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.witness import Client
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_observer import NavigationObserver
from ios.adapters.navigation_observation_owner import NavigationObservationOwner
from ios.adapters.navigation_places_state import bookmark_baseline
from ios.adapters.navigation_sample import NavigationSampleOwner,NavigationMarkerPending
from ios.adapters.navigation_samples import NavigationSamples
from ios.self_tests import test_ios_navigation_observation_owner as fields
from ios.self_tests import test_ios_navigation_samples as images
from self_tests import test_navigation_scene as scene
from navigation_observation import viewpoint_urls


class NavigationObserverTests(unittest.TestCase):
    activate=images.NavigationSamplesTests.activate
    def setUp(self):
        self.harness=scene.NavigationSceneTests();self.harness.setUp();self.addCleanup(self.harness.doCleanups)
        # Configure the modeled clock BEFORE the run or any original exists.
        self.now=lambda:1_000_000
        self.harness.server.journal.clock=lambda:self.now()
        self.harness.provider.clock_ms=lambda:int(self.now())
        self.run=self.harness.open();self.client=self.harness.client
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.sdk=images.SDK(self.harness,self.run);self.gpu=images.GPU(self.sdk)
        self.now=lambda:1_000_000+self.sdk.gpu.clock*1000
        self.fixture=NavigationFixtureReader(self.client,self.run,epoch_ms=lambda:int(self.now()),monotonic=lambda:self.sdk.gpu.clock)
        self.book_source=fields.BookSource(self.sdk,self.root/'bookmarks.json');self.model_source=fields.ModelSource(self.sdk)
        self.http_source=fields.HttpSource(self.sdk);self.dialog_source=fields.DialogSource(self.sdk);self.ui=fields.UI(self.sdk)
        self.reply_queries=[];self.reply_sequence=0
        def replies():
            self.sdk.gpu.clock+=.001;self.reply_sequence+=1
            return json.dumps(dict(navigationReplyVersion=1,commandId=self.reply_queries[-1]['commandId'],runId=self.run,
                instance='e'*32,sequence=self.reply_sequence,processId=42,capturedEpochMs=self.sdk.gpu.epoch(),
                currentLookupGeneration=2,currentLookupActive=False,events=[]))
        self.sources=dict(bookmarks=self.book_source.reader(),model=self.model_source.reader(),http=self.http_source.reader(),
            dialogs=self.dialog_source.reader(),ui=self.ui,replies=NativeNavigationReplies(self.reply_queries.append,replies,
                self.sdk.gpu.epoch,lambda:self.sdk.okay,42,ios=True,monotonic=lambda:self.sdk.gpu.clock,sleep=self.sdk.gpu.sleep))
        self.native=self.sdk.native();self.navigation=self.sdk.navigation.reader();self.fixture.attach()
        self.baseline=bookmark_baseline(images.BINDING,self.run,self.sources['bookmarks'].read(self.run))
        self.publisher=Client(self.client.url,self.harness.server.actor_token)

    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except BaseException as caught:error=caught
        if error is not None:raise error

    def index(self,role='actor',historical=False):
        def child(request):
            return NavigationSampleOwner(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-'+request[4:]+'-sample.json')),
                self.root,images.BINDING,self.run,role,0,request,self.lock,lambda:self.sdk.okay,native=self.sdk.native(),
                navigation=self.sdk.navigation.reader(),fixture=self.fixture,frame_factory=self.gpu.factory,sleep=self.sdk.gpu.sleep,
                monotonic=lambda:self.sdk.gpu.clock,epoch_ms=self.now)
        return NavigationSamples(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-samples.json')),
            self.root,images.BINDING,self.run,role,0,self.lock,lambda:self.sdk.okay,
            factory=None if historical else child,historical=historical)

    def observer(self,role='actor',historical=False):
        def factory(request,previous):
            return NavigationObservationOwner(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-'+request+'-observation.json')),
                self.index(role),images.BINDING,self.run,role,0,request,self.lock,lambda:self.sdk.okay,
                native=self.native,navigation=self.navigation,sources=self.sources,fixture=self.fixture,
                previous=previous,epoch_ms=self.now,monotonic=lambda:self.sdk.gpu.clock)
        return NavigationObserver(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-observer.json')),
            self.index(role,historical),factory=None if historical else factory,historical=historical,
            epoch_ms=self.now,monotonic=lambda:self.sdk.gpu.clock)

    def take(self,observer,label='A',ticket=None):
        return observer.read(ticket or self.fixture.phase.status()['activations'][-1]['ticket'],
            viewpoint_urls(self.harness.inputs['sceneUrl'])[label],label,self.now()-1,
            baseline=self.baseline,provider_inputs=self.harness.inputs)

    def test_actual_actor_originals_publish_using_separate_real_http_authority(self):
        with self.held():
            observer=self.observer();measured=self.take(observer);original=deepcopy(observer.store.read())
            self.assertEqual('A',measured['state']['location']);self.assertEqual(1,measured['sequence'])
            self.assertTrue((self.root/measured['imageName']).is_file())
            receipt=observer.publish(self.publisher)
            self.assertEqual(measured['state'],receipt['facts']);self.assertEqual(measured['capturedEpochMs'],receipt['capturedEpochMs'])
            self.assertEqual(1,len(self.client.observe()['entries']))
            self.assertEqual(original,observer.store.read());commands=deepcopy(self.gpu.commands);self.sdk.okay=False
            frozen=self.observer(historical=True);self.assertEqual(measured,frozen.latest())
            self.assertEqual(commands,self.gpu.commands)
            with self.assertRaises(NativeUIError):self.take(frozen)

    def test_primary_cannot_publish_and_wrong_requested_pose_cannot_become_facts(self):
        with self.held():
            primary=self.observer('primary');self.take(primary)
            with self.assertRaises(NativeUIError):primary.publish(self.publisher)
            actor=self.observer()
            with self.assertRaises(NativeUIError):self.take(actor,label='B')
            self.assertEqual('reserved',actor.state['rows'][-1]['status']);self.assertEqual(1,self.gpu.frames)
            self.assertEqual([],self.client.observe()['entries'])

    def test_lost_publication_return_is_resolved_from_actual_journal_without_second_post(self):
        with self.held():
            observer=self.observer();measured=self.take(observer);request=self.publisher.request;posts=[]
            def lost(path,value=None,**kwargs):
                result=request(path,value,**kwargs)
                if path.endswith('/samples'):posts.append(path);raise OSError('Synthetic lost publication return')
                return result
            self.publisher.request=lost
            with self.assertRaises(OSError):observer.publish(self.publisher)
            saved=deepcopy(observer.store.read());again=self.observer()
            with self.assertRaises(NativeUIError):self.take(again)
            self.assertEqual(saved,again.store.read());self.assertEqual(1,len(posts))
            receipt=again.confirm_publication(self.publisher);self.assertEqual(measured['state'],receipt['facts'])
            self.assertEqual(receipt,again.publish(self.publisher))
            self.assertEqual(1,len(posts));self.assertEqual(1,len(self.client.observe()['entries']))

    def test_lost_final_acquisition_return_adopts_originals_but_never_makes_them_fresh(self):
        with self.held():
            observer=self.observer();write=observer.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['sequence']==1:raise OSError('Synthetic lost observer return')
                write(value,previous)
            observer.store.write=lost
            with self.assertRaises(OSError):self.take(observer)
            commands=deepcopy(self.gpu.commands);reads=self.ui.reads;self.sdk.gpu.sleep(5.)
            again=self.observer();old=again.recover();self.assertEqual('A',old['state']['location'])
            self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)
            with self.assertRaises(NativeUIError):again.publish(self.publisher)
            self.assertEqual([],self.client.observe()['entries'])

    def test_interrupted_sources_require_explicit_local_abandonment_then_new_identity(self):
        with self.held():
            observer=self.observer();self.ui.fail=True
            with self.assertRaises(OSError):self.take(observer)
            saved=deepcopy(observer.store.read());self.ui.fail=False
            again=self.observer()
            with self.assertRaises(NativeUIError):self.take(again)
            self.assertEqual(saved,again.store.read());again.recover(abandon_sources=True)
            first=again.state['rows'][0]['requestId'];self.assertEqual('failed',again.state['rows'][0]['status'])
            measured=self.take(again);self.assertNotEqual(first,measured['requestId'])
            self.assertEqual(1,measured['sequence']);self.assertEqual(2,self.gpu.frames)

    def test_pending_marker_retains_originals_and_cannot_be_published(self):
        with self.held():
            observer=self.observer();self.gpu.marker='c'*32
            with self.assertRaises(NavigationMarkerPending):self.take(observer)
            self.assertEqual('marker-pending',observer.state['rows'][0]['status'])
            with self.assertRaises(NativeUIError):observer.publish(self.publisher)
            self.gpu.marker=self.fixture.phase.status()['activations'][-1]['ticket'];self.assertEqual(1,self.take(observer)['sequence'])

    def test_missing_or_changed_sealed_image_archive_never_borrows_embedded_original(self):
        with self.held():
            observer=self.observer();self.take(observer);owner=observer.owners()[-1]
            store=owner.images.archive_store(owner.state['imageRow']);value=store.read();store.discard(value)
            with self.assertRaises(NativeUIError):observer.latest()

    def test_slow_publication_journal_blocks_send_after_durable_intent_without_restamping(self):
        with self.held():
            observer=self.observer();measured=self.take(observer);publisher=observer.publisher(self.publisher);write=publisher.store.write
            def slow(value,previous):
                result=write(value,previous);pending=unpack(value['payload'])[0]['pending']
                if pending is not None and pending['phase']=='issued':self.sdk.gpu.sleep(2.)
                return result
            publisher.store.write=slow
            with patch.object(observer,'publisher',return_value=publisher),self.assertRaises(NativeUIError):observer.publish(self.publisher)
            state=observer.publication_state();self.assertEqual('issued',state['pending']['phase'])
            self.assertEqual(measured['capturedEpochMs'],state['pending']['body']['capturedEpochMs'])
            self.assertEqual([],self.client.observe()['entries'])

    def test_changed_memory_or_foreign_journal_client_cannot_supply_an_original(self):
        with self.held():
            observer=self.observer();self.take(observer);observer.state['rows'][0]['sequence']=2
            with self.assertRaises(NativeUIError):observer.latest()
            observer=self.observer();observer.publish(self.publisher)
            foreign=Client('http://127.0.0.1:1/feature-fixture/v1','x'*32)
            foreign.request=lambda *_args,**_kwargs:(_ for _ in ()).throw(AssertionError('Foreign client must not be read'))
            with self.assertRaises(NativeUIError):observer.confirm_publication(foreign)

    def test_later_publication_keeps_prior_body_receipt_sequence_and_original_clock(self):
        with self.held():
            observer=self.observer();first=self.take(observer);observer.publish(self.publisher)
            prior=deepcopy(observer.publication_state()['records']);self.activate('c'*32,'B')
            second=self.take(observer,'B','c'*32);observer.publish(self.publisher)
            self.assertEqual(2,second['sequence']);self.assertEqual(prior,observer.publication_state()['records'][:1])
            publisher=observer.publisher(self.publisher);records=publisher.state['records']
            self.assertEqual(first['capturedEpochMs'],publisher.load(records[0])['intent']['body']['capturedEpochMs'])
            self.assertEqual('B',publisher.load(records[1])['intent']['body']['facts']['location'])
            self.assertEqual([1,2],[row['actorSequence'] for row in self.client.observe()['entries']])
            self.assertEqual(second,self.observer(historical=True).latest())


if __name__=='__main__':unittest.main()
