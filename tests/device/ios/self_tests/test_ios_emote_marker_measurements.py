"""Counterexamples for exact owned Script/marker and independent drain joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import emote_marker_measurements as marker
from ios.adapters.emote_marker_files import originals
from ios.self_tests.test_ios_emote_world import packet,URL,NONCE,RUN
from self_tests.test_native_script_terminal import packet as terminal_packet

DIRECTORY='file:///actual/feature-script-'+RUN
FILES=dict(runId=RUN,fixtureUrl=URL.split('tickets/')[0],ticket='a'*32,nonce=NONCE)


def frames():
    after=packet();scripts=after['source']['scriptOriginal']['source'];scripts['sourceIdentityVersion']=1
    engine=scripts['engines'][0];engine['url']=DIRECTORY+'/script-bundle/main.js'
    engine['required']['modules'][0]['url']=DIRECTORY+'/script-bundle/companion.js'
    raw=originals(RUN,FILES['fixtureUrl'],FILES['ticket'],NONCE)['script-bundle/main.js'].decode().encode('utf-16le')
    engine['code']=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(raw)//2,
        sha256=hashlib.sha256(raw).hexdigest(),submittedEpochMs=15000)
    manager=dict(instance=engine['required']['instance'],assigned=True,url=engine['url'],loadGeneration=1,assignedEpochMs=14000)
    scripts.update(membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[manager]))
    before=deepcopy(after);before['source']['markers']=[]
    before['source']['tree'].update(totalEntities=0,entities=[])
    before['source']['scriptOriginal']['source']['effects'].update(scannedEntities=0,entities=[])
    before['source']['scriptOriginal']['source']['engines']=[]
    before['source']['scriptOriginal']['source']['membership'].update(revision=0,managers=[])
    return before,after


class MarkerMeasurementsTests(unittest.TestCase):
    def test_exact_submitted_original_bytes_actual_assigned_url_and_returned_marker_ID_join(self):
        before,after=frames();owned=marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)
        self.assertEqual(after['source']['markers'][0]['id'],owned['marker']['id'])
        self.assertEqual(DIRECTORY+'/script-bundle/main.js',owned['manager']['url'])

    def test_marker_only_requested_file_bytes_foreign_manager_or_missing_companion_cannot_authorize(self):
        for fault in ('code','url','companion','assigned','preexisting','nonce','extraEntity'):
            before,after=frames();engine=after['source']['scriptOriginal']['source']['engines'][0]
            if fault=='code':engine['code']['sha256']='f'*64
            elif fault=='url':engine['url']='file:///foreign/main.js'
            elif fault=='companion':engine['required']['modules'][0]['loaded']=False
            elif fault=='assigned':after['source']['scriptOriginal']['source']['membership']['managers'][0]['assignedEpochMs']=12000
            elif fault=='preexisting':before=deepcopy(after)
            elif fault=='nonce':after['source']['markers'][0]['userData']=after['source']['markers'][0]['userData'].replace(NONCE,'0'*32)
            else:
                row=deepcopy(after['source']['tree']['entities'][0]);row['id']='22222222-2222-4222-8222-222222222222'
                after['source']['tree']['entities'].append(row);after['source']['tree']['totalEntities']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)

    def test_domain_body_unowned_scene_and_original_view_are_preserved(self):
        for field,value in (('domain',dict(serverless=True)),('avatar',dict(feetPosition=[1,0,4])),
                            ('avatar',dict(inAir=True)),('avatar',dict(modelScale=2))):
            before,after=frames();after['source'][field].update(value)
            with self.subTest(value=value),self.assertRaises(NativeUIError):marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)

    def terminal(self,owned):
        value=terminal_packet()
        for row in value['source']['events']:
            row['manager']=deepcopy(owned['manager']);row['capturedEpochMs']+=5000
            if row['code'] is not None:row['code']=deepcopy(owned['code'])
        return value

    def test_full_map_restoration_needs_owned_thread_exit_after_stop_and_original_camera(self):
        before,after=frames();owned=marker.admitted(before,after,FILES,DIRECTORY,after_epoch=13000)
        clean=deepcopy(before);proof=self.terminal(owned)
        self.assertEqual(3,len(marker.restored(before,clean,owned,proof,after_sequence=1,after_epoch=17001)))
        for fault in ('thread','lateBarrier','view','orbit','managerAlive','markerAlive'):
            current=deepcopy(clean);term=deepcopy(proof);epoch=17001
            if fault=='thread':term['source']['events'].pop();term['source']['eventSequence']-=1
            elif fault=='lateBarrier':epoch=19000
            elif fault=='view':current['source']['view']['position'][0]+=.1
            elif fault=='orbit':current['source']['cameraOrbit']['boomLength']+=1
            elif fault=='managerAlive':current=deepcopy(after);current['source']['markers']=[];current['source']['tree']=deepcopy(before['source']['tree']);current['source']['scriptOriginal']['source']['effects'].update(scannedEntities=0,entities=[])
            else:current=deepcopy(after)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                marker.restored(before,current,owned,term,after_sequence=1,after_epoch=epoch)


if __name__=='__main__':unittest.main()
