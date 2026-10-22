"""Compile/execute the original private actor IPC against real Qt5/POSIX."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
HARNESS = r'''
#include "tests/device/native/ChatActorFiles.h"
#include <QTemporaryDir>
#include <cassert>
using overte::e2e::ChatActorFiles;
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir directory;assert(directory.isValid());
    assert(::chmod(QFile::encodeName(directory.path()).constData(),0700)==0);
    ChatActorFiles files(directory.path(),QString(64,'a'),QString(32,'b'),[] {
        return QVariantMap{{"sessionId",QUuid("11111111-1111-4111-8111-111111111111")},
            {"position",QVariantMap{{"x",2.0},{"y",0.0},{"z",2.0}}}};
    });assert(files.available());
    auto write=[&](QJsonObject value) {
        QFile command(directory.path()+"/chat-peer-input.v1.json");assert(command.open(QIODevice::WriteOnly|QIODevice::Truncate));
        assert(command.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner));
        const auto bytes=QJsonDocument(value).toJson(QJsonDocument::Compact)+'\n';assert(command.write(bytes)==bytes.size());command.close();
    };
    QJsonObject hold{{"schemaVersion",1},{"commandId",QString(32,'c')},{"runId",QString(32,'d')},{"operation","hold"},
        {"position",QJsonObject{{"x",40.0},{"y",0.0},{"z",2.0}}}};
    write(hold);assert(files.takeInput()==hold.toVariantMap());assert(files.takeInput().isEmpty());
    QFile receipt(directory.path()+"/chat-peer-input-receipt.v1.json");assert(receipt.open(QIODevice::ReadOnly));
    auto original=QJsonDocument::fromJson(receipt.readAll()).object();receipt.close();
    assert(original.value("native").toObject().value("operation")=="hold");
    assert(original.value("native").toObject().value("sequence")==1);
    assert(original.value("native").toObject().value("peerInputVersion")==2);
    assert(original.value("native").toObject().value("avatarPosition").toObject().value("x")==2.0); // Actual provider, never requested 40.
    QJsonObject send{{"schemaVersion",1},{"commandId",QString(32,'e')},{"runId",QString(32,'d')},{"operation","send"},
        {"channel","domain"},{"textKey","reply"}};
    auto bad=send;bad.insert("textKey","private body");write(bad);assert(files.takeInput().isEmpty());
    bad=send;bad.insert("expected",true);write(bad);assert(files.takeInput().isEmpty());
    write(send);assert(files.takeInput()==send.toVariantMap());
    write(hold);assert(files.takeInput().isEmpty()); // Non-adjacent replay remains refused.
    QJsonObject restore{{"schemaVersion",1},{"commandId",QString(32,'f')},{"runId",QString(32,'d')},{"operation","restore"}};
    write(restore);assert(files.takeInput()==restore.toVariantMap());
    QJsonObject release{{"schemaVersion",1},{"commandId",QString(32,'1')},{"runId",QString(32,'d')},{"operation","release"}};
    write(release);assert(files.takeInput()==release.toVariantMap());
    send.insert("commandId",QString(32,'2'));write(send);assert(files.takeInput().isEmpty());
    assert(QFile::remove(directory.path()+"/chat-peer-input-receipt.v1.json"));
    files.tick([](const QVariantMap&){return QVariantMap();});assert(files.available());
    overte::e2e::ChatPeerPosition positions;
    const QUuid self("11111111-1111-4111-8111-111111111111"),peer("22222222-2222-4222-8222-222222222222");
    const QString run(32,'a');
    QVariantMap query{{"schemaVersion",1},{"commandId",QString(32,'4')},{"runId",run},
        {"action","feature-chat-peer-position"},{"peerSha256",overte::e2e::ChatPeerPosition::identity(run,peer)}};
    const QVariantMap primary{{"x",0.0},{"y",0.0},{"z",0.0}},remote{{"x",40.0},{"y",0.0},{"z",2.0}};
    const auto measured=positions.request(query,self,primary,peer,remote);
    assert(!measured.isEmpty() && measured.value("source").toMap().value("peerPosition").toMap()==remote);
    assert(positions.request(query,self,primary,peer,remote).isEmpty());
    query.insert("commandId",QString(32,'5'));query.insert("peerSha256",QString(64,'f'));
    assert(positions.request(query,self,primary,peer,remote).isEmpty());
    query.insert("position",remote);assert(!overte::e2e::ChatPeerPosition::command(query));
    auto badPoint=remote;badPoint.insert("x",true);assert(!overte::e2e::ChatPeerPosition::position(badPoint));
}
'''


class PeerInputNativeTests(unittest.TestCase):
    def test_original_private_actor_once_only_input_and_release(self):
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt5Core'], text=True))
        library = subprocess.check_output(['pkg-config', '--variable=libdir', 'Qt5Core'], text=True).strip()
        with tempfile.TemporaryDirectory(prefix='overte-chat-peer-native-') as scratch:
            unit = Path(scratch) / 'test.cpp'; binary = Path(scratch) / 'test'; unit.write_text(HARNESS)
            compiled = subprocess.run(['c++', '-std=c++17', '-fPIC', '-DOVERTE_E2E_FEATURE_TESTS',
                '-I' + str(ROOT), str(unit), '-o', str(binary), '-L' + library, '-Wl,-rpath,' + library, *flags],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(0, compiled.returncode, compiled.stderr[:6000])
            executed = subprocess.run([str(binary), '--testScript'], capture_output=True, text=True, timeout=10)
            self.assertEqual(0, executed.returncode, executed.stderr[:2000])


if __name__ == '__main__': unittest.main()
