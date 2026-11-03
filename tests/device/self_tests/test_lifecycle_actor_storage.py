"""Real files/OFDs and fail-closed transfer; no native/effect simulation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import os
from pathlib import Path
import tempfile
import secrets
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_actor_storage import LifecycleActorStorage,STAGE,decode_snapshot,snapshot_file
from adapters.script_journey.history import canonical,MAX_RAW
from adapters.pico4.lifecycle_actor_originals import ActorOriginals
from adapters.script_journey.lock import ScriptSourceLock


class LifecycleActorStorageTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(tempfile.mkdtemp(prefix='lifecycle-storage-originals-'));self.path.chmod(0o700)
        print('Actor storage originals retained: '+str(self.path),flush=True)
        self.lock=ScriptSourceLock(self.path/'script-sources.lock')
        self.store=PrivateFeatureState(self.path/'lifecycle-actor-originals.json')
        self.scope=dict(picoLifecycleActorSourceVersion=2,runId='historical-codec-only',binding={},role='actor',
            stage='storage-codec-only',producerHostProcessIdentity='historical',
            parentHostProcessIdentity='historical-parent',fixtureUrl='historical://no-live-owner')
        self.fresh_count=0
        def fresh():self.fresh_count+=1
        with self.lock.held():self.owner=LifecycleActorStorage(self.store,self.scope,self.lock,lambda:True,fresh)
        self.addCleanup(self.owner.close_host)

    def reading(self):
        self.owner.begin();self.owner.retain('request',dict(nonce='exact original'))
        self.owner.retain('response',dict(raw='  original whitespace\n',clock=123))

    def complete(self,sequence):
        self.reading();self.owner.native_record(dict(publication=dict(sequence=sequence)))
        self.owner.issue_publication(dict(sequence=sequence));self.owner.publication_phase(dict(original=sequence))
        self.owner.retire_stage();self.owner.delivered(dict(accepted=sequence))

    def test_exact_copies_and_observed_closes_allow_only_retired_slot_reuse(self):
        with self.lock.held():
            self.complete(1);self.complete(2);self.owner.verify()
            self.assertEqual(6,len(self.owner.disk['chunks']));self.assertFalse((self.path/STAGE).exists())
            for row in self.owner.disk['records']:
                value,_=self.owner.original(row['native']);_root,entries=decode_snapshot(value['staging'])
                self.assertEqual(['request','response'],[entry['key'] for entry in entries])
                phase,_=self.owner.original(row['phase']);final=phase['stagingTransfer']
                from adapters.pico4.lifecycle_actor_storage import checked_file
                observed=checked_file(final)['retirementReceipts']
                self.assertEqual(2,len(observed));self.assertTrue(all(receipt['originalFileDescriptionClosed'] for receipt in observed))
                reply,_=self.owner.original(row['reply'])
                self.assertTrue(reply['stagingRetirement']['receipt']['originalDirectoryDescriptionClosed'])
        historical=ActorOriginals(self.store)
        self.assertEqual('  original whitespace\n',historical.last('response',record=1)['raw'])
        self.assertGreater(self.fresh_count,0)

    def test_actual_lost_stage_cas_keeps_original_child_and_forbids_retry_or_cold_adoption(self):
        with self.lock.held():
            self.owner.begin();stage=self.owner.stage;write=stage.physical.write
            def lost(value,previous):
                result=write(value,previous)
                if value['chunks']:raise OSError('Actual durable stage CAS reply lost')
                return result
            stage.physical.write=lost
            with self.assertRaises(OSError):self.owner.retain('response',dict(raw='exact retained failure'))
            self.assertTrue(stage.history._path(0).exists());self.assertTrue(self.owner.failed)
            with self.assertRaises(NativeUIError):self.owner.retain('next',{})
            with self.assertRaises(NativeUIError):LifecycleActorStorage(self.store,self.scope,self.lock,lambda:True,lambda:None)

    def test_same_bytes_new_immutable_destination_stops_before_first_staged_unlink(self):
        with self.lock.held():
            self.reading();stage=self.owner.stage;copied=stage.copied
            def replaced(index,snapshot):
                copied(index,snapshot);path=self.owner.history._path(0)
                replacement=path.with_name('owned-same-bytes-copy.json');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
                os.replace(replacement,path)
            stage.copied=replaced
            with self.assertRaises(NativeUIError):self.owner.native_record(dict(publication={}))
            self.assertTrue(self.owner.failed);self.assertTrue(all(stage.history._path(i).exists() for i in range(2)))
            self.assertEqual([],stage.disk['retired'])

    def test_actual_unlink_refusal_retains_issued_intent_and_every_original(self):
        with self.lock.held():
            self.reading();stage=self.owner.stage
            unlink=os.unlink
            def refused(name,*args,**kwargs):
                if str(name).startswith(STAGE+'.frame-'):raise PermissionError('Original unlink refused')
                return unlink(name,*args,**kwargs)
            with patch('adapters.pico4.lifecycle_actor_storage.os.unlink',side_effect=refused):
                with self.assertRaises(PermissionError):self.owner.native_record(dict(publication={}))
            self.assertEqual('issued',stage.store.read()['unlink']['phase']);self.assertEqual([],stage.disk['retired'])
            self.assertTrue(all(stage.history._path(i).exists() for i in range(2)))
            with self.assertRaises(NativeUIError):self.owner.begin()

    def test_actual_same_node_fd_recycle_never_closes_foreign_replacement_or_unlinks(self):
        with self.lock.held():
            self.reading();stage=self.owner.stage;owner=stage.owners[0];descriptor=owner.fd
            os.close(descriptor);replacement=os.open(stage.history._path(0),os.O_RDONLY|os.O_CLOEXEC)
            self.assertEqual(descriptor,replacement)
            try:
                with self.assertRaises(NativeUIError):self.owner.native_record(dict(publication={}))
                self.assertTrue(owner.lost);self.assertFalse(owner.close());os.fstat(replacement)
                self.assertTrue(stage.history._path(0).exists());self.assertTrue(self.owner.failed)
            finally:
                os.close(replacement)
                # The test owns this exact unexposed duplicate; production
                # preserves uncertain handles until real process exit.
                os.close(owner.anchor);owner.anchor=-1

    def test_actual_stage_root_same_byte_replacement_is_not_adopted(self):
        with self.lock.held():
            self.reading();stage=self.owner.stage;path=stage.store.path
            replacement=path.with_name('owned-replaced-stage.json');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
            os.replace(replacement,path)
            with self.assertRaises(NativeUIError):self.owner.native_record(dict(publication={}))
            self.assertTrue(self.owner.failed);self.assertTrue(stage.history._path(0).exists())

    def foreign_pending(self,name):
        with self.lock.held():
            self.reading();foreign=self.path/name;foreign.write_bytes(b'foreign unknown original');foreign.chmod(0o600)
            count=len(self.owner.stage.files)
            with self.assertRaises(NativeUIError):self.owner.verify()
            self.assertTrue(self.owner.failed);self.assertEqual(count,len(self.owner.stage.files))
            self.assertEqual(b'foreign unknown original',foreign.read_bytes())
            with self.assertRaises(NativeUIError):self.owner.retain('next',{})

    def test_foreign_stage_pending_file_is_preserved_and_poisoned_without_next_append(self):
        self.foreign_pending(STAGE+'.pending-foreign')

    def test_foreign_main_pending_file_is_preserved_and_poisoned_without_next_append(self):
        self.foreign_pending(self.store.path.name+'.pending-foreign')

    def test_real_unlink_followed_by_same_node_close_uncertainty_keeps_copy_and_issued_intent(self):
        with self.lock.held():
            self.reading();stage=self.owner.stage;owner=stage.owners[0];close=owner.close;replacement=[]
            def recycled():
                descriptor=owner.fd;os.close(descriptor)
                foreign=os.open('/proc/self/fd/'+str(owner.anchor),os.O_RDONLY|os.O_CLOEXEC)
                if foreign!=descriptor:
                    os.dup2(foreign,descriptor,inheritable=False);os.close(foreign)
                replacement.append(descriptor);return close()
            owner.close=recycled
            try:
                with self.assertRaises(NativeUIError):self.owner.native_record(dict(publication={}))
                self.assertFalse(stage.history._path(0).exists());self.assertTrue(stage.history._path(1).exists())
                self.assertEqual('issued',stage.store.read()['unlink']['phase']);self.assertEqual([],stage.disk['retired'])
                self.assertEqual(0,os.fstat(replacement[0]).st_nlink)
                copied=ActorOriginals(self.store).pending();self.assertEqual(['request','response'],[row['key'] for row in copied])
                self.assertEqual('  original whitespace\n',copied[1]['value']['raw'])
            finally:
                owner.close=close
                for descriptor in replacement:os.close(descriptor)
                os.close(owner.anchor);owner.anchor=-1

    def test_split_high_entropy_original_survives_verified_copy_and_real_part_retirement(self):
        raw=base64.b64encode(secrets.token_bytes(120000)).decode('ascii')
        with self.lock.held():
            self.owner.begin();self.owner.retain('literal',dict(raw=raw,originalClock=123))
            count=len(self.owner.stage.files);self.assertGreater(count,1)
            self.owner.native_record(dict(publication={}));self.owner.issue_publication({})
            self.owner.publication_phase({});self.owner.retire_stage();self.owner.delivered({})
        passive=ActorOriginals(self.store);self.assertEqual(raw,passive.last('literal',record=0)['raw'])
        self.assertGreater(passive.root['decodedSourceBytes'],len(raw))
        self.assertGreater(len(passive.root['chunks']),3)

    def test_compressed_originals_cannot_hide_decoded_live_copy_peak_budget(self):
        with self.lock.held():
            self.owner.begin();raw='original source '*400000
            self.owner.retain('first',dict(raw=raw));self.owner.retain('second',dict(raw=raw))
            stage=self.owner.stage;before=[path.read_bytes() for path in (stage.history._path(i) for i in range(len(stage.files)))]
            with self.assertRaises(NativeUIError):self.owner.native_record(dict(publication={}))
            self.assertTrue(self.owner.failed);self.assertEqual([],self.store.read()['chunks'])
            self.assertEqual(before,[stage.history._path(i).read_bytes() for i in range(len(stage.files))])
            self.assertIsNone(self.store.read()['pending']['native']);self.assertEqual([],stage.disk['retired'])

    def test_lost_real_manifest_unlink_reply_keeps_main_issued_and_blocks_slot_reuse(self):
        with self.lock.held():
            self.reading();self.owner.native_record(dict(publication={}))
            self.owner.issue_publication({});self.owner.publication_phase({});unlink=os.unlink
            def lost(name,*args,**kwargs):
                result=unlink(name,*args,**kwargs)
                if name==STAGE:raise OSError('Actual root unlink reply lost')
                return result
            with patch('adapters.pico4.lifecycle_actor_storage.os.unlink',side_effect=lost):
                with self.assertRaises(OSError):self.owner.retire_stage()
            self.assertEqual('issued',self.store.read()['pending']['manifestRemoval']['phase'])
            self.assertFalse((self.path/STAGE).exists());self.assertTrue(self.owner.failed)
            with self.assertRaises(NativeUIError):self.owner.begin()

    def test_historical_v1_codec_stays_readable_without_becoming_live_v2_owner(self):
        # Explicit synthetic codec fixture; no producer/process/effect verdict.
        old=PrivateFeatureState(self.path/'historical-v1.json');scope=deepcopy(self.scope);scope['picoLifecycleActorSourceVersion']=1
        value=dict(scope,phase='reading',chunks=[],bundles=[],records=[],pending=None,publication=None)
        old.write(value,None);history=ChatSourceChunks(old,scope)
        for original in ({'raw':'exact v1 source'},{'activations':[]}):
            reference,parts=source_bundles.prepare(original,len(value['bundles']),value['bundles'])
            for part in parts:
                previous=deepcopy(value);value['chunks']=history.append(part,value['chunks']);old.write(value,previous)
            previous=deepcopy(value);value['bundles'].append(reference);old.write(value,previous)
        previous=deepcopy(value);value['records']=[dict(originals=dict(source=0),phase=1,publication=dict(sequence=1))];old.write(value,previous)
        passive=ActorOriginals(old);self.assertEqual('exact v1 source',passive.last('source',record=0)['raw'])
        with self.lock.held():
            with self.assertRaises(NativeUIError):LifecycleActorStorage(old,scope,self.lock,lambda:True,lambda:None)

    def test_passive_v2_reader_refuses_another_records_valid_immutable_source_group(self):
        with self.lock.held():self.complete(1);self.complete(2)
        previous=self.store.read();changed=deepcopy(previous)
        changed['records'][0]['native']=previous['records'][1]['native']
        self.store.write(changed,previous)
        with self.assertRaises(NativeUIError):ActorOriginals(self.store).group(0)

    def test_stage2_counter_is_required_typed_and_stage1_historical_missing_means_zero(self):
        # Explicit empty historical codec DTOs; no physical/live ownership claim.
        value=dict(actorStagingVersion=1,sourceScopeSha256='d'*64,record=0,phase='reading',state='collecting',
            chunks=[],bundles=[],entries=[],transfer=None,retired=[],unlink=None)
        def encoded(value):
            raw=canonical(value)+b'\n';stamp=[1,1,0o100600,os.geteuid(),1,len(raw),1,1]
            return dict(actorStagingSnapshotVersion=1,root=snapshot_file(STAGE,raw,stamp),files=[])
        self.assertEqual([],decode_snapshot(encoded(value))[1])
        current=dict(value,actorStagingVersion=2,nestedDecodedBytes=0)
        self.assertEqual([],decode_snapshot(encoded(current))[1])
        for invalid in (None,True,-1,MAX_RAW):
            bad=deepcopy(current)
            if invalid is None:bad.pop('nestedDecodedBytes')
            else:bad['nestedDecodedBytes']=invalid
            with self.subTest(counter=invalid),self.assertRaises(NativeUIError):decode_snapshot(encoded(bad))

    def test_nested_decode_charge_is_durable_before_copy_and_part_of_actual_budget(self):
        with self.lock.held():
            self.reading();self.owner.reserve_nested(4096)
            self.assertEqual(4096,self.owner.stage.store.read()['nestedDecodedBytes'])
            self.owner.native_record(dict(publication={}));self.owner.issue_publication({})
            self.owner.publication_phase({});self.owner.retire_stage();self.owner.delivered({})
        original=ActorOriginals(self.store);root,_=decode_snapshot(original.group(0)['staging'])
        self.assertEqual(4096,root['nestedDecodedBytes']);self.assertGreater(original.root['decodedSourceBytes'],4096)

    def test_failed_nested_reservation_preserves_every_raw_before_any_interpretation(self):
        with self.lock.held():
            self.reading();stage=self.owner.stage;before=stage.store.read()
            with self.assertRaises(NativeUIError):self.owner.reserve_nested(MAX_RAW)
            self.assertEqual(before,stage.store.read());self.assertTrue(self.owner.failed)
            self.assertEqual(0,stage.store.read()['nestedDecodedBytes']);self.assertEqual(2,len(stage.files))


if __name__=='__main__':unittest.main()
