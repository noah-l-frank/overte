"""Actual large inventory bytes, durable partials and immutable carrier checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_process_inventory import TabletWebProcessInventory
from self_tests.test_completed_frame_lease import BINDING,RUN


class TabletProcessInventoryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.binding=dict(BINDING,processIdentity='42');self.owner=self.make()
    def make(self,**kwargs):return TabletWebProcessInventory(self.root,self.binding,RUN,self.lock,lambda:True,monotonic=lambda:0.,**kwargs)
    def inventory(self):return {str(self.root):{name:list(value) for name,value in EmoteOriginalLease(self.root,self.owner.paths()).rows.items()}}
    def test_actual_large_original_tree_exceeding_old_journal_fits_multiple_unchanged_bounded_frames(self):
        for _ in range(1800):(self.root/secrets.token_hex(120)).touch(mode=0o600,exist_ok=False)
        value=self.inventory()
        with self.assertRaises(NativeUIError):pack([dict(inventories=value)])
        reference=self.owner.write(value);self.assertGreaterEqual(len(self.owner.state['chunks']),2)
        self.assertEqual(value,self.make(historical=True).read(reference))
        self.assertLess(len(pack([dict(inventories=reference)])['data']),48*1024)
        self.assertTrue(all(self.owner.frames.path(ref).stat().st_size<=1024*1024 for ref in self.owner.state['chunks']))
        original={path:(path.stat(),path.read_bytes()) for path in self.owner.paths()}
        self.assertEqual(reference,self.owner.write(value))
        self.assertEqual(original,{path:(path.stat(),path.read_bytes()) for path in self.owner.paths()})
        lease=object.__new__(EmoteOriginalLease);lease.root=self.root;lease.mutable=set(self.owner.paths())
        lease.rows={key:tuple(row) for key,row in value[str(self.root)].items()};lease.guard()
    def test_actual_lost_saved_intent_recovers_opened_complete_bytes_without_phase_inode_or_byte_rewrite(self):
        value=self.inventory();intent=self.owner.frames.intent
        def lose(kind,ref):
            if ref['phase']=='saved':raise OSError('Actual saved-intent return lost after complete file flush')
            return intent(kind,ref)
        self.owner.frames.intent=lose
        with self.assertRaises(OSError):self.owner.write(value)
        rebuilt=self.make();self.assertFalse(rebuilt.state['complete']);self.assertEqual('opened',rebuilt.state['chunks'][0]['phase'])
        path=rebuilt.frames.path(rebuilt.state['chunks'][0]);before=path.stat();raw=path.read_bytes()
        reference=rebuilt.recover();self.assertEqual('opened',rebuilt.state['chunks'][0]['phase'])
        self.assertEqual(before,path.stat());self.assertEqual(raw,path.read_bytes());self.assertEqual(value,rebuilt.read(reference))
    def test_actual_empty_opened_file_stays_owned_and_cannot_be_replayed_or_qualified(self):
        value=self.inventory();intent=self.owner.frames.intent
        def lose(kind,ref):
            answer=intent(kind,ref)
            if ref['phase']=='opened':raise OSError('Actual interruption before the first frame byte')
            return answer
        self.owner.frames.intent=lose
        with self.assertRaises(OSError):self.owner.write(value)
        rebuilt=self.make();ref=rebuilt.state['chunks'][0];path=rebuilt.frames.path(ref);before=path.stat()
        self.assertEqual(0,before.st_size)
        for action in (rebuilt.recover,lambda:rebuilt.write(value)):
            with self.assertRaises(NativeUIError):action()
        self.assertEqual(before,path.stat());self.assertEqual(b'',path.read_bytes());self.assertFalse(self.make().state['complete'])
    def test_same_inode_rewrite_restoring_mtime_and_hardlink_cannot_mutate_an_admitted_inventory(self):
        reference=self.owner.write(self.inventory());path=self.owner.frames.path(self.owner.state['chunks'][0])
        before=path.stat();raw=path.read_bytes();path.write_bytes(raw);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(NativeUIError):self.owner.read(reference)
        current=self.owner.reference();os.link(path,self.root/'actual-unowned-hardlink')
        with self.assertRaises(NativeUIError):self.owner.read(current)
    def test_foreign_binding_and_historical_mutation_do_not_change_original_owner(self):
        value=self.inventory();reference=self.owner.write(value);before={p:p.read_bytes() for p in self.owner.paths()}
        self.binding['processIdentity']='43'
        with self.assertRaises(NativeUIError):self.make(historical=True)
        self.binding['processIdentity']='42';history=self.make(historical=True)
        for action in (history.recover,lambda:history.write(value)):
            with self.assertRaises(NativeUIError):action()
        self.assertEqual(value,history.read(reference));self.assertEqual(before,{p:p.read_bytes() for p in self.owner.paths()})


if __name__=='__main__':unittest.main()
