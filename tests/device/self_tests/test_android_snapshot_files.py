"""Execute the real run-as scripts against ordinary files; no device/candidate proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adb_transport import AdbTransport
from adapters import android_snapshot_files
from adapters.android_snapshot_files import AndroidSnapshotFiles, SnapshotFileError

PREFIX = 'parity-0123456789abcdef-still-png'
NAME = PREFIX + '-snap_1792368000000_1.png'
CONTEXT = {'sourceRevision': '1' * 40, 'artifactSha256': '2' * 64, 'processIdentity': '42:123'}
PAYLOAD = b'opaque original bytes\x00\r\n\xff (image validity belongs to the independent decoder)'

SDK = r'''#!/usr/bin/env python3
import os,shlex,subprocess,sys
from pathlib import Path
args=sys.argv[1:]
assert args[:3]==['-s','test-only-transport','exec-out'] and len(args)==4
remote=shlex.split(args[3])
assert remote[:4]==['run-as','org.overte.test','sh','-c']
assert remote[5]=='overte-snapshot-files'
root=Path(os.environ['OVERTE_TEST_SNAPSHOT_APP_ROOT'])
script=remote[4]
reading='head -c' in script
completing=os.environ.get('OVERTE_TEST_SNAPSHOT_COMPLETE_ZERO')
if reading and completing=='before' and (root/'files/Snapshots'/remote[6]).stat().st_size==0:
    (root/'files/Snapshots'/remote[6]).write_bytes(b'new original after empty reservation')
if reading and os.environ.get('OVERTE_TEST_SNAPSHOT_GROW_BEFORE_READ'):
    (root/'files/Snapshots'/remote[6]).write_bytes(b'x'*64)
if reading and os.environ.get('OVERTE_TEST_SNAPSHOT_ADD_COMPANION'):
    (root/'files/Snapshots'/os.environ['OVERTE_TEST_SNAPSHOT_ADD_COMPANION']).write_bytes(b'actual companion boundary bytes')
result=subprocess.run(['sh','-c',script,*remote[5:]],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
if reading and os.environ.get('OVERTE_TEST_SNAPSHOT_TRANSFER_LOG'):
    Path(os.environ['OVERTE_TEST_SNAPSHOT_TRANSFER_LOG']).write_text(str(len(result.stdout)))
if reading and os.environ.get('OVERTE_TEST_SNAPSHOT_REPLACE_AFTER_READ'):
    (root/'files/Snapshots'/remote[6]).write_bytes(b'replaced after actual transfer')
if reading and os.environ.get('OVERTE_TEST_SNAPSHOT_REPLACE_SAME_BYTES'):
    path=root/'files/Snapshots'/remote[6]
    replacement=path.with_suffix('.owned-replacement');replacement.write_bytes(path.read_bytes());replacement.replace(path)
if reading and completing=='after' and (root/'files/Snapshots'/remote[6]).stat().st_size==0:
    (root/'files/Snapshots'/remote[6]).write_bytes(b'new original after empty reservation')
output=result.stdout
if reading and os.environ.get('OVERTE_TEST_SNAPSHOT_CORRUPT_TRANSFER')=='frame': output=output[:-1]
elif reading and os.environ.get('OVERTE_TEST_SNAPSHOT_CORRUPT_TRANSFER')=='payload':
    content=bytearray(output)
    content[content.index(10)+1]^=1
    output=bytes(content)
sys.stdout.buffer.write(output)
# ADB exec-out copies the exec: stream and returns zero after a connection.
# The remote script's status is not conveyed by its host exit code.
raise SystemExit(0)
'''


@unittest.skipUnless(os.name != 'nt' and shutil.which('sh'), 'POSIX fixture for Android-side file scripts')
class OriginalAndroidSnapshotFiles(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-snapshot-files-')
        self.root = Path(self.temporary.name)
        self.app = self.root / 'controlled app root'
        self.snapshots = self.app / 'files/Snapshots'
        self.snapshots.mkdir(parents=True)
        self.artifacts = self.root / 'artifacts'
        self.sdk = self.root / 'adb'
        self.sdk.write_text(SDK)
        self.sdk.chmod(0o700)
        self.environment = patch.dict(os.environ, {'OVERTE_TEST_SNAPSHOT_APP_ROOT': str(self.app)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temporary.cleanup)
        self.checks = 0

    def check(self):
        self.checks += 1

    def reader(self, **overrides):
        values = dict(adb=AdbTransport(str(self.sdk)), selector='test-only-transport', package='org.overte.test',
            context=CONTEXT, check_continuity=self.check, artifact_directory=self.artifacts)
        values.update(overrides)
        return AndroidSnapshotFiles(**values)

    def save(self, name=NAME, content=PAYLOAD):
        path = self.snapshots / name
        path.write_bytes(content)
        return path

    def test_actual_scripts_copy_exact_binary_bytes_and_keep_artifacts_immutable(self):
        self.save()
        reader = self.reader()
        observed = reader.files(PREFIX)
        self.assertEqual(len(observed['files']), 1)
        file = observed['files'][0]
        self.assertEqual(file['basename'], NAME)
        self.assertEqual((self.artifacts / file['artifact']).read_bytes(), PAYLOAD)
        self.assertEqual(reader.files(PREFIX), observed)
        self.assertGreaterEqual(self.checks, 16)
        self.assertEqual(len(list(self.artifacts.iterdir())), 1)
        self.assertEqual((self.artifacts / file['artifact']).stat().st_mode & 0o777, 0o600)
        self.assertNotIn('passed', observed)
        self.assertNotIn('installedCandidateVerified', observed)

    def test_missing_directory_and_unrelated_originals_are_not_invented(self):
        self.save('unrelated-account-photo.png')
        self.assertEqual(self.reader().files(PREFIX), {'files': []})
        (self.snapshots / 'unrelated-account-photo.png').unlink()
        self.snapshots.rmdir()
        self.assertEqual(self.reader().files(PREFIX), {'files': []})
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_empty_original_remains_visible_to_pre_capture_freshness_and_decoder(self):
        self.save(content=b'')
        observed = self.reader().files(PREFIX)['files']
        self.assertEqual([row['basename'] for row in observed], [NAME])
        self.assertEqual((self.artifacts / observed[0]['artifact']).read_bytes(), b'')

    def test_empty_reservation_can_complete_during_either_side_of_the_actual_read(self):
        for moment in ('before', 'after'):
            self.save(content=b'')
            with self.subTest(moment=moment), patch.dict(os.environ, {'OVERTE_TEST_SNAPSHOT_COMPLETE_ZERO': moment}):
                result = self.reader().files(PREFIX)
            artifact = self.artifacts / result['files'][0]['artifact']
            self.assertEqual(artifact.read_bytes(), b'new original after empty reservation')

    def test_gif_companion_arriving_during_still_copy_is_legitimate_progress(self):
        prefix = 'parity-0123456789abcdef-animated'
        still = prefix + '-snap_1792368000000_1.png'
        companion = prefix + '-snap_1792368000000_1.gif'
        self.save(still)
        with patch.dict(os.environ, {'OVERTE_TEST_SNAPSHOT_ADD_COMPANION': companion}):
            first = self.reader().files(prefix)
        self.assertEqual([row['basename'] for row in first['files']], [still])
        second = self.reader().files(prefix)
        self.assertEqual({row['basename'] for row in second['files']}, {still, companion})

    def test_original_replacement_during_copy_is_refused_before_artifact_publication(self):
        self.save()
        with patch.dict(os.environ, {'OVERTE_TEST_SNAPSHOT_REPLACE_AFTER_READ': '1'}):
            with self.assertRaisesRegex(SnapshotFileError, 'changed during observation'):
                self.reader().files(PREFIX)
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_same_original_bytes_on_replaced_inode_are_not_the_original_file(self):
        self.save()
        with patch.dict(os.environ,{'OVERTE_TEST_SNAPSHOT_REPLACE_SAME_BYTES':'1'}):
            with self.assertRaisesRegex(SnapshotFileError,'changed during observation'):self.reader().files(PREFIX)
        self.assertEqual([],list(self.artifacts.iterdir()))

    def test_original_stat_identity_and_hash_are_retained_without_changing_public_file_dto(self):
        path=self.save();reader=self.reader();result=reader.files(PREFIX)
        row=reader.last_original['files'][0]
        self.assertEqual({'basename','artifact'},set(result['files'][0]));self.assertEqual(NAME,row['basename'])
        self.assertEqual(str(path.stat().st_ino),row['originalStat'].split()[1])
        self.assertEqual(CONTEXT,reader.last_original['context']);self.assertEqual(len(PAYLOAD),row['bytes'])
        self.assertEqual(2,reader.last_original['snapshotFileOriginalVersion'])

    def test_legacy_three_column_source_never_becomes_original_stat_and_path_provenance(self):
        for version in ('1','2'):
            raw=('OVT_SNAPSHOT_FILES_V'+version+'\n'+NAME+'\t1\t'+'a'*64+'\nOVT_SNAPSHOT_FILES_END_V'+version+'\n').encode()
            reader=self.reader()
            with self.subTest(version=version),patch.object(reader,'_execute',return_value=raw),self.assertRaises(SnapshotFileError):reader.files(PREFIX)
            self.assertIsNone(reader.last_original);self.assertEqual([],list(self.artifacts.iterdir()))

    def test_truncated_transfer_never_passes_even_with_an_unchanged_original(self):
        self.save()
        for kind in ('frame', 'payload'):
            with self.subTest(kind=kind), patch.dict(os.environ, {'OVERTE_TEST_SNAPSHOT_CORRUPT_TRANSFER': kind}):
                with self.assertRaises(SnapshotFileError):
                    self.reader().files(PREFIX)
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_malformed_native_names_are_not_exported_as_artifact_paths(self):
        self.save(PREFIX + '-unexpected name.png')
        with self.assertRaises(SnapshotFileError):
            self.reader().files(PREFIX)
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_actual_remote_read_caps_growth_before_the_host_transport_buffers_it(self):
        self.save(content=b'x' * 16)
        log = self.root / 'private-transfer-size'
        with patch.dict(os.environ, {'OVERTE_TEST_SNAPSHOT_GROW_BEFORE_READ': '1',
                                     'OVERTE_TEST_SNAPSHOT_TRANSFER_LOG': str(log)}), \
                patch.object(android_snapshot_files, 'MAX_BYTES', 32):
            with self.assertRaises(SnapshotFileError):
                self.reader().files(PREFIX)
        self.assertEqual(int(log.read_text()), 33 + len(android_snapshot_files.BYTES_HEADER)
                         + len(android_snapshot_files.BYTES_FOOTER))
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_symlink_hardlink_and_directory_alias_are_refused(self):
        original = self.root / 'unrelated-private-file'
        original.write_bytes(PAYLOAD)
        for kind in ('symlink', 'hardlink', 'root-alias'):
            with self.subTest(kind=kind):
                if kind == 'symlink': (self.snapshots / NAME).symlink_to(original)
                elif kind == 'hardlink': os.link(original, self.snapshots / NAME)
                else:
                    self.snapshots.rmdir()
                    self.snapshots.symlink_to(self.root, target_is_directory=True)
                with self.assertRaises(SnapshotFileError):
                    self.reader().files(PREFIX)
                if kind == 'root-alias':
                    self.snapshots.unlink()
                    self.snapshots.mkdir()
                else: (self.snapshots / NAME).unlink()
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_oversized_count_and_payload_are_bounded_inside_the_real_file_command(self):
        for index in range(9):
            self.save(PREFIX + '-snap_' + str(index) + '.png')
        with self.assertRaises(SnapshotFileError):
            self.reader().files(PREFIX)
        for path in self.snapshots.iterdir(): path.unlink()
        huge = self.save()
        with huge.open('wb') as stream: stream.truncate(256 * 1024 * 1024 + 1)
        with self.assertRaises(SnapshotFileError):
            self.reader().files(PREFIX)
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_process_or_candidate_continuity_loss_prevents_publication(self):
        self.save()
        def check():
            self.checks += 1
            if self.checks == 4: raise RuntimeError('private target/candidate changed')
        with self.assertRaisesRegex(SnapshotFileError, 'lost its bound application'):
            self.reader(check_continuity=check).files(PREFIX)
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_existing_foreign_artifact_bytes_or_alias_are_not_overwritten(self):
        self.save()
        reader = self.reader()
        observed = reader.files(PREFIX)
        artifact = self.artifacts / observed['files'][0]['artifact']
        artifact.write_bytes(b'foreign bytes must survive')
        with self.assertRaisesRegex(SnapshotFileError, 'artifact collision'):
            reader.files(PREFIX)
        self.assertEqual(artifact.read_bytes(), b'foreign bytes must survive')
        artifact.unlink()
        destination = self.root / 'other-file'
        destination.write_bytes(PAYLOAD)
        artifact.symlink_to(destination)
        with self.assertRaisesRegex(SnapshotFileError, 'artifact collision'):
            reader.files(PREFIX)
        self.assertTrue(artifact.is_symlink())

    def test_unbounded_prefix_and_nonprivate_artifact_root_are_rejected(self):
        reader = self.reader()
        for prefix in ('../../private', 'parity-$(command)', PREFIX + ';id', None):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                reader.files(prefix)
        self.assertEqual(self.checks, 0)
        self.artifacts.chmod(0o755)
        with self.assertRaisesRegex(SnapshotFileError, 'not private'):
            self.reader()


if __name__ == '__main__':
    unittest.main()
