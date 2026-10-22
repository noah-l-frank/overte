"""Normal Pico app controls with explicit SDK/Qt effect seams; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
import unittest
from unittest.mock import patch
import test_normal_scripts as sources
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_apps import project,same_reference,snapshot
from adapters.pico4.navigation import validate_snapshot

class PicoBrowserAppTests(unittest.TestCase):
    def setUp(self):
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.adapter,self.native=fixture.instance,fixture.native;self.native.opened=True;self.button=str(uuid.uuid4());self.lost=False;self.effect=0
        self.lock=self.adapter._script_journey()._lock(self.native.target)
        before_snapshot=self.native.snapshot;before_write=self.native.write_debug_app_file
        def capture():
            value=before_snapshot();row=dict(id='browser-app.web',buttonId=self.button,caption='WEB TEST',componentSourceSha256='a'*64,
                token=str(uuid.uuid5(uuid.NAMESPACE_URL,self.button)),enabled=True,focused=False,inputReady=True)
            value.update(picoBrowserAppControlsVersion=1,controls=[row]);return value
        def write(target,package,path,raw):
            call=json.loads(raw)
            if path!='files/overte-e2e/navigation-ui-command.json' or not call.get('controlId','').startswith('browser-app.'):
                return before_write(target,package,path,raw)
            self.native.inputs.append(deepcopy(call));self.native.sequence=call['sequence'];self.effect+=1
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=call['commandId'],sequence=call['sequence'],
                performed=True,error='',processId=123,updatedEpochMs=self.native.epoch_milliseconds(target))
            if self.lost:raise NativeUIError('Lost original app input return')
        for boundary in (patch.object(self.native,'snapshot',side_effect=capture),patch.object(self.native,'write_debug_app_file',side_effect=write)):
            boundary.start();self.addCleanup(boundary.stop)
        self.snapshot=capture
    def source(self,read_only=False):
        return self.adapter._browser_app_controls(self.native.target,source_lock=self.lock,read_only=read_only)
    def test_passive_tile_source_does_not_create_or_adopt_the_default_script_manager(self):
        from pathlib import Path
        manager_path=Path(self.adapter._script_paths(self.native.target)[0]);self.assertFalse(manager_path.exists())
        with self.lock.held():
            source=self.source(read_only=True);source.capture()
        self.assertFalse(manager_path.exists());self.assertEqual([],self.native.inputs)

    def test_actual_private_factory_uses_exact_root_lock_and_normal_single_pointer_command(self):
        with self.lock.held():
            source=self.source();original=source.capture();source.activate('browser-app.web',reference=original)
        self.assertEqual(1,self.effect);self.assertEqual(1,len(self.native.inputs));self.assertIs(self.lock,source.lock)
        self.assertEqual('activate',self.native.inputs[0]['action']);self.assertEqual(original['controls'][0]['token'],self.native.inputs[0]['controlToken'])
    def test_read_only_role_and_missing_lock_refuse_before_publication(self):
        with self.assertRaises((ValueError,RuntimeError)):self.source()
        with self.lock.held():
            source=self.source(read_only=True);original=source.capture()
            with self.assertRaises((ValueError,RuntimeError)):source.activate('browser-app.web',reference=original)
        self.assertEqual([],self.native.inputs)
    def test_replacement_button_uuid_cannot_recapture_original_reference(self):
        with self.lock.held():
            source=self.source();original=source.capture();self.button=str(uuid.uuid4())
            with self.assertRaises((ValueError,RuntimeError)):source.activate('browser-app.web',reference=original)
        self.assertEqual([],self.native.inputs)
    def test_lost_original_delivery_is_not_automatically_repeated(self):
        with self.lock.held():
            source=self.source();original=source.capture();self.lost=True
            with self.assertRaises((ValueError,RuntimeError)):source.activate('browser-app.web',reference=original)
        self.assertEqual(1,self.effect);self.assertEqual(1,len(self.native.inputs))
    def test_changed_candidate_is_refused_before_input(self):
        with self.lock.held():
            source=self.source();original=source.capture();self.native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):source.activate('browser-app.web',reference=original)
        self.assertEqual([],self.native.inputs)
    def test_native_dto_requires_version_actual_identity_and_closed_caption(self):
        original=self.snapshot();validate_snapshot(original,123,self.native.epoch_milliseconds(self.native.target))
        for key,value in (('caption','WEB'),('buttonId','0'*32),('componentSourceSha256','expected'),('inputReady',1)):
            bad=deepcopy(original);bad['controls'][0][key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,RuntimeError)):validate_snapshot(bad,123,self.native.epoch_milliseconds(self.native.target))
        bad=deepcopy(original);bad.pop('picoBrowserAppControlsVersion')
        with self.assertRaises((ValueError,RuntimeError)):validate_snapshot(bad,123,self.native.epoch_milliseconds(self.native.target))
    def test_full_reference_scope_and_control_are_not_replaced_by_similar_rows(self):
        original=project(self.snapshot())
        for edit in ('sequence','pid','epoch','row'):
            bad=deepcopy(original)
            if edit=='sequence':bad['scope']['sequence']+=1
            if edit=='pid':bad['scope']['processId']+=1
            if edit=='epoch':bad['scope']['elapsedMs']+=5001
            if edit=='row':bad['controls'][0]['componentSourceSha256']='b'*64
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):same_reference(original,bad,'browser-app.web')
if __name__=='__main__':unittest.main()
