"""Real private files around a synthetic actor; no Agent or device is started."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_actor_files import ChatActorFiles,COMMAND,RESULT,SOURCE,encode,node
from adapters.native_chat_observation import NativeChatObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests.test_native_chat_observation import Boundary,BINDING,RUN


class FileActor:
    """Synthetic original writer with a separately retained result descriptor."""
    def __init__(self,root):
        self.root=root;self.native=Boundary();self.last=None;self.fd=-1
        self.ignored=False;self.release=True;self.mutate=None
        self.source_fd=os.open(root/SOURCE,os.O_RDONLY)
    def close(self):
        if self.fd>=0:os.close(self.fd);self.fd=-1
    def tick(self):
        path=self.root/COMMAND
        if not path.exists() or self.ignored:return
        raw=path.read_bytes();request=json.loads(raw)
        if self.last==request['commandId']:return
        self.last=request['commandId'];self.native.send(request)
        temporary=self.root/'.native-result'
        descriptor=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        try:
            envelope=dict(actorFileVersion=1,commandNode=node(path.stat()),resultNode=node(os.fstat(descriptor)),native=deepcopy(self.native.value))
            if self.mutate:self.mutate(envelope)
            os.write(descriptor,encode(envelope));os.fsync(descriptor);os.replace(temporary,self.root/RESULT)
            self.close();self.fd=descriptor;descriptor=-1
        finally:
            if descriptor>=0:os.close(descriptor)
            temporary.unlink(missing_ok=True)
    def close_all(self):
        self.close();os.close(self.source_fd)
    def released(self,identity):
        if node(os.fstat(self.source_fd))==identity:return False
        if self.release and self.native.retired and not (self.root/RESULT).exists():self.close()
        return self.fd<0 or node(os.fstat(self.fd))!=identity


class ActorFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'actor';self.root.mkdir(mode=0o700)
        self.store=PrivateFeatureState(Path(self.temp.name)/'files.json');self.sha=hashlib.sha256(b'actual assigned script').hexdigest()
        source=dict(actorVersion=1,instance='c'*32,processId=123,configuredEpochMs=19900,scriptSha256=self.sha)
        path=self.root/SOURCE;path.write_bytes(encode(source));path.chmod(0o600)
        self.actor=FileActor(self.root);self.addCleanup(self.actor.close_all);self.clock=0;self.alive=True
        self.transport=self.make();self.addCleanup(self.transport.detach)
    def make(self):
        result=ChatActorFiles(self.root,self.store,BINDING,self.sha,lambda:self.alive,self.actor.released,
            component_only=True,clock_ms=lambda:20000,monotonic=lambda:self.clock,sleep=self.sleep)
        self.addCleanup(result.detach);return result
    def sleep(self,delay):self.clock+=delay
    def request(self,operation='inspect',nonce='f'*32):
        return dict(schemaVersion=1,commandId=nonce,action='feature-chat-observe',operation=operation,runId=RUN)
    def produce(self,request=None):
        self.transport.send(request or self.request());self.actor.tick();return json.loads(self.transport.read())
    def reader(self):
        def read():self.actor.tick();return self.transport.read()
        return NativeChatObservation(self.transport.send,read,lambda:20000,lambda:self.alive,123,
            monotonic=lambda:self.clock,sleep=self.sleep)

    def test_original_reader_receives_native_events_and_retirement_closes_actual_unlinked_fd(self):
        reader=self.reader();self.assertFalse(reader.perform(RUN,'inspect')['source']['scopePresent'])
        reader.perform(RUN,'observe');self.actor.native.event()
        value=reader.perform(RUN,'inspect');self.assertEqual(1,len(value['source']['events']))
        reader.perform(RUN,'retire');reader.perform(RUN,'inspect');self.transport.close()
        self.assertIsNone(self.store.read());self.assertFalse((self.root/COMMAND).exists());self.assertFalse((self.root/RESULT).exists())
        self.assertTrue((self.root/SOURCE).exists());self.assertEqual(-1,self.actor.fd)

    def test_strict_root_descriptor_recycling_cannot_publish_or_close_foreign_original_directory_handle(self):
        transport=ChatActorFiles(self.root,self.store,BINDING,self.sha,lambda:self.alive,self.actor.released,
            component_only=True,clock_ms=lambda:20000,monotonic=lambda:self.clock,sleep=self.sleep,require_original_fd=True)
        descriptor,anchor=transport.fd,transport.fd_owner.anchor
        os.close(descriptor);foreign=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        try:
            self.assertEqual(descriptor,foreign)
            with self.assertRaises(NativeUIError):transport.send(self.request())
            transport.detach();self.assertEqual(self.root.stat().st_ino,os.fstat(foreign).st_ino)
            self.assertFalse((self.root/COMMAND).exists());self.assertIsNone(self.store.read()['pending'])
        finally:os.close(foreign);os.close(anchor)

    def test_stale_original_reply_is_preserved_while_waiting_never_relabelled(self):
        original=self.produce();request=self.request(nonce='e'*32);self.transport.send(request)
        self.assertEqual(original,json.loads(self.transport.read()))
        self.actor.tick();fresh=json.loads(self.transport.read())
        self.assertEqual(request['commandId'],fresh['commandId']);self.assertGreater(fresh['sequence'],original['sequence'])

    def test_ignored_query_and_missing_result_fail_reader_without_green_empty_ledger(self):
        self.actor.ignored=True
        with self.assertRaises(NativeUIError):self.reader().perform(RUN,'observe')
        self.assertLessEqual(self.clock,5);self.assertIsNotNone(self.store.read()['request'])
        self.actor.ignored=False;self.actor.tick();self.transport.read();(self.root/RESULT).unlink()
        with self.assertRaises(NativeUIError):self.transport.read()

    def test_noop_pending_manifest_write_cannot_publish_an_original_native_command(self):
        self.transport.store.write=lambda _value,_previous:None
        with self.assertRaises(NativeUIError):self.transport.send(self.request())
        self.assertFalse((self.root/COMMAND).exists());self.assertEqual([],self.actor.native.commands)
        self.assertTrue((self.root/SOURCE).exists());self.assertEqual(self.transport.pid,123)

    def test_byte_identical_copied_result_is_rejected_even_on_first_acquisition(self):
        self.transport.send(self.request());self.actor.tick();original=(self.root/RESULT).read_bytes()
        copy=self.root/'copied';copy.write_bytes(original);copy.chmod(0o600);os.replace(copy,self.root/RESULT)
        with self.assertRaises(NativeUIError):self.transport.read()
        self.assertIsNone(self.store.read()['result']);self.assertIsNotNone(self.store.read()['request'])

    def test_copied_reply_with_rewritten_envelope_inode_is_not_held_by_the_actual_actor(self):
        self.transport.send(self.request());self.actor.tick();envelope=json.loads((self.root/RESULT).read_bytes())
        copy=self.root/'copied';descriptor=os.open(copy,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            envelope['resultNode']=node(os.fstat(descriptor));os.write(descriptor,encode(envelope))
        finally:os.close(descriptor)
        os.replace(copy,self.root/RESULT)
        with self.assertRaises(NativeUIError):self.transport.read()
        self.assertIsNone(self.store.read()['result'])

    def test_unheld_source_metadata_is_not_native_actor_provenance(self):
        original=self.transport.released;self.transport.released=lambda _:True
        with self.assertRaises(NativeUIError):self.transport.send(self.request())
        self.assertFalse((self.root/COMMAND).exists());self.transport.released=original

    def test_foreign_command_node_native_instance_process_and_nonce_are_rejected(self):
        for field in ('command-node','instance','pid','nonce','version','retimed'):
            def mutate(value):
                if field=='command-node':value['commandNode']['inode']='0'
                elif field=='instance':value['native']['instance']='e'*32
                elif field=='pid':value['native']['processId']=124
                elif field=='nonce':value['native']['commandId']='d'*32
                elif field=='version':value['actorFileVersion']=True
                else:value['native']['capturedEpochMs']=19800
            self.actor.mutate=mutate
            with self.subTest(field=field):
                self.transport.send(self.request(nonce=('%032x' % (10+len(self.actor.native.commands)))))
                self.actor.tick()
                with self.assertRaises(NativeUIError):self.transport.read()
        self.assertIsNone(self.store.read()['result'])

    def test_replaced_command_or_source_is_rejected_and_never_unlinked(self):
        self.produce();path=self.root/COMMAND;replacement=self.root/'new';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
        original_fd=os.open(path,os.O_RDONLY);self.addCleanup(os.close,original_fd);os.replace(replacement,path)
        with self.assertRaises(NativeUIError):self.transport.send(self.request(nonce='e'*32))
        self.assertTrue(path.exists());self.assertIsNone(self.store.read()['pending'])
        source=self.root/SOURCE;source.write_bytes(source.read_bytes().replace(b'19900',b'19800'))
        with self.assertRaises(NativeUIError):self.transport.read()
        self.assertTrue(source.exists())

    def test_private_modes_symlinks_hardlinks_and_foreign_files_are_not_adopted(self):
        self.transport.send(self.request());self.actor.tick();path=self.root/RESULT
        path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.transport.read()
        path.chmod(0o600);os.link(path,self.root/'link')
        with self.assertRaises(NativeUIError):self.transport.read()
        (self.root/'link').unlink();path.rename(self.root/'foreign');path.symlink_to(self.root/'foreign')
        with self.assertRaises((NativeUIError,OSError)):self.transport.read()
        self.assertTrue(path.is_symlink());self.assertIsNotNone(self.store.read())

    def test_failed_intent_write_prevents_command_and_uncertain_publication_is_not_replayed(self):
        original=self.store.write
        def fail(*_):raise NativeUIError('journal unavailable')
        self.store.write=fail
        with self.assertRaises(NativeUIError):self.transport.send(self.request())
        self.assertFalse((self.root/COMMAND).exists())
        calls=0
        def fail_after_write(value,previous):
            nonlocal calls
            calls+=1
            if calls==2:raise NativeUIError('journal unavailable after actual publication')
            return original(value,previous)
        self.store.write=fail_after_write
        with self.assertRaises(NativeUIError):self.transport.send(self.request())
        self.assertTrue((self.root/COMMAND).exists());self.assertIsNotNone(self.store.read()['pending'])
        self.store.write=original
        with self.assertRaises(NativeUIError):self.transport.send(self.request(nonce='e'*32))
        self.assertEqual('f'*32,json.loads((self.root/COMMAND).read_bytes())['commandId'])

    def uncertain_v3(self,operation='observe',*,produce=True,reset=True):
        from self_tests.test_chat_cache_lifetime import NativeBoundary
        if reset:self.actor.native=NativeBoundary()
        request=self.request(operation=operation)
        original=self.store.write;calls=[0]
        def lost(value,previous):
            calls[0]+=1
            if calls[0]==2:raise NativeUIError('Original command published, manifest receipt lost')
            return original(value,previous)
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.transport.send(request)
        self.store.write=original
        if produce:self.actor.tick()
        self.assertEqual(request,self.store.read()['pending'])
        return request

    def test_pending_v3_resolves_only_actual_processed_original_and_can_then_query_passively(self):
        request=self.uncertain_v3();before_command=(self.root/COMMAND).read_bytes();before_result=(self.root/RESULT).read_bytes()
        command_node=node((self.root/COMMAND).stat());result_node=node((self.root/RESULT).stat())
        self.transport.detach();self.transport=self.make()
        value=json.loads(self.transport.reconcile_pending(request))
        self.assertEqual(request['commandId'],value['source']['openedCommandId']);self.assertIsNone(self.store.read()['pending'])
        self.assertEqual(before_command,(self.root/COMMAND).read_bytes());self.assertEqual(before_result,(self.root/RESULT).read_bytes())
        self.assertEqual(command_node,node((self.root/COMMAND).stat()));self.assertEqual(result_node,node((self.root/RESULT).stat()))
        self.assertEqual(['observe'],[row['operation'] for row in self.actor.native.commands])
        self.transport.send(self.request(nonce='e'*32));self.actor.tick();self.transport.read()
        self.assertEqual(['observe','inspect'],[row['operation'] for row in self.actor.native.commands])

    def test_pending_missing_original_response_is_retained_without_command_rewrite(self):
        request=self.uncertain_v3(produce=False);original=self.store.read();raw=(self.root/COMMAND).read_bytes()
        with self.assertRaises((NativeUIError,OSError)):self.transport.reconcile_pending(request)
        self.assertEqual(original,self.store.read());self.assertEqual(raw,(self.root/COMMAND).read_bytes())
        self.assertEqual([],self.actor.native.commands)

    def corrupt_pending_result(self,fault):
        request=self.uncertain_v3();envelope=json.loads((self.root/RESULT).read_bytes())
        if fault=='foreign-open':envelope['native']['source']['openedCommandId']='e'*32
        else:
            envelope['native']['chatVersion']=2
            envelope['native']['source'].pop('openedCommandId');envelope['native']['source'].pop('retiredCommandId')
        # Retain the actual original synthetic writer FD/inode; this fault
        # tests content admission independently of copied-file refusal.
        os.ftruncate(self.actor.fd,0);os.lseek(self.actor.fd,0,os.SEEK_SET);os.write(self.actor.fd,encode(envelope))
        original=self.store.read()
        with self.assertRaises(NativeUIError):self.transport.reconcile_pending(request)
        self.assertEqual(original,self.store.read())

    def test_pending_foreign_first_mutation_id_never_closes_original_intent(self):self.corrupt_pending_result('foreign-open')
    def test_pending_legacy_result_never_closes_original_intent(self):self.corrupt_pending_result('legacy')

    def test_pending_copied_command_cannot_supply_original_inode_receipt(self):
        request=self.uncertain_v3();original=self.store.read();path=self.root/COMMAND
        copy=self.root/'copied-command';copy.write_bytes(path.read_bytes());copy.chmod(0o600);os.replace(copy,path)
        with self.assertRaises(NativeUIError):self.transport.reconcile_pending(request)
        self.assertEqual(original,self.store.read())

    def test_pending_copied_result_with_forged_current_node_is_not_held_by_original_actor(self):
        request=self.uncertain_v3();original=self.store.read();envelope=json.loads((self.root/RESULT).read_bytes())
        copy=self.root/'copied-result';descriptor=os.open(copy,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        try:
            envelope['resultNode']=node(os.fstat(descriptor));os.write(descriptor,encode(envelope));os.replace(copy,self.root/RESULT)
        finally:os.close(descriptor)
        with self.assertRaises(NativeUIError):self.transport.reconcile_pending(request)
        self.assertEqual(original,self.store.read())

    def test_pending_retire_consumes_original_matching_fence_without_repeated_input(self):
        from self_tests.test_chat_cache_lifetime import NativeBoundary
        self.actor.native=NativeBoundary();self.produce(self.request('observe',nonce='e'*32))
        request=self.uncertain_v3('retire',reset=False);value=json.loads(self.transport.reconcile_pending(request))
        self.assertTrue(value['source']['retired']);self.assertEqual(request['commandId'],value['source']['retiredCommandId'])
        self.assertEqual('e'*32,value['source']['openedCommandId'])
        self.assertEqual(['observe','retire'],[row['operation'] for row in self.actor.native.commands])

    def test_pending_inspect_consumption_is_not_an_open_request_or_delivery_verdict(self):
        request=self.uncertain_v3('inspect');value=json.loads(self.transport.reconcile_pending(request))
        self.assertFalse(value['source']['scopePresent']);self.assertEqual('',value['source']['openedCommandId'])
        self.assertEqual(['inspect'],[row['operation'] for row in self.actor.native.commands])

    def test_cache_lifetime_peer_recovery_uses_actual_original_files_then_new_inspects(self):
        from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
        from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_chat_cache_lifetime import NativeBoundary
        self.actor.native=NativeBoundary();root=self.store.path.parent
        owner=ChatCaptureOwner(PrivateFeatureState(root/'capture.json'),BINDING,lambda:self.alive,component_only=True)
        self.actor.native.store=owner.store;owner.begin(RUN)
        initial=self.reader().perform(RUN,'inspect');owner.admit(initial)
        lifetime=PrivateFeatureState(root/'lifetime.json');lock=ScriptSourceLock(root/'script-sources.lock')
        def flow():return ChatCacheLifetime(OwnedChatCapture(self.reader(),owner,RUN),lifetime,lock,monotonic=lambda:self.clock)
        write=self.store.write
        def lost(value,previous):
            if value['pending'] is None and value['request'] is not None and value['request']['operation']=='observe':
                raise NativeUIError('Original Observe publication landed; receipt lost')
            return write(value,previous)
        self.store.write=lost
        with self.assertRaises(NativeUIError):flow().activate()
        self.store.write=write;self.actor.tick();pending=self.store.read()['pending']
        self.assertEqual(pending,lifetime.read()['activation']['request'])
        self.transport.reconcile_pending(pending);replacement=flow();replacement.activate();replacement.retire()
        self.assertEqual(['observe','retire'],[row['operation'] for row in self.actor.native.commands if row['operation']!='inspect'])
        self.assertEqual('retired',lifetime.read()['phase']);self.assertIsNotNone(owner.store.read())
        self.transport.close();self.assertEqual(-1,self.actor.fd)
        self.assertIsNone(self.store.read());self.assertIsNotNone(lifetime.read())

    def test_pending_final_guard_native_jump_does_not_return_fresh_under_frozen_host(self):
        request=self.uncertain_v3();original=self.transport.clock_ms;epoch=[20000];self.transport.clock_ms=lambda:epoch[0]
        write=self.store.write
        def late(value,previous):
            write(value,previous)
            if value['pending'] is None:epoch[0]+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.transport.reconcile_pending(request)
        # The original completed transaction may remain consumed after a lost
        # fresh receipt. It cannot cause another Observe on the actual actor.
        self.assertIsNone(self.store.read()['pending']);self.assertEqual(['observe'],[row['operation'] for row in self.actor.native.commands])
        self.transport.clock_ms=original

    def test_pending_reconciliation_lost_manifest_receipt_keeps_actual_consumption_without_resend(self):
        request=self.uncertain_v3();write=self.store.write
        def lost(value,previous):write(value,previous);raise NativeUIError('Original consumption saved, reply lost')
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.transport.reconcile_pending(request)
        self.store.write=write;self.assertIsNone(self.store.read()['pending'])
        self.transport.detach();self.transport=self.make();self.assertEqual(request['commandId'],json.loads(self.transport.read())['commandId'])
        self.assertEqual(['observe'],[row['operation'] for row in self.actor.native.commands])

    def test_known_complete_journal_recovers_same_actor_without_adopting_replacement_source(self):
        original=self.produce();self.transport.detach();self.transport=self.make()
        self.assertEqual(original,json.loads(self.transport.read()))
        old=self.root/SOURCE;fd=os.open(old,os.O_RDONLY);self.addCleanup(os.close,fd)
        replacement=self.root/'replacement';replacement.write_bytes(old.read_bytes());replacement.chmod(0o600);os.replace(replacement,old)
        with self.assertRaises(NativeUIError):self.make()

    def test_initial_foreign_files_absent_journal_wrong_script_and_process_guard_refuse(self):
        self.transport.detach();self.store.discard(self.store.read());(self.root/COMMAND).write_text('{}');(self.root/COMMAND).chmod(0o600)
        with self.assertRaises(NativeUIError):self.make()
        self.assertIsNone(self.store.read());(self.root/COMMAND).unlink();self.sha='f'*64
        with self.assertRaises(NativeUIError):self.make()
        self.alive=False
        with self.assertRaises(NativeUIError):self.make()

    def test_active_cache_and_false_retirement_do_not_remove_original_files(self):
        reader=self.reader();reader.perform(RUN,'observe')
        with self.assertRaises(NativeUIError):self.transport.close()
        self.actor.native.ignore_retire=True
        with self.assertRaises(NativeUIError):reader.perform(RUN,'retire')
        self.assertTrue((self.root/COMMAND).exists());self.assertTrue((self.root/RESULT).exists());self.assertIsNotNone(self.store.read())

    def test_open_native_result_fd_is_incomplete_cleanup_and_recovery_checks_actual_release(self):
        reader=self.reader();reader.perform(RUN,'observe');reader.perform(RUN,'retire');reader.perform(RUN,'inspect')
        self.actor.release=False
        with self.assertRaises(NativeUIError):self.transport.close()
        self.assertLessEqual(self.clock,1.5);self.assertTrue(self.store.read()['removed']);self.assertGreaterEqual(self.actor.fd,0)
        self.transport.detach();self.transport=self.make();self.actor.release=True;self.transport.close()
        self.assertIsNone(self.store.read());self.assertEqual(-1,self.actor.fd)

    def test_pending_journal_foreign_run_and_unexpected_parameters_cannot_mutate_source(self):
        for edit in ({'expected':[]},{'operation':'send'},{'commandId':'ios-'+'f'*32}):
            with self.assertRaises(NativeUIError):self.transport.send(self.request()|edit)
        self.produce()
        with self.assertRaises(NativeUIError):self.transport.send(self.request(nonce='e'*32)|{'runId':'b'*32})
        self.assertEqual(1,len(self.actor.native.commands))


if __name__=='__main__':unittest.main()
