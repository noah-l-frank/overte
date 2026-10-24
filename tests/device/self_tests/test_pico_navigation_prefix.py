"""Continuous original Python/HTTP/Session flow; Qt/VM/OS are explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import shutil
import unittest
from unittest.mock import patch
import uuid
from urllib.request import build_opener, ProxyHandler, HTTPSHandler

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_navigation_directory import NativeNavigationDirectory
from adapters.native_navigation_modals import NativeNavigationModals
from adapters.native_navigation_panels import NativeNavigationPanels
from adapters.navigation_arrival import NavigationArrival
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.navigation_directory import NavigationDirectory
from adapters.navigation_origin import NavigationOrigin
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.pico4.navigation import NativeNavigationIO, PicoNavigation
from adapters.pico4.navigation_prefix import NavigationPrefix, VERBS
from adapters.pico4.navigation_prefix_source import NavigationPrefixSource
from adapters.pico4.normal_navigation_origin import PicoNavigationOriginIO
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_places_ui import TokenPlacesUI
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.server import make_server
from feature_journeys.witness import Client, Journal
from navigation_observation import viewpoint_urls
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests import test_navigation_directory as directory_fixture
from self_tests import test_navigation_origin as origin_fixture
from self_tests import test_navigation_arrival as arrival_fixture
from self_tests import test_token_places_ui as places
from self_tests.test_pico_tablet_home import original as home_original
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests import test_account_provider as tls_fixture
from feature_journeys import witness

RUN=places.RUN
INPUTS=directory_fixture.INPUTS
PID=31


class Model(origin_fixture.Model,directory_fixture.Model):
    def __init__(self,root):
        super().__init__(root);self.page=False;self.owner_test=None
        self.native_packets={};self.native_counters={};self.home_count=0;self.root_birth=None
    def raw(self):
        value=origin_fixture.Model.raw(self) if self.login else directory_fixture.Model.raw(self)
        # The actual Pico snapshot exports Origin v1 on every surface (not
        # only Login). Home itself is the original entity, never a QML button.
        value['navigationOriginControlsVersion']=1;value['featureControlsVersion']=1;value['processId']=PID
        value['controls']=[row for row in value['controls'] if row['id']!='tablet.home']
        return value
    def send(self,command):
        if self.login:reply,epoch=origin_fixture.Model.send(self,command)
        else:reply,epoch=directory_fixture.Model.send(self,command)
        reply['processId']=PID;return reply,epoch
    def source_read(self,request):
        directory_fixture.Model.source_read(self,request);self.source_packet['processId']=PID
        if not self.page:self.source_packet['roots']=[]
    def source_send(self,request):
        origin_fixture.Model.source_send(self,request);self.packet['processId']=PID
    def native_send(self,request):
        super().native_send(request);self.native_packet['processId']=PID
    def bookmarks(self):
        from adapters.native_location_bookmarks import NativeLocationBookmarks
        return NativeLocationBookmarks(self.native_send,lambda:json.dumps(self.native_packet),self.epoch,self.guard,PID,monotonic=lambda:self.clock,sleep=self.sleep)
    def private(self,request,kind):
        self.native_counters[kind]=self.native_counters.get(kind,0)+1
        sequence=self.native_counters[kind];scope=dict(bridgeId=self.bridge,generation=self.generation,sequence=self.sequence,
            elapsedMs=100+round(self.clock*1000),observedEpochMs=self.epoch())
        if kind=='panels':
            if self.page and self.root_birth is None:self.root_birth=self.epoch()
            value=dict(navigationPanelsVersion=2,commandId=request['commandId'],runId=RUN,instance='7'*32,sequence=sequence,
                processId=PID,capturedEpochMs=self.epoch(),complete=True,ui=scope|dict(open=True,ready=True),
                roots=[] if not self.page else [dict(rootId='e'*32,profile='pico-places-v1',sourceSha256='d'*64,
                    firstObservedEpochMs=self.root_birth,alive=True,inCurrentTree=True,visible=True)],lookup=dict(complete=True,home=None,address=None))
        else:
            value=dict(navigationModalVersion=1,commandId=request['commandId'],runId=RUN,instance='8'*32,sequence=sequence,
                processId=PID,capturedEpochMs=self.epoch(),uiEpochMs=self.epoch(),uiElapsedMs=scope['elapsedMs'],
                uiInputSequence=self.sequence,uiBridgeId=self.bridge,uiGeneration=self.generation,tabletOpen=True,rootComplete=True,records=[])
        self.native_packets[kind]=value
    def reader_for(self,kind):
        cls=NativeNavigationPanels if kind=='panels' else NativeNavigationModals
        return cls(lambda request:self.private(request,kind),lambda:json.dumps(self.native_packets.get(kind)),
            self.epoch,self.guard,PID,monotonic=lambda:self.clock,sleep=self.sleep)


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationPrefixTests(unittest.TestCase):
    model_type=Model
    @classmethod
    def setUpClass(cls):tls_fixture.AccountProviderTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):tls_fixture.AccountProviderTests.tearDownClass.__func__(cls)
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.temporary._finalizer.detach()
        self.root=Path(self.temporary.name);self.root.chmod(0o700);self.model=self.model_type(self.root)
        print('Retained original Navigation prefix fixture:',self.root,flush=True)
        self.address=patch.object(places,'ADDRESS',viewpoint_urls(INPUTS['sceneUrl'])['A']);self.address.start();self.addCleanup(self.address.stop)
        self.server=make_server('r'*64,'p'*64,navigation_resources=self.model.provider,tls_context=self.server_context)
        self.server.journal=Journal(clock=self.model.epoch);registered=self.server.journal.register('world-navigation')
        self.server.journal.runs[RUN]=self.server.journal.runs.pop(registered)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.thread.join,2);self.addCleanup(self.server.shutdown)
        self.url='https://127.0.0.1:'+str(self.server.server_port);self.model.network=self.url
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=self.client_context),witness.NoRedirect())
        for change in (patch.object(witness,'build_opener',return_value=self.opener),
                       patch.object(directory_fixture,'urlopen',side_effect=self.opener.open)):
            change.start();self.addCleanup(change.stop)
        self.clients={role:Client(self.url+'/feature-fixture/v1',token) for role,token in (('primary','r'*64),('actor','p'*64))}
        for client in self.clients.values():client.run=RUN;client.area='world-navigation'
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.activate('baseline')
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity=str(PID)+':'+getattr(self,'process_start','synthetic-start'),sessionId=self.model.bridge,
            generation=0,targetFingerprint=self.target_fingerprint() if hasattr(self,'target_fingerprint') else 'c'*64)
        self.world=arrival_fixture.Model(run=RUN);self.addCleanup(self.world.close);self.world.epoch=self.model.epoch
        self.world.guard=self.model.guard;self.world.subject.edit=lambda value:value.update(processId=PID)
        self.home_sequence=0;self.qstatus=None;self.qcommand=None;self.original_calls=0
        test=self
        class Transport(FakeTransport):
            def stage(self,envelope,profile,*,before_publish=None):
                if before_publish is not None:
                    # Session callbacks may use original memory/host CAS/clock,
                    # never reenter HTTP, SDK/native guards or source readers.
                    with patch.object(test.flow.phase,'read',side_effect=AssertionError('HTTP in Session callback')):
                        before_publish(deepcopy(envelope));before_publish(deepcopy(envelope))
                self.envelopes.append(deepcopy(envelope))
                if hasattr(test.model,'consume_controller'):test.model.consume_controller(envelope)
                else:
                    test.model.home_count+=1;test.model.login=False;test.model.focus='';test.model.generation=str(uuid.uuid4())
                return dict(sequence=envelope['sequence'])
        self.xr=Transport();self.session=PicoOpenXrAdapterSession(self.xr,'owned-model',self.root);self.session.begin(self.binding['processIdentity'])
        self.flows={};self.flow=self.make('primary')

    def activate(self,verb):
        ctx=context(RUN)
        if verb=='directory-search':
            prior=sum(row['stimulus']['verb']==verb for row in self.server.journal.runs[RUN]['phaseActivations'])
            inputs=dict(query=ctx['hidden' if prior==0 else 'name'])
        elif verb=='directory-select':inputs=dict(destination=ctx['destination'])
        else:inputs={} if verb in ('baseline','open') else dict(name=ctx['renamed' if 'rename' in verb else 'name'])
        self.ticket=uuid.uuid4().hex;self.server.journal.activate(RUN,self.ticket,verb,inputs);self.model.provider.activate(RUN,self.ticket)
        return dict(contractVersion=CONTRACT_VERSION,runId=RUN,fixtureUrl=self.url+'/feature-fixture/v1/runs/'+RUN+'/',ticket=self.ticket,verb=verb,inputs=inputs)

    def write(self,target,package,path,raw):
        self.assertEqual(('owned-model','org.overte.pico'),(target,package));self.qcommand=raw
        value=json.loads(raw)
        if value:self.qstatus,_epoch=self.model.send(value)
    def read(self,target,package,path,**_options):
        if path.endswith('observation.json'):return json.dumps(self.model.raw())
        if path.endswith('status.json'):return json.dumps(self.qstatus)
        return self.qcommand
    def installed(self,_target):self.original_calls+=1;return True
    def make(self,role):
        adb=SimpleNamespace(write_debug_app_file=self.write,read_debug_app_file=self.read,epoch_milliseconds=lambda _target:self.model.epoch(),foreground_package=lambda _target:'org.overte.pico')
        adapter=SimpleNamespace(adb=adb,require_same_process=lambda *_args:self.model.guard(),require_pico_session_identity=lambda _target:self.binding['processIdentity'],
            _installation=self.installed,probe_retry_policy=lambda:(1,0),require=lambda _target:True,pico_input_session=lambda _target:self.session)
        transport=NativeNavigationIO(adapter,'owned-model',self.binding['processIdentity'],lambda _op:None)
        navigation=PicoNavigation(transport,self.root/('normal-'+role+'.json'),dict(schemaVersion=1,sourceRevision='a'*40,
            artifactSha256='b'*64,installedCandidateVerified=True),self.binding['processIdentity'],INPUTS['sceneUrl'],monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        original=PicoScriptIO(navigation)
        def ui(intent):return TokenPlacesUI(PicoPlacesIO(original),intent,RUN,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        from adapters.native_navigation_environment import NativeNavigationEnvironment
        env=NativeNavigationEnvironment(self.model.source_send,lambda:json.dumps(self.model.packet) if self.model.packet else '',self.model.epoch,self.model.guard,PID,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        directory_native=NativeNavigationDirectory(self.model.source_read,lambda:json.dumps(self.model.source_packet),self.model.epoch,self.model.guard,PID,monotonic=lambda:self.model.clock,sleep=self.model.sleep);bookmarks_native=self.model.bookmarks()
        def home():
            self.home_sequence+=1
            return home_original()|dict(commandId=uuid.uuid4().hex,processId=PID,sourceSequence=self.home_sequence,
                elapsedMs=100+round(self.model.clock*1000),capturedEpochMs=self.model.epoch(),tabletShown=getattr(self.model,'shown',True),onHomeScreen=not self.model.login and not self.model.page)
        home_source=SimpleNamespace(pid=PID,capture=home,guard=self.model.guard,clock_ms=self.model.epoch,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        origin=NavigationOrigin(PicoNavigationOriginIO(original),env,self.root/'navigation-prefix-origin.json',RUN,self.binding,self.model.guard,
            home=PicoTabletHome(home_source,lambda _pose:None),monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        directory=NavigationDirectory(ui,directory_native,lambda:self.clients[role].request('/runs/'+RUN+'/navigation'),self.root/'navigation-prefix-directory.json',
            RUN,self.binding,self.model.provider.instance,INPUTS,self.url,directory_fixture.PROFILE,self.model.guard,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        bookmarks=NavigationBookmarks(ui,bookmarks_native,self.root/'navigation-prefix-bookmarks.json',RUN,self.binding,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        def probe(after):
            value=self.world.probe(after);value['nativeMotion']['processId']=PID;return value
        def subject_send(request):self.world.update_subject();self.world.subject.send(request)
        subject=NativeGraphicsSubject(subject_send,self.world.subject.original,self.model.epoch,self.model.guard,PID,require_framework=True,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        arrival=NavigationArrival(probe,subject,self.model.epoch,self.model.guard,RUN,self.binding,INPUTS['sceneUrl'],monotonic=lambda:self.model.clock)
        source=NavigationPrefixSource(ui(lambda _value:self.fail('Actor input')),arrival,bookmarks_native,self.model.reader_for('panels'),env,
            self.model.reader_for('modals'),directory_native,directory.status,RUN,self.binding,INPUTS,self.model.provider.instance,
            self.url,directory_fixture.PROFILE,self.model.epoch,self.model.guard)
        phase=PhaseFixtureReader(self.clients[role],RUN,'world-navigation',epoch_ms=self.model.epoch,monotonic=lambda:self.model.clock)
        result=NavigationPrefix(self.root/'navigation-prefix-owner.json',source,phase,self.lock,origin,directory,bookmarks,self.session,
            role=role,monotonic=lambda:self.model.clock)
        self.flows[role]=result;return result

    def test_original_a_origin_home_places_and_four_bookmark_actions_with_fresh_actor_sources(self):
        self.flow.prepare();baseline=self.flow.observe();self.assertEqual('A',baseline['state']['location']);self.assertFalse(baseline['state']['panel'])
        actor=self.make('actor');self.assertEqual(baseline['state'],actor.observe()['state'])
        for index,verb in enumerate(VERBS[:7]):
            call=self.activate(verb);self.flow.act(call)
            before=len(self.model.calls);actual=self.flow.observe();peer=actor.observe()
            self.assertEqual(before,len(self.model.calls));self.assertEqual(actual['state'],peer['state'])
            self.assertEqual('A',actual['state']['location']);self.assertTrue(actual['state']['panel'])
            self.assertEqual(expand(SCENARIOS['world-navigation']['steps'][index]['state'],context(RUN)),actual['state'])
            self.assertFalse(actual['fullNavigationRecipe']);self.assertTrue(actual['journalsRetained'])
        self.assertEqual(1,self.model.home_count);self.assertEqual(7,len(self.flow.state['completed']))
        self.assertEqual(origin_fixture.ORIGINAL,self.flow.origin.state['original']['selectedServer'])
        self.assertEqual(1,len(self.model.reads));self.assertTrue(self.original_calls)
        store=PrivateFeatureState(self.root/'navigation-prefix-primary-sources.json');record=store.read()
        frames=ChatSourceChunks(store,dict(runId=RUN,binding=self.binding,role='primary')).load(record['chunks'])
        changed=deepcopy(frames[1]);changed['provider']['responses'][0]['bytes']+=1
        with self.assertRaises(ValueError):self.flow.source.advance_frames(changed,frames[2])
        changed=deepcopy(frames[1]);changed['phase']['activations'][0]['ticket']=uuid.uuid4().hex
        with self.assertRaises(ValueError):self.flow.source.advance_frames(changed,frames[2])

    def test_hidden_and_owned_search_use_one_original_read_and_negative_quiet_without_resend(self):
        self.flow.prepare()
        for verb in VERBS[:5]:self.flow.act(self.activate(verb))
        hidden=self.activate('directory-search');self.flow.act(hidden)
        state=self.flow.observe()['state'];self.assertEqual(context(RUN)['hidden'],state['searchQuery']);self.assertEqual([],state['searchResults'])
        quiet=self.flow.directory.state['active']['quiet'];self.assertTrue(quiet)
        self.assertGreaterEqual(quiet[-1]['native']['capturedEpochMs']-quiet[0]['native']['capturedEpochMs'],3000)
        call=self.activate('directory-search');self.model.lose_control=('places.search','replace')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        count=sum((c['controlId'],c['action'])==('places.search','replace') for c in self.model.calls)
        self.model.lose_control=None;self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(count,sum((c['controlId'],c['action'])==('places.search','replace') for c in self.model.calls))
        result=self.flow.observe()['state'];self.assertEqual(context(RUN)['name'],result['searchQuery'])
        self.assertEqual([context(RUN)['destination']],result['searchResults']);self.assertEqual(1,len(self.model.reads))

    def test_version_one_original_prefix_remains_readable_without_new_search_authority(self):
        self.flow.prepare()
        for verb in VERBS[:5]:self.flow.act(self.activate(verb))
        # Version-envelope compatibility seam only. All five actual normal
        # inputs/effects above are retained, never invented closed originals.
        original=self.flow.store.read();legacy=deepcopy(original);legacy['navigationPrefixVersion']=1;legacy.pop('lookupReceipt',None)
        self.flow.store.write(legacy,original);self.flow=self.make('primary')
        self.assertEqual(context(RUN)['renamed'],self.flow.observe()['state']['bookmarkName'])
        before=deepcopy(self.model.calls)
        with self.assertRaises(NativeUIError):self.flow.act(self.activate('directory-search'))
        self.assertEqual(before,self.model.calls);self.assertEqual(1,self.flow.store.read()['navigationPrefixVersion'])

    def test_owned_search_cannot_replace_the_original_hidden_search_phase(self):
        self.flow.prepare()
        for verb in VERBS[:5]:self.flow.act(self.activate(verb))
        # A valid later inventory value still has no authority at step six.
        self.activate('directory-search');call=self.activate('directory-search')
        before=deepcopy(self.model.calls);parent=self.flow.store.read();child=self.flow.directory.store.read()
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(before,self.model.calls);self.assertEqual(parent,self.flow.store.read());self.assertEqual(child,self.flow.directory.store.read())

    def opened(self):
        self.flow.prepare();self.flow.observe();self.flow.act(self.activate('open'))

    def test_applied_lost_bookmark_save_cold_reopens_without_resending_original_input(self):
        self.opened();self.flow.act(self.activate('bookmark-add-cancel'));call=self.activate('bookmark-add')
        self.model.lose_control=('places.bookmark.save','activate')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual('places.bookmark.save',self.flow.bookmarks.state['active']['pending']['controlId'])
        self.assertEqual(1,sum(c['controlId']=='places.bookmark.save' for c in self.model.calls))
        self.model.lose_control=None;self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(1,sum(c['controlId']=='places.bookmark.save' for c in self.model.calls))
        self.assertEqual(context(RUN)['name'],self.flow.observe()['state']['bookmarkName'])
        before=deepcopy(self.model.calls);self.flow.act(call);self.assertEqual(before,self.model.calls)
        self.assertTrue((self.root/'navigation-prefix-bookmarks.json').exists())

    def test_ignored_bookmark_persistence_retains_original_pending_and_never_retries_save(self):
        self.opened();self.flow.act(self.activate('bookmark-add-cancel'));call=self.activate('bookmark-add')
        self.model.ignore_persistence=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        before=deepcopy(self.model.calls);self.model.ignore_persistence=False;self.flow=self.make('primary')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(before,self.model.calls);self.assertEqual([],self.model.storage()['owned'])
        self.assertEqual('places.bookmark.save',self.flow.bookmarks.state['active']['pending']['controlId'])
        with self.assertRaises(NativeUIError):self.make('actor').observe()

    def test_actual_phase_advance_in_last_source_guard_prevents_original_qml_writer(self):
        self.flow.prepare();call=self.activate('open');before=deepcopy(self.model.calls);guard=self.flow.source.guard;fired=[]
        def advance():
            if self.flow.state['deliveries'] and self.flow.state['deliveries'][-1]['controlId']=='places.entry' and not fired:
                fired.append(True);self.activate('bookmark-add')
            return guard()
        self.flow.source.guard=advance
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertTrue(fired);self.assertEqual(before,self.model.calls)
        self.assertEqual('places.entry',self.flow.state['active']['pending']['controlId'])
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(before,self.model.calls)

    def test_changed_current_query_inside_original_bracket_is_archived_before_refusal(self):
        self.opened();reader=self.flow.source.readers['directory'];send=reader.send;changed=[]
        def change(request):
            send(request)
            if not changed:self.model.query=context(RUN)['hidden'];changed.append(True)
        reader.send=change
        with self.assertRaises(NativeUIError):self.flow.observe()
        store=PrivateFeatureState(self.root/'navigation-prefix-primary-sources.json');record=store.read()
        self.assertEqual('reading',record['phase'])
        # The uncommitted child is a retained actual original, not a successful
        # sample or an alias of the old manifest's last source frame.
        path=store.path.with_name(store.path.name+'.frame-001.json');self.assertTrue(path.exists())
        with self.assertRaises(NativeUIError):self.flow.observe()

    def test_wrong_grounded_current_scene_cannot_borrow_a_stale_places_address(self):
        self.opened();self.world.position='B'
        with self.assertRaises(NativeUIError):self.flow.observe()
        self.assertEqual('reading',PrivateFeatureState(self.root/'navigation-prefix-primary-sources.json').read()['phase'])
        self.assertTrue((self.root/'navigation-prefix-primary-sources.json.frame-001.json').exists())

    def test_late_final_native_clock_change_refuses_publication_without_retiming_originals(self):
        self.opened();guard=self.flow.source.guard;changed=[];offset=[0];host=self.model.clock
        self.flow.source.clock_ms=lambda:self.model.epoch()+offset[0]
        store=PrivateFeatureState(self.root/'navigation-prefix-primary-sources.json')
        def advance():
            record=store.read()
            if record is not None and record['phase']=='ready' and len(record['chunks'])==2 and not changed:
                changed.append(True);offset[0]=2000
            return guard()
        self.flow.source.guard=advance
        with self.assertRaises(NativeUIError):self.flow.observe()
        self.assertTrue(changed);record=store.read();self.assertEqual(2,len(record['chunks']))
        chunks=ChatSourceChunks(store,dict(runId=RUN,binding=self.binding,role='primary'));frames=chunks.load(record['chunks'])
        captured=frames[-1]['before']['ui']['observedEpochMs'];self.assertGreaterEqual(self.flow.source.clock_ms()-captured,2000)
        self.assertEqual(host,self.model.clock)
        self.assertEqual(captured,frames[-1]['after']['ui']['observedEpochMs'])


if __name__=='__main__':unittest.main()
