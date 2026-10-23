"""Actual publisher/seal/host-close bodies; parent/native provenance are seams.

No product Actor or device starts. The existing compiled-source fixture supplies
actual original Python source histories; the two captured Linux OFD pairs belong
to this test process. Separate factory tests cover passive Pico acquisition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import select
import subprocess
import sys
from types import SimpleNamespace
import unittest
import uuid

from adapters.chat_actor_files import ChatActorFiles
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.chat_journey.source_chunks import digest
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_composition import PicoChatWitness
from adapters.pico4.chat_cursor_actor import PicoChatCursorActor
from adapters.pico4.chat_host_close import host_identity
from fixture.chat_actor_process import LinuxChatActorProcess
from self_tests import test_chat_observation_publisher as seams
from self_tests.chat_cursor_fixture import cleanup


class PicoChatCursorActorTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatObservationPublisherTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        h=self.h;self.actor=PicoChatCursorActor.__new__(PicoChatCursorActor);a=self.actor
        a.target='producer-seam';a.source=h.initial.source;a.store=PrivateFeatureState(h.root/'actual-actor-owner.json')
        a.stop_store=PrivateFeatureState(h.root/'actual-actor-stop.json');a.previous=None;a.previous_sha=digest(None);a.root_stamp=None
        a.return_store=PrivateFeatureState(h.root/'actual-actor-return.json')
        a.consumption_store=PrivateFeatureState(h.root/'actual-actor-consumption.json')
        a.return_sender=None;a.return_started=a.parent_consumed=False
        a.failed=a.started=a.closed=False;a.publisher=h.owner;a.seal=None;a.seal_receipt=None;a.stop_value=a.stop_stamp=a.stop_raw=None
        a.scope=dict(picoChatCursorActorVersion=3,instance=uuid.uuid4().hex,runId=a.source.run,fixtureUrl=a.source.fixture_url,
            binding=deepcopy(h.cursor.scope['binding']),peerBinding=deepcopy(h.cursor.scope['peerBinding']),hostProcessIdentity=host_identity())
        a.scope_sha=digest(a.scope)
        original=a.original=PicoChatWitness.__new__(PicoChatWitness);original.binding=deepcopy(a.scope['binding'])
        original.native=SimpleNamespace(guard=lambda:True)
        peer=original.peer=OwnedChatPeer.__new__(OwnedChatPeer);peer.retirement_files=None;peer.guard=lambda:True
        original.lock=h.initial.samples.locks[0];peer.lock=h.initial.samples.locks[1];peer.binding=deepcopy(a.scope['peerBinding'])
        original.publisher=SimpleNamespace(samples=h.h.samples('actor',h.flow.w.witness_store))
        peer.files=ChatActorFiles.__new__(ChatActorFiles);peer.files.fd_owner=OriginalDescriptor(h.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        peer.files.fd=peer.files.fd_owner.fd
        peer.process=LinuxChatActorProcess.__new__(LinuxChatActorProcess)
        peer.process.fd_owner=OriginalDescriptor('/proc/self/exe',os.O_RDONLY|os.O_CLOEXEC);peer.process.fd=peer.process.fd_owner.fd
        a.pairs=tuple((owner,dict(label=label,node=list(owner.node),fd=owner.fd,anchor=owner.anchor)) for label,owner in
            (('peer-directory',peer.files.fd_owner),('peer-executable',peer.process.fd_owner)))
        a.pairs_sha=digest([row for _owner,row in a.pairs]);self.addCleanup(a.detach)
        parent_store=PrivateFeatureState(h.root/'actual-parent-admission.json')
        self.parent=dict(picoChatCompositionVersion=6,runId=a.source.run,fixtureUrl=a.source.fixture_url,binding=a.scope['binding'],
            peerBinding=a.scope['peerBinding'],peerOriginBasis='native-configured-metadata-only',phase='step-completed',completedSteps=1)
        parent_store.write(self.parent,None);self.parent_store=parent_store
        cleanup_owner=[]
        peer.reader=lambda:cleanup_owner[0].samples.peer
        a.adapter=SimpleNamespace(_chat_composition_store=lambda _target:parent_store,
            _scripts=lambda _target:SimpleNamespace(binding=a.scope['binding']),
            _chat_observation=lambda _target,_source,samples,**kw:h.observation(samples,'active') if kw['stage']=='active' else cleanup_owner[0],
            _chat_cache_absence=lambda *_args,**_kwargs:cleanup_owner[0].samples,
            _chat_cursor_source_seal=lambda _target,publisher,**_kwargs:ChatCursorSourceSeal(publisher,PrivateFeatureState(h.root/'actual-actor-seal.json')))
        a.save('publishing',pairs=[deepcopy(row) for _owner,row in a.pairs],returnedPublication=None);a.publish()
        # Preserve the actual native ordinary Open and both original stage
        # sources, with the remaining 24 inputs explicitly metadata seams.
        h.flow.next(1)
        self.parent['completedSteps']=2;parent_store.write(self.parent,parent_store.read());a.publish()
        cleanup_owner.append(cleanup(h.h,h.cursor));self.parent.update(phase='caches-retired',completedSteps=26)
        parent_store.write(self.parent,parent_store.read());a.publish()
        self.command=dict(picoChatCursorActorStopVersion=1,commandId=uuid.uuid4().hex,instance=a.scope['instance'],
            runId=a.source.run,afterSequence=len(a.publisher.rows),ticket=a.publisher.rows[-1]['payload']['ticket'])
        if not getattr(self,'defer_stop_command',False):a.stop_store.write(self.command,None)

    def independent_parent_consumption(self):
        # Actual second host process and independent original-byte/nonce read.
        # Its graph admission is an explicit seam; the generic Receiver tests
        # separately qualify original process ownership and kernel return.
        entry=self.h.root/'return-parent.py'
        entry.write_text("""import sys
