"""Actual modeled native render admission; no requested IDs create evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_resource_disposition import resource_admission,ResourceAdmissionPending
from ios.self_tests.test_ios_web_closures import ClosureBoundary,RUN,URL

ENTITY='12345678-1234-4123-8123-123456789abc'
PAGE=URL+'tickets/'+'f'*32+'/graphics-marker.v1.html'


class WorldWebResourceAdmissionTests(unittest.TestCase):
    def boundary(self):
        source=ClosureBoundary();source.version=5
        source.mutate=lambda value:value['contexts'][0]['descriptor'].update(identitySha256=hashlib.sha256(('web-entity:'+ENTITY).encode()).hexdigest())
        return source,source.reader()
    def test_original_full_painted_path_required_and_returned_admission_does_not_mutate_source(self):
        source,reader=self.boundary();original=reader.read(RUN,URL);result=resource_admission(original,ENTITY,PAGE)
        self.assertEqual([1],result['contexts']);self.assertEqual(original['instance'],result['instance'])
        result['contexts'].clear();self.assertEqual([1],resource_admission(original,ENTITY,PAGE)['contexts'])
        for entity,url in ((ENTITY.replace('a','b'),PAGE),(ENTITY,PAGE+'other')):
            with self.subTest(entity=entity,url=url),self.assertRaises(ResourceAdmissionPending):resource_admission(original,entity,url)
    def test_valid_not_yet_painted_is_pending_but_invalid_original_is_never_retryable_admission(self):
        source,reader=self.boundary();source.created=0
        with self.assertRaises(ResourceAdmissionPending):resource_admission(reader.read(RUN,URL),ENTITY,PAGE)
        source,reader=self.boundary();source.resources['native-bitmap']=dict(created=0,retired=0,pending=0)
        with self.assertRaises(ResourceAdmissionPending):resource_admission(reader.read(RUN,URL),ENTITY,PAGE)
        source,reader=self.boundary();original=reader.read(RUN,URL);original['complete']=False
        with self.assertRaises(NativeUIError) as caught:resource_admission(original,ENTITY,PAGE)
        self.assertNotIsInstance(caught.exception,ResourceAdmissionPending)


if __name__=='__main__':unittest.main()
