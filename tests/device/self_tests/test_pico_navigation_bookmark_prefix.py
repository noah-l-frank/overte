"""Eleven continuous normal actions; Qt/VM/GPU/OS remain explicit models.

Real Python owners/Session, private files, TLS, PNG/archive/receipt release and
separate role queries execute. The model does not prove changed scene pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import traceback
import unittest
import uuid
from urllib.request import Request
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.source_chunks import json_digest
from adapters.navigation_arrival import stereo_frame
from adapters.navigation_transit import NavigationTransit
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_transit_join import NavigationTransitJoin
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.history import unpack
from adapters.token_places_ui import TokenPlacesUI,sha
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import DIRECTORY,QUERY
from feature_journeys.scenarios import SCENARIOS,expand
from navigation_observation import viewpoint_urls
from self_tests import test_pico_navigation_dismissal_prefix as dismissal
from self_tests import test_pico_navigation_prefix as prefix
from self_tests import test_pico_navigation_transit_prefix as first_transit


class Model(dismissal.Model):
    def __init__(self,root):
        super().__init__(root);self.bookmark_reopen=False;self.bookmark_root=None;self.old_directory_roots=[];self.old_panel_roots=[]
        self.lose_bookmark_open=False;self.lose_bookmark_entry=False;self.lose_bookmark_visit=False;self.bookmark_ignored=False
        self.bookmark_visits=[]

    def in_bookmark(self):
        flow=getattr(self.owner_test,'flow',None)
        return flow is not None and flow.state is not None and flow.state['active'] is not None and flow.state['active']['verb']=='bookmark-visit'

    def raw(self):
        value=super().raw()
        if self.bookmark_reopen and self.lookup_mode and self.shown and self.lookup.page=='home' and self.lookup.page_number==1:
            # Same ordinary Home Places entry as the already executed first
            # open; no product button, test setter or hidden entry is added.
            original=first_transit.Model.raw(self)
            value['controls'] += [row for row in original['controls'] if row['id']=='places.entry']
        if self.bookmark_root is not None:
            for row in value['controls']:
                if row['id']=='places.page':
                    row['rootInstance']=self.bookmark_root
                    row['currentAddressSha256']=sha(viewpoint_urls(prefix.INPUTS['sceneUrl'])[self.owner_test.world.position])
        return value

    def source_read(self,request):
        super().source_read(request)
        if self.bookmark_root is not None:
            current=self.source_packet['roots'][0];current['rootId']=self.bookmark_root
            self.source_packet['roots']=deepcopy(self.old_directory_roots)+[current]

    def private(self,request,kind):
        super().private(request,kind)
        if kind=='panels' and self.bookmark_root is not None:
            current=self.native_packets[kind]['roots'][0];current['rootId']=self.bookmark_root
            self.native_packets[kind]['roots']=deepcopy(self.old_panel_roots)+[current]

    def consume_controller(self,envelope):
        if envelope['commands'][0]['operation']=='tablet.open' and self.in_bookmark():
            child=self.owner_test.flow.bookmark_join
            rows=unpack(json.loads(child.store.path.read_text())['payload']);assert rows[0]['phase']=='opening' and rows[0]['controller'] is not None
            self.controller_calls.append(deepcopy(envelope));self.shown=True;self.generation=str(uuid.uuid4());self.bookmark_reopen=True
            if self.lose_bookmark_open:raise NativeUIError('Synthetic applied bookmark Open response lost')
            return
        return super().consume_controller(envelope)

    def send(self,command):
        control=command['controlId']
        if self.in_bookmark() and self.bookmark_reopen and self.lookup_mode:
            child=self.owner_test.flow.bookmark_join;assert child.state['pending']['controlId']==control
            if control.startswith('tablet.page.'):
                self.sync_lookup();self.lookup.intents.append(dict(control=control))
                reply,epoch=self.lookup.send(command);self.sequence=self.lookup.sequence
                self.calls.append(deepcopy(command));return reply,epoch
            assert control=='places.entry'
            self.old_directory_roots=deepcopy(self.source_packet['roots']);self.old_panel_roots=deepcopy(self.native_packets['panels']['roots'])
            assert all(not row['alive'] for row in self.old_directory_roots+self.old_panel_roots)
            self.bookmark_root=uuid.uuid4().hex;self.root_birth=self.epoch();self.root_dead=False;self.lookup_mode=False
            self.revision=0;self.last_message=None;self.records_hash=None;self.query='';self.tab=0
            reply=super().send(command)
            # Original READY_FOR_CONTENT calls transmitPortalList/fetchMetaverse
            # in places.js:172–177,339–348. This explicit VM/network producer
            # acquires a genuinely new controlled TLS response on that event.
            with self.owner_test.opener.open(Request(self.network+DIRECTORY+'?'+QUERY,headers={'Cache-Control':'no-cache'}),timeout=2) as response:
                body=response.read();header=response.headers['X-Overte-Fixture-Response']
            first=len(self.messages);self.received(body,header,origin=self.network)
            for row in self.messages[first:]:
                row['targetRootId']=self.bookmark_root
                if row['deliveredRootId'] is not None:row['deliveredRootId']=self.bookmark_root
            if self.lose_bookmark_entry:raise NativeUIError('Synthetic applied bookmark Places entry response lost')
            return reply
        reply=super().send(command)
        if control.startswith('places.bookmark.visit.'):
            name=next(name for name in self.map if sha(name)==control.rsplit('.',1)[1]);address=self.map[name]
            self.bookmark_visits.append(deepcopy(command))
            if not self.bookmark_ignored and address==viewpoint_urls(prefix.INPUTS['sceneUrl'])['A']:self.owner_test.world.position='A'
            if self.lose_bookmark_visit:raise NativeUIError('Synthetic applied normal bookmark Visit response lost')
        return reply


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationBookmarkPrefixTests(unittest.TestCase):
    model_type=Model
    setUpClass=classmethod(prefix.NavigationPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(prefix.NavigationPrefixTests.tearDownClass.__func__)
    setUp=prefix.NavigationPrefixTests.setUp
    write=prefix.NavigationPrefixTests.write
    read=prefix.NavigationPrefixTests.read
    installed=prefix.NavigationPrefixTests.installed
    activate=dismissal.NavigationDismissalPrefixTests.activate
    def make(self,role):
        parent=dismissal.NavigationDismissalPrefixTests.make(self,role);m=self.model
        def factory(owner):
            original=owner.transit()
            def transit(prior):
                old=original.transit
                child=NavigationTransit(lambda intent:TokenPlacesUI(PicoPlacesIO(owner.source.normal.io.original),intent,prefix.RUN,monotonic=lambda:m.clock,sleep=m.sleep),
                    old.arrival,old.roots,old.bookmarks,old.stereo_factory,self.root/'navigation-prefix-bookmark-transit.json',prefix.RUN,self.binding,old.scene_url,
                    m.guard,directory=owner.directory,home=PicoTabletHome(old.home.source,lambda _pose:None),panels=old.panels,
                    monotonic=lambda:m.clock,sleep=m.sleep,defer_stereo_until_close=True)
                return NavigationTransitJoin(owner,child,original.normal,original.graphics,self.root/'navigation-prefix-bookmark-transit-join.json',kind='bookmark',prior=prior)
            return NavigationBookmarkJoin(owner,transit,self.root/'navigation-prefix-bookmark-join.json')
        parent.bookmark_factory=factory;return parent

    def first_ten(self):
        self.flow.prepare()
        for verb in prefix.VERBS[:10]:self.flow.act(self.activate(verb))

    def test_continuous_eleven_normal_actions_original_bookmark_A_new_page_close_and_stereo(self):
        self.flow.prepare();self.flow.observe();actor=self.make('actor');actor.observe()
        for index,verb in enumerate(prefix.VERBS):
            try:self.flow.act(self.activate(verb))
            except Exception as error:
                if error.__context__ is not None:traceback.print_exception(error.__context__)
                raise
            actual=self.flow.observe();peer=actor.observe()
            expected=expand(SCENARIOS['world-navigation']['steps'][index]['state'],context(prefix.RUN))
            if index==8:self.assertIn(actual['state']['addressDialog'],expected.pop('addressDialog')['oneOf'])
            self.assertEqual(expected,{key:value for key,value in actual['state'].items() if key in expected});self.assertEqual(actual['state'],peer['state'])
        owner=self.flow.bookmark_visit();self.assertEqual('closed',owner.state['phase']);self.assertFalse(self.model.shown)
        self.assertEqual(9,len(self.model.controller_calls));self.assertEqual(1,len(self.model.bookmark_visits));self.assertEqual(1,len(self.model.ok_inputs))
        self.assertEqual(1,len(self.model.http_originals));self.assertEqual(2,len(self.model.reads));self.assertEqual(2,len(self.world.gpu.commands))
        child=owner.transit_original();self.assertEqual('bookmark',child.transit.state['kind']);self.assertTrue(child.transit.state['quiet']);self.assertTrue(child.close_original().state['quiet'])
        old=self.flow.transit();self.assertEqual('directory',old.transit.state['kind']);self.assertNotEqual(old.state['ticket'],child.state['ticket'])
        stereo=child.transit.stereo_factory(child.state['ticket']);before=old.transit.stereo_factory(old.state['ticket'])
        self.assertEqual('A',stereo_frame(stereo.state['frame'],stereo.image_bytes(),prefix.RUN,self.binding,prefix.INPUTS['sceneUrl'])['location'])
        self.assertEqual('B',stereo_frame(before.state['frame'],before.image_bytes(),prefix.RUN,self.binding,prefix.INPUTS['sceneUrl'])['location'])
        self.assertNotEqual(stereo.state['frame']['capture']['requestId'],before.state['frame']['capture']['requestId'])
        self.assertIsNone(self.world.owner_store('primary').read());self.assertFalse(stereo.state['proof']['memory']['present'])
        self.assertFalse(actual['fullNavigationRecipe']);self.assertTrue(actual['journalsRetained'])

    def test_lost_applied_open_cold_reads_new_home_without_second_open(self):
        self.first_ten();call=self.activate('bookmark-visit')
        with patch.object(self.session,'_wait_for_ack',side_effect=NativeUIError('Synthetic lost ACK after original host-save')):
            with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(8,json.loads(self.session.state_path.read_text())['nextSequence'])
        self.assertTrue(self.model.shown);self.assertEqual(7,len(self.model.controller_calls));self.assertFalse(self.model.bookmark_visits)
        self.flow=self.make('primary');read=self.xr.read_status;answers=[]
        def original_status(**kwargs):
            status=read(**kwargs)
            if len(self.xr.envelopes)==7 and kwargs.get('expected_sequence') is None and self.flow.bookmark_join.state['phase']=='opening':
                if not answers:status.update(state='active',activeCommandId=self.xr.envelopes[-1]['commands'][0]['id'])
                answers.append(deepcopy(status))
            return status
        with patch.object(self.xr,'read_status',side_effect=original_status):self.flow.act(call)
        self.assertEqual(['active','neutral'],[row['state'] for row in answers])
        self.assertEqual(answers,[row['status'] for row in self.flow.bookmark_visit().state['openStatuses']])
        self.assertEqual(9,len(self.model.controller_calls));self.assertEqual(1,len(self.model.bookmark_visits));self.assertEqual('A',self.flow.observe()['state']['location'])
        # Isolate the actual pending Open grammar from later child/prior or
        # digest mismatches: valid original pending state first, then Boolean
        # schema with its matching recomputed record digest must still refuse.
        owner=self.flow.bookmark_visit();pending=deepcopy(owner.state)
        pending.update(phase='opening',after=None,page=None,transitJoinSha256=None,pending=None,history=[],qml=[])
        owner.validate(pending)
        bad=deepcopy(pending);bad['controller']['envelope']['schemaVersion']=True
        bad['controller']['sha256']=json_digest(bad['controller']['envelope'])
        with self.assertRaises(NativeUIError):owner.validate(bad)

    def test_transport_grant_without_host_save_stays_unresolved_before_any_new_qt_or_controller(self):
        self.first_ten();call=self.activate('bookmark-visit');self.model.lose_bookmark_open=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        original=self.session.state_path.read_bytes();count=len(self.model.calls)
        self.assertEqual(7,json.loads(original)['nextSequence']);self.assertTrue(self.model.shown)
        self.model.lose_bookmark_open=False;self.flow=self.make('primary')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(original,self.session.state_path.read_bytes());self.assertEqual(count,len(self.model.calls))
        self.assertEqual(7,len(self.model.controller_calls));self.assertFalse(self.model.bookmark_visits)
        self.assertEqual('opening',self.flow.bookmark_join.state['phase']);self.assertEqual([],self.flow.bookmark_join.state['openStatuses'])

    def test_lost_applied_places_entry_cold_reads_original_new_page_and_never_reenters(self):
        self.first_ten();call=self.activate('bookmark-visit');self.model.lose_bookmark_entry=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        before=sum(row['controlId']=='places.entry' for row in self.model.calls);self.assertEqual(2,before)
        self.assertEqual(2,len(self.model.reads));self.assertFalse(self.model.bookmark_visits)
        self.model.lose_bookmark_entry=False;self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(before,sum(row['controlId']=='places.entry' for row in self.model.calls));self.assertEqual(2,len(self.model.reads))
        self.assertEqual(1,len(self.model.bookmark_visits));self.assertEqual(9,len(self.model.controller_calls))

    def test_lost_applied_bookmark_visit_cold_uses_actual_A_without_second_visit(self):
        self.first_ten();call=self.activate('bookmark-visit');self.model.lose_bookmark_visit=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual('A',self.world.position);self.assertEqual(1,len(self.model.bookmark_visits));self.assertEqual(7,len(self.model.controller_calls))
        self.model.lose_bookmark_visit=False;self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(1,len(self.model.bookmark_visits));self.assertEqual(9,len(self.model.controller_calls));self.assertEqual(2,len(self.world.gpu.commands))

    def test_accepted_bookmark_input_without_actual_arrival_preserves_pending_and_blocks_home_close_image(self):
        self.first_ten();call=self.activate('bookmark-visit');self.model.bookmark_ignored=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        child=self.flow.bookmark_visit().transit_original().transit
        self.assertEqual(2,child.state['stage']);self.assertIsNotNone(child.state['pending']);self.assertEqual('B',self.world.position)
        self.assertEqual(1,len(self.model.bookmark_visits));self.assertEqual(7,len(self.model.controller_calls));self.assertEqual(1,len(self.world.gpu.commands))
        self.assertEqual(10,len(self.flow.state['completed']));self.assertTrue(child.store.path.exists())

    def test_phase_advance_in_last_open_guard_blocks_controller_and_preserves_original_close(self):
        self.first_ten();call=self.activate('bookmark-visit');guard=self.flow.source.guard;changed=[]
        def advance():
            child=self.flow.bookmark_join
            if child is not None and child.state is not None and child.state['phase']=='opening' and not changed:
                changed.append(True);ticket=uuid.uuid4().hex
                self.server.journal.activate(prefix.RUN,ticket,'restart-app',{});self.model.provider.activate(prefix.RUN,ticket)
            return guard()
        self.flow.source.guard=advance
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertTrue(changed);self.assertFalse(self.model.shown);self.assertEqual(6,len(self.model.controller_calls));self.assertFalse(self.model.bookmark_visits)
        self.assertEqual('opening',self.flow.bookmark_join.state['phase']);self.assertIsNone(self.flow.bookmark_join.state['controller'])
        self.assertEqual('closed',self.flow.dismiss().close_original().state['phase'])

    def test_original_ten_action_v5_owner_cannot_acquire_bookmark_open_or_visit_authority(self):
        self.first_ten();original=self.flow.store.read();legacy=deepcopy(original)
        legacy['navigationPrefixVersion']=5
        self.flow.store.write(legacy,original);self.flow=self.make('primary')
        controllers=deepcopy(self.model.controller_calls);qml=deepcopy(self.model.calls)
        with self.assertRaises(NativeUIError):self.flow.act(self.activate('bookmark-visit'))
        self.assertEqual(controllers,self.model.controller_calls);self.assertEqual(qml,self.model.calls)
        self.assertEqual([],self.model.bookmark_visits);self.assertEqual(1,len(self.world.gpu.commands))
        self.assertIsNone(self.flow.bookmark_join)


if __name__=='__main__':unittest.main()
