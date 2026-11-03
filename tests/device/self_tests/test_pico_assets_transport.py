"""Actual Pico Assets factory transport cap; Native/SDK identity are models.

Only execute is replaced at the original AdbTransport write boundary. No ADB,
compiler, native product process or Domain is invoked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from adb_transport import AdbTransport
from adapters.normal_ui import NativeUIError
from self_tests.pico_assets_prefix_fixture import AssetsPrefixModel
import test_normal_scripts as normal


class AssetsCanonicalTransportTests(unittest.TestCase):
    def test_actual_factory_stage_hits_original_generic_cap_before_execute(self):
        fixture=normal.PicoNormalScriptsTests(methodName='runTest');fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root=Path(tempfile.mkdtemp(prefix='pico-assets-transport-'));root.chmod(0o700)
        temporary=fixture.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        (root/'canonical-original-root.txt').write_text(temporary.name+'\n')
        model=AssetsPrefixModel(self,root,fixture,manual_owner=False)
        fields=model.activate('upload',{'resource':'gltf-bundle/main.gltf'})
        writes=[];errors=[];execute=Mock(side_effect=AssertionError('No SDK process may execute'))
        def original_write(target,package,path,raw):
            writes.append(dict(package=package,path=path,bytes=len(raw.encode()),command=json.loads(raw)))
            try:return AdbTransport.write_debug_app_file(model.native,target,package,path,raw)
            except Exception as error:errors.append(str(error));raise
        with model.lock.held():
            files=model.adapter._assets_file_owner(model.native.target,model.run,fields['ticket'],model.url,stage=2)
            with patch.object(model.native,'write_debug_app_file',side_effect=original_write), \
                    patch.object(model.native,'_validate_debug_app_file',AdbTransport._validate_debug_app_file,create=True), \
                    patch.object(model.native,'execute',execute,create=True):
                with self.assertRaises(NativeUIError):
                    files.native.request('stage',model.run,files.state['ownerToken'],files.inputs)
        self.assertEqual(1,len(writes));self.assertEqual('stage',writes[0]['command']['operation'])
        self.assertGreater(writes[0]['bytes'],16384);self.assertLessEqual(writes[0]['bytes'],61440)
        self.assertTrue(any('invalid or oversized' in error for error in errors));execute.assert_not_called()
        self.assertEqual([],files.native.history);self.assertEqual([],model.calls)
        result=dict(canonicalFactory=True,originalAdbTransport=True,stageBytes=writes[0]['bytes'],
            genericLimit=16384,nativeLimit=61440,executeCalls=execute.call_count,
            expectedRefusal=True,nativeQualified=False,wholeCommonQualified=False,errors=errors)
        (root/'canonical-stage-cap.json').write_text(json.dumps(result,indent=2)+'\n')
        print('Retained canonical stage cap counter:',root,flush=True)


if __name__=='__main__':unittest.main()
