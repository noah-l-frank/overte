"""Independent original IPA and directory fixtures; no native binary execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters.bundle_identity import artifact_bundle,compare,root_digest,name,EMPTY


class BundleIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'candidate.ipa'
        self.info=dict(CFBundleIdentifier='org.example.overte',CFBundleExecutable='Overte',
            OverteE2ETestBuildContractVersion=1,UIFileSharingEnabled=True)
        # Explicitly synthetic file bytes, not a compiled/package qualification.
        self.files={'Info.plist':plistlib.dumps(self.info),'Overte':b'synthetic native file',
            'qml/Chat.qml':b'original qml','scripts/chat.js':b'original js','empty.txt':b'',
            '_CodeSignature/CodeResources':b'actual signature bytes'}

    def archive(self,*,edit=None,extra=(),compression=zipfile.ZIP_DEFLATED,reverse=False):
        files=dict(self.files)
        if edit:files.update(edit)
        with zipfile.ZipFile(self.path,'w',compression=compression) as output:
            values=list(files.items())
            if reverse:values.reverse()
            for key,value in values:
                info=zipfile.ZipInfo('Payload/Overte.app/'+key);info.external_attr=(stat.S_IFREG|0o644)<<16
                info.compress_type=compression;output.writestr(info,value)
            for info,value in extra:output.writestr(info,value)
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def actual_directory_manifest(self):
        # Read original files separately from ZIP parsing. The byte algorithm
        # matches the future native source; this does not execute that C++.
        root=Path(self.temp.name)/'Overte.app';root.mkdir()
        for key,value in self.files.items():
            path=root/key;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        entries={}
        for path in root.rglob('*'):
            relative=path.relative_to(root).as_posix()
            entries[relative]=('D',0,EMPTY) if path.is_dir() else ('F',path.stat().st_size,hashlib.sha256(path.read_bytes()).digest())
        return dict(bundleContractVersion=1,bundleId=self.info['CFBundleIdentifier'],
            executableSha256=hashlib.sha256((root/'Overte').read_bytes()).hexdigest(),**root_digest(entries))

    def test_independently_read_original_app_files_match_archive_content(self):
        digest=self.archive();candidate=artifact_bundle(self.path,digest)
        actual=self.actual_directory_manifest();self.assertEqual(actual,compare(actual,candidate))
        self.assertEqual(6,candidate['fileCount']);self.assertEqual(9,candidate['nodeCount'])
        self.assertNotEqual(digest,candidate['bundleSha256'])

    def test_zip_order_compression_and_implicit_directories_do_not_replace_byte_identity(self):
        first=artifact_bundle(self.path,self.archive())
        second=artifact_bundle(self.path,self.archive(reverse=True,compression=zipfile.ZIP_STORED))
        self.assertEqual(first,second)
        directory=zipfile.ZipInfo('Payload/Overte.app/qml/');directory.external_attr=(stat.S_IFDIR|0o755)<<16
        third=artifact_bundle(self.path,self.archive(extra=[(directory,b'')]))
        self.assertEqual(first,third)

    def test_changed_qml_script_executable_signature_or_plist_never_match_old_archive(self):
        actual=self.actual_directory_manifest()
        for path in self.files:
            changed=self.files[path]+b' changed'
            if path=='Info.plist':changed=plistlib.dumps(self.info|{'CFBundleVersion':'changed'})
            candidate=artifact_bundle(self.path,self.archive(edit={path:changed}))
            with self.subTest(path=path),self.assertRaises(ValueError):compare(actual,candidate)

    def test_expected_archive_hash_is_never_returned_as_native_bundle_measurement(self):
        digest=self.archive();candidate=artifact_bundle(self.path,digest)
        with self.assertRaises(ValueError):artifact_bundle(self.path,'f'*64)
        with self.assertRaises(ValueError):compare(candidate|{'bundleSha256':digest},candidate)
        with self.assertRaises(ValueError):compare(candidate|{'expected':candidate},candidate)

    def test_wrong_bundle_types_counts_digest_or_version_fail_closed(self):
        candidate=artifact_bundle(self.path,self.archive())
        for edit in ({'bundleContractVersion':True},{'bundleContractVersion':2},{'nodeCount':True},
            {'fileCount':0},{'nodeCount':1},{'totalBytes':0},{'executableSha256':'bad'},
            {'bundleId':'private/path'},{'bundleSha256':'A'*64}):
            changed=candidate|edit
            with self.subTest(edit=edit),self.assertRaises(ValueError):compare(changed,changed)

    def test_missing_e2e_markers_invalid_executable_or_duplicate_members_are_rejected(self):
        for edit in ({'UIFileSharingEnabled':False},{'OverteE2ETestBuildContractVersion':True},
                     {'CFBundleExecutable':'../Overte'},{'CFBundleIdentifier':'wrong'}):
            digest=self.archive(edit={'Info.plist':plistlib.dumps(self.info|edit)})
            with self.assertRaises(ValueError):artifact_bundle(self.path,digest)
        duplicate=zipfile.ZipInfo('Payload/Overte.app/qml/Chat.qml')
        with __import__('warnings').catch_warnings():
            __import__('warnings').simplefilter('ignore',UserWarning)
            digest=self.archive(extra=[(duplicate,b'other')])
        with self.assertRaises(ValueError):artifact_bundle(self.path,digest)

    def test_unsafe_links_aliases_names_extra_app_and_changed_artifact_are_rejected(self):
        for path in ('../escape','qml/../escape','qml//bad','bad\\name','bad\nname','QML/chat.qml'):
            digest=self.archive(edit={path:b'foreign'})
            with self.subTest(path=path),self.assertRaises(ValueError):artifact_bundle(self.path,digest)
        link=zipfile.ZipInfo('Payload/Overte.app/link');link.external_attr=(stat.S_IFLNK|0o777)<<16
        other=zipfile.ZipInfo('Payload/Other.app/Info.plist')
        for extra in ([(link,b'/foreign')],[(other,b'other')]):
            digest=self.archive(extra=extra)
            with self.assertRaises(ValueError):artifact_bundle(self.path,digest)
        digest=self.archive();self.path.write_bytes(self.path.read_bytes()+b'changed')
        with self.assertRaises(ValueError):artifact_bundle(self.path,digest)

    def test_symlink_candidate_is_not_opened_or_extracted(self):
        digest=self.archive();link=self.path.with_name('alias.ipa');link.symlink_to(self.path)
        with self.assertRaises((ValueError,OSError)):artifact_bundle(link,digest)
        self.assertFalse((Path(self.temp.name)/'Payload').exists())

    def test_manifest_record_framing_is_unambiguous_and_parents_are_actual(self):
        digest=hashlib.sha256(b'x').digest()
        first=root_digest({'a':('F',1,digest),'bc':('F',1,digest)})
        second=root_digest({'ab':('F',1,digest),'c':('F',1,digest)})
        self.assertNotEqual(first['bundleSha256'],second['bundleSha256'])
        with self.assertRaises(ValueError):root_digest({'missing/a':('F',1,digest)})
        for value in ('','/root','a/./b','a/../b','a\x00b','a\nb'):
            with self.assertRaises(ValueError):name(value)


if __name__=='__main__':unittest.main()
