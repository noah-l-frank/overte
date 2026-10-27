"""Existing JS probe/AFC-format precision seam, not native Qt/V8 execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64,json,subprocess,unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import chat_qml_sources as source
from ios.self_tests.chat_qml_cache_source_fixture import cache_packet,unit,RUN
from self_tests.test_native_feature_observation import probe_source
from ios.self_tests import test_ios_qt_image_bytes as image_fixture


class ChatQmlWireTests(unittest.TestCase):
    def test_actual_probe_preserves_uint64_decimal_ids_and_bounded_number_fields(self):
        case=image_fixture.QtImageBytesTests();self.addCleanup(case.doCleanups)
        _archive,_binding,_digest,image=case.prepare()
        value=cache_packet(19000);value.update(iosChatQmlSourcesVersion=2,qtEntryImage=image)
        value['clockAfter'].update(epochMs=20003,monotonicMs=1003)
        maximum=str(2**64-1);image.update(fileDevice=maximum,fileInode=maximum)
        for position in ('cacheAtLoad','cacheAtRead'):
            mapped=value['source'][position]['unit']['mappingOriginal']
            for file in (mapped['mappedFile'],mapped['writeOriginal']['fileBefore'],mapped['writeOriginal']['fileCommitted']):
                file.update(device=maximum,inode=maximum)
            mapped['mappingSequence']=1000000000;mapped['writeOriginal']['writeSequence']=1000000000
        query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId=RUN)
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const native=PACKET;let saved=null;
const Test={featureIOSChatQmlSources:q=>({...native,requestId:q.commandId}),saveObject:(v,f)=>{if(f!=="feature-ios-chat-qml-sources.json")throw Error("wrong original file");saved=v}};
SOURCE
applyClientCommand(QUERY);process.stdout.write(JSON.stringify(saved));
'''.replace('PACKET',json.dumps(value)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
        afc=base64.b64encode(result.stdout.encode());original=json.loads(base64.b64decode(afc))
        expected=dict(value,requestId=query['commandId']);self.assertEqual(expected,original)
        self.assertIsInstance(unit(original)['mappingOriginal']['mappedFile']['inode'],str)
        source.original(original)

    def test_numeric_or_rounded_filesystem_ids_never_become_a_valid_original(self):
        for value in (2**53,2**64-1,float(2**64-1),'018446744073709551615'):
            original=cache_packet();unit(original)['mappingOriginal']['mappedFile']['inode']=value
            with self.subTest(value=repr(value)),self.assertRaises(NativeUIError):source.original(original)


if __name__=='__main__':unittest.main()
