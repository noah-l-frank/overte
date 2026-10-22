"""Submitted World Web bytes and original scene/worker restoration boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_marker_measurements as marker
from ios.adapters.world_web_files import originals
from ios.self_tests import test_ios_emote_marker_measurements as fixture
from ios.self_tests.test_ios_emote_marker_measurements import frames as emote_frames,FILES,DIRECTORY


def frames():
    before,after=emote_frames();after['source']['markers'][0]['sourceUrl']=FILES['fixtureUrl']+'tickets/'+FILES['ticket']+'/reference.html'
    code=after['source']['scriptOriginal']['source']['engines'][0]['code']
    raw=originals(FILES['runId'],FILES['fixtureUrl'],FILES['ticket'],FILES['nonce'])['script-bundle/main.js'].decode().encode('utf-16le')
    code.update(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest())
    return before,after


class WorldWebMarkerMeasurementsTests(unittest.TestCase):
    def test_actual_exact_web_source_manager_companion_and_original_camera_are_required(self):
        before,after=frames();owned=marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)
        self.assertEqual(1,owned['iosWorldWebMarkerVersion'])
        self.assertTrue(owned['marker']['sourceUrl'].endswith('/reference.html'))
        self.assertNotIn('iosEmoteMarkerVersion',owned)
        for fault in ('emoteCode','emotePage','codeUnits','companion','manager','view','extraEntity'):
            b,a=frames();engine=a['source']['scriptOriginal']['source']['engines'][0]
            if fault=='emoteCode':engine['code']=deepcopy(emote_frames()[1]['source']['scriptOriginal']['source']['engines'][0]['code'])
            elif fault=='emotePage':a['source']['markers'][0]['sourceUrl']=emote_frames()[1]['source']['markers'][0]['sourceUrl']
            elif fault=='codeUnits':engine['code']['codeUnits']+=1
            elif fault=='companion':engine['required']['modules'][0]['loaded']=False
            elif fault=='manager':a['source']['scriptOriginal']['source']['membership']['managers'][0]['assignedEpochMs']=12000
            elif fault=='view':a['source']['view']['position'][0]+=.1
            else:
                row=deepcopy(a['source']['tree']['entities'][0]);row['id']='22222222-2222-4222-8222-222222222222'
                a['source']['tree']['entities'].append(row);a['source']['tree']['totalEntities']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):marker.admitted(b,a,FILES,DIRECTORY,after_epoch=13000)

    def test_failed_actual_entity_creation_retains_worker_and_cannot_be_full_admission(self):
        before,after=frames();after['source']['markers']=[];after['source']['tree']=deepcopy(before['source']['tree'])
        after['source']['scriptOriginal']['source']['effects']=deepcopy(before['source']['scriptOriginal']['source']['effects'])
        owned=marker.executed(before,after,FILES,DIRECTORY,after_epoch=13000)
        self.assertIsNone(owned['marker']);self.assertEqual(1,owned['iosWorldWebPartialMarkerVersion'])
        with self.assertRaises(NativeUIError):marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)
        proof=fixture.MarkerMeasurementsTests().terminal(owned)
        self.assertEqual(3,len(marker.partial_restored(before,before,owned,proof,after_sequence=1,after_epoch=17001)))

    def test_ordinary_restoration_needs_complete_actual_worker_terminal_and_original_view(self):
        before,after=frames();owned=marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)
        proof=fixture.MarkerMeasurementsTests().terminal(owned)
        self.assertEqual(3,len(marker.restored(before,before,owned,proof,after_sequence=1,after_epoch=17001)))
        for fault in ('thread','code','oldBarrier','view','running'):
            clean=deepcopy(before);term=deepcopy(proof);epoch=17001
            if fault=='thread':term['source']['events'].pop();term['source']['eventSequence']-=1
            elif fault=='code':term['source']['events'][-1]['code']['sha256']='f'*64
            elif fault=='oldBarrier':epoch=19000
            elif fault=='view':clean['source']['cameraOrbit']['boomLength']+=.1
            else:clean['source']['scriptOriginal']=deepcopy(after['source']['scriptOriginal']);clean['source']['scriptOriginal']['source']['effects']=deepcopy(before['source']['scriptOriginal']['source']['effects'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):marker.restored(before,clean,owned,term,after_sequence=1,after_epoch=epoch)

    def test_already_ended_worker_uses_actual_code_and_two_terminal_boundaries(self):
        before,after=frames();owned=marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)
        proof=fixture.MarkerMeasurementsTests().terminal(owned)
        result=marker.finished(before,before,FILES,DIRECTORY,proof,after_sequence=0,after_epoch=13000)
        self.assertIsNone(result['marker']);self.assertEqual(owned['manager'],result['manager'])
        emote=emote_frames()[1]['source']['scriptOriginal']['source']['engines'][0]['code']
        for event in proof['source']['events']:
            if event['code'] is not None:event['code']=deepcopy(emote)
        with self.assertRaises(NativeUIError):marker.finished(before,before,FILES,DIRECTORY,proof,after_sequence=0,after_epoch=13000)


if __name__=='__main__':unittest.main()
