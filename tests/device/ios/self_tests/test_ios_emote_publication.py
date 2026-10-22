"""Real actor HTTP publication from separately archived Emote/receiver originals.

All native packets are synthetic. Private source/image byte validation and
loopback fixture authentication, journal/receipt/CAS are actual host behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_peer import session_sha
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.self_tests.test_ios_avatar_renderers import PEER
from ios.self_tests.emote_original_fixtures import Originals
from ios.self_tests.test_ios_emote_peer import ACTOR
from ios.self_tests.test_ios_emote_peer_sources import original as peer_original
from ios.self_tests.test_ios_emote_sources import RUN,BINDING


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.primary=self.root/'primary';self.primary.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.primary_lock=ScriptSourceLock(self.primary/'script-feature-sources.lock')
        self.primary_held=self.primary_lock.held();self.primary_held.__enter__()
        self.native=Originals(self.primary,self.primary_lock,role='actor')
        self.ref=self.native.append(18800,baseline=True,domain=dict(selfSha256=session_sha(PEER),avatarMixerSha256='c'*64))
        self.peers=IOSEmotePeerSources(PrivateFeatureState(self.root/'ios-emote-actor-peer-sources.json'),self.root,ACTOR,RUN,
            None,self.lock,lambda:True,historical=True);self.peers.historical=False;self.peers.save()
        peer=peer_original();self.peers.state['pending']=dict(original=None,manifest=None,partial={});self.peers.save()
        item=self.peers.originals.write(1,peer);refs=self.peers.originals.append([],item)
        self.peers.frames.append(peer);self.peers.state.update(revision=1,manifests=refs,pending=None);self.peers.save()
        self.decoder=IOSEmoteObservationDecoder(self.native.owner,ACTOR,'actor',self.root,dict(source='world-render-target'),
            self.lock,phase_instance='3'*32,peers=self.peers)
        self.original=dict(iosEmoteObservationOriginalVersion=1,runId=RUN,role='actor',binding=ACTOR,primaryBinding=BINDING,
            sequence=1,ticket='4'*32,source=self.ref,sourceRecovery=None,peerRecovery=None,proof=dict(kind='idle',baseline=self.ref,before=None,played=None,inputBarrier=None),
            peerBefore=None,peerAfter=self.peers.reference(),marker=None,imageBefore=None,image=None,
            acquisition=dict(hostBeforeEpochMs=90000.,hostAfterEpochMs=91000.,hostBeforeMonotonic=1.,hostAfterMonotonic=2.))
        self.now=89000.;self.server=make_server('r'*64,'a'*64);self.server.journal.clock=lambda:self.now
        self.server.journal.phase_instance='3'*32
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,self.server.journal.register('emotes'))
        self.now=89900.;self.server.journal.activate(RUN,'4'*32)
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start()
        url='http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1';self.client=Client(url,'a'*64)
        self.now=91100.;self.phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.now,monotonic=lambda:2.1)
        self.phase.status()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.primary_held.__exit__(None,None,None);self.held.__exit__(None,None,None);self.temp.cleanup()
    def publisher(self):return PhaseWitnessPublisher(PrivateFeatureState(self.root/('phase-publication-emotes-'+RUN+'-actor.json')),
        ACTOR,self.phase,self.lock,lambda:True,self.decoder.derive,epoch_ms=lambda:self.now,monotonic=lambda:2.1)
    def test_actual_original_decoder_to_authenticated_actor_journal_and_no_duplicate_post(self):
        owner=self.publisher();posts=[];real=self.client.request
        def request(path,value=None,**kwargs):
            if path.endswith('/samples'):posts.append(deepcopy(value))
            return real(path,value,**kwargs)
        with patch.object(self.client,'request',side_effect=request):
            self.assertEqual(1,owner.publish(self.original));self.assertEqual(1,self.publisher().publish(self.original))
        self.assertEqual(1,len(posts));entry=self.server.journal.snapshot(RUN)['entries'][0]
        self.assertEqual('idle',entry['facts']['animation']);self.assertFalse(entry['facts']['override'])
        self.assertEqual(90000.,entry['capturedEpochMs']);self.assertEqual(18800,self.native.owner.frames[0]['group']['native']['capturedEpochMs'])
        with patch.object(self.client,'request',side_effect=AssertionError('Historical decoder must never call HTTP')):
            archive=PhaseWitnessPublisher.archive(owner.store.read(),store=owner.store,binding=ACTOR,run=RUN,area='emotes',
                fixture_url=self.client.url,phase_instance='3'*32,validate_original=self.decoder.derive)
        self.assertEqual(1,len(archive['records']))
    def test_lost_actual_committed_publication_resolves_without_new_input_or_post(self):
        owner=self.publisher();real=self.client.request;posts=[]
        def lost(path,value=None,**kwargs):
            result=real(path,value,**kwargs)
            if path.endswith('/samples'):posts.append(value);raise OSError('Synthetic lost committed return')
            return result
        with patch.object(self.client,'request',side_effect=lost),self.assertRaises(OSError):owner.publish(self.original)
        self.assertEqual(1,len(posts));recovered=self.publisher()
        def read_only(path,value=None,**kwargs):
            self.assertFalse(path.endswith('/samples'));return real(path,value,**kwargs)
        with patch.object(self.client,'request',side_effect=read_only):self.assertTrue(recovered.resolve())
        self.assertEqual(1,len(self.server.journal.snapshot(RUN)['entries']))
    def test_primary_public_result_other_sender_or_rewritten_original_is_rejected_before_post(self):
        corrupt=deepcopy(self.original);corrupt['state']=dict(animation='Waving')
        with self.assertRaises(NativeUIError):self.decoder.derive(corrupt)
        corrupt=deepcopy(self.original);corrupt['binding']=BINDING
        with self.assertRaises(NativeUIError):self.decoder.derive(corrupt)
        path=next(self.primary.glob('emote-frame-sources-*.json'));path.write_bytes(b'{}')
        with self.assertRaises(NativeUIError):self.decoder.derive(self.original)
        self.assertEqual([],self.server.journal.snapshot(RUN)['entries'])


if __name__=='__main__':unittest.main()
