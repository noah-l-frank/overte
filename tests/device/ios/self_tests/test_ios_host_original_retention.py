"""Real private directories, GC and child KeyboardInterrupt; no device/build."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from ios.self_tests.retained_host_roots import retain_owned_root


PROGRAM=r'''
import hashlib,json,os,signal,sys,tempfile
from pathlib import Path
from ios.self_tests.retained_host_roots import retain_owned_root
directory=tempfile.TemporaryDirectory(dir=sys.argv[1]);root=Path(directory.name)
retain_owned_root(directory,expected_root=root)
path=root/'original.bin';path.write_bytes(b'actual-original-before-interruption')
info=path.stat()
print(json.dumps(dict(root=str(root),device=info.st_dev,inode=info.st_ino,
 sha256=hashlib.sha256(path.read_bytes()).hexdigest())),flush=True)
os.kill(os.getpid(),signal.SIGINT)
'''


class HostOriginalRetentionTests(unittest.TestCase):
    def setUp(self):
        self.parent=tempfile.TemporaryDirectory();self.addCleanup(self.parent.cleanup)
        self.root=Path(self.parent.name)

    def test_real_cleanup_gc_and_repeated_retention_keep_original_path_inode_and_bytes(self):
        directory=tempfile.TemporaryDirectory(dir=self.root);root=Path(directory.name)
        self.assertEqual(root,retain_owned_root(directory,expected_root=root))
        path=root/'original.bin';path.write_bytes(b'original\x00\xff')
        original=(path.stat().st_dev,path.stat().st_ino,path.read_bytes())
        directory.cleanup();self.assertEqual(root,retain_owned_root(directory,expected_root=root))
        self.assertFalse(directory._finalizer.alive);del directory;gc.collect()
        self.assertEqual(original,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()))

    def test_real_child_sigint_and_interpreter_finalization_preserve_exact_original(self):
        child=subprocess.run([sys.executable,'-c',PROGRAM,str(self.root)],capture_output=True,text=True,timeout=10)
        self.assertIn(child.returncode,(-signal.SIGINT,130));self.assertIn('KeyboardInterrupt',child.stderr)
        original=json.loads(child.stdout);path=Path(original['root'])/'original.bin';info=path.stat()
        self.assertEqual(self.root,path.parent.parent)
        self.assertEqual((original['device'],original['inode']),(info.st_dev,info.st_ino))
        self.assertEqual(original['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_wrong_root_never_detaches_an_unrelated_live_finalizer(self):
        directory=tempfile.TemporaryDirectory(dir=self.root);root=Path(directory.name)
        with self.assertRaises(ValueError):retain_owned_root(directory,expected_root=self.root)
        self.assertTrue(directory._finalizer.alive);directory.cleanup();self.assertFalse(root.exists())

    def test_replaced_retained_root_is_refused_without_removing_original_bytes(self):
        directory=tempfile.TemporaryDirectory(dir=self.root);root=Path(directory.name)
        retain_owned_root(directory,expected_root=root);path=root/'original.bin';path.write_bytes(b'actual original')
        original=(path.stat().st_ino,path.read_bytes());moved=self.root/'moved-original-root';root.rename(moved);root.mkdir(mode=0o700)
        with self.assertRaises(ValueError):directory.cleanup()
        with self.assertRaises(ValueError):retain_owned_root(directory,expected_root=root)
        self.assertEqual(original,((moved/path.name).stat().st_ino,(moved/path.name).read_bytes()))


if __name__=='__main__':unittest.main()
