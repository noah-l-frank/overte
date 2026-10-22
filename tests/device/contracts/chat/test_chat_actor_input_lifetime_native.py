"""Original Qt5 actor input lifetime -> Linux FD inventory -> Python validator.

Owned stdin worker only; Avatar, NodeList and assigned-script inputs are seams.
No Assignment Client, product service, device or network is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_chat_actor_pending_native import HARNESS as ORIGINAL
from adapters.chat_actor_files import ChatActorFiles
from adapters.chat_peer_input import ChatPeerInput,COMMAND,RECEIPT
from adapters.chat_journey.peer_input_close import ChatPeerInputClose
from adapters.script_journey.lock import ScriptSourceLock
from adapters.native_chat_observation import NativeChatObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.chat_actor_process import LinuxChatActorProcess

HARNESS=ORIGINAL.replace('#include <iostream>','#include <iostream>\n#include <thread>')
HARNESS=HARNESS.replace('observation.instance());assert(files.available());','''observation.instance(),[&] {
        return QVariantMap{{"sessionId",self},{"position",QVariantMap{{"x",2.0},{"y",0.0},{"z",2.0}}}};
    });assert(files.available());''')
HARNESS=HARNESS.replace('        assert(line=="tick");','''        if (line=="poll") { files.takeInput();std::cout << "poll" << std::endl;continue; }
        if (line=="foreignpoll") {
            std::thread foreign([&] { assert(!files.available());assert(files.takeInput().isEmpty());
                files.tick([](const QVariantMap&) { assert(false);return QVariantMap(); }); });
            foreign.join();assert(files.available());std::cout << "foreignpoll" << std::endl;continue;
        }
        assert(line=="tick");''')


class NativeInputLifetimeTests(unittest.TestCase):
    def test_original_release_unlink_native_fd_absence_and_late_poll_remain_observable(self):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        with tempfile.TemporaryDirectory(prefix='overte-chat-native-input-life-') as scratch:
            root=Path(scratch);unit=root/'test.cpp';binary=root/'test';unit.write_text(HARNESS)
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
                str(unit),'-o',str(binary),'-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
            actor=root/'actor';actor.mkdir(mode=0o700)
            worker=subprocess.Popen([str(binary),'--testScript','--e2eChatActorDir',str(actor)],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            kernel=transport=None
            try:
                def receive():
                    self.assertTrue(select.select([worker.stdout],[],[],2)[0],'original native worker unavailable')
                    return worker.stdout.readline().strip()
                self.assertEqual('ready',receive())
                def issue(operation):
                    worker.stdin.write(operation+'\n');worker.stdin.flush();self.assertEqual(operation,receive())
                kernel=LinuxChatActorProcess(worker.pid,actor,hashlib.sha256(binary.read_bytes()).hexdigest(),
                    lambda pid:pid==worker.pid and worker.poll() is None)
                binding=dict(scope='NATIVE_UI_COMPONENT_ONLY',processIdentity=kernel.process_identity,
                    sessionId='owned-native-input-worker',generation=1,targetFingerprint='b'*64)
                transport=ChatActorFiles(actor,PrivateFeatureState(root/'files.json'),binding,'a'*64,kernel.guard,kernel.released,
                    component_only=True,sleep=lambda delay:(issue('poll'),time.sleep(delay)))
                def read():issue('tick');return transport.read()
                reader=NativeChatObservation(transport.send,read,transport.clock_ms,kernel.guard,worker.pid)
                run='d'*32
                def capture():
                    frame=reader.perform(run,'inspect');request=transport.store.read()['request']
                    value=transport.read_input_lifetime(request)
                    original=json.loads(transport.last_input_lifetime_raw)
                    self.assertEqual(frame,original['native']);self.assertEqual(value,original['inputLifetime'])
                    return value
                baseline=capture();self.assertEqual('',baseline['ownerRunId']);self.assertEqual(0,baseline['sequence'])
                self.assertFalse(baseline['releaseConsumed']);self.assertFalse(baseline['receiptHandle']['open'])
                owner=ChatPeerInput(transport,PrivateFeatureState(root/'inputs.json'),run)
                released=owner.issue('release');self.assertTrue(released['releaseConsumed'])
                actual=capture();self.assertTrue(actual['releaseConsumed']);self.assertEqual(run,actual['ownerRunId'])
                self.assertEqual(released['instance'],actual['instance']);self.assertEqual(1,actual['sequence'])
                self.assertEqual(released['scriptPolls'],actual['scriptPolls'])
                original_node=actual['receiptHandle']['node'];self.assertFalse(kernel.released(original_node))
                self.assertTrue(actual['command']['present']);self.assertTrue(actual['receipt']['present'])
                close=ChatPeerInputClose(owner,reader,PrivateFeatureState(root/'input-close.json'),
                    ScriptSourceLock(root/'script-sources.lock'))
                try:closed=close.run()
                except NativeUIError as error:
                    cause=error
                    while cause.__context__ is not None:cause=cause.__context__
                    raise AssertionError('Actual original native input closure failed') from cause
                self.assertEqual('complete',closed['phase'])
                self.assertTrue(any(row['stage']=='before' for row in close.frames))
                self.assertTrue(any(row['stage']=='after' for row in close.frames))
                with self.assertRaises(NativeUIError):owner.issue('inspect')
                after=capture();self.assertFalse(after['command']['present']);self.assertFalse(after['receipt']['present'])
                self.assertFalse(after['receiptHandle']['open']);self.assertEqual({},after['receiptHandle']['node'])
                self.assertTrue(kernel.released(original_node));self.assertEqual(actual['scriptPolls'],after['scriptPolls'])
                issue('foreignpoll');foreign=capture();self.assertEqual(after['scriptPolls'],foreign['scriptPolls'])
                issue('poll');late=capture();self.assertEqual(after['scriptPolls']+1,late['scriptPolls'])
                self.assertFalse((actor/COMMAND).exists());self.assertFalse((actor/RECEIPT).exists())
                # Wrong original query cannot acquire the current resource source.
                request=transport.store.read()['request'];request['commandId']='f'*32
                with self.assertRaises(NativeUIError):transport.read_input_lifetime(request)
                self.assertIsNotNone(owner.store.read())
            finally:
                if transport is not None:transport.detach()
                if kernel is not None:kernel.close()
                if worker.poll() is None:
                    worker.stdin.write('quit\n');worker.stdin.flush()
                    try:worker.wait(timeout=3)
                    except subprocess.TimeoutExpired:worker.kill();worker.wait(timeout=3)
                for stream in (worker.stdin,worker.stdout,worker.stderr):stream.close()


if __name__=='__main__':unittest.main()
