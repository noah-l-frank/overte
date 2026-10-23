"""Whole original acquisition, real private files and actual journal publication.

Host generated JS executes; native/UIKit/SDK transport is modeled. The actual
phase/publisher journals run unchanged. No native or device execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from ios.adapters import tablet_web_sources,tablet_web_source,tablet_web_dom,tablet_web_buttons,tablet_web_state,tablet_web_closures,uikit_input,web_script_emissions,tablet_web_deferred
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner,ORDER,FRAME_KEYS
from ios.adapters.tablet_web_observer import TabletWebObserver,TabletWebDOMDisposition,resources
from ios.self_tests.tablet_web_history_fixture import frame
from ios.self_tests.test_ios_emote_sources import BINDING
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT,stamp
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS
from self_tests import test_native_feature_observation as native_tests

CLASSES=dict(sources=tablet_web_sources.IOSTabletSources,trace=tablet_web_source.IOSTabletWebSource,dom=TabletWebDOMDisposition,
    buttons=tablet_web_buttons.IOSTabletWebButtons,uikit=uikit_input.IOSUIKitInput,state=tablet_web_state.IOSTabletWebState,
    closures=tablet_web_closures.IOSTabletWebClosures,emissions=web_script_emissions.IOSWebScriptEmissions,deferred=tablet_web_deferred.IOSTabletWebDeferred)


class Boundary:
    def __init__(self,original):
        self.frame=deepcopy(original);self.mono=0.;self.host=1700000005000;self.epoch=original['document']['clockAfter']['epochMs'];self.calls=[];self.sent={};self.raw={}
        self.native_count=0;self.native_raw=None;self.lost=None
        self.journal=Journal(lambda:self.host+self.mono*1000)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('tablet-web')
        self.journal.activate(RUN,'f'*32);self.client=Client(ROOT.split('/runs/')[0],'a'*64);self.client.request=self.request;self.posts=0
        self.phase=PhaseFixtureReader(self.client,RUN,'tablet-web',epoch_ms=lambda:self.host+self.mono*1000,monotonic=lambda:self.mono)
    def request(self,path,value=None,**kwargs):
        if path.endswith('/phase'):return self.journal.phase(RUN,kwargs['phase_nonce'])
        if path.endswith('/samples'):
            if value is not None:self.posts+=1;self.journal.publish(RUN,value)
            return self.journal.snapshot(RUN)
        if path=='/runs/'+RUN and value is None:return self.journal.snapshot(RUN)
        raise AssertionError('Unexpected fixture request')
    def reader(self,name):
        def send(query):
            self.calls.append(name);self.sent[name]=deepcopy(query)
            if self.lost==name:raise OSError('Actual modeled native source return lost')
            value=deepcopy(self.frame[FRAME_KEYS.get(name,name)]);value.update(commandId=query['commandId'],sequence=value['sequence']+self.calls.count(name)-1)
            if name=='closures':value['capturedEpochMs']=self.epoch
            else:value['clockBefore']=value['clockAfter']=stamp(self.epoch)
            if name=='dom' and value['status']=='ready':value['source']['dom']['requestId']=query['commandId']
            self.raw[name]=json.dumps(value)
        return CLASSES[name](send,lambda:self.raw[name],lambda:self.epoch,lambda:True,31,monotonic=lambda:self.mono,sleep=lambda _:None)
    def native(self):
        template=native_tests.Boundary();template.send(dict(commandId='ios-'+'1'*32))
        def send(query):
            self.native_count+=1;value=deepcopy(template.sample);epoch=self.epoch-100 if self.native_count%2 else self.epoch+100
            if self.native_count%2==0:self.mono+=.2
            def clocks(node):
                if type(node) is dict:
                    for key,child in node.items():
                        if key.endswith('EpochMs'):node[key]=epoch
                        else:clocks(child)
                elif type(node) is list:
                    for child in node:clocks(child)
            clocks(value);value.update(processId=31,sequence=self.native_count,requestId=query['commandId']);self.native_raw=json.dumps(value)
        return NativeFeatureObservation(send,lambda:self.native_raw,lambda:self.epoch+100 if self.native_count%2==0 and self.native_count else self.epoch-100,
            lambda:True,31,ios=True,native_clock_bound=True,monotonic=lambda:self.mono,sleep=lambda _:None)


class TabletWebSourceOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.frame,cls.app=frame()
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.boundary=Boundary(self.frame)
    def owner(self,*,historical=False,role='actor',lock=None):
        return TabletWebSourceOwner(self.root,BINDING,RUN,role,ROOT,31,lock or self.lock,lambda:True,epoch_ms=lambda:int(self.boundary.host+self.boundary.mono*1000),monotonic=lambda:self.boundary.mono,historical=historical)
    def prepare(self):
        source=self.owner();source.remember_app(self.app);return source
    def capture(self,source):
        return source.capture({name:self.boundary.reader(name) for name in ORDER},self.boundary.native(),self.boundary.phase,lambda:deepcopy(self.frame['browser']))
    def test_actual_nine_queries_raw_ownership_full_facts_and_historical_source_original_replay(self):
        source=self.prepare();parts,record=self.capture(source)
        self.assertEqual(list(ORDER),self.boundary.calls);self.assertEqual(2,self.boundary.native_count);self.assertEqual(1,len(source.state['records']))
        self.assertEqual(1,source.facts(ORIGINS)['public']['bridgeEchoes']);historical=self.owner(historical=True)
        measured,original,_frame=historical.facts_at(source.state['records'][0],ORIGINS)
        self.assertEqual(record,original);self.assertEqual(parts['document'],measured['document']);self.assertEqual(os.getpid(),original['hostProcessId'])
        with self.assertRaises(NativeUIError):self.capture(historical)
        self.assertEqual(9,len(self.boundary.calls))
    def test_historical_frame_without_admitted_app_remains_original_and_cannot_supply_app_facts(self):
        source=self.owner();parts,record=self.capture(source);reference=deepcopy(source.state['records'][0])
        calls=deepcopy(self.boundary.calls);historical=self.owner(historical=True)
        actual,frame,history=historical.frame_at(reference)
        self.assertEqual(record,actual);self.assertEqual(parts,frame);self.assertEqual([parts],history)
        actual['browser']['responses'].clear();frame['sources']['roots'].clear()
        self.assertEqual(record,historical.frame_at(reference)[0])
        with self.assertRaises(NativeUIError):historical.facts_at(reference,ORIGINS)
        with self.assertRaises(NativeUIError):source.frame_at(reference)
        self.assertEqual(calls,self.boundary.calls)
    def test_lost_native_query_retains_earlier_actual_originals_and_never_resumes_or_resends(self):
        source=self.prepare();self.boundary.lost='state'
        with self.assertRaises(NativeUIError):self.capture(source)
        before=list(self.boundary.calls);rebuilt=self.owner();self.assertTrue(rebuilt.blocked);self.assertEqual('failed',rebuilt.state['pending']['status'])
        self.assertEqual(5,len(rebuilt.state['pending']['components'][:-1]));self.assertIsNone(rebuilt.state['pending']['components'][-1]['reference'])
        with self.assertRaises(NativeUIError):self.capture(rebuilt)
        self.assertEqual(before,self.boundary.calls)
    def test_wrong_held_lock_is_rejected_before_any_parent_or_query_journal(self):
        foreign=ScriptSourceLock(self.root/'foreign.lock')
        with foreign.held(),self.assertRaises(NativeUIError):self.owner(lock=foreign)
        self.assertEqual([],list(self.root.glob('tabletweb-*')));self.assertEqual([],self.boundary.calls)

    def test_retired_browser_original_is_retained_but_stops_before_terminal_native_query(self):
        source=self.prepare();retired=deepcopy(self.frame['browser']);retired['browserFixtureVersion']=2
        # A widened neutral parser cannot authorize retired inventory for this
        # active source. The actual callback result is still owned first.
        with patch('ios.adapters.world_web_measurements.browser_original',return_value=retired) as neutral:
            with self.assertRaises(NativeUIError):
                source.capture({name:self.boundary.reader(name) for name in ORDER},self.boundary.native(),self.boundary.phase,lambda:retired)
            neutral.assert_not_called()
        self.assertEqual(1,self.boundary.native_count)
        self.assertEqual('failed',source.state['pending']['status'])
        self.assertEqual(retired,source.state['pending']['browser'])
        self.assertIsNone(source.state['pending']['nativeAfter'])
        rebuilt=self.owner(historical=True)
        self.assertTrue(rebuilt.blocked);self.assertEqual(retired,rebuilt.state['pending']['browser'])

    def test_returned_history_cannot_substitute_retired_browser_even_with_updated_original_digest(self):
        from adapters.native_clock_join import digest
        source=self.prepare();parts,record=self.capture(source)
        changed=deepcopy(record);changed['browser']['browserFixtureVersion']=2
        parts['browser']=deepcopy(changed['browser']);changed['clockJoin']['originalsSha256']=digest(parts)
        with patch('ios.adapters.world_web_measurements.browser_original',return_value=changed['browser']) as neutral:
            with self.assertRaises(NativeUIError):source._record(changed,1,None)
            neutral.assert_not_called()
    def test_actor_publication_uses_its_real_original_decoder_and_committed_journal_once(self):
        source=self.prepare();observer=TabletWebObserver(source,{name:self.boundary.reader(name) for name in ORDER},self.boundary.native(),self.boundary.phase,
            lambda:deepcopy(self.frame['browser']),ORIGINS)
        original=observer.observe();derived=observer.validate_original(original);self.assertEqual(1,derived['public']['state']['bridgeEchoes'])
        publisher=observer.actor_publisher();self.assertEqual(1,publisher.publish(original));self.assertEqual(1,self.boundary.posts)
        self.assertEqual(1,publisher.publish(original));self.assertEqual(1,self.boundary.posts)
        self.assertEqual(derived['public']['state']['bridgeMessages'],self.boundary.journal.snapshot(RUN)['entries'][0]['facts']['bridgeMessages'])
        self.assertNotIn('connection:tablet-web-observer',derived['public']['resources']);self.assertIn('input:tablet-held-input-objects',derived['public']['resources'])
        self.assertIn('panel:tablet-native-targets',derived['public']['resources']);self.assertIn('file:tablet-app-inputs',derived['public']['resources'])

    def test_empty_baseline_has_no_app_or_host_resources_and_ended_outsider_cache_is_not_owned(self):
        original=deepcopy(self.frame)
        original['ledger'].update(events=[],eventSequence=0)
        original['sources'].update(roots=[],navigations=[],carriers=[])
        original['document'].update(status='unavailable',source={})
        for name in ('models','tablets','buttons','controls'):original['buttons'][name]=[]
        original['state'].update(owners=[],targets=[],otherLiveTablets=0)
        original['browser'].update(sequence=0,responses=[])
        original['touches']['targets']=[]
        # Actual returned/ended outsider contacts and their still-cached objects
        # remain in the global source rather than being erased from evidence.
        for row in original['touches']['contacts']:row['source']=None
        for row in original['touches']['dispatches']:
            for phase in row['phases']:phase['source']=None
        self.boundary=Boundary(original);source=self.owner()
        observer=TabletWebObserver(source,{name:self.boundary.reader(name) for name in ORDER},self.boundary.native(),self.boundary.phase,
            lambda:deepcopy(original['browser']),ORIGINS)
        strict=tablet_web_dom.IOSTabletWebDOM(lambda query:None,lambda:'',lambda:1,lambda:True,31)
        with self.assertRaises(NativeUIError):strict._ready(original['document'])
        observation=observer.observe();actual=observer.validate_original(observation)
        self.assertEqual([],actual['public']['resources']);self.assertEqual(0,actual['public']['state']['bridgeEchoes'])
        self.assertEqual(list(ORDER),self.boundary.calls);self.assertEqual([],source.state['apps'])
        self.assertTrue(any(row['alive'] and row['kind']=='touch' for row in original['touches']['objects']))
        self.assertEqual(1,observer.actor_publisher().publish(observation))
        source.remember_app(self.app)
        self.assertEqual([],observer.validate_original(observation)['public']['resources'])
        self.assertEqual(1,len(source.state['apps']))

    def test_unowned_active_contact_pending_dispatch_and_foreign_focus_cannot_qualify_empty_baseline(self):
        # The typed history is validated separately before this projection;
        # these counterexamples exercise its additional global-activity gate.
        original=deepcopy(self.frame)
        for row in original['touches']['contacts']:row['source']=None
        for row in original['touches']['dispatches']:
            for phase in row['phases']:phase['source']=None
        for fault in ('contact','dispatch','focus'):
            changed=deepcopy(original)
            if fault=='contact':changed['touches']['contacts'][0]['active']=True
            elif fault=='dispatch':changed['touches']['pendingDispatches']=[1]
            else:changed['state']['targets'][0]['subtreeResponder']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):resources(changed,dict(apps=[]))

    def test_parent_original_clock_child_host_brackets_and_actual_phase_birth_cannot_be_substituted(self):
        source=self.prepare();_parts,record=self.capture(source)
        for fault in ('native-copy','host-copy','child-host','phase-before','phase-after'):
            changed=deepcopy(record)
            if fault=='native-copy':
                changed['clockJoin']['nativeBefore']=deepcopy(changed['clockJoin']['nativeBefore']);changed['clockJoin']['nativeAfter']=deepcopy(changed['clockJoin']['nativeAfter'])
                changed['clockJoin']['nativeBefore']['instance']='0'*32;changed['clockJoin']['nativeAfter']['instance']='0'*32
            elif fault=='host-copy':changed['clockJoin']['hostAfterEpochMs']-=1
            elif fault=='child-host':changed['before']['epochMs']+=1
            elif fault=='phase-before':changed['phaseBefore']['capturedEpochMs']=changed['clockJoin']['hostBeforeEpochMs']+1
            else:changed['phaseAfter']['capturedEpochMs']=changed['clockJoin']['hostAfterEpochMs']-1
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):source._record(changed,1,None)

    def test_lost_complete_parent_flush_recovers_actual_same_bytes_inode_without_new_query(self):
        source=self.prepare();fsync=os.fsync;lost=[False]
        def flush(descriptor):
            name=os.readlink('/proc/self/fd/'+str(descriptor))
            if not lost[0] and 'tabletweb-acquisitions-frame-' in name:lost[0]=True;raise OSError('Actual complete parent flush return lost')
            return fsync(descriptor)
        with patch('os.fsync',side_effect=flush),self.assertRaises(OSError):self.capture(source)
        rebuilt=self.owner();self.assertTrue(rebuilt.blocked);reference=deepcopy(rebuilt.state['intent']);self.assertEqual('opened',reference['phase'])
        path=rebuilt.originals.path(reference);before=path.stat();raw=path.read_bytes();calls=deepcopy(self.boundary.calls)
        rebuilt.recover_original();self.assertEqual(before,path.stat());self.assertEqual(raw,path.read_bytes());self.assertEqual(calls,self.boundary.calls)
        historical=self.owner(historical=True);self.assertFalse(historical.blocked);self.assertEqual(1,historical.facts_at(historical.state['records'][0],ORIGINS)[0]['public']['bridgeEchoes'])

    def test_empty_opened_parent_prefix_is_retained_and_historical_mutations_remain_blocked(self):
        source=self.prepare();intent=source.originals.intent
        def opened(kind,value):
            intent(kind,value)
            if value['phase']=='opened':raise OSError('Actual empty parent prefix interruption')
        source.originals.intent=opened
        with self.assertRaises(OSError):self.capture(source)
        rebuilt=self.owner(historical=True);self.assertTrue(rebuilt.blocked);self.assertEqual(0,rebuilt.state['inspection']['bytes'])
        path=rebuilt.originals.path(rebuilt.state['intent']);self.assertEqual(b'',path.read_bytes())
        with self.assertRaises(NativeUIError):rebuilt.recover_original()
        with self.assertRaises(NativeUIError):rebuilt.remember_app(self.app)
        os.link(path,self.root/'foreign-hardlink')
        with self.assertRaises(NativeUIError):self.owner(historical=True)


if __name__=='__main__':unittest.main()
