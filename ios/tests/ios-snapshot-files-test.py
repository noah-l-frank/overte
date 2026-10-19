#!/usr/bin/env python3
"""Execute the actual native reader against original host filesystem bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/device'))
from snapshot_file_contract import CHUNK_BYTES, MAX_FILE_BYTES, read_request


class SnapshotFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='ios-snapshot-files-sdk-')
        cls.binary = Path(cls.build.name) / 'reader'
        cls.environment = dict(os.environ)
        major = cls.environment.get('OVERTE_NATIVE_QT_MAJOR', '6')
        if major not in ('5', '6'):
            raise ValueError('Select Qt5 or Qt6')
        libraries = []
        if major == '5' and cls.environment.get('OVERTE_QT5_HOST_ROOT'):
            sdk = Path(cls.environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            cls.environment.update(PKG_CONFIG_SYSROOT_DIR=str(sdk),
                PKG_CONFIG_LIBDIR=str(sdk / 'usr/lib64/pkgconfig'), LD_LIBRARY_PATH=str(sdk / 'usr/lib64'))
            libraries = ['-L' + str(sdk / 'usr/lib64')]
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt' + major + 'Core'],
            env=cls.environment, text=True))
        subprocess.run(['c++', '-std=c++17', '-fPIC', '-DOVERTE_IOS_E2E_TEST_BUILD=1',
            '-I' + str(ROOT / 'ios/ui'), '-I' + str(ROOT / 'interface/src'),
            str(ROOT / 'ios/ui/IOSSnapshotFiles.cpp'), str(Path(__file__).with_suffix('.cpp')),
            '-o', str(cls.binary), *libraries, *flags], env=cls.environment, check=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ios-original-snapshot-')
        self.root = Path(self.temporary.name) / 'Snapshots'
        self.root.mkdir()
        self.prefix = 'parity-0123456789abcdef-still-png'
        self.name = self.prefix + '-snap_123456789_1.png'
        self.reader = subprocess.Popen([str(self.binary), str(self.root)], env=self.environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def tearDown(self):
        self.reader.stdin.close()
        self.reader.wait(timeout=5)
        self.reader.stdout.close()
        self.temporary.cleanup()

    def command(self, operation='list', **values):
        command = {'schemaVersion': 1, 'commandId': 'ios-' + 'a' * 32,
            'action': 'snapshot-files', 'operation': operation, 'prefix': self.prefix} | values
        self.reader.stdin.write(json.dumps(command) + '\n')
        self.reader.stdin.flush()
        return json.loads(self.reader.stdout.readline())

    def read_original(self, row, **values):
        return self.command('read', name=row['name'], revision=row['revision'], offset=0, **values)

    def test_original_multichunk_bytes_have_actual_os_metadata_hash_and_process(self):
        content = bytes(range(256)) * 700
        (self.root / self.name).write_bytes(content)
        (self.root / 'unrelated-private-name.png').write_bytes(b'never exported')
        listed = self.command()
        self.assertTrue(listed['ok'])
        self.assertEqual(listed['processId'], self.reader.pid)
        self.assertNotIn('private-name', json.dumps(listed))
        self.assertEqual(len(listed['files']), 1)
        row = listed['files'][0]
        self.assertEqual(row['sha256'], hashlib.sha256(content).hexdigest())
        self.assertEqual(row['size'], len(content))
        original = bytearray()
        while len(original) < len(content):
            response = self.command('read', name=self.name, revision=row['revision'], offset=len(original))
            self.assertTrue(response['ok'])
            self.assertEqual(response['processId'], self.reader.pid)
            self.assertEqual(response['file']['offset'], len(original))
            chunk = base64.b64decode(response['file']['data'], validate=True)
            self.assertLessEqual(len(chunk), CHUNK_BYTES)
            original.extend(chunk)
            self.assertEqual(response['file']['eof'], len(original) == len(content))
        self.assertEqual(bytes(original), content)
        self.assertEqual(self.command()['files'], listed['files'])

    def test_missing_directory_and_empty_reservation_are_truthful_not_completed_captures(self):
        self.root.rmdir()
        self.assertEqual(self.command()['files'], [])
        self.root.mkdir()
        (self.root / self.name).touch()
        row = self.command()['files'][0]
        self.assertEqual(row['size'], 0)
        (self.root / self.name).write_bytes(b'original completed later')
        newer = self.command()['files'][0]
        self.assertNotEqual(newer['revision'], row['revision'])
        self.assertFalse(self.read_original(row)['ok'])
        self.assertTrue(self.read_original(newer)['ok'])

    def test_file_directory_and_hard_link_aliases_never_export_bytes(self):
        foreign = self.root.parent / 'private'; foreign.write_bytes(b'foreign')
        path = self.root / self.name
        for kind in ('symbolic', 'hard', 'directory', 'fifo'):
            if kind == 'symbolic': path.symlink_to(foreign)
            elif kind == 'hard': os.link(foreign, path)
            elif kind == 'directory': path.mkdir()
            else: os.mkfifo(path)
            with self.subTest(kind=kind):
                response = self.command()
                self.assertFalse(response['ok'])
                self.assertNotIn('files', response)
            path.rmdir() if kind == 'directory' else path.unlink()
        self.root.rmdir(); self.root.symlink_to(self.root.parent, target_is_directory=True)
        self.assertFalse(self.command()['ok'])
        self.root.unlink()

    def test_replacement_or_content_change_cannot_reuse_an_original_revision(self):
        path = self.root / self.name; path.write_bytes(b'original')
        for change in ('replace', 'overwrite-restore-mtime', 'hard-link-after-list'):
            row = self.command()['files'][0]
            old_stat = path.stat()
            if change == 'replace':
                replacement = self.root.parent / 'new'; replacement.write_bytes(b'original')
                replacement.replace(path)
            elif change == 'overwrite-restore-mtime':
                path.write_bytes(b'altered!'); os.utime(path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            else:
                os.link(path, self.root.parent / 'alias')
            with self.subTest(change=change):
                self.assertFalse(self.read_original(row)['ok'])
        (self.root.parent / 'alias').unlink()

    def test_unexpected_own_name_count_and_sparse_oversize_fail_before_transfer(self):
        path = self.root / (self.prefix + '-unexpected.png'); path.touch()
        self.assertFalse(self.command()['ok']); path.unlink()
        for number in range(9):
            (self.root / (self.prefix + '-snap_123_' + str(number) + '.png')).touch()
        self.assertFalse(self.command()['ok'])
        for path in self.root.iterdir(): path.unlink()
        with (self.root / self.name).open('wb') as stream: stream.truncate(MAX_FILE_BYTES + 1)
        self.assertFalse(self.command()['ok'])

    def test_every_native_wire_guard_agrees_with_shared_closed_contract(self):
        baseline = {'schemaVersion': 1, 'commandId': 'ios-' + 'a' * 32,
            'action': 'snapshot-files', 'operation': 'list', 'prefix': self.prefix}
        valid_read = baseline | {'operation': 'read', 'name': self.name, 'revision': 'a' * 64, 'offset': 0}
        for command in (baseline, valid_read): self.assertEqual(read_request(command), command)
        invalid = [baseline | change for change in ({'schemaVersion': True}, {'commandId': 'foreign'},
            {'operation': 'capture'}, {'root': '/Documents'}, {'files': []}, {'prefix': self.prefix + '\n'})]
        invalid += [valid_read | change for change in ({'name': '../other.png'}, {'name': self.name + '\n'},
            {'revision': 'A' * 64}, {'offset': True}, {'offset': -1}, {'offset': 0.5}, {'offset': MAX_FILE_BYTES + 1})]
        for command in invalid:
            with self.subTest(command=command):
                with self.assertRaises(ValueError): read_request(command)
                self.assertEqual(self.command(**{k: v for k, v in command.items() if k != 'operation'},
                    operation=command['operation']), {})

    def test_eof_and_out_of_range_reads_cannot_invent_bytes(self):
        (self.root / self.name).write_bytes(b'original')
        row = self.command()['files'][0]
        at_end = self.command('read', name=self.name, revision=row['revision'], offset=row['size'])
        self.assertTrue(at_end['ok'])
        self.assertTrue(at_end['file']['eof'])
        self.assertEqual(at_end['file']['data'], '')
        beyond = self.command('read', name=self.name, revision=row['revision'], offset=row['size'] + 1)
        self.assertFalse(beyond['ok'])

    def test_actual_async_test_api_is_gated_bounded_and_publishes_atomic_private_receipts(self):
        source = (ROOT / 'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start = source.index('bool TestScriptingInterface::iosSnapshotFilesRequest(')
        end = source.index('bool TestScriptingInterface::iosTextTest(', start)
        stage = Path(self.temporary.name)
        driver = stage / 'producer.cpp'
        driver.write_text(r'''
#include "IOSSnapshotFiles.h"
#include "ui/SnapshotStorage.h"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLoggingCategory>
#include <QSaveFile>
#include <QSemaphore>
#include <QThreadPool>
#include <QVariantMap>
#include <iostream>
Q_LOGGING_CATEGORY(trace_test, "trace.test")
class TestScriptingInterface {
public:
 QString _testResultsLocation;
 bool iosSnapshotFilesRequest(const QVariantMap& command);
};
BODY
int main(int argc, char** argv) {
 QCoreApplication app(argc, argv);
 app.setOrganizationName("SnapshotReaderTest"); app.setApplicationName("Producer");
 const auto directory = QString::fromLocal8Bit(argv[1]); QDir().mkpath(directory);
 const auto root = overte::snapshot::storageRoot(); QDir().mkpath(root);
 const QString prefix("parity-0123456789abcdef-still-png");
 QFile original(QDir(root).filePath(prefix+"-snap_123_1.png"));
 if(!original.open(QIODevice::WriteOnly) || original.write("actual original native bytes")!=28) return 2;
 original.close();
 TestScriptingInterface owner; owner._testResultsLocation=directory;
 QVariantMap request {{"schemaVersion",1},{"commandId","ios-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  {"action","snapshot-files"},{"operation","list"},{"prefix",prefix}};
 if (!app.arguments().contains("--testScript")) {
  if(owner.iosSnapshotFilesRequest(request) || QFile::exists(QDir(directory).filePath("ios-snapshot-file-result.json"))) return 3;
  std::cout << "rejected without test launch"; return 0;
 }
 auto invalid=request; invalid["root"]=root;
 if(owner.iosSnapshotFilesRequest(invalid)) return 4;
 owner._testResultsLocation.clear();
 if(owner.iosSnapshotFilesRequest(request)) return 5;
 owner._testResultsLocation=directory;
 QThreadPool::globalInstance()->setMaxThreadCount(1);
 QSemaphore blocker;
 QThreadPool::globalInstance()->start([&blocker]{blocker.acquire();});
 if(!owner.iosSnapshotFilesRequest(request)) return 6;
 auto second=request; second["commandId"]="ios-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
 if(owner.iosSnapshotFilesRequest(second)) return 7;
 blocker.release();
 if(!QThreadPool::globalInstance()->waitForDone(5000)) return 8;
 QFile receipt(QDir(directory).filePath("ios-snapshot-file-result.json"));
 if(!receipt.open(QIODevice::ReadOnly)) return 9;
 std::cout << receipt.readAll().constData(); return 0;
}
'''.replace('BODY', source[start:end]))
        # Compile the actual owning API body, with only the enclosing app
        # singleton replaced. Real Qt threading, QStandardPaths, storage reader
        # and QSaveFile run; UIKit and application linking remain unperformed.
        major = self.environment.get('OVERTE_NATIVE_QT_MAJOR', '6')
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt' + major + 'Core'],
            env=self.environment, text=True))
        libraries = (['-L' + self.environment['LD_LIBRARY_PATH']]
                     if major == '5' and self.environment.get('OVERTE_QT5_HOST_ROOT') else [])
        binary = stage / 'producer'
        subprocess.run(['c++', '-std=c++17', '-fPIC', '-DOVERTE_IOS_E2E_TEST_BUILD=1',
            '-I' + str(ROOT / 'ios/ui'), '-I' + str(ROOT / 'interface/src'),
            str(driver), str(ROOT / 'ios/ui/IOSSnapshotFiles.cpp'), '-o', str(binary), *libraries, *flags],
            env=self.environment, check=True, timeout=60)
        environment = self.environment | {'XDG_DATA_HOME': str(stage / 'data')}
        result_directory = stage / 'results'
        denied = subprocess.run([str(binary), str(result_directory)], env=environment,
            check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(denied.stdout, 'rejected without test launch')
        accepted = subprocess.run([str(binary), str(result_directory), '--testScript'], env=environment,
            check=True, capture_output=True, text=True, timeout=10)
        observed = json.loads(accepted.stdout)
        self.assertTrue(observed['ok'])
        self.assertEqual(observed['commandId'], 'ios-' + 'a' * 32)
        self.assertEqual(observed['files'][0]['sha256'], hashlib.sha256(b'actual original native bytes').hexdigest())
        receipt = result_directory / 'ios-snapshot-file-result.json'
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main(verbosity=2)
