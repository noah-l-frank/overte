"""Original-state composition with coherent modeled native/UI/GPU sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import navigation_product_state as measured
from ios.self_tests.test_ios_navigation_places_state import Harness as Places,INPUTS,BINDING,RUN,TICKET
from ios.self_tests.test_ios_navigation_error_state import Harness as Error
from ios.self_tests.test_ios_navigation_challenge import bundle as image_bundle
from ios.self_tests.test_ios_navigation_ui import observed,root as address_root
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from navigation_observation import viewpoint_urls

FIXTURE='http://controlled.invalid:49121/feature-fixture/v1/runs/'+RUN+'/'


class World:
    def __init__(self,path,*,label='A',panel=True,missing=False,cleared=False,address=False,ticket=TICKET):
        self.places=Places(path);self.error=Error(missing=missing,provider=self.places.provider)
        if cleared:self.error.source.respond();self.error.source.destroy()
        if ticket!=TICKET:self.places.provider.activate(RUN,ticket)
        self.image,self.navigation=image_bundle(label,ticket,offset=1.,index=1,scene_url=INPUTS['sceneUrl'],
            fixture_url=FIXTURE,provider_instance=self.places.provider.instance,return_source=True)
        self.error.source.clock=self.navigation.clock+.01;error,_error_clock=self.error.read(address=address)
        self.places.http.clock=self.error.source.clock+.01;place,_place_clock=self.places.read(panel=panel)
        # This is ONE newly created SDK UI observation for the common live UI,
        # not a retimed historical snapshot. Actual product observations are
        # never rewritten by the production composition code.
        self.places.http.clock+=.001;ui=observed(*([address_root()] if address else []))
        ui.update(sampleEpochMs=self.places.http.epoch(),elapsedMs=round(self.places.http.clock*1000),tabletShown=panel,
            placesControlsVersion=2,placesSourceSequence=2,navigationDialogControlsVersion=1,
            navigationDialogSourceSequence=self.error.sequence)
        ui['controls']=deepcopy(place['ui']['controls'])
        if self.error.source.rows and self.error.source.rows[0]['dialog'] is not None:
            if self.error.source.rows[0]['dialog']['visible']:
                ui['controls'] += [dict(row,frame=dict(x=10,y=20,width=300,height=40))
                                   for row in self.error.source.controls()['controls']]
        self.navigation.clock=self.places.http.clock+.01;current=self.navigation.reader().read(RUN)
        self.originals={name:place[name] for name in ('bookmarks','model','http')}
        self.originals.update(dialogs=error['dialogs'],replies=error['replies'],ui=ui,currentNavigation=current)
        self.originals.update({name:self.image['frame'][name] for name in measured.IMAGE})
        self.clock=self.join()
        self.options=dict(baseline=self.places.baseline,provider_inputs=INPUTS,fixture_url=FIXTURE,
            provider_instance=self.places.provider.instance,directory=self.places.proof,missing=self.error.proof)

    def join(self):
        inner=self.image['frame']['clockJoin'];start=inner['nativeBefore']['capturedEpochMs']-1
        end=self.originals['currentNavigation']['clockAfter']['epochMs']+1
        return dict(clockJoinVersion=1,hostBeforeEpochMs=inner['hostBeforeEpochMs']-1,
            hostAfterEpochMs=inner['hostBeforeEpochMs']-1+end-start,hostBeforeMonotonic=inner['hostBeforeMonotonic']-.001,
            hostAfterMonotonic=inner['hostBeforeMonotonic']-.001+(end-start)/1000,
            nativeBefore=global_packet(start,2),nativeAfter=global_packet(end,5),originalsSha256=digest(self.originals),
            sourceTimes=[dict(source=name,field=field,epochMs=packet[field]) for name,packet in self.originals.items()
                         for field in ('capturedEpochMs','sampleEpochMs') if field in packet])

    def project(self,**changes):
        options=dict(self.options);options.update(changes)
        return measured.compose(RUN,BINDING,self.originals,self.clock,self.image,**options)


class NavigationProductStateTests(unittest.TestCase):
    def world(self,**options):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        return World(Path(directory.name)/'bookmarks.json',**options)

    def test_all_eight_actual_fields_share_original_ui_clock_process_and_rendered_scene(self):
        w=self.world();before=deepcopy((w.originals,w.clock,w.image));result=w.project()
        self.assertEqual(dict(location='A',bookmark=False,bookmarkName='',searchQuery='',
            searchResults=[w.places.ctx['destination']],error='none',panel=True,addressDialog=False),result['state'])
        self.assertEqual(before,(w.originals,w.clock,w.image));self.assertNotIn('passed',result)
        self.assertEqual(w.image['ticket'],result['ticket']);self.assertEqual(digest(w.originals),result['originalsSha256'])

    def test_actual_B_with_its_matching_visible_missing_modal_is_not_requested_arrival(self):
        for address in (False,True):
            w=self.world(label='B',panel=False,missing=True,address=address);state=w.project()['state']
            self.assertEqual('B',state['location']);self.assertEqual('not-found',state['error'])
            self.assertEqual(address,state['addressDialog']);self.assertFalse(state['panel'])

    def test_dismissal_keeps_old_missing_ticket_while_current_image_uses_new_phase(self):
        w=self.world(label='B',panel=False,missing=True,cleared=True,address=True,ticket='f'*32)
        proof=deepcopy(w.error.proof);result=w.project()
        self.assertEqual('none',result['state']['error']);self.assertTrue(result['state']['addressDialog'])
        self.assertEqual('f'*32,result['ticket']);self.assertEqual(TICKET,w.error.proof['admission']['ticket'])
        self.assertEqual(proof,w.error.proof)

    def test_current_native_pose_cannot_borrow_an_earlier_image_of_another_location(self):
        w=self.world();w.originals['currentNavigation']['source']['avatar']['feetPosition']=[2,0,4];w.clock=w.join()
        with self.assertRaises(NativeUIError):w.project()

    def test_current_scene_or_view_change_after_image_is_not_a_coherent_state(self):
        for fault in ('generation','camera','url','marker','fov'):
            w=self.world();source=w.originals['currentNavigation']['source']
            if fault=='generation':source['sceneLoads']['currentGeneration']+=1
            elif fault=='camera':source['view']['position'][0]+=.1
            elif fault=='url':source['sceneUrl']=viewpoint_urls(INPUTS['sceneUrl'])['B']
            elif fault=='marker':source['challengeMarker']['entity']['sourceUrl']+='-foreign'
            else:source['view']['fieldOfViewDegrees']+=1
            w.clock=w.join()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):w.project()

    def test_current_navigation_must_follow_all_original_field_reads(self):
        w=self.world();w.originals['ui']['sampleEpochMs']=w.originals['currentNavigation']['clockAfter']['epochMs']
        w.clock=w.join()
        with self.assertRaises(NativeUIError):w.project()

    def test_image_packets_cannot_be_swapped_or_replayed_in_a_different_outer_acquisition(self):
        for fault in ('capture','global-counter','native-birth','host-window'):
            w=self.world()
            if fault=='capture':
                w.originals['capture']=deepcopy(w.originals['capture']);w.originals['capture']['sequence']+=1;w.clock=w.join()
            elif fault=='global-counter':w.clock['nativeBefore']['sequence']=3
            elif fault=='native-birth':w.clock['nativeBefore']['instance']=w.clock['nativeAfter']['instance']='f'*32
            else:w.clock['hostBeforeMonotonic']+=.01;w.clock['hostBeforeEpochMs']+=10
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):w.project()

    def test_wrong_fixture_candidate_or_source_context_does_not_publish_eight_fields(self):
        for change in (dict(fixture_url=FIXTURE+'foreign/'),dict(provider_instance='f'*32),
                       dict(provider_inputs=dict(INPUTS,sourceRevision='f'*40))):
            w=self.world()
            with self.subTest(change=change),self.assertRaises(NativeUIError):w.project(**change)

    def test_whole_clock_and_subset_validation_views_preserve_all_original_times(self):
        w=self.world();original=deepcopy(w.clock)
        subset,view=measured.validation_view(w.clock,w.originals,measured.PLACES)
        for name in set(original)-{'originalsSha256','sourceTimes'}:self.assertEqual(original[name],view[name])
        self.assertEqual(original,w.clock);self.assertEqual(digest(subset),view['originalsSha256'])
        self.assertEqual([dict(source='ui',field='sampleEpochMs',epochMs=w.originals['ui']['sampleEpochMs'])],view['sourceTimes'])

    def test_missing_original_or_fresh_hash_around_old_scene_frame_does_not_qualify(self):
        w=self.world();w.originals.pop('http');w.clock['originalsSha256']=digest(w.originals)
        with self.assertRaises(NativeUIError):w.project()
        w=self.world();w.originals['model']['complete']=False;w.clock=w.join()
        with self.assertRaises(NativeUIError):w.project()

    def test_historical_composition_keeps_original_packets_and_cannot_claim_a_new_read(self):
        w=self.world();serialized=json.dumps(w.originals,sort_keys=True);first=w.project();second=w.project()
        self.assertEqual(first,second);self.assertEqual(serialized,json.dumps(w.originals,sort_keys=True))
        self.assertEqual(w.clock['hostBeforeEpochMs'],second['acquiredHostEpochMs'])
