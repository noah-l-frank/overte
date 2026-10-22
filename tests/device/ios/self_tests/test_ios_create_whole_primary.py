"""Composed Python/Node/file/PNG journey; native/device SDKs are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
import json
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.create_export_artifact import CreateExportArtifact
from feature_journeys.scenarios import SCENARIOS
from ios.self_tests.create_whole_fixture import ComposedCreate
from ios.self_tests.test_ios_create_state import RUN
from ios.self_tests.test_ios_create_files import BINDING


class CreateWholePrimaryTests(unittest.TestCase):
    def test_loaded_actual_node_marker_retirement_native_pointer_default_worker_and_original_pixels(self):
        fixture=ComposedCreate(self);fixture.scope.prepare();fixture.domain.paint();fixture.scope.admit_rendered()
        fixture.journal.activate(RUN,'2'*32,'cleanup',{})
        original=fixture.retirement.cleanup('2'*32)
        measured=fixture.retirement.validate_original(original)
        self.assertEqual([],measured['public']['resources']);self.assertFalse(fixture.domain.running)
        self.assertEqual(1,fixture.domain.io.actions.count('scripts.stop.0'))
        self.assertFalse(fixture.domain.files.root.exists());self.assertEqual([],measured['public']['state']['objects'])
        frozen=fixture.retirement.frozen();actual_before=deepcopy(fixture.pointer_native.requests)
        def forbidden(*_args,**_kwargs):raise AssertionError('Frozen Create validation called a native SDK')
        with patch.object(fixture.source,'capture',side_effect=forbidden),patch.object(fixture.scope,'capture',side_effect=forbidden):
            for sample in frozen.all_samples():sample.frame_owner.factory=forbidden
            self.assertEqual(measured,frozen.validate_original(original))
        self.assertEqual(actual_before,fixture.pointer_native.requests)
        # Preserve the actual private PNG/inode; a final proof must still fail
        # if its bytes are changed after a successful warm validation.
        path=fixture.before.frame_owner.root/fixture.before.frame_owner.name;path.write_bytes(b'foreign PNG')
        with self.assertRaises(NativeUIError):frozen.validate_original(original)

    def test_all_21_normal_create_steps_then_actual_whole_retirement_keep_every_original_owner(self):
        f=ComposedCreate(self);actions=f.prepare();accept=f.h.ah.ui.accept_file
        def exported(role,id_,directory,run):
            if role=='import':accept(role,id_,directory,run);f.product.selected()['position']=[0,1,-3];return
            selected=f.product.selected();row={key:deepcopy(selected[key]) for key in ('id','name','type','modelURL','textures')}
            row['dimensions']=dict(zip('xyz',selected['dimensions']))
            (f.h.ah.file_boundary.root/'export.json').write_text(json.dumps(dict(DataVersion=0,Entities=[row])));f.product.dismiss(role,id_)
        f.h.ah.ui.accept_file=exported
        def export(name):return CreateExportArtifact(PrivateFeatureState(f.root/name),f.lock,f.root,BINDING,RUN,lambda:True)
        f.history.export_resolver=export
        for index,step in enumerate(SCENARIOS['create']['steps']):
            query=f.h.ah.query(index);f.journal.activate(RUN,query['ticket'],query['verb'],query['inputs']);actions.act(query)
            sample=None;artifact=None
            if set(step['evidence']) & {'image','changed'}:
                f.render(query['ticket']);sample=f.sample('ios-'+format(index+100,'032x'))
            if 'file' in step['evidence']:artifact=export('ios-create-export-'+format(index+200,'032x')+'-artifact.json')
            value=f.history.capture(sample=sample,policy=getattr(f,'policy',None),export_artifact=artifact)
            self.assertEqual(step['state'],value['state'],step['verb'])
        f.journal.activate(RUN,'2'*32,'cleanup',{});original=f.retirement.cleanup('2'*32)
        measured=f.retirement.validate_original(original);self.assertEqual([],measured['public']['resources'])
        self.assertEqual(5,len(actions.state['owned']));self.assertFalse(f.items);self.assertEqual('retired',actions.files.state['phase'])
        self.assertEqual(1,sum(method=='POST' for method,_,_ in f.w3c));self.assertEqual(1,f.domain.io.actions.count('scripts.stop.0'))
        self.assertEqual(14,len(f.retirement.all_samples()));self.assertTrue(all(owner.frame_owner.store.read()['phase']=='released' for owner in f.retirement.all_samples()))


if __name__=='__main__':unittest.main()
