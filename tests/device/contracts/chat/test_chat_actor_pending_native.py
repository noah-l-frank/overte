"""Actual Qt5 cache/IPC headers, original Linux PID/FD and Python no-replay join.

This is an owned stdin test worker, not Overte/Assignment Client or a service.
NodeList, assigned script and networking are explicit constant input seams.
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
from adapters.chat_actor_files import ChatActorFiles
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.native_chat_observation import ChatCaptureOwner,NativeChatObservation,OwnedChatCapture
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from fixture.chat_actor_process import LinuxChatActorProcess

HARNESS=r'''
#include "tests/device/native/ChatActorFiles.h"
#include "tests/device/native/ChatObservation.h"
#include <iostream>
#include <QThread>
#include <string>
#include <cassert>
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const auto args=app.arguments();
    assert(args.contains("--testScript") && args.count("--e2eChatActorDir")==1);
    const auto root=args.value(args.indexOf("--e2eChatActorDir")+1);
    overte::e2e::ChatObservation observation;overte::e2e::ChatDomainSession domain;
    const QUuid self("11111111-1111-4111-8111-111111111111"),mixer("22222222-2222-4222-8222-222222222222");
    domain.changed(QUuid("33333333-3333-4333-8333-333333333333"),true,QThread::currentThread()==app.thread());
    overte::e2e::ChatActorFiles files(root,QString(64,'a'),observation.instance());assert(files.available());
    std::cout << "ready" << std::endl;std::string line;int opens=0,retires=0;
    while (std::getline(std::cin,line)) {
        if (line=="quit") { return 0; }
        if (line=="counts") { std::cout << opens << ' ' << retires << std::endl;continue; }
        assert(line=="tick");
        files.tick([&](const QVariantMap& request) {
            if(request.value("operation")=="observe")++opens;
            if(request.value("operation")=="retire")++retires;
            auto session=domain.snapshot(request.value("runId").toString());session.insert("mixerActive",true);
            return observation.request(request,self,mixer,session);
        });
        assert(files.available());std::cout << "tick" << std::endl;
    }
}
'''


class NativePendingTests(unittest.TestCase):
    def test_actual_cpp_pending_observe_and_retire_join_uses_original_inodes_and_no_resend(self):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        with tempfile.TemporaryDirectory(prefix='overte-chat-native-pending-') as directory:
            root=Path(directory);unit=root/'test.cpp';binary=root/'test';unit.write_text(HARNESS)
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
                str(unit),'-o',str(binary),'-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
            actor=root/'actor';actor.mkdir(mode=0o700)
            worker=subprocess.Popen([str(binary),'--testScript','--e2eChatActorDir',str(actor)],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            kernel=transport=None
            try:
                def receive():
                    self.assertTrue(select.select([worker.stdout],[],[],2)[0],'owned native worker response unavailable')
                    return worker.stdout.readline().strip()
                self.assertEqual('ready',receive())
                kernel=LinuxChatActorProcess(worker.pid,actor,hashlib.sha256(binary.read_bytes()).hexdigest(),
                    lambda pid:pid==worker.pid and worker.poll() is None)
                binding=dict(scope='NATIVE_UI_COMPONENT_ONLY',processIdentity=kernel.process_identity,sessionId='owned-native-header-worker',
                    generation=1,targetFingerprint='b'*64)
                def tick():
                    worker.stdin.write('tick\n');worker.stdin.flush();self.assertEqual('tick',receive())
                def wait(delay):tick();time.sleep(delay)
                transport=ChatActorFiles(actor,PrivateFeatureState(root/'files.json'),binding,'a'*64,kernel.guard,kernel.released,
                    component_only=True,sleep=wait)
                def reader():
                    def read():tick();return transport.read()
                    return NativeChatObservation(transport.send,read,transport.clock_ms,kernel.guard,worker.pid)
                run='d'*32;owner=ChatCaptureOwner(PrivateFeatureState(root/'capture.json'),binding,kernel.guard,component_only=True)
                owner.begin(run);owner.admit(reader().perform(run,'inspect'))
                lifetime=PrivateFeatureState(root/'lifetime.json');lock=ScriptSourceLock(root/'script-sources.lock')
                def flow():return ChatCacheLifetime(OwnedChatCapture(reader(),owner,run),lifetime,lock)
                original_write=transport.store.write
                def lose(operation):
                    def write(value,previous):
                        if value['pending'] is None and value['request'] is not None and value['request']['operation']==operation:
                            raise NativeUIError('Original native command published, manifest receipt unavailable')
                        return original_write(value,previous)
                    transport.store.write=write
                lose('observe')
                with self.assertRaises(NativeUIError):flow().activate()
                transport.store.write=original_write;tick();request=transport.store.read()['pending']
                opened=json.loads(transport.reconcile_pending(request));self.assertEqual(3,opened['chatVersion'])
                self.assertEqual(request['commandId'],opened['source']['openedCommandId'])
                current=flow();current.activate();lose('retire')
                with self.assertRaises(NativeUIError):current.retire()
                transport.store.write=original_write;tick();request=transport.store.read()['pending']
                retired=json.loads(transport.reconcile_pending(request));self.assertTrue(retired['source']['retired'])
                self.assertEqual(request['commandId'],retired['source']['retiredCommandId'])
                final=flow().retire();self.assertFalse(final['source']['scopePresent']);self.assertEqual([],final['source']['events'])
                worker.stdin.write('counts\n');worker.stdin.flush();self.assertEqual('1 1',receive())
                original_result=transport.store.read()['result']['stamp'];transport.close()
                self.assertTrue(kernel.released({key:original_result[key] for key in ('device','inode')}))
                self.assertIsNotNone(owner.store.read());self.assertEqual('retired',lifetime.read()['phase'])
            finally:
                if transport is not None:transport.detach()
                if kernel is not None:kernel.close()
                if worker.poll() is None:
                    worker.stdin.write('quit\n');worker.stdin.flush()
                    try:worker.wait(timeout=3)
                    except subprocess.TimeoutExpired:worker.kill();worker.wait(timeout=3)
                for stream in (worker.stdin,worker.stdout,worker.stderr):stream.close()


if __name__=='__main__':unittest.main()
