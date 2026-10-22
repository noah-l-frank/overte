"""Primary terminal recipes use real normal events at synthetic peer bounds."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from unittest.mock import patch
import uuid
from ios.adapters import normal_input,avatar_controls
from ios.self_tests import test_ios_avatar_actions as harness


class SocialWidget(harness.Widget):
    def __init__(self,fixture):super().__init__(fixture);self.tab='nearbyTab'
    def rows(self):
        rows=super().rows()
        if self.screen=='people':
            next(row for row in rows if row['id']=='people.page')['activeTab']=self.tab
            if self.dialog=='none':
                for identifier in ('people.nearby','people.connections'):
                    rows.append(dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier)),enabled=True,focused=False,
                        inputReady=True,rootId=self.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml'))
        return rows
    def post(self,request,timeout):
        payload=json.loads(request.data);identifier=None
        if payload['operation']=='edit':
            matches=[row for row in self.rows() if row['token']==payload['input']['fieldToken']]
            if matches:identifier=matches[0]['id']
        result=super().post(request,timeout)
        if identifier in ('people.nearby','people.connections'):self.tab='nearbyTab' if identifier=='people.nearby' else 'connectionsTab'
        return result


class PrimarySocialRecipeTests(unittest.TestCase):
    def test_actual_cancel_and_independent_peer_terminals_close_then_fetch_real_connections_tab(self):
        for verb,terminal in (('connection-cancel','outgoing'),('peer-reject','declined'),('peer-accept','success')):
            case=harness.AvatarActionTests();case.setUp();self.addCleanup(case.doCleanups)
            case.fixture.widget=SocialWidget(case.fixture)
            original=case.mutate
            def mutate(name,value):
                original(name,value)
                if name=='people':
                    widget=case.fixture.widget;root=value['source']['roots'][0]
                    root.update(rootId=widget.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml',activeTab=widget.tab)
                    root['connectionState']['phase']=widget.phase;root['panels']['connectionPrompt']=widget.dialog=='connection'
            case.fixture.mutate=mutate
            native=normal_input.NativeInput(case.fixture.widget,'owned-session',case.fixture.widget.target,case.fixture.widget.process,
                native_epoch_ms=case.fixture.now,monotonic=lambda:case.fixture.clock,sleep=case.fixture.sleep)
            case.readers=case.fixture.readers();case.readers['ui']=avatar_controls.IOSAvatarIO(native)
            with self.subTest(verb=verb),case.lock.held(),patch.object(normal_input,'urlopen',case.fixture.widget.post):
                case.source=case.make_sources();owner=case.owner();owner.prepare()
                widget=case.fixture.widget;widget.screen='people';widget.dialog='connection';widget.phase=terminal
                query=case.action(verb,{},'a'*32);self.assertEqual({'performed':True},owner.act(query))
                self.assertEqual(('idle','none','connectionsTab'),(widget.phase,widget.dialog,widget.tab))
                controls=[event['intent']['controlId'] for event in owner.inputs.state['calls'][-1]['events']]
                self.assertEqual('people.connections',controls[-1]);self.assertIn('people.cancel',controls)
                count=len(widget.requests);owner.act(query);self.assertEqual(count,len(widget.requests))


if __name__=='__main__':unittest.main()
