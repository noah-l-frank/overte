"""Executed complete Pal/protocol/request originals at explicit host boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from ios.adapters.avatar_exact_callers import pins
from ios.self_tests.avatar_people_node import PeopleNode


class AvatarPeopleNodeTests(unittest.TestCase):
    def setUp(self):
        self.clock=[1700000000000]
        self.config={role:dict(self='00000000-0000-4000-8000-00000000000'+str(index),domain='00000000-0000-4000-8000-000000000003',
            endpoint='https://owned.invalid',loggedIn=True,account=role,accountGeneration=1) for index,role in enumerate(('primary','actor'),1)}
        self.node=PeopleNode(self,self.config,lambda:self.clock[0],lambda:self.clock[0]/1000)
    def match(self,rows,name):
        expected=pins()['profiles'][name]['frames']
        self.assertEqual([{key:row[key] for key in ('url','line','column')} for row in rows],
            [dict(url='qrc:/scripts'+row['source'],line=row['line'],column=row['column']) for row in expected])
        self.assertTrue(all(not row['isEval'] and not row['isConstructor'] for row in rows))
    def test_actual_pal_request_incoming_consent_open_response_and_poll_callpaths(self):
        value=self.node.request('request',role='primary',peer=self.config['actor']['self'])
        self.assertEqual(('outgoing','incoming'),tuple(value['views'][role]['phase'] for role in ('primary','actor')))
        self.assertEqual(value['views']['primary']['requestId'],value['views']['actor']['requestId'])
        self.match(value['timers']['primary'][0]['details']['callerFrames'],'protocol-request-watch')
        self.match(value['timers']['actor'][0]['details']['callerFrames'],'protocol-incoming-watch')
        value=self.node.request('respond',role='actor',accept=True)
        self.assertEqual(2,len(value['requests']));names={'primary':'protocol-submit-accepted','actor':'protocol-submit-ready'}
        for row in value['requests']:self.match(row['openStack'],names[row['role']])
        row=value['requests'][0];value=self.node.request('reply',id=row['id'],raw=json.dumps(dict(connection='pending')))
        self.match(value['nativeCalls'][0]['stack'],'xhr-response-callback')
        self.match(value['timers'][row['role']][-1]['details']['callerFrames'],'protocol-poll-delay')
        self.clock[0]+=300;value=self.node.request('tick')
        for role in ('primary','actor'):
            created=[event for event in value['timers'][role] if event['kind']=='created']
            self.match(created[1]['details']['callerFrames'],'protocol-poll-delay' if role==row['role'] else 'protocol-watch-tick')
        self.assertEqual(1,len(value['requests']));self.match(value['requests'][0]['openStack'],'protocol-poll-request')
    def test_qml_request_service_uses_actual_native_callback_and_no_synchronous_sender_parent(self):
        value=self.node.request('qml-request',role='primary',options=dict(uri='https://owned.invalid/api/v1/users?filter=connections'))
        row=value['requests'][0];self.match(row['openStack'],'xhr-page-request')
        value=self.node.request('reply',id=row['id'],raw='{"status":"success","data":{"users":[]}}')
        self.match(value['nativeCalls'][0]['stack'],'xhr-response-callback')


if __name__=='__main__':unittest.main()
