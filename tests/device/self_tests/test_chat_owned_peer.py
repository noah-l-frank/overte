"""Passive peer acquisition against one owned synthetic stdin Python worker.

Native SOURCE/build/script rows are explicit producer seams. The executable,
PID/start/boot, original environment/config, native-held inode and host files
are actual Linux originals. The separate Qt5 source test runs the C++ producer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from adapters.chat_actor_files import SOURCE,encode
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from fixture.owned_processes import OwnedProcesses

WORKER=r'''
import json,os,sys,time
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--e2eChatActorDir')+1])
value=dict(actorVersion=2,instance='b'*32,processId=os.getpid(),configuredEpochMs=int(time.time()*1000),scriptSha256='a'*64,
    build=dict(cleanConfiguredSource=True,compiledSourceRevision='c'*40))
fd=os.open(root/'chat-actor-source.v1.json',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
os.write(fd,(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode());os.fsync(fd)
print('ready',flush=True);sys.stdin.readline();os.close(fd)
'''


@unittest.skipUnless(sys.platform.startswith('linux'),'Actual Linux actor host contract')
class OwnedPeerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='overte-owned-chat-peer-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.actor=self.root/'actor';self.actor.mkdir(mode=0o700)
        self.state=self.root/'state';self.state.mkdir(mode=0o700);home=self.root/'config-home';home.mkdir(mode=0o700)
        environment=os.environ.copy();environment['XDG_CONFIG_HOME']=str(home);self.owner=OwnedProcesses(environment)
        self.peers=[]
        self.worker=subprocess.Popen([sys.executable,'-c',WORKER,'--testScript','--e2eChatActorDir',str(self.actor)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment)
        self.addCleanup(self.stop);self.assertEqual('ready',self.worker.stdout.readline().strip())
        self.config=PrivateFeatureState(self.root/'actor-config.json');self.store=PrivateFeatureState(self.state/'actor-files.json')
        self.config.write(dict(actorFilesVersion=1,directory=str(self.actor),expectedScriptSha256='a'*64,
            expectedExecutableSha256=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),
            ownerToken=self.owner.owner,configHome=self.owner.config_home),None)
        self.lock=ScriptSourceLock(self.state/'script-sources.lock')
    def stop(self):
        for peer in self.peers:peer.close_host()
        if self.worker.poll() is None:self.worker.stdin.write('close\n');self.worker.stdin.flush()
        self.worker.wait(timeout=3)
        for stream in (self.worker.stdin,self.worker.stdout,self.worker.stderr):stream.close()
    def acquire(self):
        peer=OwnedChatPeer(self.config,self.store,source_lock=self.lock);self.peers.append(peer);return peer
    def test_actual_static_binding_lock_and_original_process_source_ownership_without_command(self):
        peer=self.acquire();self.assertIs(self.lock,peer.lock);self.assertEqual('c'*40,peer.binding['sourceRevision'])
        self.assertEqual(self.config.read()['expectedExecutableSha256'],peer.binding['artifactSha256'])
        self.assertEqual(str(self.worker.pid),peer.binding['processIdentity'].split(':')[0]);self.assertEqual('b'*32,peer.binding['sessionId'])
        self.assertTrue(peer.guard());self.assertEqual({SOURCE},set(path.name for path in self.actor.iterdir()))
        original=self.store.path.read_bytes();reader=peer.reader();self.assertEqual(self.worker.pid,reader.pid)
        self.assertEqual(original,self.store.path.read_bytes());self.assertFalse((self.state/'chat-capture-owner.json').exists())
        peer.close_host();self.assertIsNone(self.worker.poll());self.assertEqual(original,self.store.path.read_bytes())
    def test_unknown_compiled_origin_and_foreign_config_owner_executable_script_are_not_adopted(self):
        original=self.config.read()
        for key,value in (('ownerToken','f'*64),('expectedExecutableSha256','f'*64),('expectedScriptSha256','f'*64)):
            changed={**original,key:value};self.config.write(changed,self.config.read())
            with self.assertRaises(NativeUIError):self.acquire()
            self.assertFalse(self.store.path.exists());self.assertIsNone(self.worker.poll())
        self.config.write(original,self.config.read())
        source=self.actor/SOURCE;raw=source.read_bytes();value=json.loads(raw)
        value['build']=dict(cleanConfiguredSource=False,compiledSourceRevision='');source.write_bytes(encode(value));source.chmod(0o600)
        with self.assertRaises(NativeUIError):self.acquire()
        self.assertFalse(self.store.path.exists())
    def test_original_config_inode_native_source_inode_and_binding_cannot_be_replaced(self):
        for changed in ('config','source','binding'):
            with self.subTest(changed=changed):
                h=OwnedPeerTests();h.setUp();self.addCleanup(h.doCleanups);peer=h.acquire()
                if changed=='binding':peer.binding['sourceRevision']='f'*40
                else:
                    path=h.config.path if changed=='config' else h.actor/SOURCE
                    raw=path.read_bytes();path.rename(path.with_name(path.name+'.original'));path.write_bytes(raw);path.chmod(0o600)
                with self.assertRaises((NativeUIError,OSError)):peer.guard()
                self.assertIsNotNone(h.store.read());self.assertIsNone(h.worker.poll())
    def test_actual_reader_cannot_publish_without_exact_original_peer_lock(self):
        peer=self.acquire();reader=peer.reader()
        with self.assertRaises((ValueError,RuntimeError)):reader.perform('d'*32,'inspect')
        self.assertEqual({SOURCE},set(path.name for path in self.actor.iterdir()));self.assertIsNone(self.store.read()['request'])
        with self.assertRaises(NativeUIError):
            OwnedChatPeer(self.config,PrivateFeatureState(self.state/'other-files.json'),source_lock=ScriptSourceLock(self.root/'script-sources.lock'))

    def test_recycled_original_executable_descriptor_is_foreign_and_never_closed_by_peer_detach(self):
        peer=self.acquire();process=peer.process;descriptor,anchor=process.fd,process.fd_owner.anchor
        self.assertIsNotNone(peer.files.fd_owner)
        os.close(descriptor);foreign=os.open(f'/proc/{self.worker.pid}/exe',os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(descriptor,foreign)
            with self.assertRaises(NativeUIError):peer.guard()
            peer.close_host();self.assertEqual(Path(f'/proc/{self.worker.pid}/exe').stat().st_ino,os.fstat(foreign).st_ino)
            self.assertIsNotNone(self.store.read());self.assertIsNone(self.worker.poll())
        finally:os.close(foreign);os.close(anchor)


if __name__=='__main__':unittest.main()
