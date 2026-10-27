"""Declared current mesh getter packets; native code is not executed here."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_renderers as source
from ios.self_tests import test_ios_create_state as create


def packet():
    actual=create.version2(create.packet());create.add_model(actual);create.version2(actual)
    return dict(iosAssetsModelRenderersVersion=1,requestId='ios-'+'a'*32,runId=create.RUN,instance='b'*32,sequence=1,
        processId=42,clockDomain='native-main-assets-model-renderers',clockBefore=dict(epochMs=create.EPOCH,monotonicMs=10),
        clockAfter=dict(epochMs=create.EPOCH+2,monotonicMs=12),source=dict(complete=True,domainId=create.DOMAIN,localSessionId=create.SESSION,
            tree=deepcopy(actual['source']['tree']),models=[dict(entityId=create.ID,present=True,loaded=True,addedToScene=True,
                renderable=True,needsFixup=False,visible=True,failed=False,renderItemIds=[7,19],boundsReady=True,
                origin=dict(modelUrl='atp:/actual.fbx',watcherUrl='atp:/actual.fbx',geometry=dict(readerId='d'*32,mappingIds=['e'*32])),
                bounds=dict(corner=[-.5,1,-2],dimensions=[1,1,0]))],renderedPixelsAvailable=False,resourceRetirementAvailable=False))


class AssetsModelRenderersTests(unittest.TestCase):
    def test_actual_planar_mesh_bound_and_items_are_separate_from_pixels_or_lifetimes(self):
        value=packet();before=deepcopy(value);row=source.model(value,create.ID)
        self.assertEqual([1,1,0],row['bounds']['dimensions']);self.assertEqual([7,19],row['renderItemIds'])
        self.assertIs(False,value['source']['renderedPixelsAvailable']);self.assertIs(False,value['source']['resourceRetirementAvailable']);self.assertEqual(before,value)

    def test_no_expected_subject_or_bounds_can_enter_the_query(self):
        value=packet();query=dict(schemaVersion=1,commandId=value['requestId'],action=source.ACTION,runId=create.RUN)
        for key,extra in (('entityId',create.ID),('bounds',value['source']['models'][0]['bounds']),('requestedUrl','atp:/wanted.fbx')):
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.command(dict(query,**{key:extra}))

    def test_incomplete_tree_wrong_process_domain_or_false_render_verdict_is_unavailable(self):
        for fault in ('tree','complete','pid','domain','pixels','retirement','unknown'):
            value=packet()
            if fault=='tree':value['source']['tree']['complete']=False
            elif fault=='complete':value['source']['complete']=False
            elif fault=='pid':value['processId']=43
            elif fault=='domain':value['source']['domainId']='wanted-domain'
            elif fault=='pixels':value['source']['renderedPixelsAvailable']=True
            elif fault=='retirement':value['source']['resourceRetirementAvailable']=True
            else:value['source']['models'][0]['expectedBounds']=value['source']['models'][0]['bounds']
            query=dict(schemaVersion=1,commandId=value['requestId'],action=source.ACTION,runId=create.RUN)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):source.validate(value,query,42)

    def test_invalid_duplicate_unsorted_overlarge_or_missing_mesh_items_cannot_be_loaded_subject(self):
        for ids in ([0],[True],[19,7],[7,7],[2**32],list(range(1,4098)),[]):
            value=packet();value['source']['models'][0]['renderItemIds']=ids
            with self.subTest(ids=ids[:3]),self.assertRaises(NativeUIError):source.model(value,create.ID)

    def test_actual_absent_or_not_ready_model_cannot_become_a_rendered_or_empty_retirement_verdict(self):
        for fault in ('absent','loaded','added','renderable','fixup','visible','failed','bounds'):
            value=packet();row=value['source']['models'][0]
            if fault=='absent':
                for key in ('present','loaded','addedToScene','renderable','visible','boundsReady'):row[key]=False
                row.update(renderItemIds=[],bounds=None,origin=None)
            elif fault=='bounds':row.update(boundsReady=False,bounds=None)
            elif fault in ('fixup','failed'):row['needsFixup' if fault=='fixup' else 'failed']=True;row.update(boundsReady=False,bounds=None)
            else:row[{'added':'addedToScene'}.get(fault,fault)]=False;row.update(boundsReady=False,bounds=None)
            source.original(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.model(value,create.ID)

    def test_loaded_mesh_without_actual_accepted_geometry_reader_stays_unqualified(self):
        for fault in ('none','unknown','duplicate','invalid'):
            value=packet();origin=value['source']['models'][0]['origin']
            if fault=='none':origin['geometry']=None
            elif fault=='unknown':origin['geometry']['readerId']=''
            elif fault=='duplicate':origin['geometry']['mappingIds']*=2
            else:origin['geometry']['readerId']='wanted-reader'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.model(value,create.ID)

    def test_nonfinite_negative_point_line_or_unbounded_geometry_is_rejected(self):
        for fault in ('nan','infinite','negative','point','line','unbounded'):
            value=packet();bounds=value['source']['models'][0]['bounds']
            if fault=='nan':bounds['corner'][0]=float('nan')
            elif fault=='infinite':bounds['corner'][0]=float('inf')
            elif fault=='negative':bounds['dimensions'][2]=-1
            elif fault=='point':bounds['dimensions']=[0,0,0]
            elif fault=='line':bounds['dimensions']=[1,0,0]
            else:bounds['corner'][0]=1e13
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)

    def test_sequence_tree_instance_and_both_clock_axes_must_follow_actual_history(self):
        before=packet()
        for fault in (None,'sequence','request','instance','tree','utc','monotonic'):
            value=deepcopy(before);value.update(requestId='ios-'+'c'*32,sequence=2)
            value['clockBefore']=dict(epochMs=create.EPOCH+3,monotonicMs=13);value['clockAfter']=dict(epochMs=create.EPOCH+5,monotonicMs=15)
            if fault=='sequence':value['sequence']=1
            elif fault=='request':value['requestId']=before['requestId']
            elif fault=='instance':value['instance']='c'*32
            elif fault=='tree':value['source']['tree']['treeInstance']='c'*32
            elif fault=='utc':value['clockBefore']['epochMs']=create.EPOCH
            elif fault=='monotonic':value['clockBefore']['monotonicMs']=10
            query=dict(schemaVersion=1,commandId=value['requestId'],action=source.ACTION,runId=create.RUN)
            if fault is None:self.assertIs(value,source.validate(value,query,42,previous=before))
            else:
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query,42,previous=before)
