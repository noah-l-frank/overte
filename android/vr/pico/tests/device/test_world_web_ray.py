"""Original native world geometry and bounded normal controller input, no device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_create_polyvox_controls_native import original
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_world_browser_ray import WorldBrowserRayTests,WorldBoundary,RUN,URL,OWNER,VIEW
from adapters.pico4.browser_source import validate
from adapters.script_journey.lock import ScriptSourceLock


class WorldWebNativeRayTests(unittest.TestCase):
    def test_original_provider_raypick_and_renderer_map_actual_qt_item_transform_and_dpi_cap(self):
        prefix=Path(os.environ['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment=dict(os.environ,PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Quick'],text=True,env=environment))
        evidence=os.environ.get('OVERTE_WORLD_WEB_RAY_EVIDENCE')
        if evidence:
            evidence=Path(evidence);info=evidence.lstat()
            self.assertTrue(evidence.is_dir() and not evidence.is_symlink())
            self.assertEqual(0o700,info.st_mode & 0o777);self.assertEqual(os.getuid(),info.st_uid)
            self.assertEqual([],list(evidence.iterdir()))
        sources=[ROOT/name for name in (
            'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp',
            'libraries/entities-renderer/src/RenderableWebEntityItem.cpp','interface/src/raypick/RayPick.cpp',
            'tests/device/native/PicoWorldWebRay.h','tests/device/native/NormalControlUi.h','tests/device/adapters/pico4/world_browser_ray.py',
            'tests/device/adapters/pico4/browser_source.py','tests/device/self_tests/test_pico_world_browser_ray.py',
            'android/vr/pico/tests/device/world-web-ray-native.cpp','android/vr/pico/tests/device/test_world_web_ray.py')]
        signatures={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
        with tempfile.TemporaryDirectory(prefix='world-web-original-') as temporary:
            stage=Path(temporary)
            bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
            renderer=(ROOT/'libraries/entities-renderer/src/RenderableWebEntityItem.cpp').read_text()
            raypick=(ROOT/'interface/src/raypick/RayPick.cpp').read_text()
            constants='\n'.join(line for line in renderer.splitlines() if line.startswith(('static int MAX_WINDOW_SIZE =','const float METERS_TO_INCHES =')))
            controls=(ROOT/'tests/device/native/NormalControlUi.h').read_text()
            hit_test='namespace overte::e2e { class NormalControlUi {public:\n'+original(controls,'static QRectF visibleRect(')+'\n'+original(controls,'static bool ownsPoint(')+'\n};}'
            bodies=[constants,hit_test,original(bridge,'bool effectiveVisible('),original(bridge,'void installWorldWebRayProvider() {'),
                original(renderer,'glm::vec2 WebEntityRenderer::getWindowSize('),
                original(renderer,'void WebEntityRenderer::handlePointerEventAsTouch('),
                original(raypick,'glm::vec2 RayPick::projectOntoXYPlane(')]
            (stage/'actual-world-ray.inc').write_text('\n'.join(bodies))
            subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
                '-I'+str(ROOT),'-I'+str(stage),'-isystem',os.environ['OVERTE_TEST_GLM_INCLUDE'],
                str(HERE/'world-web-ray-native.cpp'),'-L'+str(prefix/'usr/lib64'),'-o',str(stage/'test'),*flags],env=environment,check=True,timeout=90)
            result=subprocess.run([str(stage/'test'),str(stage/'originals.json')],env=environment,capture_output=True,text=True,timeout=15)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            self.assertIn('PASS original world ray provider',result.stdout)
            raw=(stage/'originals.json').read_bytes();rays=json.loads(raw);self.assertEqual(3,len(rays))
            self.assertEqual(signatures,{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources})
            if evidence:
                (evidence/'native-originals.json').write_bytes(raw)
                (evidence/'actual-world-ray.inc').write_bytes((stage/'actual-world-ray.inc').read_bytes())
                (evidence/'source-manifest.json').write_text(json.dumps(signatures,sort_keys=True,indent=2)+'\n')
                (evidence/'native-output.txt').write_text(result.stdout+result.stderr)
                for path in evidence.iterdir():path.chmod(0o600)
            # Feed the literal C++ output through the production consumer. The
            # Android DOM is an explicit seam, independently validated below.
            boundary=WorldBoundary(ScriptSourceLock(stage/'script-sources.lock'))
            for index,ray in enumerate(rays):
                boundary.epoch=ray['capturedEpochMs'];call=dict(schemaVersion=1,commandId='1'*32,action='pico-world-web',
                    operation='measure-ray',runId=RUN,fixtureUrl=URL,ownerToken=OWNER,control='bridge',
                    **{k:VIEW[k] for k in ('handle','creation','grant','page')})
                boundary.send(call);packet=deepcopy(boundary.packet);packet['source']['worldRay']=ray
                validate(packet,call,123,packet['capturedEpochMs'])
                bad=deepcopy(packet);bad['source']['worldRay']['worldPoint'][0]+=.1
                with self.assertRaises((ValueError,RuntimeError)):validate(bad,call,123,packet['capturedEpochMs'])


class WorldWebRayFactoryTests(unittest.TestCase):
    def test_actual_private_factory_uses_existing_session_and_same_original_lock_without_claiming_feature(self):
        import test_normal_scripts as original
        from adapters.pico4.browser_source import FILE
        from openxr_input.adapter_session import PicoOpenXrAdapterSession
        from self_tests.test_pico_openxr_adapter_session import FakeTransport
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        adapter,native=h.instance,h.native;lock=adapter._script_journey()._lock(native.target)
        boundary=WorldBoundary(lock);transport=FakeTransport()
        session=PicoOpenXrAdapterSession(transport,native.target,lock.path.parent);session.begin(native.identity)
        saved_write,saved_read=native.write_debug_app_file,native.read_debug_app_file
        def write(target,package,path,raw):
            call=json.loads(raw)
            if call.get('action')!='pico-world-web':return saved_write(target,package,path,raw)
            boundary.epoch=native.epoch_milliseconds(target);boundary.send(call)
            boundary.packet['processId']=int(native.identity.split(':')[0])
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return saved_read(target,package,path,**options)
            self.assertEqual({'attempts':1},options);return json.dumps(boundary.packet)
        intents=[];streams=[];publishes=[]
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read), \
                patch.object(adapter,'require_pico_session_identity',return_value=native.identity),patch.object(adapter,'pico_input_session',return_value=session):
            with lock.held():
                click=adapter._world_browser_click(native.target,source_lock=lock,intent=intents.append,
                    stream_intent=streams.append,before_publish=publishes.append)
                self.assertIs(click.io.lock,lock);self.assertEqual([],transport.envelopes)
                actor=adapter._browser_originals(native.target,source_lock=lock,tablet=False)
                self.assertIs(actor.lock,lock);self.assertTrue(actor.read_only)
                self.assertTrue(click.click(RUN,URL,OWNER,VIEW,'bridge')['performed'])
            self.assertEqual(1,len(transport.envelopes));self.assertEqual(streams,publishes)
            self.assertEqual(1,len(intents));self.assertEqual([],native.inputs)
            self.assertNotIn('feature.world-web.act',adapter.capabilities(native.target))


if __name__=='__main__':unittest.main()
