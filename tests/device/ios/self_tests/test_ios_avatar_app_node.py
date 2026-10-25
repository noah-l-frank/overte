"""Actual complete AvatarApp source yields independent executed caller locations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from ios.adapters.avatar_exact_callers import pins
from ios.self_tests.avatar_app_node import AvatarAppNode


class AvatarAppNodeTests(unittest.TestCase):
    def setUp(self):
        self.clock=1700000000000;self.config=dict(self='00000000-0000-4000-8000-000000000001')
        self.node=AvatarAppNode(self,self.config,lambda:self.clock)
        self.node.request('screen',open=True)
    def profile(self,actual,name):
        expected=pins()['profiles'][name]['frames']
        self.assertEqual([dict(url='qrc:/scripts'+row['source'],line=row['line'],column=row['column']) for row in expected],
            [{key:row[key] for key in ('url','line','column')} for row in actual])
    def test_normal_add_and_delete_use_real_api_uuid_hips_and_actual_timer_locations(self):
        value=self.node.request('message',message=dict(method='addWearable',url='https://owned.invalid/model.gltf'))
        added=value['calls'][-1];self.assertEqual('addEntity',added['method']);self.assertEqual(0,added['properties']['parentJointIndex'])
        self.assertEqual(self.config['self'],added['properties']['parentID']);self.assertTrue(added['host'])
        self.profile(added['frames'],'avatar-wearable-create');self.profile(value['events'][0]['details']['callerFrames'],'avatar-wearable-added')
        self.assertEqual(added['id'],value['entities'][0]['id']);self.clock+=400;value=self.node.request('tick')
        self.assertEqual(['created','fired','destroyed','callback-enter','callback-leave'],[row['kind'] for row in value['events']])
        value=self.node.request('message',message=dict(method='deleteWearable',entityID=added['id']))
        deleted=value['calls'][-1];self.assertEqual(added['id'],deleted['id']);self.assertEqual([],value['entities'])
        self.profile(deleted['frames'],'avatar-wearable-delete');self.profile(value['events'][-1]['details']['callerFrames'],'avatar-wearable-deleted')
        value=self.node.request('screen',open=False);self.assertEqual([],value['pending']);self.assertEqual('destroyed',value['events'][-1]['kind'])
    def test_bookmark_actual_native_callback_keeps_reentrant_original_frame_and_close_cancels_timer(self):
        self.config['bookmarks']={'owned':dict(avatarUrl='https://owned.invalid/avatar.fst',avatarScale=1,avatarEntites=[])}
        value=self.node.request('message',config=self.config,message=dict(method='selectAvatar',name='owned'))
        self.profile(value['events'][-1]['details']['callerFrames'],'avatar-bookmark-loaded-reentrant')
        value=self.node.request('screen',open=False);self.assertEqual([],value['pending']);self.assertEqual('destroyed',value['events'][-1]['kind'])


if __name__=='__main__':unittest.main()