sys.path.insert(0,DEVICE_PATH)
import hashlib
import uuid
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state,scope,SCOPE
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import need
from adapters.host_process_identity import host_identity
from adapters.script_journey.history import canonical
import base64,json
config=PrivateFeatureState(sys.argv[2]).read()
store=PrivateFeatureState(config['root']);value,raw,physical=state(store)
original={key:value[key] for key in SCOPE};scope(original);need(value['phase']=='ready')
frames=ChatSourceChunks(store,original).load(value['chunks'])
payload=b''.join(base64.b64decode(row['rawBase64'],validate=True) for row in frames)
need(hashlib.sha256(payload).hexdigest()==original['payloadSha256'])
root=json.loads(payload);need(root['picoChatCursorActorVersion']==3 and root['phase']=='host-closed')
need(payload==canonical(root)+b'\\n')
ack=dict(observerReturnConsumptionVersion=1,scopeSha256=digest(original),returnId=original['returnId'],
    originalRequestId=original['originalRequestId'],producerHostProcessIdentity=original['producerHostProcessIdentity'],
    consumerHostProcessIdentity=host_identity(),nonce=uuid.uuid4().hex,readyRootSha256=hashlib.sha256(raw).hexdigest(),
    readyRootStamp=physical,payloadSha256=original['payloadSha256'])
