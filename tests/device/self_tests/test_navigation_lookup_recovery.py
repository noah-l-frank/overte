"""Original Python lookup-to-dismissal flow; Qt/VR/native boundaries synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
import threading
import unittest
import uuid
from urllib.error import HTTPError
from urllib.request import urlopen
from adapters.native_navigation_modals import retired
from adapters.navigation_error_dismissal import NavigationErrorDismissal
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
from adapters.token_navigation_error_ui import TokenNavigationErrorUI
from feature_journeys.server import make_server
from feature_journeys.navigation_fixture import DIRECTORY
from feature_journeys.fixtures import context
from self_tests import test_navigation_missing as missing
from adapters.navigation_arrival import pose_packet

RUN,TICKET,ORIGIN=missing.RUN,missing.TICKET,missing.ORIGIN

DISMISS='d'*32


class NavigationLookupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=missing.NavigationMissingTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.native;self.path=self.fixture.world.root/'dismissal.json'
        self.ignore=False;self.lose=False;self.retain=False
        snapshot=self.source.snapshot;send=self.source.send
        def controls():
            value=snapshot();value['navigationErrorControlsVersion']=1
            if self.source.opened:
                for row in self.source.modal.records:
                    if not row['rootAlive']:continue
                    event=row['event'];control='navigation.error.ok.'+row['modalId']
                    value['controls'].append(dict(id=control,token=str(uuid.uuid5(uuid.NAMESPACE_URL,control+event['eventId'])),
                        enabled=True,focused=False,inputReady=True,modalId=row['modalId'],eventId=event['eventId'],runId=RUN,
                        lookupGeneration=event['lookupGeneration'],createdEpochMs=row['createdEpochMs'],messageSha256=row['messageSha256']))
            return value
        def normal_input(command):
            if not command['controlId'].startswith('navigation.error.ok.'):return send(command)
            disk=json.loads(self.path.read_text());self.assertEqual('pending',disk['phase'])
            self.assertEqual(command['controlId'],disk['input']['controlId'])
            self.assertEqual(command['controlToken'],disk['input']['controlToken'])
            self.assertEqual(self.source.sequence+1,command['sequence'])
            row=next(r for r in controls()['controls'] if r['id']==command['controlId'])
            self.assertEqual(row['token'],command['controlToken']);self.assertEqual(self.source.generation,command['generation'])
            self.source.sequence+=1;self.source.inputs.append(deepcopy(command))
            if not self.ignore:self.source.modal.finish(root=self.retain,listener=self.retain)
            if self.lose:raise NativeUIError('Synthetic applied original OK result lost')
            return dict(schemaVersion=1,bridgeId=self.source.bridge,commandId=command['commandId'],sequence=self.source.sequence,
                performed=True,error='',processId=31,updatedEpochMs=self.source.epoch),self.source.epoch
        self.source.snapshot=controls;self.source.send=normal_input
    def lookup(self):
        self.fixture.act();self.lookup_state=deepcopy(self.fixture.owner().state)
        self.source.provider.activate(RUN,DISMISS)
    def dismissal(self):
        return NavigationErrorDismissal(lambda intent:TokenNavigationErrorUI(PicoNavigationErrorIO(self.fixture.normal.io),intent,RUN),
            self.source.replies(),self.source.modals(),lambda:self.source.provider.snapshot(RUN),self.path,RUN,self.fixture.world.binding,
            self.source.provider.instance,self.source.inputs_config,self.source.owned_origin,self.source.guard,
            monotonic=lambda:self.source.clock,sleep=self.source.sleep)
    def dismiss(self):return self.dismissal().act(DISMISS,self.lookup_state['submitEpochMs'],lookup_ticket=TICKET)
    def test_normal_goto_to_new_challenge_ok_retains_one_original_response_and_three_second_retirement(self):
        before=self.source.book.storage();self.lookup();event=deepcopy(self.lookup_state['joined']['event'])
        self.assertEqual(dict(performed=True),self.dismiss());state=self.dismissal().state
        self.assertEqual('complete',state['phase']);self.assertEqual(event,state['joined']['event'])
        self.assertEqual(TICKET,state['joined']['response']['ticket']);self.assertEqual(DISMISS,state['original']['provider']['ticket'])
        self.assertEqual(1,len(self.source.provider.snapshot(RUN)['responses']));self.assertEqual(7,len(state['quiet']))
        self.assertEqual(1024,retired(state['last']['modal'],event)['selectedButton'])
        pose=self.fixture.world.arrival().read()
        self.assertEqual('B',pose_packet(pose,RUN,self.fixture.world.binding,missing.SCENE,self.source.epoch))
        self.assertEqual(before,self.source.book.storage());self.assertEqual(6,len(self.source.inputs))
        count=len(self.source.inputs);self.dismiss();self.assertEqual(count,len(self.source.inputs));self.assertEqual(2,len(self.source.controller_calls))
    def test_lost_lookup_submit_and_lost_ok_resume_their_own_original_intents_without_resends(self):
        self.source.lose='navigation.address:submit'
        with self.assertRaises(NativeUIError):self.fixture.act()
        self.source.lose=None;self.lookup();self.lose=True
        with self.assertRaises(NativeUIError):self.dismiss()
        self.assertEqual('pending',self.dismissal().state['phase']);count=len(self.source.inputs);self.lose=False
        self.assertEqual(dict(performed=True),self.dismiss());self.assertEqual(count,len(self.source.inputs))
        self.assertEqual(1,sum(r['controlId']=='navigation.address' and r['action']=='submit' for r in self.source.inputs))
    def test_wrong_lookup_ticket_or_original_submit_barrier_never_borrows_the_live_modal(self):
        self.lookup();count=len(self.source.inputs)
        for ticket,barrier in ((DISMISS,self.lookup_state['submitEpochMs']),(TICKET,self.source.epoch+1)):
            with self.subTest(ticket=ticket,barrier=barrier),self.assertRaises(NativeUIError):
                self.dismissal().act(DISMISS,barrier,lookup_ticket=ticket)
            self.assertEqual(count,len(self.source.inputs));self.assertFalse(self.path.exists())
    def test_consumed_but_ignored_ok_or_retained_qobjects_never_replay_or_claim_retirement(self):
        for fault in ('ignore','retain'):
            self.setUp();self.lookup();setattr(self,fault,True)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.dismiss()
            count=len(self.source.inputs)
            with self.assertRaises(NativeUIError):self.dismiss()
            self.assertEqual(count,len(self.source.inputs));self.assertEqual('pending',self.dismissal().state['phase'])
    def test_normal_submit_real_loopback_404_body_and_header_survive_later_dismissal_challenge(self):
        server=make_server('r'*32,'p'*32,navigation_resources=self.source.provider)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.source.owned_origin=f'http://127.0.0.1:{server.server_port}';responses=[]
        def fetch():
            try:
                with urlopen(self.source.owned_origin+DIRECTORY+'/'+context(RUN)['hidden'],timeout=2) as unexpected:unexpected.read()
            except HTTPError as response:
                try:
                    body=response.read();identity=response.headers['X-Overte-Fixture-Response']
                    responses.append((response.code,body,identity));return responses[-1]
                finally:response.close()
            self.fail('Owned missing name did not return HTTP 404')
        self.source.fetch_missing=fetch
        try:
            self.lookup();self.dismiss();state=self.dismissal().state
            self.assertEqual(1,len(responses));status,body,identity=responses[0];receipt=state['joined']['response']
            self.assertEqual(404,status);self.assertEqual(identity,receipt['responseId'])
            self.assertEqual(hashlib.sha256(body).hexdigest(),receipt['sha256']);self.assertEqual(len(body),receipt['bytes'])
            self.assertEqual(TICKET,receipt['ticket']);self.assertEqual(DISMISS,state['original']['provider']['ticket'])
            self.assertEqual(self.source.owned_origin,state['joined']['event']['origin'])
            self.assertEqual(6,len(self.source.inputs));self.assertEqual('complete',state['phase'])
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual(0,server.internal_errors)


if __name__=='__main__':unittest.main()
