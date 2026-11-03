"""Resume-phase original Page profile only; no OS interruption is simulated away.

Lower QML/native/fixture producers are explicit host models. Actual existing
normal Capture/Page originals, CAS, files and locks execute. A lifecycle counter
alone never closes the separately required original OS bridge or rendered proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_resume_page import SnapshotResumePage
from ios.self_tests.test_ios_snapshot_capture_rendered_review import ReviewDomain,RUN

RESUME='e'*32


class ResumePageDomain(ReviewDomain):
    def __init__(self,case):
        super().__init__(case);super().prepare()
        self.original_phase=deepcopy(unpack(PrivateFeatureState(self.ctx.root/'ios-snapshot-primary-capture-owner.json').read()['payload'])[0]['phaseOriginal'])
        self.f.now+=10;self.activated=self.f.now;self.resume_verb='background-resume';self.resume_counts=None
        mutate=self.ctx.native.mutate
        def producer(value):
            mutate(value)
            if self.resume_counts is not None:value['lifecycle']=deepcopy(self.resume_counts)
        self.ctx.native.mutate=producer

    def resume_client(self):
        domain=self
        class Phase(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                need(path=='/runs/'+RUN+'/phase');domain.capture.phase_sequence+=1
                old=domain.original_phase
                activation=dict(sequence=len(old['activations'])+1,ticket=RESUME,activatedEpochMs=domain.activated,
                    stimulus=dict(verb=domain.resume_verb,inputs={}))
                return dict(fixturePhaseVersion=1,instance=old['instance'],sequence=domain.capture.phase_sequence,
                    requestId=phase_nonce,runId=RUN,area='snapshots',capturedEpochMs=domain.f.now,active=True,
                    createdEpochMs=old['createdEpochMs'],retiredEpochMs=None,activations=deepcopy(old['activations'])+[activation])
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.capture.mono,sleep=self.capture.sleep)

    @contextmanager
    def resumed_page(self):
        lock=ScriptSourceLock(self.ctx.root/'script-feature-sources.lock')
        with lock.held():
            source=self.runtime._sources('primary')
            owner=SnapshotResumePage(self.runtime,'primary',RUN,lock,source,
                ui=NativeUI(source['client'],source['session'],source['check']),
                phase=PhaseFixtureReader(self.resume_client(),RUN,'snapshots',epoch_ms=self.capture.epoch,monotonic=self.capture.mono),
                epoch_ms=self.capture.epoch,monotonic=self.capture.mono,sleep=self.capture.sleep,combined=True)
            yield owner


class SnapshotResumePageTests(unittest.TestCase):
    def test_actual_capture_then_new_resume_page_has_separate_original_profile_and_no_new_input(self):
        d=ResumePageDomain(self);inputs=deepcopy(d.clicks)
        with d.resumed_page() as page:
            result=page.prepare(RESUME);self.assertEqual(3,page.previous['iosSnapshotPageOwnerVersion'])
            self.assertEqual(3,page.record(1)['iosSnapshotPageObservationVersion'])
            self.assertEqual([],page.state['actions']);self.assertTrue(all(result[key]for key in (
                'originalOSBridgeRequired','renderedReviewRequired','independentActorSceneRequired','pairedCleanupRequired','wholeFeatureRequired')))
            self.assertIn('ios-snapshot-resume-page',page.frames.namespace)
            source_count=d.ctx.native.sequence;self.assertEqual(result,page.prepare(RESUME));self.assertEqual(source_count,d.ctx.native.sequence)
            with self.assertRaises(NativeUIError):IOSSnapshotPageOwner.archive(page.store,page.lock,page.binding,RUN,page.fixture_url,combined=True)
            historical=SnapshotResumePage.archive(page.store,page.lock,page.binding,RUN,page.fixture_url,combined=True)
            self.assertEqual(page.record(1),historical.record(1));self.assertEqual(source_count,d.ctx.native.sequence)
        self.assertEqual(inputs,d.clicks);self.assertEqual(1,d.capture.capture_count);self.assertEqual(0,d.screen_calls)

    def test_exact_one_declared_lifecycle_transition_stays_owned_without_os_or_pixel_acceptance(self):
        d=ResumePageDomain(self)
        with d.resumed_page() as page:
            result=page.prepare(RESUME);before=page.record(1)['clockJoin']['nativeAfter']['lifecycle']
            d.resume_counts=dict(launches=before['launches'],backgrounds=before['backgrounds']+1,activations=before['activations']+1)
            ref=page.observe();after=page.original(ref);self.assertEqual(d.resume_counts,after['clockJoin']['nativeAfter']['lifecycle'])
            self.assertTrue(result['originalOSBridgeRequired'] and result['renderedReviewRequired'] and result['wholeFeatureRequired'])
        self.assertEqual(1,d.capture.capture_count);self.assertEqual(0,d.screen_calls)

    def test_extra_background_or_relaunch_counter_is_not_an_admissible_resume_page_prefix(self):
        for kind in ('extra-background','relaunch'):
            d=ResumePageDomain(self)
            with self.subTest(kind=kind),d.resumed_page() as page:
                page.prepare(RESUME);before=page.record(1)['clockJoin']['nativeAfter']['lifecycle']
                d.resume_counts=dict(launches=before['launches']+int(kind=='relaunch'),
                    backgrounds=before['backgrounds']+2,activations=before['activations']+1)
                with self.assertRaises(NativeUIError):page.observe()
                self.assertEqual(1,len(page.state['records']));self.assertIsNotNone(page.state['observation'])
            self.assertEqual(1,d.capture.capture_count)

    def test_wrong_current_phase_refuses_before_any_new_native_query_or_navigation(self):
        d=ResumePageDomain(self);d.resume_verb='close';native=d.ctx.native.sequence;clicks=deepcopy(d.clicks)
        with d.resumed_page() as page,self.assertRaises(NativeUIError):page.prepare(RESUME)
        self.assertEqual(native,d.ctx.native.sequence);self.assertEqual(clicks,d.clicks)

    def test_saved_original_lost_parent_return_recovers_without_repeating_native_acquisition(self):
        d=ResumePageDomain(self)
        with d.resumed_page() as page:
            save=page.save
            def lose():
                if page.state['records']:raise OSError('Saved original Resume Page before parent CAS return')
                return save()
            with patch.object(page,'save',side_effect=lose),self.assertRaises(OSError):page.prepare(RESUME)
        native=d.ctx.native.sequence;commands=deepcopy(d.capture.commands)
        with d.resumed_page() as page:
            page.prepare(RESUME);self.assertEqual(1,len(page.state['records']));self.assertEqual(native,d.ctx.native.sequence)
        self.assertEqual(commands,d.capture.commands);self.assertEqual(1,d.capture.capture_count)

    def test_resume_owner_cannot_drive_navigation_capture_or_retire_original_page(self):
        d=ResumePageDomain(self);clicks=deepcopy(d.clicks)
        with d.resumed_page() as page:
            page.prepare(RESUME)
            for call in (lambda:page.open(RESUME),lambda:page.capture(RESUME),lambda:page.drive('unexpected','tablet.home'),page.restore):
                with self.assertRaises(NativeUIError):call()
        self.assertEqual(clicks,d.clicks);self.assertEqual(1,d.capture.capture_count)
