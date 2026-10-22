"""Original native source/IPC and Linux FD identity; owned stdin worker only.

The configured revision macro is an explicit compiler input seam. Configure
helper tests independently establish real clean/dirty Git metadata. This is
not an Assignment Client build, domain, service or device qualification.
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
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.chat_actor_files import ChatActorFiles
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.chat_actor_process import LinuxChatActorProcess

HARNESS=r'''
#include "tests/device/native/ChatActorFiles.h"
#include <iostream>
#include <string>
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const auto args=app.arguments();
    overte::e2e::ChatActorFiles files(args.value(args.indexOf("--e2eChatActorDir")+1),QString(64,'a'),QString(32,'b'));
    if(!files.available())return 2;
    std::cout<<"ready"<<std::endl;std::string line;std::getline(std::cin,line);return 0;
}
'''


class NativeActorSourceTests(unittest.TestCase):
    def test_actual_compiled_known_and_unknown_identity_use_original_private_native_held_source(self):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        for known in (False,True):
            with self.subTest(known=known),tempfile.TemporaryDirectory(prefix='overte-chat-source-native-') as directory:
                root=Path(directory);unit=root/'test.cpp';unit.write_text(HARNESS);binary=root/'test';revision='c'*40
                definitions=['-DOVERTE_E2E_FEATURE_TESTS']
                if known:definitions.append('-DOVERTE_E2E_CONFIGURED_SOURCE_REVISION="'+revision+'"')
                compiled=subprocess.run(['c++','-std=c++17','-fPIC',*definitions,'-I'+str(ROOT),str(unit),'-o',str(binary),
                    '-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
                self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
                actor=root/'actor';actor.mkdir(mode=0o700)
                worker=subprocess.Popen([str(binary),'--testScript','--e2eChatActorDir',str(actor)],stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                process=transport=None
                try:
                    self.assertTrue(select.select([worker.stdout],[],[],3)[0]);self.assertEqual('ready',worker.stdout.readline().strip())
                    process=LinuxChatActorProcess(worker.pid,actor,hashlib.sha256(binary.read_bytes()).hexdigest(),
                        lambda pid:pid==worker.pid and worker.poll() is None)
                    binding=dict(scope='NATIVE_UI_COMPONENT_ONLY',processIdentity=process.process_identity,
                        sessionId='actual-native-source-worker',generation=0,targetFingerprint='e'*64)
                    transport=ChatActorFiles(actor,PrivateFeatureState(root/'files.json'),binding,'a'*64,
                        process.guard,process.released,component_only=True)
                    self.assertEqual(2,transport.source['actorVersion']);self.assertEqual(worker.pid,transport.source['processId'])
                    self.assertEqual(known,transport.source['build']['cleanConfiguredSource'])
                    if known:self.assertEqual(revision,transport.require_compiled_source())
                    else:
                        self.assertEqual('',transport.source['build']['compiledSourceRevision'])
                        with self.assertRaises(NativeUIError):transport.require_compiled_source()
                    original=(actor/'chat-actor-source.v1.json').read_bytes()
                    transport.source['build']['compiledSourceRevision']='f'*40
                    with self.assertRaises(NativeUIError):transport.require_compiled_source()
                    self.assertEqual(original,(actor/'chat-actor-source.v1.json').read_bytes())
                finally:
                    if transport is not None:transport.detach()
                    if process is not None:process.close()
                    if worker.poll() is None:worker.stdin.write('quit\n');worker.stdin.flush()
                    worker.wait(timeout=3)
                    for stream in (worker.stdin,worker.stdout,worker.stderr):stream.close()
                self.assertEqual(0,worker.returncode)


if __name__=='__main__':unittest.main()
