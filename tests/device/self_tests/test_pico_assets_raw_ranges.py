"""Layout2 over actual Parent journals/ranges/OFDs; Native/Qt remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_prefix import PicoAssetsPrefix
from adapters.pico4.assets_prefix_originals import AssetsPrefixOriginals
from adapters.pico4.assets_raw_archive import compact
from adapters.pico4.assets_raw_ranges import MAX_LITERAL,AUX,AssetsRawRanges
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.script_journey.history import canonical
from self_tests.pico_assets_prefix_fixture import AssetsPrefixModel
import test_normal_scripts as normal


class AssetsRawRangesTests(unittest.TestCase):
    def setUp(self):
        fixture=normal.PicoNormalScriptsTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        if getattr(self,'numeric_native_identity',False):
            fixture.native.identity='123:314159'
            active=patch.object(fixture.native,'require_process_identity',side_effect=lambda identity:self.assertEqual(fixture.native.identity,identity))
            active.start();self.addCleanup(active.stop)
        self.root=Path(tempfile.mkdtemp(prefix='pico-assets-raw-ranges-'));self.root.chmod(0o700)
        temporary=fixture.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        self.model=AssetsPrefixModel(self,self.root,fixture,manual_owner=False);m=self.model
        def build():
            return PicoAssetsPrefix(self.root/'ranges-parent.json',m.binding,m.phase,m.lock,m.mappings(),m.uploads(),
                lambda:json.dumps(m.snapshot()),m.controls,m.create_controls,m.cancel,m.guard,m.epoch,upload_factory=lambda _parent:None)
        if self._testMethodName=='test_initial_audio_cas_lost_keeps_original_owner_after_traceback_gc':
            import weakref
            from adapters.normal_feature_state import PrivateFeatureState
            from adapters.pico4.assets_raw_ranges import UNCONFIRMED
            write=PrivateFeatureState.write;self.ctor_lost_writes=[]
            def lost(store,value,previous):
                result=write(store,value,previous)
                if store.path.name.endswith('.child-raw2'):
                    self.ctor_lost_writes.append(str(store.path))
                    raise OSError('Actual initial Audio root CAS succeeded; original response lost')
                return result
            with patch.object(PrivateFeatureState,'write',new=lost):
                try:build()
                except NativeUIError:pass
                else:self.fail('The actual initial Audio CAS response must be lost')
            self.assertEqual(1,len(self.ctor_lost_writes))
            matches=[value for value in UNCONFIRMED if value.owner.store.path==self.root/'ranges-parent.json']
            self.assertEqual(1,len(matches));self.partial_ref=weakref.ref(matches[0])
            return
        if self._testMethodName=='test_actual_constructor_callbacks_pin_audio_before_save_and_bill_actual_files':
            self.ctor_bills=[];save=AudioRawArchive.save
            def initial(audio):
                owner=audio.identity.__self__
                def check():
                    self.assertIs(audio,owner.audio);self.assertIs(audio,owner.original_audio)
                    self.assertIs(audio,owner._original_audio);self.assertFalse(owner.audio_ctor_complete)
                    own=audio.bill();current=owner.owner.bill();actual=owner.other_bill()
                    self.assertIsNone(owner.owner.raw_archive)
                    self.assertEqual(current['frames']+own['files']-own['parts']+2,actual['parts'])
                    self.assertEqual(current['decodedBytes']+owner.overlay,actual['decodedBytes'])
                    self.assertEqual(current['storedBytes']+owner.overlay,actual['storedBytes'])
                    self.ctor_bills.append(dict(own=own,parent=current,other=actual))
                check();result=save(audio);check();return result
            with patch.object(AudioRawArchive,'save',new=initial):self.parent=build()
        else:self.parent=build()
        self.addCleanup(self.parent.raw_archive.close_host)
        self.assertIs(type(self.parent.raw_archive),AssetsRawRanges)
        print('Retained actual Parent/Layout2 originals:',self.root,flush=True)

    def acquire(self,raw,*,wire=False,command=None):
        p=self.parent;command=dict(commandId=uuid.uuid4().hex) if command is None else command
        p.raw_archive.reserve('mappings',command)
        ref=p.raw_archive.retain_wire(raw) if wire else p.raw_archive.retain_bytes(raw)
        index=p.raw_receipt(dict(role='mappings',rawOriginal=compact(ref)))
        return ref,index

    def passive(self,index,expected):
        reader=AssetsPrefixOriginals(self.parent.store.path)
        try:self.assertEqual(expected,reader.literal(index));reader.verify()
        finally:self.assertTrue(reader.close_host())

    def test_one_four_mib_wire_token_plus_lossless_aux_tail_and_passive_original(self):
        raw=b'\xff'*MAX_LITERAL+b'\x00\xff framing original'
        with self.parent.lock.held():
            ref,index=self.acquire(raw,wire=True)
            self.assertIsNotNone(ref['tailBundle']);self.assertEqual(1,self.parent.raw_archive.audio.state['reads'])
            self.assertEqual(raw,self.parent.literal(index));bill=self.parent.bill()
            self.assertLessEqual(bill['frames'],512);self.assertLessEqual(bill['decodedBytes'],16*1024*1024)
            self.assertEqual(MAX_LITERAL+len(b'\x00\xff framing original'),ref['bytes'])
        self.passive(index,raw)

    def test_100_small_literals_share_ranges_and_root_stays_below64k(self):
        refs=[]
        with self.parent.lock.held():
            for index in range(100):
                raw=(str(index)+': actual distinct original').encode();refs.append((raw,*self.acquire(raw)))
            self.assertLess(self.parent.store.path.stat().st_size,65536)
            self.assertLess(self.parent.raw_archive.bill()['parts'],10)
            for raw,ref,index in refs:self.assertEqual(raw,self.parent.literal(index))
        self.passive(refs[-1][2],refs[-1][0])

    def test_actual_constructor_callbacks_pin_audio_before_save_and_bill_actual_files(self):
        archive=self.parent.raw_archive
        self.assertIs(archive.audio,archive.original_audio)
        self.assertIs(archive.audio,archive._original_audio)
        self.assertTrue(archive.audio_ctor_complete);self.assertEqual(2,len(self.ctor_bills))
        self.assertGreater(self.ctor_bills[-1]['own']['metadataBytes'],0)
        (self.root/'actual-ctor-billing.json').write_text(json.dumps(self.ctor_bills,indent=2)+'\n')
        with self.parent.lock.held():
            ref,index=self.acquire(b'actual constructor-owned original')
            self.assertEqual(b'actual constructor-owned original',archive.literal(compact(ref)))

    def test_initial_audio_cas_lost_keeps_original_owner_after_traceback_gc(self):
        import gc,sys
        from adapters.pico4.assets_raw_ranges import UNCONFIRMED
        self.assertEqual((None,None,None),sys.exc_info());gc.collect()
        archive=self.partial_ref();self.assertIsNotNone(archive)
        self.assertIn(archive,UNCONFIRMED);self.assertTrue(archive.failed)
        self.assertFalse(archive.audio_ctor_complete)
        self.assertIs(archive.audio,archive.original_audio);self.assertIs(archive.audio,archive._original_audio)
        directory=archive.audio.directory;directory.require(directory.fd)
        self.assertTrue(archive.audio.path.exists());self.assertIsNone(archive.audio.disk)
        with patch.object(directory,'close',side_effect=AssertionError('Partial owner cannot claim directory closure')) as close:
            self.assertFalse(archive.close_host());close.assert_not_called()
        directory.require(directory.fd)
        self.assertFalse(self.model.calls);self.assertFalse(self.model.inputs)
        (self.root/'unresolved-audio-ctor-owner.json').write_text(json.dumps(dict(
            tracebackCleared=True,gcCompleted=True,strongUnconfirmedOwner=True,actualHostClosure=False,
            originalDirectoryFD=directory.fd,originalDirectoryAnchorFD=directory.anchor,
            actualRootCAS=self.ctor_lost_writes[0]),indent=2)+'\n')

    def test_distinct_actual_same_scope_archive_refused_without_foreign_read_or_close(self):
        p=self.parent;archive=p.raw_archive;original=archive.audio
        with p.lock.held():
            ref,index=self.acquire(b'unchanged original bytes')
            foreign=AudioRawArchive(self.root/'foreign-original-audio.json',original.scope,p.lock,
                p.archival_identity,lambda:dict(parts=0,decodedBytes=0,storedBytes=0),
                p.phases.monotonic,literal_limit=original.literal_limit)
            self.addCleanup(foreign.close_host)
            token=foreign.reserve('mappings',dict(counterOnly=True),64)
            foreign.retain(token,b'unchanged original bytes')
            self.assertEqual(original.scope,foreign.scope)
            self.assertNotEqual(original.path.stat().st_ino,foreign.path.stat().st_ino)
            archive.audio=foreign
            # Restore only for reliable test-owned host descriptor closure;
            # the failed source is never used for a later query or input.
            self.addCleanup(setattr,archive,'audio',original)
            with patch.object(foreign,'literal',side_effect=AssertionError('No foreign byte source')) as read, \
                 patch.object(foreign,'close_host',side_effect=AssertionError('No foreign closure')) as close:
                with self.assertRaises(NativeUIError):archive.literal(compact(ref))
                self.assertFalse(archive.close_host())
                read.assert_not_called();close.assert_not_called()
            original.directory.require(original.directory.fd)
            foreign.directory.require(foreign.directory.fd)
            self.assertTrue(archive.failed)
            from adapters.pico4.assets_raw_ranges import UNCONFIRMED
            self.assertIn(archive,UNCONFIRMED)
        self.assertFalse(self.model.inputs)

    def test_missing_admitted_holder_cannot_reenter_constructor_or_claim_host_closure(self):
        p=self.parent;archive=p.raw_archive;original=archive.audio
        with p.lock.held():
            ref,index=self.acquire(b'original survives missing public holder')
            archive.audio=None;self.addCleanup(setattr,archive,'audio',original)
            with self.assertRaises(NativeUIError):archive.literal(compact(ref))
            self.assertFalse(archive.close_host())
            original.directory.require(original.directory.fd)
            self.assertTrue(archive.failed)
        self.assertFalse(self.model.inputs)

    def test_changed_public_original_pin_refuses_before_original_data_read(self):
        p=self.parent;archive=p.raw_archive;original=archive.original_audio
        with p.lock.held():
            ref,index=self.acquire(b'original private pin')
            archive.original_audio=object();self.addCleanup(setattr,archive,'original_audio',original)
            with patch.object(original,'literal',side_effect=AssertionError('No source after changed pin')) as read:
                with self.assertRaises(NativeUIError):archive.literal(compact(ref))
                self.assertFalse(archive.close_host());read.assert_not_called()
            original.directory.require(original.directory.fd)

    def test_exact_reference_refuses_overridden_get_before_invoking_it(self):
        calls=[]
        class Foreign(dict):
            def get(self,*args):calls.append(True);return super().get(*args)
        with self.parent.lock.held():
            ref,index=self.acquire(b'actual reference original')
            with self.assertRaises(NativeUIError):self.parent.raw_archive.literal(Foreign(compact(ref)))
        self.assertFalse(calls)

    def test_actual_control_mutation_after_reference_refuses_before_data_read(self):
        import adapters.pico4.assets_raw_ranges as ranges
        p=self.parent;archive=p.raw_archive;validate=ranges.compact_reference;pread=os.pread
        changed=[];reads=[]
        with p.lock.held():
            ref,index=self.acquire(b'actual original before control mutation')
            def injected(value):
                result=validate(value)
                if not changed:
                    path=archive.audio.path;path.write_bytes(path.read_bytes()+b' ');changed.append(True)
                return result
            def read(fd,*args):
                if changed and fd==archive.audio.writer.fd:reads.append(True)
                return pread(fd,*args)
            with patch.object(ranges,'compact_reference',side_effect=injected),patch.object(os,'pread',side_effect=read):
                with self.assertRaises(NativeUIError):archive.literal(compact(ref))
        self.assertTrue(changed);self.assertFalse(reads)

    def test_recycled_same_inode_literal_writer_never_reads_or_closes_foreign_fd(self):
        from adapters.pico4.assets_raw_ranges import UNCONFIRMED
        p=self.parent;archive=p.raw_archive;reads=[];pread=os.pread
        with p.lock.held():
            ref,index=self.acquire(b'original paired writer')
            writer=archive.audio.writer;fd=writer.fd
            foreign=os.open(archive.audio.part_path(0),os.O_RDWR|os.O_APPEND)
            os.close(fd);os.dup2(foreign,fd);os.close(foreign)
            before=os.fstat(fd)
            def read(current,*args):
                if current==fd:reads.append(True)
                return pread(current,*args)
            with patch.object(os,'pread',side_effect=read):
                with self.assertRaises(NativeUIError):archive.literal(compact(ref))
            self.assertFalse(reads);self.assertFalse(archive.close_host())
            after=os.fstat(fd)
            self.assertEqual((before.st_dev,before.st_ino),(after.st_dev,after.st_ino))
            self.assertTrue(archive.failed);self.assertIn(archive,UNCONFIRMED)
            # No uncertain half is closed or reassigned by test cleanup. Both
            # stay strongly held until this actual owning host exits.
            (self.root/'unresolved-literal-writer-fds.json').write_text(json.dumps(dict(
                actualHostClosure=False,retainedUntilHostExit=True,
                uncertainFD=fd,originalAnchorFD=writer.anchor),indent=2)+'\n')

    def test_large_original_command_archived_once_and_short_reference_reservation(self):
        p=self.parent;command=dict(commandId='a'*32,actualPayload='x'*37000)
        with p.lock.held():
            ref=p.command_reference(command)
            p.state['pendingSource']=dict(role='files',command=ref,raw=[])
            before=len(p.state['bundles']);p.raw_archive.reserve('files',command)
            self.assertEqual(before,len(p.state['bundles']))
            self.assertEqual(command,p.command_original(p.disk['pendingSource']['command']))
            self.assertLess(len(canonical(p.raw_archive.active['rangeToken']['command'])),4096)
            self.assertLess(p.store.path.stat().st_size,65536)
            raw=b'actual retained reply';literal=p.raw_archive.retain_bytes(raw)
            index=p.raw_receipt(dict(role='files',rawOriginal=compact(literal)),p.state['pendingSource']['raw'])
            self.assertEqual(raw,p.literal(index));self.assertEqual(before,len(p.state['bundles']))

    def test_actual_existing_four_mib_blocks_next_getter_under_same_global_bill(self):
        p=self.parent;calls=[]
        with p.lock.held():
            ref,index=self.acquire(b'a'*MAX_LITERAL)
            with self.assertRaises(NativeUIError):
                p.raw_archive.reserve('mappings',dict(commandId='b'*32))
                calls.append('must not acquire')
            self.assertFalse(calls);self.assertEqual(b'a'*MAX_LITERAL,p.literal(index))
            self.assertEqual(1,p.raw_archive.audio.state['reads'])
        self.passive(index,b'a'*MAX_LITERAL)

    def test_malformed_large_json_is_retained_before_unchanged_parser_budget_refusal(self):
        p=self.parent;raw=b'\x00'*MAX_LITERAL
        with p.lock.held():
            ref,index=self.acquire(raw)
            with self.assertRaises(NativeUIError):p.raw_archive.parser_capacity(raw.decode(),dict(commandId='a'*32))
            self.assertEqual(raw,p.literal(index));self.assertEqual(hashlib.sha256(raw).hexdigest(),ref['sha256'])
        self.passive(index,raw)

    def test_same_bytes_replaced_range_inode_refuses_actual_physical_original(self):
        p=self.parent
        with p.lock.held():
            ref,index=self.acquire(b'actual immutable original')
            path=p.raw_archive.audio.part_path(0);replacement=path.with_suffix('.replacement')
            replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
            with self.assertRaises(NativeUIError):p.literal(index)

    def test_failed_parent_cas_keeps_already_acquired_bytes_and_original_range_receipt(self):
        p=self.parent;raw=b'\xff acquired before failed root CAS'
        with p.lock.held():
            p.raw_archive.reserve('mappings',dict(commandId='a'*32));ref=p.raw_archive.retain_bytes(raw)
            with patch.object(p.store,'write',side_effect=NativeUIError('declared uncertain Parent CAS')):
                with self.assertRaises(NativeUIError):p.raw_receipt(dict(role='mappings',rawOriginal=compact(ref)))
            self.assertEqual(raw,p.raw_archive.unconfirmed)
            self.assertEqual(raw,p.raw_archive.audio.literal(ref['rangeOriginal']))
            self.assertIsNotNone(p.disk['pendingRawRead'])
        reader=AssetsPrefixOriginals(p.store.path)
        try:self.assertIsNotNone(reader.pending_read()['owningPending'])
        finally:self.assertTrue(reader.close_host())

    def test_original_final_window_stays_outside_script_lock_and_reads_same_bytes(self):
        p=self.parent
        with p.lock.held():ref,index=self.acquire(b'actual final original')
        with patch.object(p.lock,'held',side_effect=AssertionError('No final SourceLock reacquire')):
            p.raw_archive.verify(held=False)
        self.assertFalse(p.raw_archive.final_windows);self.assertEqual(0,p.raw_archive.final_overlay)
        with p.lock.held():self.assertEqual(b'actual final original',p.literal(index))

    def test_recycled_original_writer_refuses_final_before_any_new_readonly_window(self):
        p=self.parent
        with p.lock.held():self.acquire(b'actual original writer bytes')
        writer=p.raw_archive.audio.writer;descriptor=writer.fd;path=p.raw_archive.audio.part_path(0)
        os.close(descriptor);foreign=os.open(path,os.O_RDWR|os.O_APPEND|os.O_NOFOLLOW|os.O_CLOEXEC)
        if foreign!=descriptor:os.dup2(foreign,descriptor);os.close(foreign);foreign=descriptor
        calls=[]
        from adapters.chat_journey.archive_file import ClosedOriginalFile
        constructor=ClosedOriginalFile.__init__
        def observed(source,*args,**kwargs):calls.append('new original window');constructor(source,*args,**kwargs)
        try:
            with patch.object(ClosedOriginalFile,'__init__',observed),self.assertRaises(NativeUIError):
                p.raw_archive.verify(held=False)
            self.assertFalse(calls);self.assertFalse(p.raw_archive.close_host())
            self.assertEqual(writer.node,(os.fstat(foreign).st_dev,os.fstat(foreign).st_ino))
            self.assertTrue(p.raw_archive.failed)
            from adapters.pico4.assets_raw_ranges import UNCONFIRMED
            self.assertIn(p.raw_archive,UNCONFIRMED)
        finally:os.close(foreign)

    def test_final_fixed_callback_change_refused_before_new_readonly_window(self):
        p=self.parent
        with p.lock.held():self.acquire(b'actual fixed source identity')
        original=p.raw_archive.audio.clock;called=[]
        p.raw_archive.audio.clock=lambda:called.append('foreign clock')
        try:
            with self.assertRaises(NativeUIError):p.raw_archive.verify(held=False)
            self.assertFalse(called);self.assertFalse(p.raw_archive.final_windows)
        finally:p.raw_archive.audio.clock=original

    def test_passive_layout2_control_boolean_count_refused_before_any_data_reader(self):
        p=self.parent
        with p.lock.held():self.acquire(b'actual control original')
        path=p.raw_archive.audio.path;value=json.loads(path.read_bytes());value['state']['reads']=True
        path.write_bytes(canonical(value)+b'\n');path.chmod(0o600)
        with patch('adapters.pico4.assets_range_originals.AudioPCRawOriginals.__init__',side_effect=AssertionError('No data reader admission')) as data:
            with self.assertRaises(NativeUIError):AssetsPrefixOriginals(p.store.path)
        data.assert_not_called()

    def test_passive_layout2_index_extra_fields_refused_with_originals_retained(self):
        p=self.parent
        with p.lock.held():self.acquire(b'actual index original')
        path=p.raw_archive.audio.page_store(0).path;value=json.loads(path.read_bytes())
        value['receipts'][0]['foreignField']='not the closed receipt grammar'
        path.write_bytes(canonical(value)+b'\n');path.chmod(0o600)
        with self.assertRaises(NativeUIError):AssetsPrefixOriginals(p.store.path)
        from adapters.pico4.assets_range_originals import UNRESOLVED
        self.assertTrue(UNRESOLVED);self.assertIsNotNone(UNRESOLVED[-1].raw)
        self.assertTrue(UNRESOLVED[-1].close())

    def test_unknown_range_namespace_refuses_before_next_reservation(self):
        p=self.parent
        with p.lock.held():
            self.acquire(b'original');path=p.raw_archive.audio.path.with_name(p.raw_archive.audio.path.name+'.foreign')
            path.write_bytes(b'unknown');path.chmod(0o600)
            with self.assertRaises(NativeUIError):p.raw_archive.reserve('mappings',dict(commandId='b'*32))
            self.assertEqual(b'unknown',path.read_bytes())


    def index_original(self,count=1):
        with self.parent.lock.held():
            for ordinal in range(count):self.acquire(('actual-original-'+str(ordinal)).encode())
        return self.parent.raw_archive,self.parent.raw_archive.audio
    def test_actual_two_page_final_windows_preserve_every_original_byte(self):
        archive,a=self.index_original(40);self.assertEqual(2,len(a.page_bodies))
        before={i:body for i,body in a.page_bodies.items()}
        archive.verify_final();self.assertEqual([],archive.final_windows)
        for i,body in before.items():
            self.assertIs(body,a.page_bodies[i]);self.assertEqual(body+b'\n',a.page_store(i).path.read_bytes())
            self.assertIs(a.page_pins[i][0],a.pages[i])
        self.assertFalse(archive.failed);self.assertFalse(self.model.inputs)
    def test_actual_boolean_alias_in_live_index_refuses_final(self):
        archive,a=self.index_original();body=a.page_bodies[0]
        a.pages[0]['receipts'][0]['read']=False
        with self.assertRaises(NativeUIError):archive.verify_final()
        self.assertTrue(archive.failed);self.assertIs(body,a.page_bodies[0])
        self.assertEqual(body+b'\n',a.page_store(0).path.read_bytes());self.assertFalse(self.model.inputs)
    def test_changed_both_cache_and_live_index_cannot_replace_actual_file(self):
        archive,a=self.index_original();original=a.page_store(0).path.read_bytes()
        a.pages[0]['receipts'][0]['read']=1
        a.page_bodies[0]=canonical(a.pages[0])
        with self.assertRaises(NativeUIError):archive.verify_final()
        self.assertTrue(archive.failed);self.assertTrue(archive.final_windows)
        self.assertEqual(original,a.page_store(0).path.read_bytes());self.assertFalse(self.model.inputs)
    def test_actual_same_byte_new_index_inode_refuses_original_identity(self):
        archive,a=self.index_original();path=a.page_store(0).path;body=path.read_bytes();stamp=path.stat()
        replacement=path.with_name(path.name+'.owned-replacement')
        replacement.write_bytes(body);replacement.chmod(0o600);os.replace(replacement,path)
        self.assertNotEqual(stamp.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):archive.verify_final()
        self.assertTrue(archive.failed);self.assertTrue(archive.final_windows)
        self.assertEqual(body,path.read_bytes());self.assertFalse(self.model.inputs)

if __name__=='__main__':unittest.main()
