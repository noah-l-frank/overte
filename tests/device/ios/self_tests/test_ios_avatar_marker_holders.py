"""Real native parsers and actual host weak objects, with modeled producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters import original_marker_holders as policy
from ios.adapters.web_closures import drained_owned_resources,KINDS
from ios.self_tests.test_ios_web_closures import ClosureBoundary,RUN,URL
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus
from self_tests.test_native_feature_observation import Boundary as Native
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarMarkerHolderTests(unittest.TestCase):
    def originals(self):
        source=ClosureBoundary();source.version=5;reader=source.reader();admitted=reader.read(RUN,URL)
        source.retired=1;source.resources['policy-grant']=dict(created=1,retired=1,pending=0)
        return source,reader,admitted

    @staticmethod
    def inventory(source):
        return dict(inventoryVersion=2,complete=True,managers=[],pickers=[],tabletPresent=True,tabletShown=False,
            rootOwnership=source.source(),rootMembership=dict(managers=[],pickers=[]))

    def test_real_cached_groups_keep_all_original_contexts_and_never_become_resource_absence(self):
        source,reader,admitted=self.originals();current=reader.read(RUN,URL);before=deepcopy(current)
        result=policy.web('avatar',current,admitted);self.assertTrue(result['holders'])
        groups={row['original']['resourceKind']:row for row in result['holders']}
        self.assertEqual('qimage',groups['native-bitmap']['kind']);self.assertEqual('qsg-root',groups['scenegraph-node']['kind'])
        self.assertEqual(1,groups['vulkan-image']['original']['contexts'][0]['counter']['pending']);self.assertNotIn('policy-grant',groups)
        with self.assertRaises(NativeUIError):drained_owned_resources(current,admitted)
        self.assertEqual(before,current);result['holders'][0]['original'].clear()
        self.assertTrue(policy.web('avatar',current,admitted)['holders'][0]['original'])
        self.assertNotEqual(policy.web('emote',current,admitted)['holders'][0]['resource'],policy.web('avatar',current,admitted)['holders'][0]['resource'])
        with self.assertRaises(NativeUIError):policy.web('other',current,admitted)

    def test_callbacks_grants_missing_render_admission_and_foreign_source_never_supply_quiet(self):
        for name in KINDS:
            source,reader,admitted=self.originals()
            source.mutate=lambda value,name=name:value['contexts'][0]['callbacks'].update({name:dict(created=1,retired=0,pending=1)})
            with self.subTest(name=name),self.assertRaises(NativeUIError):policy.web('avatar',reader.read(RUN,URL),admitted)
        source,reader,admitted=self.originals();current=reader.read(RUN,URL)
        for fault in ('grant','resource','birth'):
            a,b=deepcopy(admitted),deepcopy(current)
            if fault=='grant':b['contexts'][0]['resources']['policy-grant']=dict(created=1,retired=0,pending=1)
            elif fault=='resource':a['contexts'][0]['resources']['offscreen-image']=dict(created=0,retired=0,pending=0)
            else:b['instance']='f'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):policy.web('avatar',b,a)

    def test_hidden_detached_actual_roots_remain_held_until_real_weak_expiry_and_legacy_inventory_is_refused(self):
        source=RootCensus();manager=Root('manager');picker=Root('picker');source.observe(manager);source.observe(picker)
        first=self.inventory(source);result=policy.ui('avatar',first,pid=31);self.assertEqual(2,len(result['holders']))
        self.assertTrue(all(row['kind']=='qt-root' for row in result['holders']));self.assertFalse(first['rootMembership']['managers'])
        second=self.inventory(source);again=policy.ui('avatar',second,pid=31,previous=result['ownership'])
        self.assertEqual([row['resource'] for row in result['holders']],[row['resource'] for row in again['holders']])
        del manager,picker;gc.collect();last=self.inventory(source)
        self.assertEqual([],policy.ui('avatar',last,pid=31,previous=again['ownership'])['holders'])
        legacy={key:deepcopy(value) for key,value in first.items() if key not in ('rootOwnership','rootMembership')};legacy['inventoryVersion']=1
        with self.assertRaises(NativeUIError):policy.ui('avatar',legacy,pid=31)
        for edit in ('incomplete','unready','shown','pid'):
            value=deepcopy(second)
            if edit=='incomplete':value['rootOwnership']['complete']=False
            elif edit=='unready':value['rootOwnership']['wholeTreeReady']=False
            elif edit=='shown':value['tabletShown']=True
            else:value['rootOwnership']['processId']=52
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):policy.ui('avatar',value,pid=31)

    def test_native_process_anchor_is_only_outstanding_process_ownership_not_ui_or_callback_drainage(self):
        source=Native();source.mutate=lambda value:value.update(processId=int(BINDING['processIdentity']))
        def capture():source.send(dict(commandId='ios-'+uuid.uuid4().hex));return deepcopy(source.sample)
        first,last=capture(),capture();row=policy.process('avatar',first,last,binding=BINDING,run=RUN)
        self.assertEqual('native-holder',row['kind']);self.assertEqual(first['lifecycle'],row['original']['lifecycle'])
        self.assertNotIn('weakAlive',row['original']);self.assertNotIn('callbacks',row['original'])
        changed=deepcopy(last);changed['instance']='f'*32
        with self.assertRaises(NativeUIError):policy.process('avatar',first,changed,binding=BINDING,run=RUN)


if __name__=='__main__':unittest.main()
