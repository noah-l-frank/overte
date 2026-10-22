"""Actual private host byte source; native file transport explicitly modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
import uuid
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_chunks as source
from snapshot_file_contract import CHUNK_BYTES,read_request
from fixture.serve import FixtureState

PREFIX='parity-'+'a'*16+'-still-png'


class SnapshotChunkTests(unittest.TestCase):
    def produce(self,raw):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);path=Path(folder.name)/(PREFIX+'-snap_1700000000000_1.png')
        path.write_bytes(raw);path.chmod(0o600);stat=path.stat()
        revision=hashlib.sha256(str((stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)).encode()).hexdigest()
        row=dict(name=path.name,size=stat.st_size,revision=revision,sha256=hashlib.sha256(raw).hexdigest());originals=[]
        with path.open('rb') as stream:
            for offset in range(0,max(1,len(raw)),source.CHUNK_BYTES):
                query=dict(schemaVersion=2,commandId='ios-'+uuid.uuid4().hex,action='snapshot-files',operation='read',prefix=PREFIX,
                    name=path.name,revision=revision,offset=offset,chunkBytes=source.CHUNK_BYTES)
                actual=stream.read(source.CHUNK_BYTES);after=os.fstat(stream.fileno());self.assertEqual(stat.st_ino,after.st_ino)
                packet=dict(schemaVersion=2,commandId=query['commandId'],operation='read',prefix=PREFIX,processId=42,sampleEpochMs=20000+offset,
                    ok=True,file=dict(name=path.name,revision=revision,size=stat.st_size,offset=offset,eof=offset+len(actual)==stat.st_size,
                    data=base64.b64encode(actual).decode()))
                originals.append(dict(query=query,packet=packet))
        return row,originals

    def test_actual_multichunk_bytes_are_identical_and_each_raw_packet_fits_existing_decoder(self):
        import json
        raw=bytes(range(256))*5000;row,originals=self.produce(raw)
        self.assertEqual(raw,source.original_bytes(row,PREFIX,originals,42));self.assertEqual(3,len(originals))
        for original in originals:
            encoded=json.dumps(original['packet']);self.assertLess(len(encoded.encode()),source.LIMIT)
            self.assertEqual(original['packet'],decode(encoded,limit=source.LIMIT))
        self.assertEqual(4*1024*1024,CHUNK_BYTES)
        legacy=dict(originals[0]['query']);legacy['schemaVersion']=1;legacy.pop('chunkBytes');self.assertEqual(legacy,read_request(legacy))

    def test_empty_original_has_one_actual_zero_byte_eof_and_real_whole_hash(self):
        row,originals=self.produce(b'');self.assertEqual(b'',source.original_bytes(row,PREFIX,originals,42))
        self.assertEqual(1,len(originals));self.assertTrue(originals[0]['packet']['file']['eof'])

    def test_missing_repeated_reordered_or_modified_actual_chunk_rejects_whole_hash(self):
        row,originals=self.produce(b'abcd'*200000)
        for fault in ('missing','duplicate','reverse','bytes','nonce','clock','revision','hash'):
            values=deepcopy(originals);expected=deepcopy(row)
            if fault=='missing':values.pop()
            elif fault=='duplicate':values[1]=deepcopy(values[0])
            elif fault=='reverse':values.reverse()
            elif fault=='bytes':values[0]['packet']['file']['data']=base64.b64encode(b'x'*source.CHUNK_BYTES).decode()
            elif fault=='nonce':values[1]['query']['commandId']=values[0]['query']['commandId'];values[1]['packet']['commandId']=values[0]['query']['commandId']
            elif fault=='clock':values[1]['packet']['sampleEpochMs']=1
            elif fault=='revision':expected['revision']='f'*64
            else:expected['sha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original_bytes(expected,PREFIX,values,42)

    def test_strict_version_chunk_size_eof_pid_and_canonical_base64(self):
        _row,originals=self.produce(b'a')
        for fault in ('size','version','extra','bool','eof','pid','base64','short'):
            value=deepcopy(originals[0]);query,packet=value['query'],value['packet']
            if fault=='size':query['chunkBytes']=1024*1024
            elif fault=='version':query['schemaVersion']=True
            elif fault=='extra':query['expectedBytes']='a'
            elif fault=='bool':packet['file']['offset']=False
            elif fault=='eof':packet['file']['eof']=False
            elif fault=='pid':packet['processId']=43
            elif fault=='base64':packet['file']['data']='YR=='
            else:packet['file']['data']=''
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):source.packet(packet,query,42)

    def test_actual_fixture_keeps_legacy_4mib_and_accepts_only_fixed_read_v2(self):
        _row,originals=self.produce(b'a');query=originals[0]['query'];fixture=FixtureState()
        self.assertEqual(query,fixture.set_client_command(query))
        old=dict(query,schemaVersion=1);old.pop('chunkBytes');self.assertEqual(old,fixture.set_client_command(old))
        invalid=[dict(query,chunkBytes=CHUNK_BYTES),dict(query,chunkBytes=True),dict(query,operation='list'),
            dict(query,schemaVersion=3),dict(query,expectedBytes='a'),dict(query,offset=True)]
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(ValueError):fixture.set_client_command(value)

    def test_actual_probe_claims_before_native_entry_and_never_resamples_an_unknown_nonce(self):
        _row,originals=self.produce(b'a');query=originals[0]['query']
        root=Path(__file__).resolve().parents[4];text=(root/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=text.index('        if (command && command.schemaVersion === 2 && command.action === "snapshot-files")')
        end=text.index('        if (command && command.schemaVersion === 1',start)
        program='''
let iosNewSourceRequests={},iosNewSourceRequestCount=0,calls=[];
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Test={iosSnapshotFilesRequest:q=>{calls.push(q);throw Error("actual queued return unknown");}};
function applyChunk(command) { BRANCH }
const q=QUERY;applyChunk(q);applyChunk(q);
applyChunk({...q,commandId:"ios-"+"f".repeat(32)});applyChunk(q);
if(calls.length!==2||JSON.stringify(calls[0])!==JSON.stringify(q))throw Error("nonce replay or changed command");
applyChunk({...q,commandId:"ios-"+"d".repeat(32),chunkBytes:4194304});
if(calls.length!==2)throw Error("unbounded version2 accepted");
'''.replace('BRANCH',text[start:end]).replace('QUERY',json.dumps(query))
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_afc_transport_and_closed_send_keep_raw_native_packet_unchanged(self):
        from unittest.mock import patch
        from ios.adapters import feature_observation
        from ios.self_tests.test_ios_snapshot_manifest import Files
        native=Files();observer=native.observer();_row,originals=self.produce(b'actual original bytes')
        query,value=originals[0]['query'],originals[0]['packet'];calls=[]
        def post(request,timeout):
            calls.append(native.fixture.set_client_command(json.loads(request.data)));native.echo=json.dumps(calls[-1]).encode()
            native.value=deepcopy(value);return native
        with patch.object(feature_observation,'post_request',post):
            observer.send(query)
            remote='@org.example.client:documents/owned-results/ios-snapshot-file-result.json'
            actual=decode(observer.original(remote=remote,limit=source.LIMIT),limit=source.LIMIT)
        self.assertEqual([query],calls);self.assertEqual(value,actual)
        self.assertEqual(b'actual original bytes',source.packet(actual,query,42))


if __name__=='__main__':unittest.main()
