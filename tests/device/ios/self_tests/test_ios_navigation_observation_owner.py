"""Real private PNG/metadata/loopback ownership, with native/SDK ports modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid

from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters import normal_input
from ios.adapters.navigation_observation_owner import NavigationObservationOwner
from ios.adapters.navigation_places_state import bookmark_baseline
from ios.adapters.navigation_sample import NavigationMarkerPending
from ios.self_tests import test_ios_navigation_samples as image_tests
from ios.self_tests.test_ios_location_bookmarks import Boundary as Books
from ios.self_tests.test_ios_places_model import Boundary as Model
from ios.self_tests.test_ios_places_http import Boundary as Http
from ios.self_tests.test_ios_navigation_dialogs import Boundary as Dialogs
from ios.self_tests.test_ios_places_settings import original_preferences
from ios.self_tests.test_ios_navigation_ui import observed
from navigation_observation import viewpoint_urls


class SharedClock:
    @property
    def clock(self):return self.sdk.gpu.clock
    @clock.setter
    def clock(self,value):self.sdk.gpu.clock=value
    def epoch(self):return self.sdk.gpu.epoch()


class BookSource(SharedClock,Books):
    def __init__(self,sdk,path):
        self.sdk=sdk;super().__init__(path)
        self.mutate=lambda value:value.update(runId=self.requests[-1]['runId'])


class ModelSource(SharedClock,Model):
    def __init__(self,sdk):
        self.sdk=sdk;super().__init__();self.pages=[];self.shown=False
        self.mutate=lambda value:value.update(runId=self.requests[-1]['runId'],iosPlacesModelVersion=2,preferences=original_preferences())


class HttpSource(SharedClock,Http):
    def __init__(self,sdk):self.sdk=sdk;super().__init__()


class DialogSource(SharedClock,Dialogs):
    def __init__(self,sdk):self.sdk=sdk;super().__init__()


class UI(normal_input.NativeInput):
    """SDK original snapshot generation, with ordinary inputs unavailable."""
    def __init__(self,sdk):self.sdk=sdk;self.sequence=0;self.reads=0;self.fail=False
    def capture(self):
        self.reads+=1
        if self.fail:raise OSError('Synthetic lost observation response')
        self.sdk.gpu.clock+=.001;self.sequence+=1;value=observed()
        value.update(sampleEpochMs=self.sdk.gpu.epoch(),elapsedMs=round(self.sdk.gpu.clock*1000),
            placesControlsVersion=2,placesSourceSequence=self.sequence,
            navigationDialogControlsVersion=1,navigationDialogSourceSequence=self.sequence)
        return normal_input.observation(value,42,self.sdk.gpu.epoch())


class NavigationObservationOwnerTests(unittest.TestCase):
    def setUp(self):
        image_tests.NavigationSamplesTests.setUp(self)
        self.book_source=BookSource(self.sdk,self.root/'bookmarks.json');self.model_source=ModelSource(self.sdk)
        self.http_source=HttpSource(self.sdk);self.dialog_source=DialogSource(self.sdk);self.ui=UI(self.sdk)
        self.reply_queries=[];self.reply_sequence=0
        def replies():
            self.sdk.gpu.clock+=.001;self.reply_sequence+=1
            return json.dumps(dict(navigationReplyVersion=1,commandId=self.reply_queries[-1]['commandId'],runId=self.run,
                instance='e'*32,sequence=self.reply_sequence,processId=42,capturedEpochMs=self.sdk.gpu.epoch(),
                currentLookupGeneration=2,currentLookupActive=False,events=[]))
        self.sources=dict(bookmarks=self.book_source.reader(),model=self.model_source.reader(),http=self.http_source.reader(),
            dialogs=self.dialog_source.reader(),ui=self.ui,replies=NativeNavigationReplies(self.reply_queries.append,replies,
                self.sdk.gpu.epoch,lambda:self.sdk.okay,42,ios=True,monotonic=lambda:self.sdk.gpu.clock,sleep=self.sdk.gpu.sleep))
        self.native=self.sdk.native();self.navigation=self.sdk.navigation.reader()
        self.baseline=bookmark_baseline(image_tests.BINDING,self.run,self.sources['bookmarks'].read(self.run))
    # Reuse only fixture factories, never the other TestCase's test methods.
    child=image_tests.NavigationSamplesTests.child
    index=image_tests.NavigationSamplesTests.index
    activate=image_tests.NavigationSamplesTests.activate
    def owner(self,request=None,*,previous=None,historical=False,images=None,binding=image_tests.BINDING):
        request=request or uuid.uuid4().hex
        return NavigationObservationOwner(PrivateFeatureState(self.root/('ios-navigation-primary-0-'+request+'-observation.json')),
            images or self.index(historical=historical),binding,self.run,'primary',0,request,self.lock,lambda:self.sdk.okay,
            native=None if historical else self.native,navigation=None if historical else self.navigation,
            sources=None if historical else self.sources,fixture=None if historical else self.fixture,
            previous=previous,historical=historical,monotonic=lambda:self.sdk.gpu.clock,
            epoch_ms=lambda:1_000_000+self.sdk.gpu.clock*1000)
    def take(self,owner,*,label='A',ticket=None):
        ticket=ticket or self.fixture.phase.status()['activations'][-1]['ticket']
        return owner.acquire(ticket,viewpoint_urls(self.harness.inputs['sceneUrl'])[label],label,
            1_000_000+self.sdk.gpu.clock*1000-1,baseline=self.baseline,provider_inputs=self.harness.inputs)

    def test_whole_originals_image_and_start_are_durable_and_historical_never_reads_sdk(self):
        with self.lock.held():
            owner=self.owner();result=self.take(owner)
            self.assertEqual(dict(location='A',bookmark=False,bookmarkName='',searchQuery='',searchResults=[],
                panel=False,addressDialog=False,error='none'),result['state'])
            self.assertEqual(11,len(owner.state['originals']));self.assertEqual('observed',owner.state['phase'])
            self.assertLess(owner.state['nativeStart']['nativeBefore']['sequence'],owner.image()[0]['frame']['clockJoin']['nativeBefore']['sequence'])
            original=deepcopy(owner.store.read());commands=deepcopy(self.gpu.commands);reads=self.ui.reads
            self.sdk.okay=False;frozen=self.owner(owner.request,historical=True)
            self.assertEqual(result,frozen.archive());self.assertEqual(original,frozen.store.read())
            self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)
            with self.assertRaises(NativeUIError):self.take(frozen)

    def test_second_acquisition_keeps_previous_whole_sources_and_actual_B_originals(self):
        with self.lock.held():
            first=self.owner();self.take(first);old=deepcopy(first.store.read());self.activate('c'*32,'B')
            second=self.owner(previous=first);result=self.take(second,label='B',ticket='c'*32)
            self.assertEqual('B',result['state']['location']);self.assertEqual(old,first.store.read())
            self.assertEqual(first.state['imageRow']['requestId'],second.state['indexBefore'][-1])
            self.assertGreater(second.state['originals']['ui']['placesSourceSequence'],first.state['originals']['ui']['placesSourceSequence'])
            self.assertEqual(result,second.archive())

    def test_pending_marker_retains_all_originals_and_next_acquisition_uses_a_new_image(self):
        with self.lock.held():
            self.gpu.marker='c'*32;first=self.owner()
            with self.assertRaises(NavigationMarkerPending):self.take(first)
            self.assertEqual('marker-pending',first.state['phase']);self.assertEqual(11,len(first.state['originals']))
            self.assertIsNone(first.archive());self.gpu.marker=self.fixture.phase.status()['activations'][-1]['ticket']
            second=self.owner(previous=first);self.assertEqual('A',self.take(second)['state']['location'])
            self.assertEqual(2,self.gpu.frames)

    def test_lost_field_read_retains_native_begin_image_and_every_accepted_partial_without_replay(self):
        with self.lock.held():
            self.ui.fail=True;owner=self.owner()
            with self.assertRaises(OSError):self.take(owner)
            retained=deepcopy(owner.store.read());self.assertIsNotNone(owner.state['nativeStart'])
            self.assertEqual(9,len(owner.state['originals']));self.assertNotIn('ui',owner.state['originals'])
            again=self.owner(owner.request);self.ui.fail=False
            with self.assertRaises(NativeUIError):self.take(again)
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(retained,again.store.read());self.assertEqual(1,self.gpu.frames);self.assertEqual(1,self.ui.reads)
            with self.assertRaises(NativeUIError):self.take(self.owner())

    def test_lost_final_return_can_only_resolve_original_record_without_source_calls(self):
        with self.lock.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                state=unpack(value['payload'])[0]
                if state['phase']=='observed':raise OSError('Synthetic lost final result')
                return write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):self.take(owner)
            owner.store.write=write;again=self.owner(owner.request);originals=deepcopy(again.state['originals'])
            commands=deepcopy(self.gpu.commands);reads=self.ui.reads;self.sdk.gpu.sleep(20.)
            self.assertIsNone(again.recover());self.assertEqual(originals,again.state['originals'])
            self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)
            self.assertEqual('A',again.archive()['state']['location'])

    def test_late_storage_or_validation_cannot_return_a_new_fresh_whole_measurement(self):
        with self.lock.held():
            owner=self.owner();validate=owner.validate
            def late():
                result=validate();self.sdk.gpu.sleep(2.);return result
            owner.validate=late
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertEqual('observed',owner.state['phase']);self.assertEqual(1,self.gpu.frames)
            again=self.owner(owner.request);self.assertEqual('A',again.archive()['state']['location'])

    def test_original_phase_change_keeps_whole_failed_attempt_and_never_recaptures(self):
        with self.lock.held():
            original=self.ui.capture
            def crossing():
                value=original();self.client.activate('c'*32,'open',{});return value
            self.ui.capture=crossing;owner=self.owner()
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.state['clockJoin'])
            again=self.owner(owner.request)
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(1,self.gpu.frames)

    def test_native_clock_before_is_saved_before_image_factory_can_fail(self):
        with self.lock.held():
            images=self.index(factory=lambda _request:(_ for _ in ()).throw(OSError('Synthetic factory failure')))
            owner=self.owner(images=images)
            with self.assertRaises(OSError):self.take(owner)
            self.assertIsNotNone(owner.state['nativeStart']);self.assertIsNone(owner.state['imageRow'])
            self.assertEqual({},owner.state['originals']);self.assertEqual([],self.gpu.commands)

    def test_new_native_source_birth_or_whole_field_counter_rollback_after_reconstruction_fails(self):
        for fault in ('birth','model','ui'):
            with self.subTest(fault=fault):
                # Each subcase has a separate admitted source cohort and files.
                self.doCleanups();self.setUp()
                with self.lock.held():
                    first=self.owner();self.take(first)
                    if fault=='birth':
                        stamp=self.sdk.native_boundary.mutate
                        def foreign(value):stamp(value);value['instance']='f'*32
                        self.sdk.native_boundary.mutate=foreign
                    elif fault=='model':
                        self.sources['model']=self.model_source.reader();self.model_source.sequence=0
                    else:self.ui.sequence=0
                    second=self.owner(previous=first)
                    with self.assertRaises(NativeUIError):self.take(second)

    def test_original_bookmark_bytes_cannot_be_replaced_by_requested_or_unowned_entries(self):
        with self.lock.held():
            self.book_source.loaded={'unowned':'hifi://actual'}
            self.book_source.path.write_text(json.dumps(self.book_source.loaded))
            owner=self.owner()
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertEqual({'unowned':'hifi://actual'},owner.state['originals']['bookmarks']['loaded']['entries'])
            self.assertEqual('reading',owner.state['phase']);self.assertEqual(1,self.gpu.frames)

    def test_native_end_is_retained_even_when_the_original_window_cannot_qualify(self):
        with self.lock.held():
            owner=self.owner();original=self.ui.capture
            def delayed():
                value=original();self.sdk.gpu.sleep(2.);return value
            self.ui.capture=delayed
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertIsNotNone(owner.state['nativeEnd']);self.assertIsNotNone(owner.state['clockJoin'])
            self.assertIsNone(owner.state['phaseAfter']);self.assertEqual(11,len(owner.state['originals']))
            again=self.owner(owner.request)
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(1,self.gpu.frames)

    def test_skipping_the_immediate_predecessor_or_mutating_its_record_is_rejected(self):
        with self.lock.held():
            first=self.owner();self.take(first);second=self.owner(previous=first);self.take(second)
            with self.assertRaises(NativeUIError):self.take(self.owner(previous=first))
            third=self.owner(previous=second)
            original=second.store.read();changed=deepcopy(original);changed['requestId']='f'*32
            second.store.write(changed,original)
            with self.assertRaises(NativeUIError):self.take(third)
            self.assertEqual(2,self.gpu.frames)

