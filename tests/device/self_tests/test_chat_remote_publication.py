"""Real separate host/source files; native clocks, HTTP transport and Parent are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
import uuid
import zlib
from adapters.chat_journey.source_chunks import digest
from contextlib import contextmanager
from unittest.mock import patch

from adapters.chat_journey.remote_publication import ChatRemotePublication,original_record,_warm_signature
from adapters.chat_journey.decoded_chunks import ChatDecodedPrefix
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.chat_journey import source_bundles
from adapters.script_journey.history import canonical,pack,unpack,MAX_PACKED,MAX_RAW
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.witness import Client
from fixture.chat_observer_process import LinuxChatObserverProcess
from self_tests.test_chat_remote_actor_return import WORKER as RETURN_WORKER

WORKER=RETURN_WORKER.split('h=fixture.PicoChatCursorActorTests();h.setUp();actor=h.actor')[0]+'''
import json
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from self_tests.chat_cursor_fixture import cleanup
h=fixture.PicoChatCursorActorTests();h.initial_only=True;h.defer_stop_command=True;h.setUp();actor=h.actor
root=h.h.root;run=actor.source.run
stores=dict(actor=actor.store,flow=actor.publisher.observation.flow_store,
    cleanup=PrivateFeatureState(root/'cleanup-admission.json'),publisher=actor.publisher.store,
    cursor=actor.publisher.cursor.store,code=actor.publisher.observation.samples.script_source.store)
for stage in ('initial','active','cleanup'):
    stores[stage+'-observation']=PrivateFeatureState(root/('global-actor-cleanup-observation.json' if stage=='cleanup' else 'independent-'+stage+'-observation.json'))
    stores[stage+'-samples']=(actor.publisher.observation.samples.store if stage=='initial' else
        h.h.h.samples('actor',h.h.flow.w.witness_store).store if stage=='active' else PrivateFeatureState(root/'global-actor-cleanup-samples.json'))
expected={key:actor.scope[key] for key in ('runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance')}
PrivateFeatureState(config['metadata']).write(dict(stores={key:str(value.path) for key,value in stores.items()},expected=expected,
    locks=[str(lock.path) for lock in (actor.original.lock,actor.original.peer.lock)],
    stop=str(actor.stop_store.path),seal=str(root/'actual-actor-seal.json'),
    returned=str(actor.return_store.path),consumption=str(actor.consumption_store.path)),None)
print('ready',flush=True)
for line in sys.stdin:
    command=json.loads(line);action=command['action']
    if action=='exit':break
    if action=='phase':value=h.h.flow.w.journal.phase(run,command['nonce'])
    elif action=='snapshot':value=h.h.flow.w.journal.snapshot(run)
    elif action=='clock':value=dict(epoch=h.h.native.epoch,host=h.h.native.host)
    elif action=='tick':h.h.flow.sleep(command['seconds']);value=True
    elif action=='publish':value=actor.publish()
    elif action=='advance':
        h.h.flow.next(1);h.parent['completedSteps']=2;h.parent_store.write(h.parent,h.parent_store.read());value=actor.publish()
    elif action=='cleanup':
        h.cleanup_owner.append(cleanup(h.h.h,h.h.cursor));h.parent.update(phase='caches-retired',completedSteps=26)
        h.parent_store.write(h.parent,h.parent_store.read());value=actor.publish()
    elif action=='late':h.h.native.epoch+=2000;value=True
    elif action=='unreturned':
        payload=dict(actor.publisher.rows[-1]['payload']);payload['actorSequence']+=1
        h.h.flow.w.journal.publish(run,payload);value=True
    elif action=='retire':h.h.flow.w.journal.close(run);value=True
    elif action=='stop':actor.stop_once();actor.publish_return();value=True
    elif action=='consume':actor.consume_return();value=True
    else:raise ValueError('Closed source fixture command')
    print(json.dumps(value,separators=(',',':')),flush=True)
'''


class ChatRemotePublicationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        retained=('test_actual_oversize_original_publication_roundtrips_across_all_parts',
            'test_original_directory_window_checks_every_child_and_closes_both_original_handles',
            'test_changed_original_child_refuses_and_closes_only_verified_directory_pair',
            'test_late_directory_observation_failure_keeps_reader_unqualified',
            'test_same_inode_recycled_directory_fd_is_retained_until_actual_fault_host_exit')
        if self._testMethodName in retained:temporary._finalizer.detach()
        else:self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);(self.root/'tmp').mkdir(mode=0o700)
        if self._testMethodName in retained:print('Retained remote source originals:',self.root,flush=True)
        self.entry=self.root/'original-publication-source.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        config=PrivateFeatureState(self.root/'config.json');self.metadata=PrivateFeatureState(self.root/'metadata.json')
        config.write(dict(metadata=str(self.metadata.path)),None);self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(config.path)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(self.root/'tmp'),
                'OVT_CHAT_PUBLICATION_TEST_OWNER':self.token})
        self.addCleanup(self.finish)
        self.assertTrue(select.select([self.worker.stdout],[],[],20)[0]);line=self.worker.stdout.readline()
        if line!=b'ready\n':
            self.worker.stdin.close();self.worker.wait(timeout=5);self.fail(repr(line)+self.worker.stderr.read().decode())
        fields=Path(f'/proc/{self.worker.pid}/stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        def owned(pid):
            try:
                with Path(f'/proc/{pid}/environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and raw.split(b'\0').count(('OVT_CHAT_PUBLICATION_TEST_OWNER='+self.token).encode())==1
            except FileNotFoundError:return False
        self.process=LinuxChatObserverProcess(identity,self.entry,config.path,hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),
            hashlib.sha256(self.entry.read_bytes()).hexdigest(),owned);self.addCleanup(self.process.close)
        metadata=self.metadata.read();self.expected=metadata['expected'];self.stores={key:PrivateFeatureState(path) for key,path in metadata['stores'].items()}
        self.assertEqual(identity,self.expected['hostProcessIdentity'])
        client=Client(self.expected['fixtureUrl'].split('/runs/')[0],'x'*32)
        def request(path,value=None,**kwargs):
            self.assertIsNone(value)
            return self.command('phase',nonce=kwargs['phase_nonce']) if path.endswith('/phase') else self.command('snapshot')
        client.request=request
        source=PhaseFixtureReader(client,self.expected['runId'],'chat',epoch_ms=lambda:self.command('clock')['epoch'],monotonic=lambda:0)
        self.owner=ChatRemotePublication(self.process,source,self.stores,self.expected,
            tuple(ScriptSourceLock(path) for path in metadata['locks']),
            PrivateFeatureState(self.stores['actor'].path.with_name('actual-remote-publication.json')),
            peer_epoch_ms=lambda:self.command('clock')['epoch'],guard=lambda:True,monotonic=lambda:0)

    def command(self,action,**fields):
        self.worker.stdin.write((json.dumps(dict(action=action,**fields))+'\n').encode());self.worker.stdin.flush()
        self.assertTrue(select.select([self.worker.stdout],[],[],20)[0]);raw=self.worker.stdout.readline()
        if not raw:
            self.worker.wait(timeout=5);self.fail(self.worker.stderr.read().decode())
        return json.loads(raw)

    def finish(self):
        if not self.worker.stdin.closed:self.worker.stdin.close()
        self.worker.wait(timeout=20)
        for stream in (self.worker.stdout,self.worker.stderr):stream.close()

    def test_actual_two_process_stage_prefixes_and_new_same_phase_queries_are_preserved(self):
        owner=self.owner;first=owner.acquire(0);self.assertEqual(1,len(first['entries']));self.assertFalse(owner.failed)
        with self.assertRaises(PhasePending):owner.acquire(1)
        self.assertEqual(1,len(owner.rows));self.command('advance');active=owner.acquire(1)
        self.assertEqual(2,len(active['entries']));self.command('cleanup');clean=owner.acquire(2)
        self.assertEqual(3,len(clean['entries']));self.command('publish');last=owner.acquire(3)
        self.assertEqual(4,len(last['entries']));self.assertEqual(4,len(owner.rows));owner.control()
        self.assertEqual(['initial','active','cleanup'],[row['stage'] for row in owner.roots['cursor']['stages']])
        self.assertEqual(4,len(owner.previous['bundles']))
        self.assertEqual(sum(ref['parts'] for ref in owner.previous['bundles']),len(owner.previous['chunks']))
        self.assertEqual(len(owner.history.identities),len(owner.previous['chunks']))
        self.assertTrue(any(ref['parts']>1 for ref in owner.previous['bundles']))
        self.assertTrue(all(owner.original(index)==row for index,row in enumerate(owner.rows)))
        self.assertIsNone(self.stores['actor'].read().get('stopCommand'))
        self.assertTrue(self.process.guard() is True);self.assertEqual(4,last['entries'][-1]['actorSequence'])
        self.assertEqual(4,len(owner.grammar.previous['frames']['publisher']));self.assertIsNone(owner.grammar.pending)

    def test_warm_metadata_keeps_legitimate_refs_aliases_deepcopy_and_dictionary_order(self):
        owner=self.owner;owner.acquire(0);seal=owner.cache_seal
        inspection=[owner.expected,owner.scope,owner.previous,owner.admitted,owner.roots]*3
        def reverse(value):
            if type(value) is dict:return {key:reverse(field) for key,field in reversed(list(value.items()))}
            if type(value) is list:return [reverse(field) for field in value]
            return value
        for name in ('expected','scope','previous','admitted','roots','paths'):
            setattr(owner,name,reverse(deepcopy(getattr(owner,name))))
        owner.metadata_control();self.assertIs(seal,owner.cache_seal)
        self.assertTrue(inspection);self.command('publish');owner.acquire(1)
        self.assertEqual(2,owner.row_count());self.assertFalse(owner.failed)
        shared={'same':[1,False,None,'x']};unshared={'a':deepcopy(shared),'b':deepcopy(shared)}
        self.assertEqual(_warm_signature({'a':shared,'b':shared}),_warm_signature(unshared))
        text=''.join(['original','-',uuid.uuid4().hex]);interned=sys.intern(text)
        self.assertEqual(_warm_signature([text,text]),_warm_signature([''.join(list(text)),interned]))

    def test_warm_signature_preserves_exact_types_and_rejects_subclass_hooks(self):
        class Forbidden(str):
            def __reduce__(self):raise AssertionError('No serialization hooks may run')
        original={'a':[1,False,None,'x']};signature=_warm_signature(original)
        for value in ({'a':tuple(original['a'])},{'a':[True,False,None,'x']},
                      {'a':[1.0,False,None,'x']},{'a':[1,False,None,b'x']}):
            self.assertNotEqual(signature,_warm_signature(value))
        for value in ({'a':[Forbidden('x')]},{1:['x']}):
            with self.assertRaises(NativeUIError):_warm_signature(value)

    def test_canonical_unicode_alias_uses_original_strict_digest_without_resealing(self):
        from adapters.chat_journey.original_memory import plain
        owner=self.owner;metadata=owner.cache_metadata;value=[None]
        def modeled(*,strict):
            result=metadata(strict=strict);result['unicodeBoundary']=value[0]
            if strict:plain(value[0])
            return result
        # Pure additional metadata field only: no source query, scope change,
        # requested effect, publication or caller-owned original is admitted.
        pairs=(('\U0001f600','\ud83d\ude00'),({'\U0001f600':'x'},{'\ud83d\ude00':'x'}))
        with patch.object(owner,'cache_metadata',modeled):
            for first,second in pairs:
                self.assertEqual(canonical(first),canonical(second))
                self.assertNotEqual(_warm_signature(first),_warm_signature(second))
                value[0]=first;owner.pin_cache();seal=owner.cache_seal
                value[0]=second
                with patch.object(owner,'cache_digest',wraps=owner.cache_digest) as strict:
                    owner.cache_control();self.assertEqual(1,strict.call_count)
                self.assertIs(seal,owner.cache_seal)

    def test_warm_cache_seal_and_forged_canonical_checksum_cannot_adopt_mutation(self):
        owner=self.owner;owner.acquire(0);before=deepcopy(owner.previous)
        owner.admitted[next(iter(owner.admitted))][0]+=1
        owner.cache_sha=owner.cache_digest() # An exposed checksum is not original admission.
        self.command('publish')
        with self.assertRaises(NativeUIError):owner.acquire(1)
        self.assertTrue(owner.failed);self.assertEqual(before,owner.store.read())
        self.assertEqual(1,owner.row_count());self.assertEqual(2,len(self.command('snapshot')['entries']))

    def test_replaced_same_value_warm_seal_cannot_become_original_admission(self):
        owner=self.owner;owner.acquire(0);owner.cache_seal=tuple(list(owner.cache_seal))
        self.command('publish')
        with self.assertRaises(NativeUIError):owner.acquire(1)
        self.assertTrue(owner.failed);self.assertEqual(1,owner.row_count())

    def test_signature_processing_cost_stays_in_original_freshness_without_clock_renewal(self):
        owner=self.owner;clock=[0.0];owner.monotonic=lambda:clock[0]
        signature=_warm_signature;delayed=[]
        def late(value):
            result=signature(value)
            if owner.previous is not None and owner.previous['phase']=='ready' and not delayed:
                delayed.append(True);clock[0]+=2
            return result
        with patch('adapters.chat_journey.remote_publication._warm_signature',side_effect=late):
            with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertEqual([True],delayed);self.assertTrue(owner.failed)
        self.assertEqual('ready',owner.store.read()['phase']);self.assertIsNone(owner.grammar.previous)
        self.assertTrue(owner.store.path.exists())

    def test_cold_storage_decodes_original_v3_parts_and_retains_v2_without_constructing_live_owner(self):
        owner=self.owner;owner.acquire(0);self.command('advance');owner.acquire(1)
        root=owner.store.read();history=ChatSourceChunks(owner.store,owner.scope);history.load(root['chunks'])
        self.assertEqual(owner.rows,[original_record(history,root,index) for index in range(len(owner.rows))])
        # A historical format fixture reuses exact original logical values;
        # no Actor, native reader, process or current observation is restored.
        legacy=PrivateFeatureState(owner.store.path.with_name('legacy-remote-source.json'))
        scope={**owner.scope,'chatRemotePublicationVersion':2,'journal':legacy.path.name}
        old=ChatSourceChunks(legacy,scope);manifest=[];previous=None
        for row in owner.rows:
            reading={**scope,'phase':'reading','chunks':manifest};legacy.write(reading,previous);previous=reading
            manifest=old.append(row,manifest)
            reading={**scope,'phase':'reading','chunks':manifest};legacy.write(reading,previous);previous=reading
        ready={**scope,'phase':'ready','chunks':manifest};legacy.write(ready,previous)
        cold=ChatSourceChunks(legacy,scope);cold.load(manifest)
        self.assertEqual(owner.rows,[original_record(cold,ready,index) for index in range(len(owner.rows))])
        self.assertEqual(2,legacy.read()['chatRemotePublicationVersion']);self.assertNotIn('bundles',legacy.read())
        self.assertEqual(2,len(self.command('snapshot')['entries']))

    def test_actual_oversize_original_publication_roundtrips_across_all_parts(self):
        print('Original oversize source fixture retained in '+str(self.root),flush=True)
        owner=self.owner;owner.acquire(0);self.command('advance');owner.acquire(1);self.command('cleanup');owner.acquire(2)
        for _attempt in range(80):
            row=owner.rows[-1];raw=canonical([row]);encoded=base64.b64encode(zlib.compress(raw,level=9))
            self.assertLessEqual(len(raw),MAX_RAW)
            if len(encoded)>MAX_PACKED:break
            after=row['publication']['sequence'];self.command('publish');owner.acquire(after)
        else:self.fail('Original source did not reach the unchanged packed-leaf boundary within the fixture bound')
        with self.assertRaises(NativeUIError):pack([row])
        self.assertEqual(row,owner.original(len(owner.rows)-1))
        root=owner.store.read();self.assertEqual('ready',root['phase']);self.assertIsNone(root['pendingBundle'])
        self.assertEqual(len(owner.rows),len(root['bundles']));self.assertEqual(len(owner.history.identities),len(root['chunks']))
        self.assertGreater(root['bundles'][-1]['parts'],1)
        self.assertEqual(row,original_record(owner.history,root,len(owner.rows)-1))
        summary=dict(scope='actual-source-storage-only',logicalRecords=len(owner.rows),physicalParts=len(root['chunks']),
            originalPackedBytes=len(encoded),logicalOriginalBytes=root['logicalBytes'],physicalRawBytes=owner.history.raw_bytes,
            originalLastBytes=root['bundles'][-1]['bytes'],originalLastSha256=root['bundles'][-1]['sha256'],deviceQualified=False)
        PrivateFeatureState(self.root/'oversize-source-summary.json').write(summary,None)
        self.assertLessEqual(len(root['chunks']),512);self.assertLessEqual(root['logicalBytes'],MAX_RAW)
        self.assertLessEqual(owner.history.raw_bytes,MAX_RAW);self.assertIsNone(owner.stop_intent)
        print(json.dumps(summary,sort_keys=True),flush=True)

    def test_historical_inspection_alias_cannot_mutate_admitted_original_or_require_process_guard(self):
        owner=self.owner;owner.acquire(0);original=source_bundles.original
        with patch('adapters.chat_journey.original_memory.json.loads',side_effect=AssertionError('Metadata must not decode old JSON')):
            owner.cache_digest();self.assertEqual(1,owner.row_count())
        def forbidden():raise AssertionError('Historical original must not probe a returned process')
        owner.process.guard=forbidden;self.assertEqual(owner.rows[0],owner.original(0))
        def alias(*args):
            result=original(*args)
            facts=owner.rows[0]['received']['entries'][0]['facts'];facts['messages']=tuple(facts['messages'])
            return result
        with patch.object(source_bundles,'original',side_effect=alias):self.assertEqual(owner.row(0),owner.original(0))
        self.assertFalse(owner.failed);owner.originals.control(owner.scope)

    def test_historical_original_rejects_internal_bytes_changed_during_literal_read_without_process_guard(self):
        owner=self.owner;owner.acquire(0);original=source_bundles.original
        def forbidden():raise AssertionError('Historical original must not probe a returned process')
        owner.process.guard=forbidden
        def changed(*args):
            result=original(*args);cache=owner.originals
            cache.raws=cache._raws=(cache.raws[0]+b' ',)
            return result
        with patch.object(source_bundles,'original',side_effect=changed),self.assertRaises(NativeUIError):owner.original(0)
        self.assertTrue(owner.failed)
        with self.assertRaises(NativeUIError):owner.original(0)

    def test_historical_original_rejects_path_change_during_literal_read_without_process_guard(self):
        owner=self.owner;owner.acquire(0);original=source_bundles.original
        def forbidden():raise AssertionError('Historical original must not probe a returned process')
        owner.process.guard=forbidden
        def changed(*args):
            result=original(*args);owner.stores['code'].path=owner.stores['code'].path.with_name('foreign-code.json');return result
        with patch.object(source_bundles,'original',side_effect=changed),self.assertRaises(NativeUIError):owner.original(0)
        self.assertTrue(owner.failed)
        with self.assertRaises(NativeUIError):owner.original(0)

    def test_final_cas_native_jump_with_frozen_host_keeps_originals_unqualified(self):
        owner=self.owner;write=owner.store.write
        def late(value,previous):
            write(value,previous)
            if value['phase']=='ready':self.command('late')
        owner.store.write=late
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(owner.failed);self.assertEqual('ready',owner.store.read()['phase'])
        self.assertIsNone(owner.grammar.previous)
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(owner.store.path.exists())

    def test_lost_actual_middle_part_keeps_original_pending_intent_and_never_requeries(self):
        owner=self.owner;owner.acquire(0);self.command('advance');owner.acquire(1);self.command('cleanup')
        original=deepcopy(owner.rows);first_new=len(owner.history.identities)
        target=owner.history.store(first_new+1).path;write=PrivateFeatureState.write;attempts=[]
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path==target:attempts.append(store.path);raise OSError('Actual middle part reply lost')
            return result
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(NativeUIError):owner.acquire(2)
        root=owner.store.read();self.assertEqual('reading',root['phase']);self.assertGreater(root['pendingBundle']['parts'],1)
        self.assertEqual(2,len(root['bundles']));self.assertEqual(original,owner.rows)
        self.assertEqual([target],attempts);self.assertTrue(target.exists());self.assertTrue(owner.failed)
        with self.assertRaises(NativeUIError):owner.acquire(2)
        self.assertEqual([target],attempts);self.assertEqual(3,len(self.command('snapshot')['entries']))

    def test_lost_actual_ready_root_cannot_adopt_complete_fragments_or_retry(self):
        owner=self.owner;write=owner.store.write;attempts=[]
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='ready':attempts.append(deepcopy(value));raise OSError('Actual ready-root reply lost')
        owner.store.write=lost
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(owner.failed);self.assertEqual('ready',owner.store.read()['phase'])
        self.assertEqual(1,len(attempts));self.assertIsNone(owner.grammar.previous)
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertEqual(1,len(attempts));self.assertEqual(1,len(self.command('snapshot')['entries']))

    def test_original_retired_phase_is_terminal_without_a_false_pending_retry(self):
        self.command('retire')
        with self.assertRaises(NativeUIError):self.owner.acquire(0)
        self.assertTrue(self.owner.failed);self.assertIsNone(self.owner.store.read())

    def test_independently_received_extra_post_without_original_return_cannot_be_truncated_or_adopted(self):
        self.command('unreturned')
        with self.assertRaises(NativeUIError):self.owner.acquire(0)
        self.assertTrue(self.owner.failed);self.assertIsNone(self.owner.store.read());self.assertEqual([],self.owner.rows)

    def test_same_bytes_original_child_replacement_is_not_adopted_on_new_real_publication(self):
        owner=self.owner;owner.acquire(0)
        self.command('publish')
        child=PrivateFeatureState(next(iter(owner.admitted)));value=child.read();child.write(value,value)
        with self.assertRaises(NativeUIError):owner.acquire(1)
        self.assertTrue(owner.failed);self.assertEqual(1,len(owner.rows));self.assertTrue(child.path.exists())

    def test_actual_outer_lock_exit_failure_keeps_ready_looking_row_unqualified(self):
        owner=self.owner;held=owner.held
        @contextmanager
        def lost():
            with held():yield
            raise OSError('Actual outer lock exit failed')
        owner.held=lost
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(owner.failed);self.assertEqual('ready',owner.store.read()['phase'])
        self.assertIsNone(owner.grammar.previous)
        with self.assertRaises(NativeUIError):owner.acquire(0)

    def test_late_pure_prefix_commit_is_still_inside_original_native_freshness(self):
        owner=self.owner;commit=owner.grammar.commit
        def late(value):commit(value);self.command('late')
        owner.grammar.commit=late
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(owner.failed);self.assertEqual('ready',owner.store.read()['phase'])
        with self.assertRaises(NativeUIError):owner.acquire(0)

    def test_decoder_prefix_commit_stays_inside_original_frozen_host_native_age(self):
        owner=self.owner;commit=ChatDecodedPrefix.commit;calls=[]
        def late(cache,candidate):
            commit(cache,candidate);calls.append(cache.path)
            if len(calls)==1:self.command('late')
        with patch.object(ChatDecodedPrefix,'commit',late),self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(calls);self.assertTrue(owner.failed);self.assertEqual('ready',owner.store.read()['phase'])
        with self.assertRaises(NativeUIError):owner.acquire(0)

    def test_decoder_prefix_only_admits_after_original_outer_lock_exit(self):
        owner=self.owner;held=owner.held
        @contextmanager
        def lost():
            with held():yield
            raise OSError('Actual outer lock exit failed before decoder admission')
        owner.held=lost
        with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(owner.failed);self.assertEqual({},owner.decoders)

    def test_decoder_commit_cannot_refresh_unrelated_mutated_ownership_checksum(self):
        owner=self.owner;commit=ChatDecodedPrefix.commit;changed=[]
        def mutate(cache,candidate):
            commit(cache,candidate)
            if not changed:
                owner.expected['instance']='f'*32;changed.append(True)
        with patch.object(ChatDecodedPrefix,'commit',mutate),self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(changed);self.assertTrue(owner.failed)
        with self.assertRaises(NativeUIError):owner.acquire(0)

    def test_warm_decoder_only_unpacks_new_original_parts_after_full_physical_load(self):
        owner=self.owner;owner.acquire(0);before={key:len(cache.records) for key,cache in owner.decoders.items()}
        self.command('publish')
        with patch('adapters.chat_journey.decoded_chunks.unpack',wraps=unpack) as decoder:owner.acquire(1)
        self.assertEqual(sum(len(cache.records)-before.get(key,0) for key,cache in owner.decoders.items()),decoder.call_count)
        self.assertTrue(decoder.call_count);owner.control()

    def test_replacement_between_first_physical_capture_and_load_is_never_adopted(self):
        owner=self.owner;load=ChatSourceChunks.load;replaced=[]
        def race(history,manifest,**options):
            if history.root.path==owner.stores['publisher'].path:
                child=history.store(0);value=child.read();child.write(value,value);replaced.append(child.path)
            return load(history,manifest,**options)
        with patch.object(ChatSourceChunks,'load',race):
            with self.assertRaises(NativeUIError):owner.acquire(0)
        self.assertTrue(replaced);self.assertTrue(owner.failed);self.assertIsNone(owner.store.read())

    def test_same_canonical_tuple_cache_cannot_become_another_fresh_read(self):
        owner=self.owner;owner.acquire(0);owner.history.identities=[list(row) for row in owner.history.identities]
        self.command('publish')
        with self.assertRaises(NativeUIError):owner.acquire(1)
        self.assertTrue(owner.failed);self.assertEqual(1,len(owner.rows))

    def test_newer_unconsumed_source_frame_cannot_refresh_original_consumed_native_epochs(self):
        owner=self.owner;owner.acquire(0);self.command('late');self.command('publish')
        with owner.held():
            with self.assertRaises(NativeUIError):owner.fresh_current()
        self.assertTrue(owner.failed);self.assertEqual(1,len(owner.rows))

    def test_original_freeze_is_not_a_stop_ack_and_permanently_blocks_new_acquisition(self):
        owner=self.owner;owner.acquire(0);row=owner.rows[-1]['publication']
        command=dict(picoChatCursorActorStopVersion=2,commandId=uuid.uuid4().hex,instance=owner.expected['instance'],
            runId=owner.expected['runId'],ticket=row['payload']['ticket'],consumedSequence=row['sequence'],
            consumedPayloadSha256=digest(row['payload']),cleanupConsumptionSha256='b'*64)
        owner.freeze(command);self.assertEqual(command,owner.stop_intent)
        with self.assertRaises(NativeUIError):owner.acquire(row['sequence'])
        self.assertFalse(owner.failed);self.assertEqual(1,len(owner.rows))
        self.assertNotIn('stopCommand',self.stores['actor'].read())

    def test_original_directory_window_checks_every_child_and_closes_both_original_handles(self):
        import adapters.chat_journey.remote_publication as module
        owner=self.owner;owner.acquire(0);observed=[];windows=[];original=module.os.stat
        def inspect(path,*args,**kwargs):
            if kwargs.get('dir_fd') is not None:
                directory=owner.directory_window;self.assertIsNotNone(directory)
                directory.require(kwargs['dir_fd']);windows.append(directory)
                self.assertIs(False,kwargs['follow_symlinks']);self.assertEqual(os.path.basename(path),path)
                observed.append(str(owner.store.path.parent/path))
            return original(path,*args,**kwargs)
        with patch.object(module.os,'stat',side_effect=inspect):owner.physical_children()
        self.assertEqual(set(owner.admitted),set(observed));self.assertEqual(len(owner.admitted),len(observed))
        self.assertEqual(1,len({id(window) for window in windows}));self.assertTrue(windows[0].closed)
        self.assertEqual((-1,-1),(windows[0].fd,windows[0].anchor));self.assertIsNone(owner.directory_window)
        owner.control();self.assertFalse(owner.failed)

    def test_changed_original_child_refuses_and_closes_only_verified_directory_pair(self):
        owner=self.owner;owner.acquire(0)
        path=Path(next(iter(owner.admitted)));info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1_000_000))
        with self.assertRaises(NativeUIError):owner.physical_children()
        self.assertTrue(owner.failed);self.assertIsNone(owner.directory_window)
        self.assertTrue(path.exists());self.assertEqual(1,owner.row_count())

    def test_late_directory_observation_failure_keeps_reader_unqualified(self):
        import adapters.chat_journey.remote_publication as module
        owner=self.owner;owner.acquire(0);calls=[];require=module.require_directory
        def unavailable(directory,path,**kwargs):
            calls.append(directory);require(directory,path,**kwargs)
            if len(calls)==2:raise NativeUIError('Explicit unavailable final original directory observation')
        with patch.object(module,'require_directory',side_effect=unavailable),self.assertRaises(NativeUIError):owner.physical_children()
        self.assertEqual(2,len(calls));self.assertIs(calls[0],calls[1]);self.assertTrue(calls[0].closed)
        self.assertTrue(owner.failed);self.assertIsNone(owner.directory_window)

    def test_same_inode_recycled_directory_fd_is_retained_until_actual_fault_host_exit(self):
        import adapters.chat_journey.remote_publication as module
        owner=self.owner;owner.acquire(0);read_fd,write_fd=os.pipe();pid=os.fork()
        if pid==0:
            os.close(read_fd)
            try:
                original=module.os.stat;changed=[]
                def recycle(path,*args,**kwargs):
                    descriptor=kwargs.get('dir_fd')
                    if descriptor is not None and not changed:
                        directory=owner.directory_window;replacement=os.open(owner.store.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
                        os.dup2(replacement,descriptor);os.close(replacement);changed.append(directory)
                    return original(path,*args,**kwargs)
                with patch.object(module.os,'stat',side_effect=recycle):
                    try:owner.physical_children()
                    except NativeUIError:pass
                    else:raise AssertionError('Recycled same-inode directory fd qualified')
                directory=owner.directory_window
                result=dict(failed=owner.failed,retained=directory is changed[0],lost=directory.lost,
                    closed=directory.closed,foreignStillOpen=os.fstat(directory.fd).st_ino==directory.node[1],
                    anchorStillOpen=os.fstat(directory.anchor).st_ino==directory.node[1])
                os.write(write_fd,json.dumps(result).encode());os.close(write_fd)
                os._exit(0)
            except BaseException:os._exit(1)
        os.close(write_fd)
        try:
            raw=os.read(read_fd,4096)
        finally:os.close(read_fd)
        waited,status=os.waitpid(pid,0);self.assertEqual(pid,waited);self.assertEqual(0,status)
        self.assertEqual(dict(failed=True,retained=True,lost=True,closed=False,foreignStillOpen=True,anchorStillOpen=True),json.loads(raw))
        # Fault-only inherited handles disappear through actual child exit;
        # the original Parent/Actor/source files and their owners stay intact.
        self.assertFalse(owner.failed);self.assertIsNone(owner.directory_window);owner.control()


def remote_publication_component_tests():
    return unittest.TestSuite(ChatRemotePublicationTests(name) for name in
        unittest.defaultTestLoader.getTestCaseNames(ChatRemotePublicationTests)
        if name!='test_actual_oversize_original_publication_roundtrips_across_all_parts')


if __name__=='__main__':unittest.main()
