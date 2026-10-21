"""Original screen/file and geometry SDK boundaries; no device or compiler."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.graphics_images import IOSGraphicsImages,capture_record
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters import feature_observation
from fixture.serve import FixtureState
from self_tests.test_completed_frame_lease import BINDING,RUN


class SDK:
    def __init__(self):
        self.clock=0.;self.calls=[];self.valid=True;self.error=False;self.native_offset=1700000000000+86400000
        stream=BytesIO();Image.new('RGB',(320,200),(20,60,140)).save(stream,format='PNG');self.raw=stream.getvalue()
        self.after=lambda:None
    def native(self):return self.native_offset+round(self.clock*1000)
    def host(self):return self.native()-86400000
    def call(self,method,path):
        self.calls.append((method,path));self.clock+=.05;self.after()
        if self.error:raise OSError('Synthetic lost SDK result')
        return base64.b64encode(self.raw).decode()
    def images(self,store,root,**options):
        return IOSGraphicsImages(store,root,BINDING,RUN,'primary',0,self,self.native,lambda:self.valid,
                                 epoch_ms=self.host,monotonic=lambda:self.clock,**options)


class ImagesTests(unittest.TestCase):
    def test_original_png_host_native_times_and_private_inode_are_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'images.json');b=SDK();images=b.images(store,root)
            row,raw=images.capture('e'*32);packet=row['capture']
            self.assertEqual(raw,b.raw);self.assertEqual(raw,(root/row['name']).read_bytes())
            self.assertEqual(86400000,packet['nativeBeforeMs']-packet['hostBeginEpochMs'])
            self.assertNotIn('capturedEpochMs',packet);self.assertNotIn('frameId',packet)
            self.assertEqual([('GET','/session/owned-session/screenshot')],b.calls)
            self.assertEqual(row,unpack(store.read()['transcript'])[0]);self.assertEqual(raw,b.images(store,root).archive(row['nonce']))
            self.assertTrue(b.images(store,root).cleanup());self.assertFalse((root/row['name']).exists())
            self.assertTrue(b.images(store,root).cleanup());self.assertIsNotNone(store.read())

    def test_missing_or_corrupt_screenshot_does_not_retry_and_retains_cleanup_ownership(self):
        for fault in ('lost','truncated','jpeg'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                root=Path(root);store=PrivateFeatureState(root/'images.json');b=SDK()
                if fault=='lost':b.error=True
                elif fault=='truncated':b.raw=b.raw[:-10]
                else:b.raw=b'JPEG'
                with self.assertRaises(NativeUIError):b.images(store,root).capture('e'*32)
                with self.assertRaises(NativeUIError):b.images(store,root).capture('e'*32)
                self.assertEqual(1,len(b.calls));row=unpack(store.read()['transcript'])[0]
                self.assertEqual('opened',row['phase']);self.assertIsNone(row['capture']);self.assertTrue(b.images(store,root).cleanup())

    def test_changed_process_late_capture_clock_jump_and_clock_regression_are_not_success(self):
        for fault in ('process','late','wall','backwards','native'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                root=Path(root);store=PrivateFeatureState(root/'images.json');b=SDK();images=b.images(store,root)
                if fault=='process':b.after=lambda:setattr(b,'valid',False)
                elif fault=='late':b.after=lambda:setattr(b,'clock',2.)
                elif fault=='wall':b.after=lambda:setattr(images,'epoch_ms',lambda:b.host()+1000)
                elif fault=='backwards':b.after=lambda:setattr(b,'clock',-.1)
                else:b.after=lambda:setattr(b,'native_offset',b.native_offset-1000)
                with self.assertRaises(NativeUIError):images.capture('e'*32)
                self.assertEqual(1,len(b.calls));self.assertIsNotNone(store.read())

    def test_replaced_file_cannot_be_read_or_deleted_and_wrong_capture_digest_fails(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'images.json');b=SDK();row,raw=b.images(store,root).capture('e'*32)
            with self.assertRaises(NativeUIError):capture_record(row['capture'],raw+b'x')
            path=root/row['name'];path.rename(root/'kept-original.png');path.write_bytes(b'foreign');path.chmod(0o600)
            with self.assertRaises(NativeUIError):b.images(store,root).archive(row['nonce'])
            with self.assertRaises(NativeUIError):b.images(store,root).cleanup()
            self.assertEqual(b'foreign',path.read_bytes());self.assertEqual('saved',unpack(store.read()['transcript'])[0]['phase'])

    def test_failed_persistence_prevents_screenshot_and_foreign_scope_cannot_adopt(self):
        class Failing(PrivateFeatureState):
            def write(self,*_):raise OSError('Synthetic persistence failure')
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);b=SDK()
            with self.assertRaises(NativeUIError):b.images(Failing(root/'failed.json'),root).capture('e'*32)
            self.assertEqual([],b.calls)
            store=PrivateFeatureState(root/'images.json');b.images(store,root).capture('e'*32)
            images=b.images(store,root);images.role='actor'
            with self.assertRaises(NativeUIError):images.cleanup()
            self.assertEqual(1,len(b.calls))


class GeometryTests(unittest.TestCase):
    def source(self):
        b=SDK();b.sent=[];b.receipt=None
        def send(command):
            b.sent.append(deepcopy(command));b.receipt=dict(schemaVersion=1,commandId=command['commandId'],observation=dict(
                schemaVersion=1,sampleEpochMs=b.native(),sampleSequence=1,
                nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,safeInsetLeft=0,safeInsetRight=0,
                              safeInsetTop=20,safeInsetBottom=20,density=2,keyboardVisible=False),window=dict(width=1024,height=728)))
        reader=OriginalGeometry(send,lambda:json.dumps(b.receipt),b.native,lambda:b.valid,monotonic=lambda:b.clock,sleep=lambda s:None)
        return b,reader

    def test_existing_command_uses_original_native_time_under_host_clock_skew(self):
        b,reader=self.source();value=reader.capture();self.assertEqual(b.receipt,value)
        self.assertEqual(1,len(b.sent));self.assertEqual('native-geometry-snapshot',b.sent[0]['action'])
        self.assertGreater(value['observation']['sampleEpochMs'],b.host()+80000000)

    def test_stale_or_foreign_geometry_and_lost_binding_fail_without_command_replay(self):
        for fault in ('stale','foreign','rotation','process','version'):
            b,reader=self.source();original=reader.send
            def changed(command):
                original(command)
                if fault=='stale':b.receipt['observation']['sampleEpochMs']-=2000
                elif fault=='foreign':b.receipt['commandId']='ios-'+'f'*32;b.clock=2
                elif fault=='rotation':b.receipt['observation']['window']['height']=1024
                elif fault=='version':b.receipt['schemaVersion']=True
                else:b.valid=False
            reader.send=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.capture()
            self.assertEqual(1,len(b.sent));self.assertIsNone(reader.last)

    def test_canonical_factory_uses_existing_closed_http_afc_and_process_binding(self):
        b,original=self.source();b.pid=42;b.paths=[];fixture=FixtureState()
        target=dict(platform='ios',physical=True,appId='org.example.client',probe={'kind':'ios-documents'},
                    testBuild=dict(fixtureOrigin='http://controlled.invalid:49121',resultsDirectory='owned-results'))
        class HTTP:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def read(self,limit):return json.dumps(b.sent[-1]).encode()[:limit]
        def post(request,timeout):
            command=fixture.set_client_command(json.loads(request.data));original.send(command);return HTTP()
        def execute(session,operation,arguments):
            self.assertEqual('owned-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/ios-ui-request-result.json'},arguments)
            b.paths.append(deepcopy(arguments));return base64.b64encode(json.dumps(b.receipt).encode()).decode()
        b.execute=execute
        source=feature_observation.FeatureObservation(b,'owned-session',target,
            lambda:dict(bundleId=target['appId'],pid=b.pid,foreground=True),epoch_ms=b.native,monotonic=lambda:b.clock,sleep=lambda _:None)
        with patch.object(feature_observation,'post_request',side_effect=post):
            value=source.geometry().capture()
        self.assertEqual(b.receipt,value);self.assertEqual(1,len(b.paths));self.assertEqual(1,len(b.sent))
        def lost(request,timeout):
            response=post(request,timeout);b.pid=43;return response
        with patch.object(feature_observation,'post_request',side_effect=lost),self.assertRaises(NativeUIError):
            source.geometry().capture()
        self.assertEqual(1,len(b.paths));self.assertEqual(2,len(b.sent))


if __name__=='__main__':unittest.main()
