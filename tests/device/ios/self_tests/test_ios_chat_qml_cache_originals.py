"""Real owned host FD/write/mmap counterexamples; native Qt producer is modeled.

These tests do not execute QSaveFile/Qt, native compilation or installed code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib,json,mmap,os
from pathlib import Path
import tempfile,time,unittest,uuid
from adapters.normal_ui import NativeUIError
from ios.adapters import chat_qml_cache_originals as source


def clock():return dict(epochMs=time.time_ns()//1000000,monotonicMs=time.monotonic_ns()//1000000)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def pin(fd):
    value=os.fstat(fd)
    return dict(device=str(value.st_dev),inode=str(value.st_ino),bytes=value.st_size,
        modifiedSeconds=value.st_mtime_ns//10**9,modifiedNanoseconds=value.st_mtime_ns%10**9,
        changedSeconds=value.st_ctime_ns//10**9,changedNanoseconds=value.st_ctime_ns%10**9)


class ChatQmlCacheOriginalTests(unittest.TestCase):
    def originals(self,*,partial=False,commit=True):
        root=Path(tempfile.mkdtemp(prefix='chat-qml-cache-originals-'));root.chmod(0o700)
        print('retained cache original root',root,flush=True)
        before=clock();text='Item {}';encoded=text.encode('utf-16le');after=clock()
        # Explicit synthetic unit/flag representation: this is NOT a Qt binary
        # Unit layout. It models only Qt's observed temporary-flag difference.
        original=b'\0'+b'explicit-host-unit-model'*8;argument=b'\1'+original[1:]
        compiler=dict(qtOverteQmlCompilerInputVersion=1,instance=uuid.uuid4().hex,sequence=1,
            processId=os.getpid(),qtVersion='6.11.1',encoding='utf16-le-code-units',codeUnits=len(encoded)//2,
            sha256=sha(encoded),requestedUrl='qrc:/scripts/communityScripts/armored-chat/armored_chat.qml',
            resolvedUrl='qrc:/scripts/communityScripts/armored-chat/armored_chat.qml',
            sourceBeforeEpochMs=before['epochMs'],sourceAfterEpochMs=after['epochMs'],
            compilerUnitBytes=len(original),compilerUnitSha256=sha(original))
        temporary=root/'cache.pending';destination=root/'cache.qmlc'
        fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);retained=os.dup(fd)
        try:
            file_before=pin(retained);started=clock();written=os.write(fd,argument[:-1] if partial else argument)
            os.fsync(fd);os.close(fd);fd=-1
            if not commit:destination.mkdir(mode=0o700)
            try:os.replace(temporary,destination);committed=True
            except OSError:committed=False
            actual_path=destination if committed else temporary
            # Preserve the exact writer inode under another private name before
            # its committed identity is captured; no later reconstruction.
            os.link(actual_path,root/'writer-original.bin')
            completed=pin(retained);ended=clock()
        finally:
            if fd>=0:os.close(fd)
            os.close(retained)
        write=dict(qtOverteQmlCacheWriteVersion=1,clockDomain=source.DOMAIN,writerId=uuid.uuid4().hex,
            processId=os.getpid(),compilerOwnerId=uuid.uuid4().hex,compilerOwnerGeneration=1,
            compilerInput=compiler,writeSequence=1,writeBefore=started,writeAfter=ended,bytes=len(argument),
            writeArgumentSha256=sha(argument),fileBefore=file_before,written=written,committed=committed,fileCommitted=completed)
        mapped_fd=os.open(actual_path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            file_before=pin(mapped_fd);map_before=clock()
            with mmap.mmap(mapped_fd,0,access=mmap.ACCESS_READ) as mapped:actual=mapped[:]
            map_after=clock();self.assertEqual(file_before,pin(mapped_fd))
        finally:os.close(mapped_fd)
        mapping=dict(qtOverteQmlCacheMappingVersion=1,clockDomain=source.DOMAIN,mappingId=uuid.uuid4().hex,
            mappingSequence=2,processId=os.getpid(),mapBefore=map_before,mapAfter=map_after,
            mappedFile=file_before,mappedBytes=len(actual),mappedSha256=sha(actual),writeOriginal=write)
        unit=dict(qtOverteQmlCacheUnitVersion=1,clockDomain=source.DOMAIN,processId=os.getpid(),
            unitOwnerId=uuid.uuid4().hex,unitReadBefore=clock(),unitReadAfter=clock(),unitGeneration=3,
            unitBytes=len(actual),unitSha256=sha(actual),mappingOriginal=mapping)
        (root/'observed-chain.json').write_text(json.dumps(unit,indent=2)+'\n');(root/'observed-chain.json').chmod(0o600)
        return root,actual_path,unit

    def test_original_fd_write_to_actual_mapping_keeps_temporary_flag_digest_distinct(self):
        _root,_path,value=self.originals();mapping=value['mappingOriginal'];write=mapping['writeOriginal']
        self.assertNotEqual(write['compilerInput']['compilerUnitSha256'],mapping['mappedSha256'])
        self.assertEqual(value,source.observed_chain(value,os.getpid()))
        self.assertEqual(write['fileCommitted'],mapping['mappedFile'])

    def test_equal_byte_path_replacement_cannot_borrow_the_original_writer_inode(self):
        root,path,value=self.originals();replacement=root/'replacement.bin';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
        os.replace(replacement,path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:actual=pin(fd)
        finally:os.close(fd)
        self.assertNotEqual(actual['inode'],value['mappingOriginal']['mappedFile']['inode'])
        changed=deepcopy(value);changed['mappingOriginal']['mappedFile']=actual
        with self.assertRaises(NativeUIError):source.validate(changed,os.getpid())
        self.assertEqual(value,source.validate(value,os.getpid()))
        self.assertTrue((root/'writer-original.bin').exists())

    def test_actual_partial_write_or_failed_atomic_commit_never_qualifies(self):
        for options in (dict(partial=True),dict(commit=False)):
            with self.subTest(options=options):
                _root,_path,value=self.originals(**options)
                with self.assertRaises(NativeUIError):source.validate(value,os.getpid())

    def test_static_mapping_copy_preserves_original_source_and_mapping_generation(self):
        _root,_path,value=self.originals();later=deepcopy(value)
        later['unitReadBefore']=clock();later['unitReadAfter']=clock()
        self.assertEqual(later,source.validate(later,os.getpid(),previous=value))
        self.assertEqual(value['mappingOriginal'],later['mappingOriginal'])
        changed=deepcopy(later);changed['mappingOriginal']['mappingId']=uuid.uuid4().hex
        with self.assertRaises(NativeUIError):source.validate(changed,os.getpid(),previous=value)

    def test_changed_mapped_bytes_or_foreign_process_cannot_use_a_good_old_chain(self):
        _root,_path,value=self.originals()
        with self.assertRaises(NativeUIError):source.validate(value,os.getpid()+1)
        for key in ('unitSha256','mappingOriginal'):
            changed=deepcopy(value)
            if key=='unitSha256':changed[key]='a'*64
            else:changed[key]['mappedSha256']='a'*64
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.validate(changed,os.getpid())

    def test_original_clocks_are_not_retimed_into_fresh_mapping_or_current_read(self):
        _root,_path,value=self.originals();changed=deepcopy(value)
        changed['mappingOriginal']['mapBefore']['epochMs']=1
        with self.assertRaises(NativeUIError):source.validate(changed,os.getpid())
        with self.assertRaises(NativeUIError):source.validate(value,os.getpid(),epoch=value['unitReadAfter']['epochMs']+2000)

    def test_partial_compiler_prefix_does_not_become_literal_direct_unit_or_installed_admission(self):
        _root,_path,value=self.originals();prefix=value['mappingOriginal']['writeOriginal']['compilerInput']
        from ios.adapters.chat_qml_sources import compiler_input
        with self.assertRaises(NativeUIError):compiler_input(prefix,os.getpid(),value['unitReadAfter']['epochMs'])
        self.assertEqual(value,source.observed_chain(value,os.getpid()))
        for claimed in ('importsComplete','installedQtSha256','requestedQtVersion','loadedRootQualified'):
            changed=deepcopy(value);changed[claimed]=True
            with self.subTest(claimed=claimed),self.assertRaises(NativeUIError):source.validate(changed,os.getpid())

    def test_missing_write_or_unknown_mapping_fields_remain_unavailable(self):
        _root,_path,value=self.originals();changed=deepcopy(value);changed['mappingOriginal']['writeOriginal']={}
        with self.assertRaises(NativeUIError):source.validate(changed,os.getpid())
        changed=deepcopy(value);changed['mappingOriginal']['cachePathSha256']='a'*64
        with self.assertRaises(NativeUIError):source.validate(changed,os.getpid())


if __name__=='__main__':unittest.main()
