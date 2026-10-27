"""Real physical-adapter/HTTP/AFC/IPA/binding composition; native SDK is modeled.

No source getter, decoder, binding result, journal or IPA-byte join is stubbed.
The existing native/OS/SDK producer fixtures remain explicit synthetic sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.ios import binding
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import appium_adapter,feature_observation,chat_qml_sources
from ios.self_tests import test_ios_installed_adapter as installed_fixture
from ios.self_tests import test_ios_qt_image_bytes as image_fixture
from ios.self_tests.chat_qml_cache_source_fixture import Boundary,RUN
from ios.self_tests.retained_host_roots import retain_owned_root


class ChatQmlCachePhysicalRuntimeTests(unittest.TestCase):
    def setUp(self):
        # Real original host IPA and separately read app-directory bytes, with
        # explicit modeled Mach-O/native-unit producer metadata.
        image=image_fixture.QtImageBytesTests();self.addCleanup(image.doCleanups)
        archive,_unused,digest,self.image=image.prepare()
        self.f=installed_fixture.InstalledAdapterTests();self.addCleanup(self.f.doCleanups);self.f.setUp()
        temporary=self.f.temp;retain_owned_root(temporary,expected_root=self.f.root)
        for index,(callback,args,kwargs) in enumerate(self.f._cleanups):
            if getattr(callback,'__self__',None) is temporary:self.f._cleanups[index]=(temporary.cleanup,args,kwargs)
        print('retained Chat physical composition root',self.f.root,flush=True)
        # Recreate the ordinary physical factory after selecting the real IPA.
        # Preserve the older fixture file; no previous binding was admitted.
        (self.f.root/'previous-unadmitted-fixture.ipa').write_bytes(self.f.artifact.read_bytes())
        self.f.artifact.write_bytes(archive.path.read_bytes())
        self.f.native.bundle=deepcopy(self.image['bundle'])
        self.f.summary.update(bundleIdentity=deepcopy(self.image['bundle']),runtime=dict(artifact='Overte.ipa'))
        self.f.summary['artifactIdentity']['artifactSha256']=digest
        self.f.target['serverUrl']='http://controlled.invalid:4723'
        self.f.adapter=binding.create_adapter(self.f.args,self.f.Base)
        self.f.adapter.describe('test-only')
        self.before=(self.f.sessions,self.f.launches)
        self.original_record=deepcopy(self.f.adapter._binding_store('test-only').read())
        self.boundary=Boundary(19000);self.afc=[];self.sdk=[];self.lost=False;self.sequence=0
        original_post=feature_observation.post_request.side_effect
        original_execute=self.f.adapter.client.execute

        def native_clock(value):
            # This is an independent native clock producer model, as in the
            # existing transport fixtures. No saved source receipt is retimed.
            def fields(row):
                if type(row) is dict:
                    for key,child in row.items():
                        if key.endswith('EpochMs'):row[key]=19000+self.boundary.time
                        else:fields(child)
                elif type(row) is list:
                    for child in row:fields(child)
            fields(value);value['processId']=42
        self.f.clock.mutate=native_clock

        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=chat_qml_sources.ACTION:return original_post(request,timeout)
            FixtureState().set_client_command(query);self.boundary.send(query);self.sequence+=1
            # New original produced inside this modeled native read interval.
            # Actual file/IPA bytes were obtained independently above.
            value=json.loads(self.boundary.raw);observed=deepcopy(self.image)
            observed.update(sequence=self.sequence,beforeEpochMs=value['clockBefore']['epochMs'],
                afterEpochMs=value['clockAfter']['epochMs'])
            value.update(iosChatQmlSourcesVersion=2,qtEntryImage=observed)
            self.boundary.raw=json.dumps(value)
            if self.lost:raise OSError('Declared lost original HTTP return after native read')
            raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()

        def read(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+chat_qml_sources.FILE):
                self.afc.append(values['remotePath'])
                return base64.b64encode(self.boundary.raw.encode()).decode()
            return original_execute(session,operation,values)

        def call(method,path,*args):
            self.assertEqual(('GET','/session/test-only'),(method,path));self.sdk.append((method,path));return {}
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))
        self.enterContext(patch.object(appium_adapter,'WebDriver',return_value=SimpleNamespace(call=call,execute=read)))

    def assert_owners_unchanged(self):
        self.assertEqual(self.before,(self.f.sessions,self.f.launches))
        self.assertEqual(self.original_record,self.f.adapter._binding_store('test-only').read())
        self.assertTrue(all(method=='GET' for method,_path in self.sdk))

    def test_real_physical_helper_reads_original_http_afc_and_binds_selected_original_ipa(self):
        value,result=self.f.adapter._chat_qml_cache_source('test-only',RUN)
        self.assertEqual(json.loads(self.boundary.raw),value)
        self.assertEqual(value['qtEntryImage'],result['original'])
        self.assertEqual(self.f.summary['artifactIdentity']['artifactSha256'],result['artifactSha256'])
        self.assertTrue(result['imageBytesBound'])
        self.assertFalse(result['qtSdkSourceAvailable']);self.assertFalse(result['importGraphAvailable']);self.assertFalse(result['aotGraphAvailable'])
        self.assertEqual((1,1),(len(self.boundary.queries),len(self.afc)))
        self.assert_owners_unchanged()

    def test_changed_installed_process_refuses_before_source_http_or_afc_without_new_session(self):
        self.f.process['pid']=43
        with self.assertRaises((ValueError,NativeUIError)):
            self.f.adapter._chat_qml_cache_source('test-only',RUN)
        self.assertEqual((0,0),(len(self.boundary.queries),len(self.afc)))
        self.assert_owners_unchanged()

    def test_lost_next_native_read_return_never_replays_or_returns_previous_good_source(self):
        original,_result=self.f.adapter._chat_qml_cache_source('test-only',RUN)
        self.lost=True
        with self.assertRaises((ValueError,NativeUIError)):
            self.f.adapter._chat_qml_cache_source('test-only',RUN)
        self.assertEqual((2,1),(len(self.boundary.queries),len(self.afc)))
        self.assertNotEqual(original['requestId'],self.boundary.queries[-1]['commandId'])
        self.assertEqual(2,len({query['commandId'] for query in self.boundary.queries}))
        self.assert_owners_unchanged()


if __name__=='__main__':unittest.main()
