"""Real durable URL owner/PicoNavigation over explicit SDK/Qt/model actors.

No sockets, native renderer, downloaded response, peer or device facts are
supplied here. Independent actual QML and original native bodies have their
own Qt host tests; this joins the real host owner and original transport.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import inspect
import hashlib
import os
from functools import partial
import base64
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
import uuid
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
import test_normal_scripts as sources
from adapters.pico4.avatar_urls import PicoAvatarUrls
from adapters.pico4 import normal_scripts
from adapters.token_script_ui import TokenScriptUI
from adapters.pico4.avatar_state import NativePicoAvatarState,ACTION,FILE,sha
from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI,PicoAvatarPeopleIO
from adapters.pico4.navigation import NativeNavigationIO
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
RUN='d'*32
ORIGINAL='qrc:/meshes/defaultAvatar_full.fst'
FBX='qrc:/meshes/mannequin/mannequin.fbx'

class AvatarUrlsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.instance,self.native=self.fixture.instance,self.fixture.native;self.target=self.native.target
        self.root=self.fixture.fixture.state_root;self.root.chmod(0o700)
        key=hashlib.sha256(('org.overte.pico\0'+self.target).encode()).hexdigest()[:32]
        self.store=PrivateFeatureState(self.root/('avatar-urls-owner-'+key+'-'+RUN+'.json'))
        self.clock=0.;self.epoch=int(time.time()*1000);self.page='home1';self.dialog=False;self.focus=False;self.entered=''
        self.lost=False;self.ignore=False;self.freeze=False;self.native_queries=0;self.packet=None;self.guard_delay=None
        self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('avatar-people')
        self.activate('baseline')
        client=Client('http://controlled.test/feature-fixture/v1','a'*64)
        client.request=lambda path,**kw:self.journal.phase(RUN,kw['phase_nonce'])
        self.phase=PhaseFixtureReader(client,RUN,'avatar-people',epoch_ms=lambda:self.epoch,monotonic=lambda:self.clock)
        self.source=dict(picoAvatarStateVersion=1,sessionId='77777777-7777-4777-8777-777777777777',requestedUrl=ORIGINAL,
            preferenceUrl=ORIGINAL,modelName='mannequin',avatarEntityStorage=dict(avatarEntityStorageVersion=1,rows=[dict(id='88888888-8888-4888-8888-888888888888',bytes=7,sha256=sha('unowned'),base64=base64.b64encode(b'unowned').decode())]),avatarLoads=self.history('a'),modelInstance='f'*32,modelUrl=ORIGINAL,modelLoads=self.history('b'),
            rigId=17,loaded=True,geometry=dict(instance='e'*32,url=FBX),scale=1,targetScale=1,hipsJoint=3,localRenderingEnabled=False)
        self.effect(ORIGINAL)
        old_read=self.native.read_debug_app_file
        def read(target,package,path,**kw):
            if path=='files/overte-e2e/'+FILE:return '' if self.packet is None else json.dumps(self.packet)
            return old_read(target,package,path,**kw)
        def write(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':raise AssertionError('Unexpected actor write')
            c=json.loads(raw);current=self.widgets();row=next(r for r in current['controls'] if r['id']==c['controlId'])
            self.assertEqual(row['token'],c['controlToken']);self.assertEqual(self.native.sequence+1,c['sequence'])
            self.native.inputs.append(deepcopy(c));self.native.sequence+=1
            identifier=c['controlId']
            if identifier=='tablet.home':self.page='home1'
            elif identifier=='tablet.page.2':self.page='home2'
            elif identifier=='avatar.entry':self.page='avatar'
            elif identifier=='avatar.url':self.dialog=True;self.entered=self.source['requestedUrl'];self.focus=False
            elif identifier=='avatar.dialog.input':
                self.focus=True
                if c['action']=='replace':self.entered=c['text']
            elif identifier=='avatar.dialog.cancel':self.dialog=False;self.focus=False
            elif identifier=='avatar.dialog.confirm':
                if not self.ignore:self.effect(self.entered)
                self.dialog=False;self.focus=False
                if self.lost:raise OSError('Declared lost reply after actual actor consumption')
            else:raise AssertionError(identifier)
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=c['commandId'],sequence=c['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.epoch)
        access=self.root/'avatar-adapter-access.json'
        PrivateFeatureState(access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=client.url,adapterToken='a'*64),None)
        for boundary in (patch.dict(os.environ,{'OVERTE_PICO_FEATURE_FIXTURE_CONFIG':str(access)}),
            patch('adapters.feature_fixture_access.client',return_value=client),
            patch.object(normal_scripts,'TokenScriptUI',partial(TokenScriptUI,monotonic=lambda:self.clock,sleep=self.sleep)),
            patch('adapters.common.time.time',side_effect=lambda:self.epoch/1000),patch.object(self.native,'snapshot',side_effect=self.widgets),patch.object(self.native,'read_debug_app_file',side_effect=read),
            patch.object(self.native,'write_debug_app_file',side_effect=write),patch.object(self.native,'epoch_milliseconds',side_effect=lambda target:self.epoch)):
            boundary.start();self.addCleanup(boundary.stop)
        # Admit the new fixture config on a cold real canonical binding; never
        # change an already sealed candidate's environment. Native/model and
        # fixture HTTP are the declared actors, not a replacement adapter.
        self.instance=self.fixture.fixture.instance()
        observer=patch.object(self.instance,'_native_feature_observer',side_effect=lambda _target:self.reader());observer.start();self.addCleanup(observer.stop)
        self.lock=self.instance._script_journey()._lock(self.target,None)
        _ui,_observe,self.binding=self.instance._script_runtime(self.target)
        self.assertFalse(any(cap.startswith('feature.avatar-people.') for cap in self.instance.capabilities(self.target)))
    def history(self,name):return dict(modelLoadsVersion=1,instance=name*32,sequence=0,capturedEpochMs=self.epoch,complete=True,currentGeneration=0,requestedSha256='',events=[])
    def effect(self,url):
        for name in ('avatarLoads','modelLoads'):
            h=self.source[name];h['currentGeneration']+=1;h['requestedSha256']=sha(url)
            h['events'].append(dict(eventSequence=len(h['events'])+1,generation=h['currentGeneration'],kind='requested',capturedEpochMs=self.epoch,requestedSha256=sha(url),resourceSha256='',success=None))
            h['events'].append(dict(eventSequence=len(h['events'])+1,generation=h['currentGeneration'],kind='finished',capturedEpochMs=self.epoch,requestedSha256=sha(url),resourceSha256=sha(url),success=not url.endswith('/missing.fst')))
        if url.endswith('/missing.fst'):
            h=self.source['modelLoads'];h['currentGeneration']+=1;h['requestedSha256']=sha(ORIGINAL)
            for kind,result in (('requested',None),('finished',True)):
                h['events'].append(dict(eventSequence=len(h['events'])+1,generation=h['currentGeneration'],kind=kind,capturedEpochMs=self.epoch,requestedSha256=sha(ORIGINAL),resourceSha256=sha(ORIGINAL) if result is not None else '',success=result))
        missing=url.endswith('/missing.fst');loaded=FBX if url==ORIGINAL or missing else url.rsplit('/',1)[0]+'/mannequin/mannequin.fbx'
        self.source.update(requestedUrl=url,preferenceUrl=url,modelUrl=ORIGINAL if missing else url,loaded=True,geometry=dict(instance=uuid.uuid4().hex,url=loaded))
    def activate(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;self.journal.activate(RUN,ticket,verb,inputs or {});return ticket
    def sleep(self,value):
        self.clock+=value
        if not self.freeze:self.epoch+=round(value*1000)
    def widgets(self):
        controls=[]
        def add(identifier,**extra):
            row=dict(id=identifier,enabled=True,focused=self.focus if identifier=='avatar.dialog.input' else False)
            if not identifier.startswith('tablet.'):row.update(inputReady=not identifier.endswith('.page'),**extra)
            identity=json.dumps({k:v for k,v in row.items() if k!='focused'},sort_keys=True)
            row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,identity));controls.append(row)
        add('tablet.home')
        if self.page=='home1':add('tablet.page.2')
        elif self.page=='home2':add('avatar.entry')
        else:
            add('avatar.page',managing=False);add('avatar.url',managing=False)
            if self.dialog:
                args=dict(managing=False,dialogTitle='Specify Avatar URL',dialogSource='ActualMessageBoxActor')
                add('avatar.dialog.input',text=self.entered,**args);add('avatar.dialog.confirm',**args);add('avatar.dialog.cancel',**args)
        return dict(schemaVersion=1,bridgeId=self.native.bridge_id,generation=self.native.generation,processId=123,elapsedMs=100+round(self.clock*1000),
            updatedEpochMs=self.epoch,lastCommandSequence=self.native.sequence,open=True,ready=True,controls=controls,featureControlsVersion=1,avatarPeopleControlsVersion=1)
    def reader(self):
        def send(request):
            self.native_queries+=1;value=deepcopy(self.source)
            for name in ('avatarLoads','modelLoads'):
                self.source[name]['sequence']+=1;value[name]['sequence']=self.source[name]['sequence'];value[name]['capturedEpochMs']=self.epoch
            self.packet=dict(schemaVersion=1,requestId=request['commandId'],instance='c'*32,sequence=self.native_queries,processId=123,
                requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=value)
        return NativePicoAvatarState(send,lambda:json.dumps(self.packet),lambda:self.epoch,lambda:True,123,monotonic=lambda:self.clock,sleep=self.sleep)
    def make(self):
        return self.instance._avatar_urls(self.target,RUN,source_lock=self.lock)
    def invoke(self,verb):
        with self.lock.held():return self.make().invoke(verb)
    def test_normal_paging_url_failure_original_restore_and_retained_owner(self):
        self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));self.invoke('act')
        self.assertEqual(['tablet.home','tablet.page.2','avatar.entry','avatar.url','avatar.dialog.input','avatar.dialog.input','avatar.dialog.confirm'],[r['controlId'] for r in self.native.inputs])
        self.activate('avatar-url',dict(resource='missing.fst'));self.invoke('act')
        state=unpack(self.store.read()['payload'])[0];self.assertTrue(state['calls'][-1]['settled'])
        self.activate('avatar-restore');self.invoke('act');state=unpack(self.store.read()['payload'])[0]
        self.assertTrue(state['restored']);self.assertEqual(ORIGINAL,self.source['requestedUrl']);self.assertIsNotNone(self.store.read());self.assertTrue(self.instance._avatar_urls_owned(self.target))
        # A second cleanup is its own real phase, preserving all original inputs.
        count=len(self.native.inputs);self.activate('cleanup');self.invoke('cleanup');self.assertEqual(count,len(self.native.inputs))
    def test_lost_confirm_is_only_observed_after_cold_reconstruction(self):
        self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));self.lost=True
        with self.assertRaises(RuntimeError):self.invoke('act')
        self.lost=False;count=len(self.native.inputs);self.invoke('reconcile');self.assertEqual(count,len(self.native.inputs))
        self.assertIsNone(unpack(self.store.read()['payload'])[0]['pending'])
    def test_last_original_guard_phase_advance_or_frozen_clock_prevents_writer(self):
        for fault in ('phase','slow'):
            with self.subTest(fault=fault):
                if fault=='slow':self.doCleanups();self.setUp()
                self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));original=NativeNavigationIO.guard;fired=[]
                def guard(io):
                    original(io)
                    if inspect.currentframe().f_back.f_code.co_name=='send' and not fired:
                        fired.append(True)
                        if fault=='phase':self.activate('cleanup')
                        else:self.clock+=2 # Native clock is intentionally frozen.
                with patch.object(NativeNavigationIO,'guard',guard):
                    with self.assertRaises(RuntimeError):self.invoke('act')
                self.assertEqual([True],fired);self.assertEqual([],self.native.inputs)
                self.assertIsNotNone(unpack(self.store.read()['payload'])[0]['pending'])
    def test_wrong_geometry_resource_generation_or_scale_cannot_supply_a_model_effect(self):
        self.invoke('prepare');ticket=self.activate('avatar-url',dict(resource='avatar-a.fst'))
        with self.lock.held():
            owner=self.make();before=deepcopy(self.source);url=self.phase.fixture_url+'tickets/'+ticket+'/avatar-a.fst'
            self.effect(url);call=dict(url=url,verb='avatar-url',before=1,phase=self.phase.status())
            self.assertTrue(owner.matches(self.source,call))
            for key,value in (('modelUrl',ORIGINAL),('geometry',dict(instance='e'*32,url=FBX)),('scale',1.5),('avatarEntityStorage',dict(avatarEntityStorageVersion=1,rows=[]))):
                altered=deepcopy(self.source);altered[key]=value;self.assertFalse(owner.matches(altered,call))
            altered=deepcopy(self.source);altered['modelLoads']['events'][-1]['success']=False;self.assertFalse(owner.matches(altered,call))
            ticket=self.activate('avatar-url',dict(resource='missing.fst'));owner.sample();call.update(before=len(owner.state['frames']),phase=self.phase.status())
            self.effect(self.phase.fixture_url+'tickets/'+ticket+'/missing.fst');call['url']=self.source['requestedUrl']
            self.assertTrue(owner.matches(self.source,call))
            altered=deepcopy(self.source);altered['geometry']['url']=url.rsplit('/',1)[0]+'/mannequin/mannequin.fbx';self.assertFalse(owner.matches(altered,call))
            altered=deepcopy(self.source);altered['avatarLoads']['currentGeneration']+=1;self.assertFalse(owner.matches(altered,call))
    def test_cold_reconstruction_rejects_forged_quiet_flags_and_preserves_original_bytes(self):
        self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));self.invoke('act')
        saved=self.store.read();state=unpack(saved['payload'])[0]
        from adapters.script_journey.history import pack
        altered=deepcopy(state);altered['calls'][0]['quiet']['first']=altered['calls'][0]['quiet']['last']
        value=deepcopy(saved);value['payload']=pack([altered]);self.store.write(value,saved)
        with self.assertRaises(RuntimeError):self.invoke('sample')
        self.assertEqual(value,self.store.read())

    def test_lost_final_delivery_cold_reconcile_never_replays_and_copy_age_is_checked(self):
        self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));original=PicoAvatarUrls.finish;fired=[]
        def finish(owner,frame):
            if owner.state['calls'] and owner.state['calls'][-1]['settled'] and not fired:
                fired.append(True);self.clock+=2 # Original native epoch stays frozen.
            return original(owner,frame)
        with patch.object(PicoAvatarUrls,'finish',finish):
            with self.assertRaises(RuntimeError):self.invoke('act')
        self.assertEqual([True],fired);count=len(self.native.inputs);self.invoke('reconcile');self.assertEqual(count,len(self.native.inputs))
        self.assertTrue(unpack(self.store.read()['payload'])[0]['calls'][-1]['settled'])

    def test_changed_original_preferences_or_unowned_storage_never_admit_normal_input(self):
        self.source['preferenceUrl']=''
        with self.assertRaises(RuntimeError):self.invoke('prepare')
        self.assertEqual([],self.native.inputs)
        self.doCleanups();self.setUp();self.invoke('prepare')
        self.source['avatarEntityStorage']['rows']=[];self.activate('avatar-url',dict(resource='avatar-a.fst'))
        with self.assertRaises(RuntimeError):self.invoke('act')
        self.assertEqual([],self.native.inputs);self.assertEqual([],unpack(self.store.read()['payload'])[0]['calls'])
    def test_owned_uri_is_normally_restored_after_uncertain_input_but_foreign_uri_is_preserved(self):
        self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));self.lost=True
        with self.assertRaises(RuntimeError):self.invoke('act')
        old=unpack(self.store.read()['payload'])[0]['pending'];self.lost=False;self.activate('cleanup');self.invoke('cleanup')
        self.assertEqual(ORIGINAL,self.source['requestedUrl']);self.assertEqual([old],unpack(self.store.read()['payload'])[0]['unresolved'])
        self.doCleanups();self.setUp();self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));self.lost=True
        with self.assertRaises(RuntimeError):self.invoke('act')
        self.lost=False;self.effect('https://foreign.invalid/avatar.fst');self.activate('cleanup');count=len(self.native.inputs)
        with self.assertRaises(RuntimeError):self.invoke('cleanup')
        self.assertEqual(count,len(self.native.inputs));self.assertEqual('https://foreign.invalid/avatar.fst',self.source['requestedUrl'])

    def test_ack_without_load_stays_pending_and_cleanup_retains_uncertain_ticket(self):
        self.invoke('prepare');self.activate('avatar-url',dict(resource='avatar-a.fst'));self.ignore=True
        with self.assertRaises(RuntimeError):self.invoke('act')
        old=unpack(self.store.read()['payload'])[0]['pending'];self.assertIsNotNone(old)
        self.ignore=False;self.activate('cleanup');count=len(self.native.inputs);self.invoke('cleanup')
        state=unpack(self.store.read()['payload'])[0];self.assertEqual([old],state['unresolved']);self.assertTrue(state['restored'])
        self.assertEqual(count,len(self.native.inputs));self.assertFalse(state['calls'][0]['settled'])

if __name__=='__main__':unittest.main()
