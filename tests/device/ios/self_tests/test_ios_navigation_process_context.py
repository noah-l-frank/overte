"""Real owned static/scene HTTP and persistence, explicitly modeled new SDK DTOs.

The app/kernel seams generate separate process originals. This suite does not
launch, kill or access any actual app or device and proves no product restart.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import unittest
import uuid
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack
from feature_journeys.fixtures import context as run_context
from ios.adapters import navigation_process_context as process
from ios.adapters.navigation_restart_proof import OWNERS
from ios.self_tests import test_ios_navigation_scene_inputs as scene_inputs_tests
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from ios.self_tests.test_ios_places_model import Boundary as Model
from ios.self_tests.test_ios_places_http import Boundary as Http
from ios.self_tests.test_ios_navigation_dialogs import Boundary as Dialogs


class NavigationProcessContextTests(unittest.TestCase):
    def setUp(self):
        # Fix the modeled host clock before the first server response exists.
        # Real filesystem latency must not turn this deterministic native seam
        # into a mixture of wall time and its independently advanced timeline.
        start=time.time()
        def host_time():
            return start+getattr(getattr(getattr(self,'h',None),'h',None),'ms',0)/1000
        clock=patch('time.time',side_effect=host_time);clock.start();self.addCleanup(clock.stop)
        self.h=scene_inputs_tests.NavigationSceneInputsTests();self.addCleanup(self.h.doCleanups);self.h.setUp()
        self.lock=self.h.h.lock
        with self.lock.held():
            owner=self.h.owner();owner.enter();self.h.owned_scene()
            self.initial=self.h.admission.archive()
        self.fixture=self.h.h.fixture;self.run=self.initial['runId'];self.url=self.h.h.provider.fixture_url
        self.owners=[str(self.h.h.root/name) for name in OWNERS]
        self.before=self.before_group()
        old=global_packet(self.before['clockJoin']['nativeAfter']['capturedEpochMs']+1,5)
        epoch=old['capturedEpochMs']+10;new=global_packet(epoch,1)
        new.update(instance='f'*32,processId=43,lifecycle=dict(backgrounds=1,activations=2,launches=2))
        self.receipt=dict(input=dict(restartInputVersion=1,componentOnly=False,oldBinding=deepcopy(self.initial['binding']),
            oldNative=self.native_id(old),phase='observed',newBinding=dict(self.initial['binding'],processIdentity='43'),
            newNative=self.native_id(new),ownerFiles=list(self.owners),scriptHandoff=None),oldNative=old,native=new,
            exit=dict(processPresenceVersion=1,commandId='ios-'+'e'*32,instance=new['instance'],sequence=1,
                processId=43,queryProcessId=42,requestedEpochMs=epoch+1,capturedEpochMs=epoch+1,presence='absent',
                nativeResult=-1,nativeError=3,errorSymbol='ESRCH'))
        self.after=self.new_group(epoch+10)
        # Exercise literal formats and every counterexample in the same pure
        # validation round used by the actual feature API, with no global memo.
        if getattr(self,'enable_context_round',True):
            from ios.adapters.navigation_observation_owner import validation_round
            replay=validation_round();replay.__enter__();self.addCleanup(replay.__exit__,None,None,None)

    @staticmethod
    def native_id(packet):return dict(pid=packet['processId'],instance=packet['instance'],lifecycle=deepcopy(packet['lifecycle']))

    def join(self,raw,pid,instance,sequence,*,offset=0):
        first=raw['inventory']['clockBefore']['epochMs']-1;last=raw['ui']['sampleEpochMs']+1
        clocks=[]
        for epoch,count in ((first,sequence),(last,sequence+1)):
            packet=global_packet(epoch,count);packet.update(processId=pid,instance=instance)
            if pid==43:packet['lifecycle']=deepcopy(self.receipt['native']['lifecycle'])
            clocks.append(packet)
        return dict(clockJoinVersion=1,hostBeforeEpochMs=1000100.+offset,hostAfterEpochMs=1000100.+offset+last-first,
            hostBeforeMonotonic=10.1+offset/1000,hostAfterMonotonic=10.1+(offset+last-first)/1000,
            nativeBefore=clocks[0],nativeAfter=clocks[1],originalsSha256=digest(raw),sourceTimes=[
                dict(source=name,field=field,epochMs=packet[field]) for name,packet in raw.items()
                for field in ('capturedEpochMs','sampleEpochMs') if field in packet])

    def before_group(self):
        raw=deepcopy(self.fixture.originals);clock=self.fixture.inventory.clock+.02
        books=self.fixture.books;books.clock=clock
        # Real file bytes and independently generated loaded-map SDK original.
        from navigation_observation import viewpoint_urls
        wanted={run_context(self.run)['renamed']:viewpoint_urls(self.fixture.inputs['sceneUrl'])['A']}
        books.path.write_text(json.dumps(wanted));books.loaded=wanted;raw['bookmarks']=books.reader().read(self.run)
        model=Model();model.clock=books.clock+.002;model.sequence=1;model.shown=False;model.pages=[]
        model.mutate=lambda value:value.update(iosPlacesModelVersion=2,preferences=deepcopy(self.initial['originals']['model']['preferences']))
        raw['model']=model.reader().read(self.run)
        http=Http();http.clock=model.clock+.002;http.sequence=1;raw['http']=http.reader().read(self.run)
        dialogs=Dialogs();dialogs.clock=http.clock+.002;dialogs.sequence=1;raw['dialogs']=dialogs.reader().read(self.run)
        raw['replies']=dict(raw['replies'],commandId='ios-'+'a'*32,sequence=2,capturedEpochMs=dialogs.epoch()+1)
        raw['ui']=dict(raw['ui'],sampleEpochMs=dialogs.epoch()+2,elapsedMs=round(dialogs.clock*1000)+2,
            placesSourceSequence=2,navigationDialogSourceSequence=self.h.b.source_sequence+1)
        address=PrivateFeatureState(self.h.h.root/'ios-navigation-address-42-inputs.json').read()
        return dict(originals=raw,clockJoin=self.join(raw,42,self.initial['clockJoin']['nativeAfter']['instance'],3),
            provider=self.h.h.provider.scene(),missing=None,addressOwner=address)

    def new_group(self,start):
        # Build a second SDK's original DTOs from its own modeled startup state.
        # Production transfer() never rewrites any source, time, counter or ID.
        raw=deepcopy(self.before['originals']);delta=start-raw['inventory']['clockBefore']['epochMs']
        epochs={'epochMs','capturedEpochMs','requestedEpochMs','sampleEpochMs','startedEpochMs','updatedEpochMs','releasedEpochMs'}
        def emit(value):
            if type(value) is list:return [emit(item) for item in value]
            if type(value) is not dict:return value
            result={}
            for key,item in value.items():
                if key=='processId':item=43
                elif key in epochs and type(item) is int:item+=delta
                elif key in ('monotonicMs','elapsedMs') and type(item) is int:item+=delta
                elif key in ('instance','treeInstance'):
                    digest_=hashlib.sha256(str(item).encode()).hexdigest()[:32]
                    item=str(uuid.UUID(hex=digest_)) if '-' in item else digest_
                elif key in ('requestId','commandId'):item='ios-'+uuid.uuid4().hex
                result[key]=emit(item)
            return result
        raw=emit(raw)
        # A genuinely new process has no old QML root. Do not carry its UUID or
        # field into the modeled startup inventory, even under new source IDs.
        raw['ui']['navigationInventory']['roots']=[]
        # Native import history and current independent read refer to the same
        # actual startup load rather than separate fabricated request identities.
        a,b=raw['inventory']['source']['sceneLoads'],raw['navigation']['source']['sceneLoads']
        a.update(sequence=1,commandId=raw['inventory']['requestId'])
        b.update(sequence=2,commandId=raw['navigation']['requestId'])
        return dict(originals=raw,clockJoin=self.join(raw,43,self.receipt['native']['instance'],2,offset=100),
            provider=self.h.h.provider.scene(),missing=None)

    def transfer(self):return process.transfer(self.initial,self.before,self.receipt,self.after,self.owners,self.url)

    def test_original_writer2_context_keeps_its_shape_and_cannot_adopt_new_surface_responsibility(self):
        original=deepcopy((self.initial,self.before,self.receipt,self.after))
        value=process.transfer(self.initial,self.before,self.receipt,self.after,self.owners,self.url,version=2)
        self.assertEqual(2,value['iosNavigationProcessContextVersion'])
        self.assertEqual(value,process.validate(value,self.owners))
        self.assertEqual(2,process.source_basis(value,self.owners)['iosNavigationProcessSourceBasisVersion'])
        self.assertNotIn('placesRoots',value['oldScope']);self.assertEqual(original,(self.initial,self.before,self.receipt,self.after))
        before=deepcopy(self.before);before['surfaceOwner']={}
        with self.assertRaises(NativeUIError):process.transfer(self.initial,before,self.receipt,self.after,self.owners,self.url,version=2)

    def rehash(self,group):group['clockJoin']['originalsSha256']=digest(group['originals'])

    def test_new_source_floor_preserves_original_admission_and_actual_persisted_bookmark_without_retiming(self):
        originals=deepcopy((self.initial,self.before,self.receipt,self.after));value=self.transfer()
        self.assertEqual(originals,(self.initial,self.before,self.receipt,self.after))
        self.assertEqual(value,process.validate(value,self.owners));basis=process.source_basis(value,self.owners)
        self.assertEqual('43',basis['binding']['processIdentity']);self.assertEqual('42',basis['bookmarkBaseline']['binding']['processIdentity'])
        self.assertEqual(self.initial['bookmarkBaseline'],basis['bookmarkBaseline']);self.assertEqual(self.after['originals'],basis['originals'])
        self.assertEqual(self.before['originals']['bookmarks']['file'],self.after['originals']['bookmarks']['file'])
        self.assertNotIn('passed',value);self.assertNotIn('restored',basis)
        self.assertEqual(3,value['iosNavigationProcessContextVersion']);self.assertEqual(3,basis['iosNavigationProcessSourceBasisVersion'])
        self.assertEqual('retained',value['oldScope']['addressRoot']['root']['status'])
        self.assertFalse(value['oldScope']['addressRoot']['root']['drained'])
        self.assertEqual([],value['after']['originals']['ui']['navigationInventory']['roots'])

    def test_old_source_reused_under_new_join_or_new_source_births_cannot_authorize_transfer(self):
        for name in self.after['originals']:
            original=deepcopy(self.after);self.after['originals'][name]=deepcopy(self.before['originals'][name]);self.rehash(self.after)
            with self.subTest(source=name),self.assertRaises((NativeUIError,ValueError)):self.transfer()
            self.after=original

    def test_retained_root_requires_the_actual_acknowledged_original_owner_and_closed_owned_text(self):
        original=deepcopy(self.before)
        for fault in ('missing','foreign-root','foreign-text','unresolved','foreign-owner','rewound-source'):
            self.before=deepcopy(original);ui=self.before['originals']['ui']
            if fault=='missing':self.before.pop('addressOwner')
            elif fault=='foreign-root':ui['navigationInventory']['roots'][0]['rootId']=str(uuid.uuid4())
            elif fault=='foreign-text':ui['navigationInventory']['roots'][0]['field']['text']='unowned edit'
            elif fault=='rewound-source':ui['navigationDialogSourceSequence']=1
            else:
                carrier=self.before['addressOwner']
                if fault=='foreign-owner':carrier['binding']['artifactSha256']='0'*64
                else:
                    state=unpack(carrier['payload'])[0];state['rows'][-1].update(phase='issued',closed=None)
                    carrier['payload']=pack([state])
            self.rehash(self.before)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.transfer()
        self.before=original

    def test_root_free_version1_history_stays_version1_and_cannot_adopt_retained_roots(self):
        # Explicit legacy SDK source: no root existed in this version-1 case.
        # This is separate from the current normal Go To retained-root case.
        before=deepcopy(self.before);before.pop('addressOwner');before['originals']['ui']['navigationInventory']['roots']=[]
        self.rehash(before);originals=deepcopy((before,self.after))
        value=process.transfer(self.initial,before,self.receipt,self.after,self.owners,self.url,version=1)
        self.assertEqual(1,value['iosNavigationProcessContextVersion']);self.assertNotIn('addressRoot',value['oldScope'])
        self.assertEqual(value,process.validate(value,self.owners));basis=process.source_basis(value,self.owners)
        self.assertEqual(1,basis['iosNavigationProcessSourceBasisVersion']);self.assertEqual(originals,(before,self.after))
        with self.assertRaises(NativeUIError):
            process.transfer(self.initial,self.before,self.receipt,self.after,self.owners,self.url,version=1)

    def test_actual_kernel_death_and_full_candidate_are_required_even_with_new_scene_and_bookmarks(self):
        original=deepcopy(self.receipt)
        for fault in ('kernel','candidate','owner','new-native'):
            if fault=='kernel':self.receipt['exit'].update(presence='unknown',nativeError=1,errorSymbol='EPERM')
            elif fault=='candidate':self.receipt['input']['newBinding']['artifactSha256']='0'*64
            elif fault=='owner':self.receipt['input']['ownerFiles'][1]=str(self.h.h.root/'other.json')
            else:self.receipt['native']['instance']=self.receipt['oldNative']['instance']
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.transfer()
            self.receipt=deepcopy(original)

    def test_acknowledged_restart_with_ignored_persisted_bookmark_cannot_report_the_old_requested_name(self):
        books=self.fixture.books;books.path.write_text('{}');books.loaded={};books.clock+=1
        packet=books.reader().read(self.run)
        for key in ('loaded','file'):self.after['originals']['bookmarks'][key]=deepcopy(packet[key])
        self.rehash(self.after)
        with self.assertRaises(NativeUIError):self.transfer()

    def test_foreign_world_unsaved_tree_or_open_ui_keeps_transfer_unresolved(self):
        original=deepcopy(self.after)
        for fault in ('world','edit','ui','preferences','lookup'):
            raw=self.after['originals']
            if fault=='world':raw['navigation']['source']['sceneUrl']='http://foreign.invalid/scene.json'
            elif fault=='edit':raw['inventory']['source']['tree']['entities'][0]['semanticSha256']='f'*64
            elif fault=='ui':raw['ui']['tabletShown']=True
            elif fault=='preferences':raw['model']['preferences']['metaverseOrigin']='http://foreign.invalid'
            else:raw['replies']['currentLookupActive']=True
            self.rehash(self.after)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.transfer()
            self.after=deepcopy(original)

    def test_historical_context_cannot_change_original_scope_or_owner_files_on_reconstruction(self):
        value=self.transfer();retained=deepcopy(value)
        self.h.h.provider.scene=lambda:self.fail('Historical validation must not read fixture')
        self.assertEqual(retained,process.validate(value,self.owners))
        for fault in ('baseline','current','owner-list','version'):
            value=deepcopy(retained)
            if fault=='baseline':value['initialAdmission']['originals']['ui']['sampleEpochMs']+=1
            elif fault=='current':value['currentScope']['scene']['sceneTicket']='0'*32
            elif fault=='owner-list':value['ownerFiles']=list(reversed(value['ownerFiles']))
            else:value['iosNavigationProcessContextVersion']=True
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):process.validate(value,self.owners)