PrivateFeatureState(config['ack']).write(ack,None)
print('consumed',flush=True)
sys.stdin.readline()
""".replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));entry.chmod(0o600)
        config=PrivateFeatureState(self.h.root/'return-parent-config.json')
        config.write(dict(root=str(self.actor.return_store.path),ack=str(self.actor.consumption_store.path)),None)
        worker=subprocess.Popen([sys.executable,str(entry),'--config',str(config.path)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PYTHONDONTWRITEBYTECODE':'1'})
        def finish():
            worker.stdin.close();worker.wait(timeout=5);worker.stdout.close();worker.stderr.close()
        self.addCleanup(finish)
        self.assertTrue(select.select([worker.stdout],[],[],5)[0]);self.assertEqual(b'consumed\n',worker.stdout.readline())
        return worker

    def test_original_stop_seals_full_graph_then_really_closes_both_captured_kernel_pairs(self):
        a=self.actor;before=self.h.queries();posts=len(self.h.posts);value=a.stop_once()
        self.assertEqual('host-closed',value['phase']);self.assertEqual('original-independent-chat-host-handles',value['sourceScope'])
        self.assertTrue(a.closed);self.assertFalse(a.failed);self.assertTrue(a.seal.completed);self.assertEqual(2,value['closedPairs'])
        self.assertTrue(all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner,_row in a.pairs))
        self.assertEqual(value,a.store.read());self.assertEqual(a.seal_receipt,a.seal.receipt(a.seal_receipt))
        self.assertTrue(a.stop_store.path.exists());self.assertTrue(all(owner.store.path.exists() for owner in a.seal.owners))
        with self.assertRaises(NativeUIError):a.publish()
        with self.assertRaises(NativeUIError):a.stop_once()
        self.assertFalse(a.failed);self.assertEqual(a.seal_receipt,a.seal.receipt(a.seal_receipt))
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))
        # The actual return producer preserves the literal successful host-close
        # root. Native guards must never run after that boundary.
        def forbidden():raise AssertionError('No native query/guard during historical return')
        a.original.native.guard=forbidden
        raw=a.store.path.read_bytes();ready=a.publish_return()
        self.assertEqual('ready',ready['phase']);self.assertEqual(raw,a.return_sender.raw)
        self.assertFalse(a.parent_consumed);worker=self.independent_parent_consumption()
        returned=a.consume_return();self.assertTrue(a.parent_consumed)
        self.assertEqual('parent-consumed',returned['phase']);self.assertEqual(returned,a.store.read())
        self.assertEqual(str(worker.pid),returned['parentHostProcessIdentity'].split(':')[0])
        self.assertEqual('consumed',a.return_store.read()['phase'])
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))
        with self.assertRaises(NativeUIError):a.publish_return()
        with self.assertRaises(NativeUIError):a.consume_return()
        self.assertFalse(a.failed)

    def test_foreign_stop_cursor_quarantines_without_sealing_republishing_or_closing_originals(self):
        a=self.actor;value={**self.command,'afterSequence':self.command['afterSequence']-1}
        a.stop_store.write(value,self.command);before=self.h.queries();posts=len(self.h.posts)
        with self.assertRaises(NativeUIError):a.stop_once()
        self.assertTrue(a.failed);self.assertTrue(a.started);self.assertFalse(a.closed);self.assertIsNone(a.seal)
        self.assertEqual('publishing',a.store.read()['phase'])
        for owner,_row in a.pairs:owner.require(owner.fd)
        a.stop_store.write(self.command,value)
        with self.assertRaises(NativeUIError):a.stop_once()
        with self.assertRaises(NativeUIError):a.publish()
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))

    def test_lost_final_host_publication_retains_originals_without_cold_receipt_or_replay(self):
        a=self.actor;write=a.store.write;before=self.h.queries();posts=len(self.h.posts)
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='host-closed':raise OSError('Original final publication receipt lost')
        a.store.write=lost
        with self.assertRaises(NativeUIError):a.stop_once()
        self.assertTrue(a.failed);self.assertFalse(a.closed);self.assertEqual('host-closed',a.store.read()['phase'])
        self.assertTrue(all(owner.closed and not owner.lost for owner,_row in a.pairs))
        with self.assertRaises(NativeUIError):a.publish_return()
        self.assertIsNone(a.return_store.read())
        with self.assertRaises(NativeUIError):a.stop_once()
        with self.assertRaises(NativeUIError):a.publish()
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))

    def test_actual_owner_root_replacement_is_refused_before_another_source_query(self):
        a=self.actor;before=self.h.queries();posts=len(self.h.posts)
        a.store.write(a.previous,a.previous)
        with self.assertRaises(NativeUIError):a.publish()
        self.assertTrue(a.failed);self.assertFalse(a.closed)
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))
        for owner,_row in a.pairs:owner.require(owner.fd)

    def test_final_actor_control_native_jump_is_inside_original_publication_freshness(self):
        a=self.actor;before=len(self.h.posts)
        def late():
            if len(self.h.posts)>before:self.h.native.epoch+=2000
            return True
        a.original.native.guard=late
        with self.assertRaises(NativeUIError):a.publish()
        self.assertTrue(a.failed);self.assertEqual(before+1,len(self.h.posts));self.assertFalse(a.closed)
        queries=self.h.queries()
        with self.assertRaises(NativeUIError):a.publish()
        self.assertEqual(queries,self.h.queries());self.assertEqual(before+1,len(self.h.posts))


if __name__=='__main__':unittest.main()
