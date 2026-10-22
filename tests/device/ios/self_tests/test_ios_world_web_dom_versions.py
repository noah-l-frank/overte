"""Closed DOM2 original field reads preserve genuine DOM1 source history."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_dom as dom
from ios.adapters.world_web_measurements import current_document
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN


class WorldWebDOMVersionsTests(unittest.TestCase):
    def test_original_legacy_and_current_native_dom_headers_join_their_actual_observer_pins(self):
        for version in (1,2):
            producer=OriginalSources(dom_version=version);document=producer.document();ledger=producer.ledger();dom.original(document)
            result=current_document(ledger,document,producer.browser.snapshot(RUN),producer.origins)
            self.assertEqual(version,document['source']['dom']['iosWorldWebDOMVersion']);self.assertEqual('reference',result['page'])
            self.assertEqual(version==2,'focused' in document['source']['dom']['elements'][0])
        raw=Path(__file__).parents[2]/'native'/'ios_world_web_dom.js'
        self.assertEqual(dom.SOURCE_PINS[2],hashlib.sha256(raw.read_bytes()).hexdigest())

    def test_current_foreign_editor_focus_value_are_private_originals_not_primary_editor_or_requested_url(self):
        producer=OriginalSources();value=producer.document();field=next(row for row in value['source']['dom']['elements'] if row['id']=='foreign')
        field.update(focused=True,value='http://actual-second-listener.invalid/reference.html');dom.original(value)
        self.assertFalse(value['source']['dom']['editor']['focused']);self.assertEqual('',value['source']['dom']['editor']['text'])
        for fault in ('boolean','twoFocused','editorMismatch','valueTooLong','legacyPin','nativeBodyAlias'):
            wrong=deepcopy(value);body=wrong['source']['dom'];row=next(row for row in body['elements'] if row['id']=='foreign')
            if fault=='boolean':row['focused']=1
            elif fault=='twoFocused':next(item for item in body['elements'] if item['id']=='navigate')['focused']=True
            elif fault=='editorMismatch':body['editor']['focused']=True
            elif fault=='valueTooLong':row['value']='a'*8193
            elif fault=='legacyPin':wrong['source']['nativeView']['observerSha256']=dom.SOURCE_PINS[1]
            else:body['iosWorldWebDOMVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):dom.original(wrong)


if __name__=='__main__':unittest.main()
