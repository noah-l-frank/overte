"""Actual temp export bytes/native stat originals and selected-renderer joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.create_export import exported
from ios.adapters.create_files import OwnedCreateFiles
from ios.self_tests.test_ios_create_files import Boundary,BINDING,RUN,URL,TICKET
from ios.self_tests.test_ios_create_state import packet,version2,add_model,add_editor,remap,ID,EPOCH


class CreateExportTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.sdk=Boundary(self.root)
        self.model=packet();row=add_model(self.model);add_editor(self.model,selected=[ID]);version2(self.model);remap(row)
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def fixtures(self,mutation=None):
        owner=OwnedCreateFiles(self.sdk.native(),PrivateFeatureState(self.root/'ios-create-files.json'),BINDING,RUN,URL,lock=self.lock)
        owner.reserve(TICKET);owner.stage();before=deepcopy(owner.state['originals'][-1]);native=deepcopy(self.model['source']['entities'][0])
        # Explicit product-export SDK seam: output is made from actual selected
        # native model properties. The adapter never writes export.json.
        entity={key:native[key] for key in ('id','name','type','modelURL','textures')};entity['dimensions']=dict(zip('xyz',native['dimensions']))
        product=dict(DataVersion=0,Entities=[entity])
        if mutation:mutation(product)
        raw=json.dumps(product,separators=(',',':')).encode();(self.sdk.root/'export.json').write_bytes(raw)
        owner.observe();after=deepcopy(owner.state['originals'][-1]);stamp=after['packet']['clockAfter']['epochMs']
        self.model['clockBefore'].update(epochMs=stamp-1,monotonicMs=stamp-EPOCH-1);self.model['clockAfter'].update(epochMs=stamp,monotonicMs=stamp-EPOCH)
        return before,after,raw
    def test_actual_product_output_is_joined_without_rewriting_export_or_reusing_staged_json(self):
        with self.held():
            before,after,raw=self.fixtures();value=exported(before,after,self.model,ID,after_native=before['packet']['clockAfter']['epochMs'])
            self.assertEqual(len(raw),value['bytes']);self.assertEqual(ID,value['entityId']);self.assertEqual(raw,(self.sdk.root/'export.json').read_bytes())
            self.assertEqual(0,json.loads(raw)['DataVersion']);self.assertEqual(3,json.loads((self.sdk.root/'entity-import.json').read_bytes())['DataVersion'])
    def test_wrong_data_version_model_source_dimensions_texture_or_uuid_cannot_be_export_evidence(self):
        for fault in ('version','source','dimensions','textures','id','type'):
            if fault!='version':self.doCleanups();self.setUp()
            def mutate(product):
                if fault=='version':product['DataVersion']=3
                elif fault=='source':product['Entities'][0]['modelURL']='http://foreign/model.gltf'
                elif fault=='dimensions':product['Entities'][0]['dimensions']['x']=2
                elif fault=='textures':product['Entities'][0]['textures']='{}'
                elif fault=='id':product['Entities'][0]['id']='99999999-9999-4999-8999-999999999999'
                else:product['Entities'][0]['type']='Box'
            with self.held():
                before,after,_=self.fixtures(mutate)
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):exported(before,after,self.model,ID,after_native=before['packet']['clockAfter']['epochMs'])
    def test_existing_output_missing_output_wrong_query_owner_pid_and_input_inode_are_rejected(self):
        with self.held():
            before,after,_=self.fixtures()
            for fault in ('preexisting','missing','token','pid','inode','selection','creator','stale'):
                first,last,model=deepcopy(before),deepcopy(after),deepcopy(self.model)
                if fault=='preexisting':first['packet']['source']['files'][1]=deepcopy(last['packet']['source']['files'][1])
                elif fault=='missing':last['packet']['source']['files'][1]=dict(name='export.json',exists=False)
                elif fault=='token':last['query']['ownerToken']='0'*64
                elif fault=='pid':last['packet']['processId']=43
                elif fault=='inode':last['packet']['source']['files'][1]['identity']['inode']=last['packet']['source']['files'][0]['identity']['inode']
                elif fault=='selection':model['source']['roots'][0]['page']['selectedIds']=[]
                elif fault=='creator':model['source']['entities'][0]['lastEditedBy']='55555555-5555-4555-8555-555555555555'
                else:model['clockBefore']['epochMs']-=2000;model['clockAfter']['epochMs']-=2000
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):exported(first,last,model,ID,after_native=before['packet']['clockAfter']['epochMs'])


if __name__=='__main__':unittest.main()
