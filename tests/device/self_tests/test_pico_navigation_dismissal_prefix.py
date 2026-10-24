"""Ten normal actions using original lookup/dismissal/Close-v2 Python owners.

TLS and retained files execute; Qt/VM/OS/native weak lifetimes are explicit
models. No seeded lookup/Transit/closed original replaces the real prefix.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_modals import retired
from adapters.navigation_error_dismissal import NavigationErrorDismissal
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_dismissal_join import NavigationDismissalJoin
from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
from adapters.script_journey.history import unpack
from adapters.token_navigation_error_ui import TokenNavigationErrorUI
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand,VERSION as CONTRACT_VERSION
from self_tests import test_pico_navigation_prefix as prefix
from self_tests import test_pico_navigation_missing_prefix as missing


class Model(missing.Model):
    def __init__(self,root):
        super().__init__(root);self.ok_inputs=[];self.lose_ok=False;self.retain_listener=False;self.raise_keyboard_after_ok=False
    def raw(self):
        value=super().raw();value['navigationErrorControlsVersion']=1
        if self.shown:
            for row in self.modal.records:
                if not row['rootAlive']:continue
                event=row['event'];identifier='navigation.error.ok.'+row['modalId']
                value['controls'].append(dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier+event['eventId'])),
                    enabled=True,focused=False,inputReady=not row['callbackFinished'],modalId=row['modalId'],eventId=event['eventId'],
                    runId=event['runId'],lookupGeneration=event['lookupGeneration'],createdEpochMs=row['createdEpochMs'],messageSha256=row['messageSha256']))
        return value
    def private(self,request,kind):
        super().private(request,kind)
        if kind=='modals':
            originals={row['modalId']:row for row in self.modal.records}
            for row in self.native_packets[kind]['records']:
                original=originals[row['modalId']];row['visible']=self.shown and original['visible'];row['inCurrentTree']=self.shown and original['inCurrentTree']
    def send(self,command):
        if not command['controlId'].startswith('navigation.error.ok.'):return super().send(command)
        child=self.owner_test.flow.dismissal_join.dismissal;disk=json.loads(child.store.path.read_text())
        assert disk['phase']=='pending' and disk['input']['controlId']==command['controlId']
        row=next(row for row in self.raw()['controls'] if row['id']==command['controlId'])
        assert row['token']==command['controlToken'] and command['generation']==self.generation and command['sequence']==self.sequence+1
        self.sequence+=1;self.ok_inputs.append(deepcopy(command));self.calls.append(deepcopy(command))
        self.modal.finish(root=False,listener=self.retain_listener)
        if self.raise_keyboard_after_ok:self.owner_test.world.ui.keyboard=True
        if self.lose_ok:raise NativeUIError('Synthetic applied normal OK response lost')
        return dict(schemaVersion=1,bridgeId=self.bridge,commandId=command['commandId'],sequence=self.sequence,
            performed=True,error='',processId=prefix.PID,updatedEpochMs=self.epoch()),self.epoch()


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationDismissalPrefixTests(unittest.TestCase):
    model_type=Model
    setUpClass=classmethod(prefix.NavigationPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(prefix.NavigationPrefixTests.tearDownClass.__func__)
    setUp=prefix.NavigationPrefixTests.setUp
    write=prefix.NavigationPrefixTests.write
    read=prefix.NavigationPrefixTests.read
    installed=prefix.NavigationPrefixTests.installed
    def activate(self,verb):
        if verb!='bookmark-visit':return missing.NavigationMissingPrefixTests.activate(self,verb)
        inputs=dict(name=context(prefix.RUN)['renamed']);self.ticket=uuid.uuid4().hex
        self.server.journal.activate(prefix.RUN,self.ticket,verb,inputs);self.model.provider.activate(prefix.RUN,self.ticket)
        return dict(contractVersion=CONTRACT_VERSION,runId=prefix.RUN,fixtureUrl=self.url+'/feature-fixture/v1/runs/'+prefix.RUN+'/',ticket=self.ticket,verb=verb,inputs=inputs)
    def make(self,role):
        owner=missing.NavigationMissingPrefixTests.make(self,role);m=self.model
        def factory(parent):
            child=NavigationErrorDismissal(lambda intent:TokenNavigationErrorUI(PicoNavigationErrorIO(parent.source.normal.io.original),intent,prefix.RUN),
                parent.source.readers['replies'],parent.source.readers['modals'],parent.directory.status,self.root/'navigation-prefix-dismissal.json',
                prefix.RUN,self.binding,m.provider.instance,prefix.INPUTS,self.url,m.guard,monotonic=lambda:m.clock,sleep=m.sleep)
            normal=TokenScriptUI(parent.source.normal.io.original,monotonic=lambda:m.clock,sleep=m.sleep)
            graphics=self.world.ui.source();graphics.clock_ms=m.epoch;graphics.monotonic=lambda:m.clock;graphics.sleep=m.sleep
            return NavigationDismissalJoin(parent,parent.missing(),child,normal,graphics,self.root/'navigation-prefix-dismissal-join.json')
        owner.dismissal_factory=factory;return owner
    def first_nine(self):
        self.flow.prepare()
        for verb in prefix.VERBS[:9]:self.flow.act(self.activate(verb))
    def test_continuous_ten_actions_original_ok_retirement_close_v2_and_independent_actor(self):
        self.flow.prepare();self.flow.observe();actor=self.make('actor');actor.observe()
        for index,verb in enumerate(prefix.VERBS[:10]):
            self.flow.act(self.activate(verb));actual=self.flow.observe();peer=actor.observe()
            expected=expand(SCENARIOS['world-navigation']['steps'][index]['state'],context(prefix.RUN))
            if index==8:self.assertIn(actual['state']['addressDialog'],expected.pop('addressDialog')['oneOf'])
            self.assertEqual(expected,{k:v for k,v in actual['state'].items() if k in expected});self.assertEqual(actual['state'],peer['state'])
        child=self.flow.dismiss();self.assertEqual('closed',child.state['phase']);self.assertFalse(self.model.shown)
        self.assertEqual(1,len(self.model.ok_inputs));self.assertEqual(1,len(self.model.http_originals));self.assertEqual(6,len(self.model.controller_calls))
        self.assertEqual('complete',child.dismissal.state['phase']);self.assertEqual(7,len(child.dismissal.state['quiet']))
        row=retired(child.dismissal.state['last']['modal'],child.lookup.state['joined']['event']);self.assertEqual(1024,row['selectedButton'])
        close=child.close_original();self.assertEqual(2,close.disk['navigationTabletCloseVersion']);self.assertEqual('dismissed-lookup',close.disk['sourceKind'])
        self.assertEqual(7,len(close.state['quiet']));self.assertEqual('B',actual['state']['location']);self.assertEqual('none',actual['state']['error'])
        self.assertFalse(actual['fullNavigationRecipe']);self.assertTrue(actual['journalsRetained'])
    def test_lost_normal_ok_cold_observes_original_callback_without_another_ok_lookup_or_toggle(self):
        self.first_nine();call=self.activate('dismiss-error');self.model.lose_ok=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(1,len(self.model.ok_inputs));self.assertEqual(5,len(self.model.controller_calls));self.model.lose_ok=False
        self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(1,len(self.model.ok_inputs));self.assertEqual(6,len(self.model.controller_calls));self.assertEqual(1,len(self.model.http_originals))
        self.assertEqual('none',self.flow.observe()['state']['error'])
    def test_lost_applied_final_close_observes_original_closed_sources_without_second_close(self):
        self.first_nine();call=self.activate('dismiss-error');self.model.lose_close=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertFalse(self.model.shown);self.assertEqual(6,len(self.model.controller_calls));self.model.lose_close=False
        self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(6,len(self.model.controller_calls));self.assertEqual(1,len(self.model.ok_inputs));self.assertEqual(1,len(self.model.http_originals))
        self.assertFalse(self.flow.observe()['state']['addressDialog'])
    def test_dead_modal_with_retained_original_listener_never_replays_ok_or_closes(self):
        self.first_nine();call=self.activate('dismiss-error');self.model.retain_listener=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(1,len(self.model.ok_inputs));self.assertEqual(5,len(self.model.controller_calls))
        self.flow=self.make('primary')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(1,len(self.model.ok_inputs));self.assertEqual(5,len(self.model.controller_calls))
        record=self.model.modal.records[0];self.assertFalse(record['rootAlive']);self.assertTrue(record['listenerAlive'])
    def test_independent_raised_keyboard_after_normal_ok_blocks_close_before_controller(self):
        self.first_nine();call=self.activate('dismiss-error');self.model.raise_keyboard_after_ok=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual('complete',self.flow.dismissal_join.dismissal.state['phase']);self.assertEqual(5,len(self.model.controller_calls))
        self.assertTrue(self.model.shown);self.assertEqual(1,len(self.model.ok_inputs))
    def test_phase_advance_after_original_ok_intent_prevents_actual_qml_writer(self):
        self.first_nine();call=self.activate('dismiss-error');guard=self.flow.source.guard;changed=[]
        def advance():
            rows=self.flow.state['deliveries']
            if rows and rows[-1]['controlId'].startswith('navigation.error.ok.') and not changed:
                changed.append(True);self.activate('bookmark-visit')
            return guard()
        self.flow.source.guard=advance
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertTrue(changed);self.assertEqual([],self.model.ok_inputs);self.assertEqual(5,len(self.model.controller_calls))
        self.assertTrue(self.model.modal.records[0]['rootAlive']);self.assertEqual(1,len(self.model.http_originals))


if __name__=='__main__':unittest.main()
