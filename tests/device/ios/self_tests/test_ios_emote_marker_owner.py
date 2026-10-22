"""Actual durable marker/quiet owner with synthetic original native readers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_marker_recovery import IOSEmoteMarkerRecovery
from ios.self_tests import test_ios_emote_marker_scope as marker_fixture
from ios.self_tests.test_ios_emote_marker_files import NativeBoundary as Files
from ios.self_tests.test_ios_emote_marker_measurements import frames
from ios.self_tests.test_ios_emote_sources import RUN
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_script_terminal import packet as terminal_packet
from ios.self_tests.test_ios_script_dialogs import packet as dialogs_packet


class Domain:
    def __init__(self,scope):
        self.scope=scope;self.time=0.;self.sequences=dict(world=0,terminal=0,dialogs=0,web=0,widgets=0);self.history=[];self.dialog_events=[]
        self.world_template=frames()[0];self.boundary=Boundary();self.files=Files();self.web_failure=False
        scope.files.native=self.files;scope.monotonic=lambda:self.time;scope.epoch_ms=lambda:90000+self.time*1000;scope.sleep=self.sleep
        scope.native=NativeFeatureObservation(self.native_send,lambda:self.boundary.original(),self.epoch,lambda:True,31,
            ios=True,native_clock_bound=True,monotonic=lambda:self.time,sleep=self.sleep)
        scope.world=SimpleNamespace(last=None,read=self.world);scope.terminals=SimpleNamespace(last=None,read=self.terminal)
        scope.dialogs=SimpleNamespace(last=None,read=self.dialogs)
        scope.web=SimpleNamespace(last=None,read=self.web);scope.work=SimpleNamespace(last=None)
        scope.live=dict(native=SimpleNamespace(capture=self.widgets));scope.state['phase']='new'
    def sleep(self,seconds):self.time+=seconds
    def epoch(self):return 20000+round(self.time*1000)
    def tick(self,name):self.time+=.005;self.sequences[name]+=1;return self.sequences[name]
    def native_send(self,query):
        self.time+=.005;self.boundary.send(query);p=self.boundary.sample;sequence=p['sequence'];epoch=self.epoch()
        p.update(processId=31,requestedEpochMs=epoch,capturedEpochMs=epoch)
        a=p['animation'];a.update(capturedEpochMs=epoch,evaluationSequence=100+sequence,overrideActive=False);a.pop('clip',None)
        p['animationFence'].update(requestedEpochMs=epoch,sequence=99+sequence)
        self.history.append(dict(frameSequence=sequence,overrideSequence=0,evaluationSequence=100+sequence,capturedEpochMs=epoch,
            overrideActive=False,joints=[dict(index=0,pose=deepcopy(a['joints'][0]))]))
        a['history']=dict(historyVersion=2,instance='e'*32,available=True,callSequence=0,overrideSequence=0,
            frameSequence=sequence,droppedEvents=0,droppedFrames=max(0,len(self.history)-32),events=[],frames=deepcopy(self.history[-32:]))
    def world(self,run):
        assert run==RUN;sequence=self.tick('world');value=deepcopy(self.world_template)
        value.update(sequence=sequence,requestId='ios-'+format(sequence+3000,'032x'))
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=self.epoch(),monotonicMs=round(self.time*1000))
        value['source']['scriptOriginal'].update(requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        return value
    def terminal(self,_after):
        sequence=self.tick('terminal');p=terminal_packet(0);p.update(commandId='ios-'+format(sequence+4000,'032x'),sequence=sequence,
            requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch());self.scope.terminals.last=deepcopy(p);return p
    def dialogs(self,run):
        sequence=self.tick('dialogs');p=dialogs_packet(sequence,self.dialog_events);p['runId']=run
        for key in ('clockBefore','clockAfter'):p[key]=dict(epochMs=self.epoch(),monotonicMs=round(self.time*1000))
        self.scope.dialogs.last=deepcopy(p);return p
    def web(self,run,url):
        sequence=self.tick('web')
        if self.web_failure:raise OSError('Synthetic lost original Web inventory')
        p=dict(iosWebClosureVersion=5,commandId='ios-'+format(sequence+5000,'032x'),runId=run,fixtureUrl=url,
            instance='5'*32,sequence=sequence,processId=31,capturedEpochMs=self.epoch(),complete=True,contexts=[])
        self.scope.web.last=deepcopy(p);return p
    def widgets(self):
        sequence=self.tick('widgets')
        return dict(schemaVersion=1,instance=str(uuid.UUID('1'*32)),frameSpace='qt-window-logical',processId=31,
            sampleEpochMs=self.epoch(),elapsedMs=round(self.time*1000),lastSequence=0,tabletShown=False,ready=True,controls=[],
            emoteControlsVersion=2,emoteGeneration=str(uuid.UUID('2'*32)),emoteSourceSequence=sequence,
            emoteInventory=dict(iosEmoteUiInventoryVersion=1,complete=True,roots=[]),scriptObservationVersion=1,scriptSourceSequence=sequence,
            scriptInventory=dict(inventoryVersion=1,complete=True,managers=[],pickers=[],tabletPresent=True,tabletShown=False))


class MarkerOwnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=marker_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.fixture.owner();self.domain=Domain(self.scope)
    def test_unused_setup_cleanup_observes_repeated_original_quiet_and_preserves_native_history(self):
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertEqual('released',self.scope.state['phase'])
        self.assertGreaterEqual(len(self.scope.state['quiet']),3);before=len(self.domain.history)
        first=self.scope.frames[self.scope.state['quiet'][0]-1]['clockJoin'];last=self.scope.frames[-1]['clockJoin']
        self.assertGreaterEqual(last['hostBeforeMonotonic']-first['hostAfterMonotonic'],3)
        left=self.scope.frames[self.scope.state['quiet'][0]-1]['world'];right=self.scope.frames[-1]['world']
        self.assertEqual(left['instance'],right['instance'])
        self.assertGreaterEqual(right['clockBefore']['monotonicMs']-left['clockAfter']['monotonicMs'],3000)
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertEqual(before,len(self.domain.history))
        rebuilt=self.fixture.owner();self.assertEqual(self.scope.frames,rebuilt.frames)
        self.assertGreater(len(rebuilt.frames[-1]['clockJoin']['nativeAfter']['animation']['history']['frames']),2)
    def test_failed_staging_retires_only_owned_native_files_after_actual_map_ui_quiet(self):
        baseline=self.scope.capture('baseline');self.scope.state.update(phase='preparing',baseline=len(self.scope.frames));self.scope.save()
        self.scope.files.reserve_marker(RUN,self.scope.fixture_url,self.scope.ticket)
        self.scope.state['fileOwnership']=self.scope.files.owned();self.scope.save();self.domain.files.fail=True
        with self.assertRaises(NativeUIError):self.scope.once('stage-marker-files',self.scope.files.stage_reserved)
        self.domain.files.fail=False;self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertIsNone(self.scope.files.store.read());self.assertIsNone(self.domain.files.files)
        self.assertEqual(['stage','release','observe'],[row[0] for row in self.domain.files.calls])
        self.assertEqual(baseline['world']['source']['tree'],self.scope.frames[-1]['world']['source']['tree'])
    def test_lost_passive_marker_read_retains_returned_originals_and_uses_distinct_future_reads(self):
        self.domain.web_failure=True
        with self.assertRaises(OSError):self.scope.capture('lost-marker-read')
        self.assertIsNotNone(self.scope.state['pending']);self.assertIn('terminal',self.scope.state['pending']['partial'])
        old_world=self.scope.state['pending']['partial']['world'];old_terminal=self.scope.state['pending']['partial']['terminal']
        self.domain.web_failure=False;actual=self.scope.capture('fresh-marker-read')
        recovery=IOSEmoteMarkerRecovery(self.scope);self.assertEqual(1,len(recovery.state['records']))
        self.assertNotEqual(old_world['requestId'],actual['world']['requestId'])
        self.assertGreater(actual['terminal']['sequence'],old_terminal['sequence']);self.assertEqual(1,len(self.scope.frames))
        self.assertEqual(old_world,recovery.prior(recovery.record(recovery.state['records'][0])['priorOwner'])['pending']['partial']['world'])


if __name__=='__main__':unittest.main()
