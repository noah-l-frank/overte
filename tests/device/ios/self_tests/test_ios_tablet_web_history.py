"""Actual host-JS facts and historical originals across positive native close."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_history import derive
from ios.self_tests.tablet_web_history_fixture import frame,close
from ios.self_tests.test_ios_emote_sources import BINDING
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS


class TabletWebHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.frame,cls.app=frame()

    def derived(self,frames=None,apps=None):return derive(frames or [self.frame],apps or [self.app],BINDING,ORIGINS)

    def test_full_original_reply_flow_derives_all_fifteen_facts_without_requested_state(self):
        result=self.derived();public=result['public']
        self.assertEqual(dict(surface='tablet',text='',page='reference',bridgeMessages=1,bridgeEchoes=1,attemptedMessages=1,documentLoads=1,
            httpStatus=200,origin='primary',documentKind='http',inlineLeases=0,deferredMessages=0,error='none',focused=False,open=True),public)
        self.assertEqual(self.frame['document'],result['document'])
        self.assertEqual(public,self.derived([self.frame,deepcopy(self.frame)])['public'])

    def test_real_native_close_retains_old_document_counts_and_does_not_claim_cached_object_death(self):
        current=close(self.frame);result=self.derived([self.frame,current]);public=result['public']
        self.assertFalse(public['open']);self.assertEqual('none',public['page']);self.assertEqual(0,public['httpStatus'])
        self.assertEqual((1,1,1,1),tuple(public[key] for key in ('bridgeMessages','bridgeEchoes','attemptedMessages','documentLoads')))
        self.assertIsNone(result['document']);self.assertTrue(current['state']['targets'][0]['alive']);self.assertTrue(current['state']['owners'][0]['alive'])
        self.assertTrue(current['touches']['objects'][0]['alive'])

    def test_missing_current_dom_teardown_entry_or_false_source_flag_cannot_hide_real_presentation(self):
        for fault in ('active','attached','responder','foreign','old-ready','state-source','source-reset','private-expected'):
            current=close(self.frame)
            if fault=='active':current['state']['owners'][0]['current']['active']=True
            elif fault=='attached':current['state']['targets'][0]['windowAttached']=True
            elif fault=='responder':current['state']['targets'][0]['subtreeResponder']=True
            elif fault=='foreign':current['state']['otherLiveTablets']=1
            elif fault=='old-ready':current['document']=deepcopy(self.frame['document'])
            elif fault=='state-source':current['state']['owners'][0]['source']['navigation']='0'*32
            elif fault=='source-reset':current['sources']['instance']='0'*32;current['sources']['commandId']='ios-'+'0'*32;current['sources']['sequence']+=1
            else:current['expected']={'open':False}
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.derived([self.frame,current])

    def test_history_requalifies_actual_app_originals_native_prefixes_and_server_response_independently(self):
        for fault in ('root-code','caller','missing-app','browser','button-generation','unavailable','native-prefix','query-rewrite'):
            value=deepcopy(self.frame);app=deepcopy(self.app);apps=[app]
            if fault=='root-code':app['scripts']['source']['engines'][0]['code']['sha256']='0'*64
            elif fault=='caller':value['emitter']['calls'][0]['caller']['manager']['instance']='0'*32
            elif fault=='missing-app':apps=[]
            elif fault=='browser':value['browser']['responses'][0]['responseId']='0'*32
            elif fault=='button-generation':app['buttons']['buttons'][0]['caller']['manager']['loadGeneration']+=1
            elif fault=='unavailable':value['document'].update(status='unavailable',source={})
            elif fault=='native-prefix':
                value['ledger']['commandId']='ios-'+'0'*32;value['ledger']['sequence']+=1;value['ledger']['events']=value['ledger']['events'][:-1]
            else:value['touches']['contacts'][0]['began']['epochMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):derive([self.frame,value],apps,BINDING,ORIGINS)


if __name__=='__main__':unittest.main()
