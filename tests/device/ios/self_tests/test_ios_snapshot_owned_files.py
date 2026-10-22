"""No-build owned-file protocol checks with actual files and host weak functors.

The native boundary is modeled; these checks do not compile or qualify iOS.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
import uuid
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import snapshot_owned_files as source,feature_observation
from ios.self_tests.test_ios_feature_observation import Native as Transport
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32
PREFIX='parity-'+RUN[:16]+'-still-png'


def query():return dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+uuid.uuid4().hex,runId=RUN)


def list_query():return dict(schemaVersion=1,action='snapshot-files',commandId='ios-'+uuid.uuid4().hex,operation='list',prefix=PREFIX)


class Token:pass


class Owned:
    """Explicit modeled native ledger using real retained host closures/files."""
    def __init__(self,root):
        self.root=root;self.now=10000;self.sequence=0;self.jobs={};self.files={};self.prefixes=[]
    def tick(self):self.now+=1;return self.now
    def clock(self):return dict(epochMs=self.tick(),monotonicMs=self.now-10000)
    def admit(self,empty=True):
        self.prefixes=[dict(prefix=PREFIX,query=list_query(),sampleEpochMs=self.tick(),initiallyEmpty=empty)]
    def capture(self):
        path=self.root/(PREFIX+'-snap_1_1.png');born=self.tick();path.write_bytes(b'actual captured host bytes')
        stat=path.stat();data=path.read_bytes();revision=hashlib.sha256(str((stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_nlink)).encode()).hexdigest()
        row=dict(name=path.name,revision=revision,sha256=hashlib.sha256(data).hexdigest(),size=len(data))
        file=dict(id=uuid.uuid4().hex,prefix=PREFIX,file=row,capture=dict(pathObservedEpochMs=self.tick(),phase='complete',fileName=path.name,
            captureInstance=uuid.uuid4().hex,requestId='snap_1_1',bornEpochMs=born,terminal='complete',nativeDrained=True),
            manifestQuery=list_query(),observedEpochMs=self.tick(),removeCommandId='')
        self.files[file['id']]=file;return file
    def queued(self,file):
        command=dict(schemaVersion=1,action=source.REMOVE,commandId='ios-'+uuid.uuid4().hex,runId=RUN,
            fileId=file['id'],manifestCommandId=file['manifestQuery']['commandId']);source.remove_command(command)
        token=Token();row=dict(query=command,queuedEpochMs=self.tick(),enteredEpochMs=None,returnedEpochMs=None,
            finallyEpochMs=None,expiredEpochMs=None,alive=True,result=None)
        self.jobs[command['commandId']]=(weakref.ref(token),row);file['removeCommandId']=command['commandId']
        def body():
            held=token;row['enteredEpochMs']=self.tick();path=self.root/file['file']['name']
            stat=path.lstat();data=path.read_bytes()
            valid=not path.is_symlink() and stat.st_nlink==1 and hashlib.sha256(data).hexdigest()==file['file']['sha256']
            if valid:path.unlink()
            row['result']=dict(ok=valid,unlinkIssued=valid,sampleEpochMs=self.tick())
            if not valid:row['result']['error']='snapshot-cleanup-original-changed'
            row['returnedEpochMs']=self.tick();row['finallyEpochMs']=self.tick()
        return command,body
    def read(self,q=None):
        q=q or query();self.sequence+=1;before=self.clock();jobs=[]
        for weak,row in self.jobs.values():
            if weak() is None and row['expiredEpochMs'] is None:row['expiredEpochMs']=self.tick()
            jobs.append(dict(deepcopy(row),alive=weak() is not None))
        return dict(iosSnapshotOwnedFilesVersion=1,requestId=q['commandId'],runId=RUN,instance='b'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-snapshot-owned-files',clockBefore=before,clockAfter=self.clock(),source=dict(complete=True,
            prefixes=deepcopy(self.prefixes),files=sorted(deepcopy(list(self.files.values())),key=lambda r:r['id']),
            jobs=sorted(jobs,key=lambda r:r['query']['commandId'])))


class SnapshotOwnedFiles(unittest.TestCase):
    def test_actual_retained_functor_blocks_retirement_after_unlink_and_normal_return(self):
        with tempfile.TemporaryDirectory() as directory:
            native=Owned(Path(directory));native.admit();file=native.capture();before=native.read();command,body=native.queued(file)
            body();self.assertFalse((native.root/file['file']['name']).exists());held=native.read()
            source.validate(held,dict(query(),commandId=held['requestId']),42,previous=before)
            with self.assertRaises(NativeUIError):source.removed(held,command,42)
            retained=body;del body
            with self.assertRaises(NativeUIError):source.removed(native.read(),command,42)
            del retained;ended=native.read();fact=source.removed(ended,command,42)
            self.assertTrue(fact['independentAbsenceRequired']);self.assertTrue(fact['quietWindowRequired'])
            source.validate(ended,dict(query(),commandId=ended['requestId']),42,previous=held)

    def test_native_success_cannot_override_preexisting_foreign_capture_or_wrong_original_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            native=Owned(Path(directory));native.admit();file=native.capture();q,body=native.queued(file);body();del body;original=native.read()
            for fault in ('preexisting','old-capture','manifest','foreign-prefix','pid','not-drained','capture-held','no-finally','no-return','not-unlinked','failed','missing-job'):
                value=deepcopy(original);owned=value['source']['files'][0];job=value['source']['jobs'][0]
                if fault=='preexisting':value['source']['prefixes'][0]['initiallyEmpty']=False
                elif fault=='old-capture':owned['capture']['bornEpochMs']=value['source']['prefixes'][0]['sampleEpochMs']-1
                elif fault=='manifest':owned['manifestQuery']['commandId']='ios-'+'f'*32
                elif fault=='foreign-prefix':owned['prefix']=PREFIX.replace('a','c',1)
                elif fault=='pid':value['processId']=43
                elif fault=='not-drained':job['alive']=True;job['expiredEpochMs']=None
                elif fault=='capture-held':owned['capture']['nativeDrained']=False
                elif fault=='no-finally':job['finallyEpochMs']=None
                elif fault=='no-return':job['returnedEpochMs']=None
                elif fault=='not-unlinked':job['result']['unlinkIssued']=False
                elif fault=='failed':job['result'].update(ok=False,error='original-changed')
                else:value['source']['jobs']=[]
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.removed(value,q,42)

    def test_actual_write_attempt_can_own_a_partial_file_after_failed_terminal_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            native=Owned(Path(directory));native.admit();file=native.capture()
            path=native.root/file['file']['name'];path.write_bytes(b'partial failed native image output')
            file['file'].update(size=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            file['capture'].update(phase='save-attempt',terminal='error')
            q,body=native.queued(file);body();del body
            self.assertFalse(path.exists());source.removed(native.read(),q,42)

    def test_actual_changed_file_or_extra_hardlink_cannot_be_retired_as_removed(self):
        for fault in ('changed','hardlink'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                native=Owned(Path(directory));native.admit();file=native.capture();q,body=native.queued(file)
                path=native.root/file['file']['name']
                if fault=='changed':path.write_bytes(b'foreign replacement bytes')
                else:(native.root/'retained-user-link').hardlink_to(path)
                body();del body;self.assertTrue(path.exists())
                with self.assertRaises(NativeUIError):source.removed(native.read(),q,42)

    def test_history_preserves_originals_and_never_forgets_or_resurrects_work(self):
        with tempfile.TemporaryDirectory() as directory:
            native=Owned(Path(directory));native.admit();file=native.capture();q,body=native.queued(file);body();del body
            before=native.read();after=native.read()
            source.validate(after,dict(query(),commandId=after['requestId']),42,previous=before)
            for fault in ('file','prefix','job','capture','row','result','resurrection','rebind'):
                value=deepcopy(after)
                if fault=='file':value['source']['files']=[];value['source']['jobs']=[]
                elif fault=='prefix':value['source']['prefixes'][0]['query']['commandId']='ios-'+'e'*32
                elif fault=='job':value['source']['jobs']=[];value['source']['files'][0]['removeCommandId']=''
                elif fault=='capture':value['source']['files'][0]['capture']['captureInstance']='f'*32
                elif fault=='row':value['source']['files'][0]['file']['sha256']='f'*64
                elif fault=='result':value['source']['jobs'][0]['result']['sampleEpochMs']+=1
                elif fault=='resurrection':value['source']['jobs'][0].update(alive=True,expiredEpochMs=None)
                else:value['instance']='e'*32
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,dict(query(),commandId=value['requestId']),42,previous=before)

    def test_actual_fixture_and_probe_reject_wire_paths_and_never_repeat_uncertain_removal(self):
        fixture=FixtureState();q=query();self.assertEqual(q,fixture.set_client_command(q))
        remove=dict(q,commandId='ios-'+uuid.uuid4().hex,action=source.REMOVE,fileId='c'*32,manifestCommandId='ios-'+'d'*32)
        self.assertEqual(remove,fixture.set_client_command(remove))
        for extra in ({'path':'/arbitrary/user.png'},{'expectedRemoved':True},{'file':{}},{'schemaVersion':True}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):fixture.set_client_command(remove|extra)
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,reads=0,files=[];const original={requestId:QUERY.commandId,source:{actual:"unchanged"}};
const Test={iosSnapshotRemoveFileRequest:q=>{calls++;throw Error("lost after queue");},
 featureIOSSnapshotOwnedFiles:q=>{reads++;return {...original,requestId:q.commandId};},saveObject:(v,n)=>files.push({v,n})};
SOURCE
const q=QUERY,r=REMOVE;applyClientCommand(r);applyClientCommand(r);
applyClientCommand(q);applyClientCommand(q);applyClientCommand(r);
if(calls!==1||reads!==1||files.length!==2)throw Error("native repeated");
if(files[0].v.accepted!==false||files[0].v.ok!==undefined)throw Error("ACK forged result");
if(files[1].v.source.actual!=="unchanged")throw Error("source relabeled");
delete Test.featureIOSSnapshotOwnedFiles;applyClientCommand({...q,commandId:"ios-"+"e".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("forged absent source");
'''.replace('QUERY',json.dumps(q)).replace('REMOVE',json.dumps(remove)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_real_factory_afc_keeps_original_native_packet(self):
        transport=Transport();observer=transport.observer();native=Owned(Path('/unused'));native.admit();calls=[]
        def post(request,timeout):
            q=transport.fixture.set_client_command(json.loads(request.data));calls.append(q);transport.echo=json.dumps(q).encode()
            transport.value=native.read(q);return transport
        def execute(session,operation,arguments):
            import base64
            self.assertEqual('mobile: pullFile',operation);self.assertTrue(arguments['remotePath'].endswith('/'+source.FILE))
            return base64.b64encode(json.dumps(transport.value).encode()).decode()
        transport.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=native.now))
        with patch.object(feature_observation,'post_request',post):packet=observer.snapshot_owned_files(clock).read(RUN)
        self.assertEqual(transport.value,packet);self.assertEqual(1,len(calls))

    def test_native_authority_comes_only_from_actual_status_and_native_list_operands(self):
        root=Path(__file__).resolve().parents[4]
        capture=(root/'interface/src/ui/Snapshot.cpp').read_text();ledger=(root/'tests/device/native/IOSSnapshotOwnedFilesObservation.h').read_text()
        storage=(root/'ios/ui/IOSSnapshotFiles.cpp').read_text();caller=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        self.assertIn('filePublished(capture,phase,path)',capture)
        self.assertIn('fileAttempted(snapshotFullPath)',capture)
        self.assertIn('fileAttempted(path)',(root/'interface/src/ui/SnapshotAnimated.cpp').read_text())
        self.assertIn('observed(request,result,storage)',caller);self.assertIn('Body body(responsibility)',caller)
        self.assertIn('std::weak_ptr<Token> actual',ledger);self.assertIn('if (!admission.empty) {return;}',ledger)
        self.assertIn('allReadJobsRetired()',ledger);self.assertIn('original.keys()!=fields',storage)
        self.assertIn('inspect(directory.value,name)!=original',storage);self.assertIn('::unlinkat(directory.value,encoded.constData(),0)',storage)
        self.assertNotIn('removeRecursively',storage)


if __name__=='__main__':unittest.main()
