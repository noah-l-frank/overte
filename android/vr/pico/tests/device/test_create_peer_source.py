"""Normal Parent plus separate real worker; replication/Native/Qt/time models.

No device, compiler, SDK, service, live fixture or Domain activation occurs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import unittest
import uuid

sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
import test_create_journey as primary_source
from create_peer_originals_host import native_domain_births
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnReceiver
from adapters.pico4.create_peer_source import FAMILY
from adapters.pico4.create_peer_parent import admit_return
from fixture.chat_observer_process import LinuxChatObserverProcess
RUN=primary_source.RUN


def native_primary(host):
    host.b.domain_births={};factory=host.adapter._create_entity_observer
    def original_reader(target,run):
        reader=factory(target,run);original=reader.original
        def read():
            raw=original()
            return json.dumps(native_domain_births(json.loads(raw),host.b.domain_births),indent=2)+'\n' if raw else raw
        reader.original=read;return reader
    host.adapter._create_entity_observer=original_reader


class CreatePeerSourceTests(unittest.TestCase):
    def setUp(self):
        self.primary=primary_source.CreateJourneyTests();self.primary._before_prepare=lambda:native_primary(self.primary)
        self.primary.setUp();self.addCleanup(self.primary.doCleanups)
        self.primary.act('open');self.primary.act('model-create',dict(resource='gltf-bundle/main.gltf'))
        self.scope=self.primary.root.issue_peer_scope();self.worker=None;self.owner=None
        self.addCleanup(self.finish)
        self.directory=self.primary.path/'independent-worker';self.directory.mkdir(mode=0o700)
        self.world=PrivateFeatureState(self.directory/'replica-model.json');self.world_previous=None;self.flags={}
        self.update()

    def update(self,**flags):
        self.flags.update(flags);b=self.primary.b
        value=dict(clock=b.now(),rows=deepcopy(b.rows),births=deepcopy(b.domain_births),phase=self.primary.journal.phase(RUN,uuid.uuid4().hex),**self.flags)
        self.world.write(value,self.world_previous);self.world_previous=deepcopy(value)

    def start(self):
        entry=Path(__file__).with_name('create_peer_originals_host.py');config=PrivateFeatureState(self.directory/'config.json')
        binding=deepcopy(self.scope['binding']);binding.update(processIdentity='456:explicit-independent-native-process',sessionId='8'*32)
        config.write(dict(scope=self.scope,binding=binding,worldPath=str(self.world.path)),None)
        self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(entry),'--config',str(config.path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OVT_CREATE_PEER_TEST_OWNER=self.token))
        self.assertEqual(dict(ready=True),self.receive())
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        self.process=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        exe_sha=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest();entry_sha=hashlib.sha256(entry.read_bytes()).hexdigest()
        def owned(pid):
            root=Path('/proc')/str(pid)
            try:
                with (root/'environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and root.stat().st_uid==os.geteuid() and raw.split(b'\0').count(('OVT_CREATE_PEER_TEST_OWNER='+self.token).encode())==1
            except FileNotFoundError:return False
        self.owner=LinuxChatObserverProcess(self.process,entry,config.path,exe_sha,entry_sha,owned)

    def receive(self):
        self.assertTrue(select.select([self.worker.stdout],[],[],30)[0],'Owned worker response missing')
        raw=self.worker.stdout.readline()
        if not raw:
            self.worker.wait(timeout=5);self.fail('Owned worker stopped: '+self.worker.stderr.read().decode())
        return json.loads(raw)

    def command(self,name,*,success=True):
        self.worker.stdin.write((name+'\n').encode());self.worker.stdin.flush();reply=self.receive()
        self.assertEqual(success,reply['ok'],reply)
        return reply.get('result',reply)

    def finish(self):
        if self.worker is not None:
            if self.worker.poll() is None:
                self.worker.stdin.write(b'exit\n');self.worker.stdin.flush()
            if not self.worker.stdin.closed:self.worker.stdin.close()
            self.worker.wait(timeout=10)
            for stream in (self.worker.stdout,self.worker.stderr):
                if stream is not None and not stream.closed:stream.close()
        if self.owner is not None:self.assertTrue(self.owner.close())

    def begin_cleanup(self):
        self.primary.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        with self.assertRaises(NativeUIError):self.primary.root.invoke('cleanup')
        self.assertEqual([],self.primary.b.rows);self.assertEqual('issued',self.primary.root.peer_state()['phase'])
        self.assertTrue(self.primary.root.store.path.exists());self.update()

    def returned(self):
        self.command('publish')
        expected=dict(runId=RUN,family=FAMILY,producerHostProcessIdentity=self.process,originalRequestId=self.scope['requestId'])
        store=PrivateFeatureState(self.directory/'return.json');ack=PrivateFeatureState(self.directory/'consumption.json')
        receiver=ObserverReturnReceiver(self.owner,store,ack,expected,admit=lambda raw,physical:admit_return(raw,physical,self.scope))
        receiver.acknowledge();self.command('consume')
        # A consumed nonce is still not actual producer-process retirement.
        with self.assertRaises(NativeUIError):self.primary.root.accept_peer_return(receiver)
        self.assertEqual('issued',self.primary.root.peer_state()['phase'])
        self.worker.stdin.write(b'exit\n');self.worker.stdin.flush();self.worker.wait(timeout=10)
        receipt=self.primary.root.accept_peer_return(receiver);self.assertEqual(FAMILY,receipt['family']);self.owner=None
        return receiver

    def test_normal_parent_independent_loaded_model_material_then_real_delete_return_and_joint_cleanup(self):
        self.start();inputs=len(self.primary.b.inputs);initial=self.command('read')
        self.assertTrue(initial['facts']['present']);self.assertEqual('Model',initial['facts']['entityType']);self.assertTrue(initial['facts']['modelLoaded'])
        self.assertFalse(initial['facts']['materialAssignmentBound']);self.assertFalse(initial['facts']['fullCreateActor'])
        self.assertEqual(inputs,len(self.primary.b.inputs));self.primary.act('apply-texture',dict(resource='checker.png'));self.update()
        loading=self.command('read');self.assertFalse(loading['facts']['materialAssignmentBound'])
        self.command('tick');changed=self.command('read');self.assertTrue(changed['facts']['materialAssignmentBound'])
        self.begin_cleanup();inputs=len(self.primary.b.inputs);closed=self.command('cleanup');self.assertTrue(closed['facts']['observedOriginalsRetired'])
        self.returned();self.primary.make();self.primary.root.invoke('cleanup')
        self.assertIsNone(self.primary.root.store.read());self.assertEqual(inputs,len(self.primary.b.inputs))
        self.assertTrue((self.directory/'create-peer-originals.json').exists());self.assertTrue((self.directory/'return.json').exists())

    def test_ignored_remote_material_is_measured_false_and_cached_original_blocks_cleanup_without_replay(self):
        self.start();self.command('read');self.primary.act('apply-texture',dict(resource='checker.png'));self.update(ignoreRenderer=True)
        measured=self.command('read');self.assertTrue(measured['facts']['modelLoaded']);self.assertFalse(measured['facts']['materialAssignmentBound'])
        self.begin_cleanup();self.update(retainResources=True);inputs=len(self.primary.b.inputs)
        retained=self.command('read');self.assertFalse(retained['facts']['observedOriginalsRetired'])
        with self.assertRaises(NativeUIError):self.primary.root.invoke('cleanup')
        self.assertEqual(inputs,len(self.primary.b.inputs));self.assertTrue(self.primary.root.source_store('peer').path.exists())
        self.update(retainResources=False);self.command('cleanup');self.returned();self.primary.make();self.primary.root.invoke('cleanup')
        self.assertEqual(inputs,len(self.primary.b.inputs));self.assertIsNone(self.primary.root.store.read())

    def test_same_client_query_refuses_peer_proof_retains_originals_and_never_requeries_failed_owner(self):
        self.update(sameClient=True);self.start();self.command('read',success=False);before=self.command('stats')
        self.assertTrue(before['failed']);self.assertGreaterEqual(before['chunks'],3);self.assertIsNotNone(before['pending'])
        self.command('read',success=False);after=self.command('stats');self.assertEqual(before,after)
        self.assertTrue(self.primary.root.source_store('peer').path.exists());self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_stale_original_response_is_retained_before_parser_refusal(self):
        self.update(stale=True);self.start();self.command('read',success=False);stats=self.command('stats')
        self.assertEqual(1,stats['entities']);self.assertEqual(0,stats['resources']);self.assertTrue(stats['pending']['query']['responses'])
        self.assertTrue((self.directory/'create-peer-originals.json').exists());self.command('read',success=False);self.assertEqual(stats,self.command('stats'))

    def test_foreign_domain_original_refuses_with_raw_response_and_parent_ownership_retained(self):
        self.update(foreignDomain=True);self.start();self.command('read',success=False);stats=self.command('stats')
        self.assertEqual(1,stats['entities']);self.assertEqual(0,stats['resources']);self.assertTrue(stats['pending']['query']['responses'])
        self.assertTrue(self.primary.root.source_store('peer').path.exists());self.command('read',success=False);self.assertEqual(stats,self.command('stats'))

    def test_replaced_remote_model_original_cannot_requalify_same_domain_entity_uuid(self):
        self.start();self.command('read');self.update(replaceModel=True);self.command('read',success=False);before=self.command('stats')
        self.assertEqual(1,before['records']);self.assertTrue(before['failed']);self.assertIsNotNone(before['pending'])
        self.command('read',success=False);self.assertEqual(before,self.command('stats'));self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_same_uuid_different_domain_creation_refuses_original_ownership_scope(self):
        self.update(differentCreation=True);self.start();self.command('read',success=False);before=self.command('stats')
        self.assertTrue(before['failed']);self.assertEqual(0,before['records']);self.assertIsNotNone(before['pending'])
        self.command('read',success=False);self.assertEqual(before,self.command('stats'))

    def test_requested_model_does_not_replace_an_actual_wrong_entity_type(self):
        self.update(wrongType=True);self.start();self.command('read',success=False);stats=self.command('stats')
        self.assertTrue(stats['failed']);self.assertEqual(0,stats['records']);self.assertIsNotNone(stats['pending'])
        self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_foreign_original_phase_provider_refuses_before_native_query(self):
        self.update(foreignPhase=True);self.start();self.command('read',success=False);stats=self.command('stats')
        self.assertEqual(0,stats['entities']);self.assertEqual(0,stats['resources']);self.assertEqual(1,stats['chunks'])
        self.assertEqual(0,stats['records']);self.assertTrue(stats['failed']);self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_legacy_original_parent_never_invents_domain_birth_or_changes_normal_input(self):
        legacy=primary_source.CreateJourneyTests();legacy.setUp();self.addCleanup(legacy.doCleanups)
        legacy.act('open');legacy.act('model-create',dict(resource='gltf-bundle/main.gltf'));inputs=len(legacy.b.inputs)
        with self.assertRaises(NativeUIError):legacy.root.issue_peer_scope()
        self.assertEqual(inputs,len(legacy.b.inputs));self.assertIsNone(legacy.root.peer_state())
        legacy.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{});legacy.root.invoke('cleanup')
        self.assertIsNone(legacy.root.store.read())

    def test_ignored_remote_creation_and_cancelled_worker_keep_parent_cleanup_owned(self):
        self.update(ignoreEntity=True);self.start();row=self.command('read')
        self.assertFalse(row['facts']['present']);self.assertFalse(row['facts']['modelLoaded']);self.assertFalse(row['facts']['observedOriginalsRetired'])
        self.worker.stdin.write(b'exit\n');self.worker.stdin.flush();self.worker.wait(timeout=10)
        self.begin_cleanup();self.assertTrue(self.primary.root.source_store('peer').path.exists())
        self.assertEqual('issued',self.primary.root.peer_state()['phase'])


if __name__=='__main__':unittest.main()
