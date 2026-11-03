"""Real raw/O_APPEND/OFD/CAS boundaries, without devices or audio processes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import hashlib
import os
import random
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_raw_archive import AudioRawArchive,PART,MAX_LITERAL
from adapters.script_journey.lock import ScriptSourceLock


class AudioRawArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pico-audio-raw2-');self.temp._finalizer.detach();self.root=Path(self.temp.name)
        print('Retained original Audio raw journal:',self.root,flush=True)
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.cost=dict(parts=66,decodedBytes=0,storedBytes=0)
        self.raw=AudioRawArchive(self.root/'audio-recipe-pc-raw.json',dict(testVersion=1),self.lock,lambda:None,lambda:dict(self.cost),lambda:1.)
        self.addCleanup(self.raw.close_host)
    def acquire(self,value,limit=MAX_LITERAL):
        token=self.raw.reserve('pc',dict(action='unit-read'),limit);return self.raw.retain(token,value)
    def test_passive_unknown_index_version_cannot_qualify_a_sealed_literal(self):
        from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.observer_return import state
        from adapters.chat_journey.source_chunks import json_digest
        self.acquire(b'original',64)
        with self.lock.held():self.raw.seal_part()
        self.raw.close_host()
        store=self.raw.page_store(0);previous=store.read();value=dict(previous,audioRawRangeIndexVersion=2)
        store.write(value,previous);unused,raw,physical=state(store)
        root=PrivateFeatureState(self.raw.path);previous=root.read();value=__import__('copy').deepcopy(previous)
        value['state']['pages'][0].update(sha256=json_digest(store.read()),physical=physical)
        root.write(value,previous)
        reader=AudioPCRawOriginals.__new__(AudioPCRawOriginals)
        try:
            with self.assertRaises(NativeUIError):reader.__init__(root.path)
        finally:
            if hasattr(reader,'directory'):reader.close()
    def test_passive_literal_reference_cannot_alias_read_zero_with_boolean(self):
        from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
        reference=self.acquire(b'original',64)
        with self.lock.held():self.raw.seal_part()
        reader=AudioPCRawOriginals(self.raw.path);self.addCleanup(reader.close)
        self.assertEqual(b'original',reader.literal(reference))
        with self.assertRaises(NativeUIError):reader.literal(dict(reference,read=False))
    def test_incompressible_one_mib_and_native_quarter_mib_nul_exact_before_parser(self):
        rng=random.Random(773);noise=bytes(rng.randrange(256) for _ in range(MAX_LITERAL))
        first=self.acquire(noise);second=self.acquire('\0'*(256*1024),256*1024)
        self.assertEqual(noise,self.raw.literal(first));self.assertEqual('\0'*(256*1024),self.raw.literal(second))
        with self.lock.held():self.raw.seal_part()
        self.assertTrue(all(row['closed'] for row in self.raw.state['parts']));self.assertTrue(all(row['bytes']<=PART for row in self.raw.state['parts']))
        self.assertEqual(20,self.raw.bill()['parts']);self.assertFalse(self.raw.state['pending'])
    def test_multiple_literal_ranges_share_one_owned_part_and_distinct_clock_receipts(self):
        refs=[self.acquire(value,256) for value in ('first',None,'\0last',b'\xff\x00')]
        self.assertEqual(1,self.raw.bill()['parts']);self.assertEqual(4,self.raw.bill()['receipts'])
        self.assertEqual(['first',None,'\0last',b'\xff\x00'],[self.raw.literal(ref) for ref in refs])
        with self.lock.held():self.raw.seal_part()
        self.assertEqual('first',self.raw.literal(refs[0]))
    def test_cap_refuses_before_actual_getter_or_send(self):
        self.cost['parts']=512;calls=[]
        with self.assertRaises(NativeUIError):
            token=self.raw.reserve('pc',dict(action='get'),MAX_LITERAL);calls.append(True);self.raw.retain(token,b'data')
        self.assertEqual([],calls);self.assertEqual([],self.raw.state['pending'])
    def test_partial_append_retains_original_prefix_and_uncertain_tail_without_retry(self):
        first=self.acquire(b'original',32);token=self.raw.reserve('pc',dict(action='next'),32);write=os.write;calls=[]
        def partial(fd,data):
            if fd==self.raw.writer.fd:
                if calls:raise OSError('Actual interrupted append')
                calls.append(True);return write(fd,data[:3])
            return write(fd,data)
        with patch('adapters.pico4.audio_raw_archive.os.write',side_effect=partial),self.assertRaises(NativeUIError):self.raw.retain(token,b'pending')
        self.assertEqual(b'originalpen',self.raw.part_path(0).read_bytes());self.assertTrue(self.raw.state['pending'])
        with self.assertRaises(NativeUIError):self.raw.reserve('pc',dict(action='no-retry'),32)
    def test_foreign_prefix_write_during_actual_append_cannot_hide_behind_new_stamp(self):
        self.acquire(b'original',32);token=self.raw.reserve('pc',dict(action='next'),32);write=os.write;once=[]
        def foreign(fd,data):
            if fd==self.raw.writer.fd and not once:
                once.append(True);other=os.open(self.raw.part_path(0),os.O_WRONLY);os.pwrite(other,b'FOREIGN!',0);os.close(other)
            return write(fd,data)
        with patch('adapters.pico4.audio_raw_archive.os.write',side_effect=foreign),self.assertRaises(NativeUIError):self.raw.retain(token,b'next')
        self.assertTrue(self.raw.state['pending']);self.assertEqual(b'FOREIGN!next',self.raw.part_path(0).read_bytes())
    def test_lost_receipt_cas_retains_literal_and_pending_intent(self):
        token=self.raw.reserve('pc',dict(action='next'),32);original=self.raw.page_store
        def store(index):
            value=original(index);write=value.write
            def lost(body,before):write(body,before);raise OSError('Lost actual index CAS response')
            value.write=lost;return value
        with patch.object(self.raw,'page_store',side_effect=store),self.assertRaises(NativeUIError):self.raw.retain(token,b'retained')
        self.assertEqual(b'retained',self.raw.part_path(0).read_bytes());self.assertTrue(self.raw.state['pending']);self.assertTrue(original(0).path.exists())
        with self.assertRaises(NativeUIError):self.raw.reserve('pc',dict(action='no-retry'),32)
    def test_same_inode_recycled_writer_ofd_is_not_force_closed(self):
        self.acquire(b'original',32);writer=self.raw.writer;fd=writer.fd;other=os.open(self.raw.part_path(0),os.O_RDWR|os.O_APPEND)
        os.close(fd);os.dup2(other,fd);os.close(other)
        self.addCleanup(os.close,fd);self.addCleanup(os.close,writer.anchor)
        with self.assertRaises(NativeUIError):self.raw.reserve('pc',dict(action='no-getter'),32)
        self.assertFalse(self.raw.close_host());self.assertGreater(os.fstat(fd).st_ino,0)
    def test_replaced_inode_and_missing_root_refuse_without_getter(self):
        self.acquire(b'original',32);path=self.raw.part_path(0);replacement=path.with_name('replacement');replacement.write_bytes(path.read_bytes());os.replace(replacement,path)
        with self.assertRaises(NativeUIError):self.raw.reserve('pc',dict(action='no-getter'),32)
    def test_later_capacity_refusal_preserves_prior_issued_return_reservation(self):
        token=self.raw.reserve('pc',dict(action='already-issued'),256)
        self.cost['parts']=512
        with self.assertRaises(NativeUIError):self.raw.reserve('pc',dict(action='never-issued'),256)
        reference=self.raw.retain(token,b'already returned original')
        self.assertEqual(b'already returned original',self.raw.literal(reference))
        self.assertTrue(self.raw.stopped);self.assertFalse(self.raw.failed)
    def test_all_parallel_receipt_metadata_is_reserved_before_any_getter(self):
        command=dict(actualUnparsedCommand='x'*3000);tokens=[]
        for index in range(32):
            try:tokens.append(self.raw.reserve('pc',dict(command,index=index),32))
            except NativeUIError:break
        self.assertTrue(tokens);self.assertLess(len(tokens),32)
        self.assertTrue(self.raw.stopped);self.assertFalse(self.raw.failed)
        for token in tokens:
            reference=self.raw.retain(token,b'original')
            self.assertEqual(b'original',self.raw.literal(reference))
        self.assertFalse(self.raw.state['pending'])
        self.assertTrue(all(path.stat().st_size<=65536 for path in self.root.iterdir()))

    def test_late_own_root_loss_keeps_exact_unconfirmed_return_without_durable_claim(self):
        token=self.raw.reserve('pc',dict(action='already-issued'),256);literal=b'observed-before-own-root-loss'
        self.raw.store.path.unlink()
        with self.assertRaises(NativeUIError):self.raw.retain(token,literal)
        self.assertEqual(literal,self.raw.unconfirmed_returns[token['read']])
        self.assertTrue(self.raw.failed);self.assertFalse(self.raw.store.path.exists())
        # Private forensic copy only; this is not an accepted raw journal part.
        (self.root/'counter-unconfirmed-return.bin').write_bytes(literal)
        with self.assertRaises(NativeUIError):self.raw.reserve('pc',dict(action='no-new-read'),256)

    def test_actual_fork_cannot_append_original_parent_writer(self):
        self.acquire(b'original',32);pid=os.fork()
        if pid==0:
            try:self.raw.reserve('pc',dict(action='foreign-fork'),32)
            except BaseException:os._exit(0)
            os._exit(1)
        _,status=os.waitpid(pid,0);self.assertEqual(0,os.waitstatus_to_exitcode(status));self.assertEqual(b'original',self.raw.part_path(0).read_bytes())

if __name__=='__main__':unittest.main()
