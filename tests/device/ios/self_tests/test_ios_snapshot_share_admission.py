"""Actual archive/installed forests and durable originals; native/OS modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import plistlib
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_companion_artifact import artifact,share_artifact
from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner
from ios.adapters import snapshot_companion_source,snapshot_share_admission_source
from ios.self_tests.snapshot_companion_domain import SnapshotCompanionDomain,RUN
from ios.self_tests.snapshot_share_admission_domain import ShareAdmissionDomain,EXTENSION,BUNDLE


class SnapshotShareAdmissionTests(unittest.TestCase):
    def test_normal_independent_admission_binds_actual_embedded_extension_and_original_archive(self):
        d=ShareAdmissionDomain(self)
        with d.owner() as owner:
            result=owner.admit('d'*32);self.assertTrue(result['archiveCodeVerified']);self.assertTrue(result['embeddedExtensionCodeVerified'])
            self.assertTrue(result['extensionProcessQualificationRequired']);self.assertEqual(BUNDLE+'.receiver',result['embeddedExtension']['bundle']['bundleId'])
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        pins={path:(path.stat().st_ino,path.stat().st_mtime_ns,path.read_bytes()) for path in d.root.iterdir() if path.name.startswith('ios-snapshot-share-code-frame-')}
        calls=len(d.requests),len(d.sdk)
        with lock.held():self.assertEqual(result,IOSSnapshotShareAdmissionOwner.archive(store,lock,binding,RUN,url,d.ipa).result())
        self.assertEqual(calls,(len(d.requests),len(d.sdk)));self.assertEqual(['clock','identity','clock'],d.clicks)
        self.assertEqual(pins,{path:(path.stat().st_ino,path.stat().st_mtime_ns,path.read_bytes()) for path in pins})

    def test_changed_actual_extension_executable_signature_provision_or_added_node_cannot_reuse_admission(self):
        for name in ('share-receiver','_CodeSignature/CodeResources','embedded.mobileprovision','unexpected-node'):
            with self.subTest(name=name):
                d=ShareAdmissionDomain(self);path=d.installed/(EXTENSION+name);path.write_bytes(b'Changed actual installed extension bytes')
                with d.owner() as owner,self.assertRaises((NativeUIError,ValueError)):owner.admit('d'*32)
                self.assertEqual(['clock','identity'],d.clicks)

    def test_invalid_or_ambiguous_selected_extension_and_app_group_fail_before_SDK_input(self):
        for fault in ('wrong-point','wrong-bundle','wrong-group','missing-executable','missing-extension','second-extension','nested-extension'):
            with self.subTest(fault=fault):
                d=ShareAdmissionDomain(self);files=deepcopy(d.files);info=plistlib.loads(files[EXTENSION+'Info.plist'])
                if fault=='wrong-point':info['NSExtension']['NSExtensionPointIdentifier']='com.apple.unrelated'
                elif fault=='wrong-bundle':info['CFBundleIdentifier']='org.foreign.receiver'
                elif fault=='wrong-group':info['OVTSnapshotShareGroup']='group.org.foreign'
                elif fault=='missing-executable':files.pop(EXTENSION+'share-receiver')
                elif fault=='missing-extension':files={name:raw for name,raw in files.items() if not name.startswith(EXTENSION)}
                elif fault=='second-extension':files.update({name.replace(EXTENSION,'PlugIns/Second.appex/'):raw for name,raw in list(files.items()) if name.startswith(EXTENSION)})
                else:files[EXTENSION+'Nested.appex/not-info']=b'Unselected nested extension'
                if fault not in ('missing-extension',):files[EXTENSION+'Info.plist']=plistlib.dumps(info)
                d.write_archive(files);d.scope['artifactSha256']=hashlib.sha256(d.ipa.read_bytes()).hexdigest()
                with self.assertRaises((NativeUIError,ValueError)):d.runtime()
                self.assertFalse(d.requests);self.assertFalse(d.sdk)

    def test_lost_original_identity_return_reconstructs_without_second_button_or_permission_action(self):
        d=ShareAdmissionDomain(self);d.loss='identity'
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.admit('d'*32)
        d.loss=None
        with d.owner() as owner:self.assertTrue(owner.admit('d'*32)['embeddedExtensionCodeVerified'])
        self.assertEqual(1,d.clicks.count('identity'));self.assertEqual(3,len(d.nonces));runtime=d.runtime();before=len(d.sdk)
        with self.assertRaises(NativeUIError):runtime.original('photos')
        self.assertEqual(before,len(d.sdk))

    def test_selected_archive_inode_and_boolean_session_generation_cannot_be_rebound(self):
        for fault in ('inode','session','source'):
            with self.subTest(fault=fault):
                d=ShareAdmissionDomain(self);runtime=d.runtime()
                if fault=='inode':
                    replacement=d.root/'replacement.ipa';replacement.write_bytes(d.ipa.read_bytes());replacement.replace(d.ipa)
                elif fault=='session':
                    old=d.session.read();d.session.write(dict(old,generation=True),old)
                else:d.source='0'*32
                with self.assertRaises((NativeUIError,ValueError,OSError)):
                    with runtime.owner(RUN,d.client()) as owner:owner.admit('d'*32)
                self.assertFalse(d.clicks)

    def test_photos_and_share_readers_reject_role_schema_and_original_namespace_substitution(self):
        photos=SnapshotCompanionDomain(self);shared=ShareAdmissionDomain(self)
        with self.assertRaises(NativeUIError):artifact(shared.ipa,shared.scope['artifactSha256'])
        with self.assertRaises(NativeUIError):share_artifact(photos.ipa,photos.scope['artifactSha256'])
        with shared.owner() as owner:
            owner.admit('d'*32);packet=owner.original(owner.state['queries'][1]);snapshot_share_admission_source.original(packet)
            with self.assertRaises(NativeUIError):snapshot_companion_source.original(packet)
            with self.assertRaises(NativeUIError):IOSSnapshotCompanionOwner.archive(owner.store,owner.lock,owner.binding,RUN,owner.fixture_url,shared.ipa)
        photos.nonce='ios-'+'a'*32;packet=photos.observe('clock')
        with self.assertRaises(NativeUIError):snapshot_share_admission_source.original(packet)

    def test_closed_compile_time_profile_keeps_shared_reader_and_no_Photos_permission_dependency(self):
        root=Path(__file__).resolve().parents[1];native=(root/'snapshot_companion/CompanionIdentity.m').read_text()
        cmake=(root/'snapshot_share_companion/CMakeLists.txt').read_text();app=(root/'snapshot_share_companion/ArchiveApp.m').read_text()
        self.assertIn('#if !defined(OVT_SNAPSHOT_SHARE_ARCHIVE)\n#import <Photos/Photos.h>',native)
        self.assertIn('OVT_SNAPSHOT_SHARE_ARCHIVE=1',cmake);self.assertNotIn('framework Photos',cmake)
        self.assertIn('OVTSnapshotCompanionIdentityPanel new',app);self.assertIn('if (closedir(directory)!=0)',native)
        photos=(root/'snapshot_companion/CMakeLists.txt').read_text();self.assertNotIn('OVT_SNAPSHOT_SHARE_ARCHIVE',photos)


if __name__=='__main__':unittest.main()
