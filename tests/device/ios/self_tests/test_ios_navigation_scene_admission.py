"""Actual base/persistence inputs and validators; native source ports modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys import navigation_base_scene as base
from feature_journeys.navigation_scene import base_scene,marker_id
from ios.adapters import navigation_scene_admission as admission
from ios.self_tests.test_ios_scene_commit_origin import Boundary as Origin
from ios.self_tests.test_ios_navigation_state import Boundary as Navigation,RUN
from ios.self_tests.test_ios_location_bookmarks import Boundary as Books
from ios.self_tests.test_ios_places_model import Boundary as Model
from ios.self_tests.test_ios_places_http import Boundary as Http
from ios.self_tests.test_ios_navigation_dialogs import Boundary as Dialogs
from ios.self_tests.test_ios_places_settings import original_preferences
from ios.self_tests.test_ios_navigation_ui import observed,root as address_root
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from self_tests.test_completed_frame_lease import BINDING
from self_tests import test_navigation_scene as scene_tests
from navigation_observation import viewpoint_urls


class Inventory(Origin):
    def __init__(self,url):self.base_url=url;super().__init__()
    def commit(self):
        if not self.commits:
            self.url=viewpoint_urls(self.base_url)['A'];self.body=base.body()
            self.raw={row['id'].strip('{}'):json.dumps(row,sort_keys=True).encode() for row in base_scene()['Entities']}
        super().commit()


class NavigationSceneAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.harness=scene_tests.NavigationSceneTests();self.harness.setUp();self.addCleanup(self.harness.doCleanups)
        self.inputs=self.harness.inputs;self.provider=self.harness.provider;url=base.resource_url(self.inputs['sceneUrl'])
        self.harness.get(url[len(self.harness.origin):]);self.base=self.harness.client.request('/navigation-base-scene')
        self.inventory=Inventory(url);inventory=self.inventory.reader().read(RUN)
        navigation=Navigation();navigation.clock=self.inventory.clock+.002;navigation.sequence=inventory['source']['sceneLoads']['sequence']
        navigation.url=viewpoint_urls(url)['A'];navigation.source['sceneUrl']=navigation.url
        navigation.version=2;navigation.source['challengeMarker']=dict(id=marker_id(RUN),present=False,entity=None)
        navigation.mutate=lambda value:value['source']['sceneLoads'].update(requests=deepcopy(self.inventory.loads))
        native=navigation.reader().read(RUN)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);path=Path(temporary.name)/'bookmarks.json';path.write_text('{}')
        books=Books(path);books.clock=navigation.clock+.002;self.books=books
        bookmarks=books.reader().read(RUN)
        model=Model();model.clock=books.clock+.002;model.shown=False;model.pages=[]
        preferences=original_preferences();preferences['metaverseOrigin']=self.harness.origin
        model.mutate=lambda value:value.update(iosPlacesModelVersion=2,preferences=deepcopy(preferences))
        model_packet=model.reader().read(RUN)
        http=Http();http.clock=model.clock+.002;http_packet=http.reader().read(RUN)
        dialogs=Dialogs();dialogs.clock=http.clock+.002;dialog_packet=dialogs.reader().read(RUN)
        replies=dict(navigationReplyVersion=1,commandId='ios-'+'f'*32,runId=RUN,instance='e'*32,sequence=1,
            processId=42,capturedEpochMs=dialogs.epoch()+1,currentLookupGeneration=1,currentLookupActive=False,events=[])
        ui=observed();ui.update(sampleEpochMs=dialogs.epoch()+2,elapsedMs=round(dialogs.clock*1000)+2,
            placesControlsVersion=2,placesSourceSequence=1,navigationDialogControlsVersion=1,navigationDialogSourceSequence=1)
        self.originals=dict(inventory=inventory,navigation=native,bookmarks=bookmarks,model=model_packet,http=http_packet,
            dialogs=dialog_packet,replies=replies,ui=ui);self.join=self.clock()
    def clock(self):
        first=self.originals['inventory']['clockBefore']['epochMs']-1;last=self.originals['ui']['sampleEpochMs']+1
        return dict(clockJoinVersion=1,hostBeforeEpochMs=1_000_000.,hostAfterEpochMs=1_000_000.+last-first,
            hostBeforeMonotonic=10.,hostAfterMonotonic=10.+(last-first)/1000,nativeBefore=global_packet(first,1),
            nativeAfter=global_packet(last,2),originalsSha256=digest(self.originals),sourceTimes=[dict(source=name,field=field,epochMs=packet[field])
                for name,packet in self.originals.items() for field in ('capturedEpochMs','sampleEpochMs') if field in packet])
    def admit(self,**changes):
        options=dict(provider_instance=self.provider.instance,provider_inputs=self.inputs);options.update(changes)
        return admission.admit(RUN,BINDING,self.originals,self.join,self.base,**options)

    def test_static_socket_bytes_match_actual_native_import_and_unchanged_map_before_any_input(self):
        before=deepcopy((self.originals,self.join,self.base));value=self.admit()
        self.assertEqual(self.base['sha256'],value['commit']['bodySha256']);self.assertEqual(before,(self.originals,self.join,self.base))
        self.assertEqual(value,admission.validate(value));self.assertNotIn('passed',value)
        self.assertEqual(self.originals['bookmarks'],value['bookmarkBaseline']['original'])
        self.assertNotEqual(self.join['hostBeforeEpochMs'],self.originals['inventory']['clockBefore']['epochMs'])

    def test_foreign_or_undelivered_base_input_cannot_admit_actual_native_state(self):
        for fault in ('instance','undelivered','unavailable','bytes'):
            base_before=deepcopy(self.base)
            if fault=='instance':self.base['instance']='f'*32
            elif fault=='undelivered':self.base['responses']=[]
            elif fault=='unavailable':self.base['available']=False
            else:self.originals['inventory']['source']['commitOrigin']['latest']['bodySha256']='f'*64
            self.join=self.clock()
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.admit()
            self.base=base_before;self.originals['inventory']['source']['commitOrigin']['latest']['bodySha256']=base_before['sha256']

    def test_unsaved_native_edit_and_additional_unowned_tree_entity_are_refused(self):
        source=self.originals['inventory']['source'];before=deepcopy(source)
        for fault in ('edit','extra'):
            if fault=='edit':source['tree']['entities'][0]['semanticSha256']='f'*64
            else:
                row=deepcopy(source['tree']['entities'][0]);row['id']='00000000-0000-4000-8000-000000000099'
                for tree in (source['tree'],source['commitOrigin']['latest']['tree']):
                    tree['entities'].append(deepcopy(row));tree['entities'].sort(key=lambda entry:entry['id']);tree['totalEntities']+=1
            self.join=self.clock()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.admit()
            self.originals['inventory']['source']=deepcopy(before);source=self.originals['inventory']['source']

    def test_preexisting_address_or_tablet_is_preserved_by_refusing_admission(self):
        for fault in ('address','tablet'):
            before=deepcopy(self.originals)
            if fault=='address':self.originals['ui']['navigationInventory']['roots']=[address_root(shown=False,visible=False)]
            else:self.originals['ui']['tabletShown']=True;self.originals['model']['tabletShown']=True
            self.join=self.clock()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.admit()
            self.originals=before

    def test_unsupported_original_file_preferences_origin_or_missing_ui_source_fail_before_input(self):
        for fault in ('absent-file','foreign-origin','maturity','fetch','ui-version'):
            before=deepcopy(self.originals)
            if fault=='absent-file':
                row=self.originals['bookmarks']['file'];row.update(status='absent',bytes=None,sha256=None,contentBase64=None,identity=None)
            elif fault=='foreign-origin':self.originals['model']['preferences']['metaverseOrigin']='http://foreign.invalid'
            elif fault=='maturity':self.originals['model']['preferences']['values']['placesAppMaturityFilter']['value']=['teen']
            elif fault=='fetch':self.originals['model']['preferences']['values']['placesAppMetaverseToFetch']['value']=['https://unowned.invalid']
            else:self.originals['ui']['placesControlsVersion']=1
            self.join=self.clock()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.admit()
            self.originals=before

    def test_unknown_body_native_pose_camera_or_scene_birth_cannot_be_requested_into_admission(self):
        for fault in ('scene-birth','moving','feet','camera','body'):
            before=deepcopy(self.originals);source=self.originals['navigation']['source']
            if fault=='scene-birth':source['sceneLoads']['instance']='f'*32
            elif fault=='moving':source['avatar']['velocity']=[1,0,0]
            elif fault=='feet':source['avatar']['feetPosition']=[.1,0,4]
            elif fault=='camera':source['view']['mode']='third person'
            else:self.originals['inventory']['source']['commitOrigin']['latest']['bodySha256']='f'*64
            self.join=self.clock()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.admit()
            self.originals=before

    def test_historical_validation_keeps_original_clocks_and_rejects_changed_proof_fields(self):
        value=self.admit();original=deepcopy(value);self.inventory.clock+=100
        self.assertEqual(original,admission.validate(value))
        value['commit']['bodySha256']='f'*64
        with self.assertRaises(NativeUIError):admission.validate(value)

    def test_stale_foreign_or_missing_original_cannot_borrow_a_new_join_hash(self):
        for fault in ('stale-ui','foreign-native','missing','legacy-origin'):
            before=deepcopy(self.originals)
            if fault=='stale-ui':self.originals['ui']['sampleEpochMs']=self.join['nativeBefore']['capturedEpochMs']-100
            elif fault=='foreign-native':self.originals['navigation']['processId']=43
            elif fault=='missing':self.originals.pop('http')
            else:
                self.originals['inventory']['iosSceneInventoryVersion']=1
                self.originals['inventory']['source'].pop('commitOrigin')
            self.join=self.clock()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.admit()
            self.originals=before;self.join=self.clock()

