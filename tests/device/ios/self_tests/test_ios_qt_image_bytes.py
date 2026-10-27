"""Real IPA/directory byte joins with explicit native/dyld/SDK models.

Synthetic Mach-O and signatures do not establish native execution, signing or
Qt source provenance. The existing installed binding/manifest readers execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib,os,struct,unittest
from pathlib import Path
from adapters.normal_ui import NativeUIError
from ios.adapters import bundle_identity,qt_image_bytes,chat_qml_sources
from ios.self_tests.chat_qml_cache_source_fixture import cache_packet,advance
from ios.self_tests import test_ios_bundle_identity as archive_fixture
from ios.self_tests import test_ios_installed_code as binding_fixture
from ios.self_tests.retained_host_roots import retain_owned_root


def macho(uuid=b'\x12'*16):
    unique=struct.pack('<II',0x1b,24)+uuid
    segment=struct.pack('<II16sQQQQiiII',0x19,72,b'__TEXT\0',0x100000000,4096,0,512,7,5,0,0)
    build=struct.pack('<IIIIII',0x32,24,2,0x00110000,0x00110000,0)
    commands=unique+segment+build
    return struct.pack('<IiiIIIII',0xfeedfacf,0x0100000c,0,2,3,len(commands),0,0)+commands+b'\0'*(512-32-len(commands))


class QtImageBytesTests(unittest.TestCase):
    def retain(self,case):
        temporary=case.temp;root=Path(temporary.name)
        retain_owned_root(temporary,expected_root=root)
        for index,(callback,args,kwargs) in enumerate(case._cleanups):
            if getattr(callback,'__self__',None) is temporary:case._cleanups[index]=(temporary.cleanup,args,kwargs)
        print('retained Qt image fixture root',root,flush=True)

    def prepare(self):
        archive=archive_fixture.BundleIdentityTests();self.addCleanup(archive.doCleanups);archive.setUp();self.retain(archive)
        archive.files['Overte']=macho();actual_sha=archive.archive();actual_bundle=archive.actual_directory_manifest()
        binding=binding_fixture.InstalledCodeTests();self.addCleanup(binding.doCleanups);binding.setUp();self.retain(binding)
        binding.scope['artifactSha256']=actual_sha;binding.native.bundle=actual_bundle;binding.binding=binding.make();binding.active()
        row=binding.store.read();path=Path(archive.temp.name)/'Overte.app'/'Overte'
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd);raw=os.read(fd,before.st_size);after=os.fstat(fd)
            self.assertEqual((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns),
                (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        finally:os.close(fd)
        # This models a dyld observation of the entry. The file bytes and IPA
        # are independently read; no machine code or actual function ran.
        commands=struct.unpack_from('<I',raw,20)[0]
        image=dict(iosQtEntryImageVersion=1,source='native-main-image-entry-fd',instance=row['observation']['instance'],
            sequence=1,processId=42,beforeEpochMs=20001,afterEpochMs=20002,bundlePreparedEpochMs=row['observation']['preparedEpochMs'],
            bundle=actual_bundle,relativePath='Overte',fileBytes=str(len(raw)),fileSha256=hashlib.sha256(raw).hexdigest(),
            imageUuid='12'*16,headerSha256=hashlib.sha256(raw[:32+commands]).hexdigest(),symbolFileOffset='256',
            fileDevice=str(before.st_dev),fileInode=str(before.st_ino))
        return archive,binding,actual_sha,image

    def test_actual_selected_ipa_member_and_installed_bundle_bytes_bind_without_sdk_source_claim(self):
        archive,binding,digest,image=self.prepare();before=deepcopy(binding.store.read())
        result=binding.binding.qt_entry_image_bytes(image,archive.path,digest)
        self.assertTrue(result['imageBytesBound']);self.assertEqual(digest,result['artifactSha256'])
        self.assertFalse(result['qtSdkSourceAvailable']);self.assertFalse(result['importGraphAvailable']);self.assertFalse(result['aotGraphAvailable'])
        self.assertEqual(before,binding.store.read());self.assertEqual(image,result['original'])
        self.assertEqual(bundle_identity.artifact_bundle(archive.path,digest),image['bundle'])

    def test_foreign_native_pid_bundle_owner_or_preparation_cannot_use_a_selected_ipa(self):
        archive,binding,digest,image=self.prepare()
        for key,value in (('processId',43),('instance','0'*32),('bundlePreparedEpochMs',1),('fileSha256','0'*64)):
            changed=deepcopy(image);changed[key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,NativeUIError)):
                binding.binding.qt_entry_image_bytes(changed,archive.path,digest)

    def test_actual_ipa_uuid_header_or_executable_offset_mismatch_refuses(self):
        archive,binding,digest,image=self.prepare()
        for key,value in (('imageUuid','0'*32),('headerSha256','0'*64),('symbolFileOffset','512'),('fileBytes','511')):
            changed=deepcopy(image);changed[key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,NativeUIError)):
                binding.binding.qt_entry_image_bytes(changed,archive.path,digest)

    def test_artifact_replacement_and_unavailable_or_changed_existing_process_fail_closed(self):
        archive,binding,digest,image=self.prepare();before=deepcopy(binding.store.read())
        binding.process['pid']=43
        with self.assertRaises((ValueError,NativeUIError)):binding.binding.qt_entry_image_bytes(image,archive.path,digest)
        binding.process['pid']=42;archive.path.write_bytes(archive.path.read_bytes()+b'changed original IPA')
        with self.assertRaises((ValueError,NativeUIError)):binding.binding.qt_entry_image_bytes(image,archive.path,digest)
        self.assertEqual(before,binding.store.read())

    def test_decimal_ids_are_lossless_and_requested_qt_version_is_never_execution_identity(self):
        _archive,_binding,_digest,image=self.prepare()
        image['fileDevice']=str(2**64-1);image['fileInode']=str(2**64-1)
        self.assertEqual(image,qt_image_bytes.validate(image,42))
        for key,value in (('fileInode',2**64-1),('fileDevice',str(2**64)),('symbolFileOffset',1),('qtVersion','6.11.1')):
            changed=deepcopy(image);changed[key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,NativeUIError)):qt_image_bytes.validate(changed,42)

    def test_actual_macho_header_parser_rejects_non_ios_truncation_or_duplicate_uuid(self):
        raw=macho();size=struct.unpack_from('<I',raw,20)[0]
        observed=bundle_identity.macho_image(raw[:32],raw[32:32+size],len(raw));self.assertEqual(2,observed['platform'])
        for fault in ('short','simulator','uuid'):
            changed=bytearray(raw)
            if fault=='simulator':struct.pack_into('<I',changed,32+24+72+8,7)
            elif fault=='uuid':struct.pack_into('<I',changed,32+24,0x1b)
            if fault=='short':changed=changed[:33]
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                bundle_identity.macho_image(bytes(changed[:32]),bytes(changed[32:32+size]),len(changed))


    def test_cache_outer_v2_requires_actual_image_and_native_query_interval(self):
        _archive,_binding,_digest,image=self.prepare()
        value=cache_packet(19000);value.update(iosChatQmlSourcesVersion=2,qtEntryImage=image)
        value['clockAfter'].update(epochMs=20003,monotonicMs=1003)
        self.assertEqual(value,chat_qml_sources.original(value))
        for fault in ('missing','old-version','late-image','numeric-inode','unknown-image-field'):
            changed=deepcopy(value)
            if fault=='missing':changed.pop('qtEntryImage')
            elif fault=='old-version':changed['iosChatQmlSourcesVersion']=1
            elif fault=='late-image':changed['qtEntryImage']['afterEpochMs']=20004
            elif fault=='numeric-inode':changed['qtEntryImage']['fileInode']=2**64-1
            else:changed['qtEntryImage']['requestedQtVersion']='6.11.1'
            with self.subTest(fault=fault),self.assertRaises((ValueError,NativeUIError)):
                chat_qml_sources.original(changed)

    def test_cache_outer_v2_requires_fresh_image_sequence_and_same_original_image_owner(self):
        _archive,_binding,_digest,image=self.prepare()
        old=cache_packet(19000);old.update(iosChatQmlSourcesVersion=2,qtEntryImage=image)
        old['clockAfter'].update(epochMs=20003,monotonicMs=1003)
        value=advance(old);value['qtEntryImage'].update(sequence=2,beforeEpochMs=20011,afterEpochMs=20012)
        query=dict(schemaVersion=1,action=chat_qml_sources.ACTION,commandId=value['requestId'],runId=value['runId'])
        self.assertEqual(value,chat_qml_sources.validate(value,query,42,previous=old))
        for key,changed_value in (('sequence',1),('instance','0'*32),('symbolFileOffset','257'),('headerSha256','0'*64)):
            changed=deepcopy(value);changed['qtEntryImage'][key]=changed_value
            with self.subTest(key=key),self.assertRaises((ValueError,NativeUIError)):
                chat_qml_sources.validate(changed,query,42,previous=old)


if __name__=='__main__':unittest.main()
