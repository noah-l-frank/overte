"""Actual phase/provider reducers behind synthetic read-only HTTP boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from feature_journeys.graphics_resources import GraphicsResources
from feature_journeys.witness import Client,Journal
from overte_phone_graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending,GraphicsRunRetired

RUN='b'*32;TICKET='c'*32;URL='http://controlled.invalid/feature-fixture/v1'


class Fixture:
    def __init__(self):
        self.epoch=20000;self.calls=[];self.edit=None
        self.graphics=GraphicsResources(URL,clock_ms=lambda:self.epoch)
        self.graphics.provision(RUN);self.graphics.activate(RUN,TICKET)
        self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('graphics')
        self.journal.activate(RUN,TICKET)
        self.client=Client(URL,'x'*64);self.client.request=self.request
        self.client.graphics_status=self.status
    def request(self,path,value=None,method=None,**kwargs):
        assert value is None and method is None
        self.calls.append(path)
        if path=='/graphics-provider':result=self.graphics.ready()|dict(internalErrors=0)
        elif path=='/runs/'+RUN+'/graphics':
            assert set(kwargs)=={'graphics_nonce'};result=self.graphics.snapshot(RUN,kwargs['graphics_nonce'])
        elif path=='/runs/'+RUN+'/active':result=self.journal.active(RUN)
        elif path=='/runs/'+RUN:result=self.journal.snapshot(RUN)
        else:raise AssertionError('Unexpected fixture transport')
        if self.edit:self.edit(path,result)
        return deepcopy(result)
    def status(self):
        with patch('feature_journeys.witness.time.time',return_value=self.epoch/1000):return Client.graphics_status(self.client)
    def reader(self):return GraphicsFixtureReader(self.client,RUN,epoch_ms=lambda:self.epoch)


class GraphicsFixtureReaderTests(unittest.TestCase):
    def setUp(self):self.f=Fixture()
    def test_original_phase_and_two_provider_reads_attach_without_register_activate_or_input(self):
        f=self.f;source=f.reader();value=source.read()
        self.assertEqual(TICKET,value['ticket']);self.assertEqual('baseline',value['verb'])
        self.assertEqual(20000,value['afterEpochMs']);self.assertEqual(f.graphics.instance,source.instance)
        self.assertEqual(['/graphics-provider','/runs/'+RUN+'/graphics','/runs/'+RUN+'/active','/runs/'+RUN,'/runs/'+RUN+'/graphics'],f.calls)
        self.assertNotIn('state',value);self.assertNotIn('resolution',value)
    def test_actual_normal_graphics_arguments_are_read_without_returning_desired_state(self):
        f=self.f;other='d'*32;f.graphics.activate(RUN,other);f.journal.activate(RUN,other,'set-resolution',dict(value=.5))
        value=f.reader().read();self.assertEqual(dict(value=.5),value['inputs']);self.assertNotIn('renderScale',value)
    def test_retired_run_returns_original_retirement_before_reading_removed_phase(self):
        f=self.f;reader=f.reader();reader.read();f.graphics.retire(RUN);f.journal.close(RUN);f.client.closed=True
        before=len(f.calls)
        with self.assertRaises(GraphicsRunRetired) as caught:reader.read()
        self.assertFalse(caught.exception.status['active']);self.assertEqual(1,len(f.calls)-before)
        self.assertEqual(TICKET,caught.exception.status['sceneTicket'])
    def test_actor_can_attach_after_retirement_without_recreating_run(self):
        f=self.f;f.graphics.retire(RUN)
        with self.assertRaises(GraphicsRunRetired):f.reader().read()
        self.assertEqual(1,len(f.graphics.runs));self.assertFalse(f.graphics.runs[RUN]['active'])
    def test_ticket_race_is_pending_without_relabeling_original_phase(self):
        f=self.f
        def changed(path,value):
            if path=='/runs/'+RUN:value['ticket']='d'*32
        f.edit=changed
        with self.assertRaises(GraphicsPhasePending):f.reader().read()
        self.assertEqual(TICKET,f.journal.active(RUN)['ticket'])
    def test_provider_phase_crossing_the_read_is_pending_and_preserves_original_history(self):
        f=self.f
        def changed(path,value):
            if path=='/runs/'+RUN:
                f.graphics.activate(RUN,'d'*32);f.journal.activate(RUN,'d'*32,'close',{})
        f.edit=changed;reader=f.reader()
        with self.assertRaises(GraphicsPhasePending):reader.read()
        self.assertEqual(2,len(reader.previous['activations']))
    def test_retirement_crossing_the_read_is_retired_and_never_borrows_old_ticket(self):
        f=self.f
        def changed(path,value):
            if path=='/runs/'+RUN:f.graphics.retire(RUN)
        f.edit=changed
        with self.assertRaises(GraphicsRunRetired):f.reader().read()
    def test_missing_stale_foreign_unhealthy_or_malformed_originals_fail(self):
        for path,edit in [('/runs/'+RUN,dict(sampleEpochMs=18499)),('/runs/'+RUN,dict(area='scripts')),
            ('/runs/'+RUN+'/active',dict(runId='f'*32)),('/runs/'+RUN+'/active',dict(schemaVersion=True)),
            ('/runs/'+RUN+'/active',dict(stimulus=dict(verb='set-resolution',inputs=dict(value=.77)))),
            ('/runs/'+RUN+'/graphics',dict(healthy=False)),('/runs/'+RUN+'/graphics',dict(instance='f'*32)),
            ('/runs/'+RUN+'/graphics',dict(capturedEpochMs=18499))]:
            f=Fixture();f.edit=lambda p,v,picked=path,edit=edit:v.update(edit) if p==picked else None
            with self.subTest(path=path,edit=edit),self.assertRaises((NativeUIError,ValueError)):f.reader().read()
    def test_existing_client_scope_is_pinned_without_silently_repairing_changed_metadata(self):
        for field,value in [('run','f'*32),('area','scripts'),('graphics_instance','f'*32),('closed',True)]:
            f=Fixture();reader=f.reader();reader.read();setattr(f.client,field,value);before=len(f.calls)
            with self.subTest(field=field),self.assertRaises((NativeUIError,ValueError)):reader.read()
            self.assertEqual(value,getattr(f.client,field))
            if field!='closed':self.assertEqual(before,len(f.calls))
    def test_provider_history_survives_reader_recreation_and_cannot_be_shortened(self):
        f=self.f;reader=f.reader();old=reader.read()['status'];f.graphics.activate(RUN,'d'*32);f.journal.activate(RUN,'d'*32,'close',{})
        new=f.reader().read(old)['status'];self.assertEqual(2,len(new['activations']))
        f.edit=lambda path,value:value.update(activations=value['activations'][:1],ticket=TICKET) if path.endswith('/graphics') else None
        with self.assertRaises((NativeUIError,ValueError)):f.reader().read(new)
    def test_actual_host_clock_cannot_regress_while_provider_remains_current(self):
        f=self.f;reader=f.reader();reader.read();reader.epoch_ms=lambda:19999
        with self.assertRaises(NativeUIError):reader.read()
    def test_boolean_or_foreign_client_provider_history_is_rejected_before_transport(self):
        for previous in (True,{},dict(instance='foreign')):
            f=Fixture();reader=f.reader();reader.read();f.client.graphics_previous=previous;before=len(f.calls)
            with self.subTest(previous=previous),self.assertRaises((NativeUIError,KeyError,ValueError)):reader.read()
            self.assertEqual(before,len(f.calls))

    def test_actual_fixture_origin_is_frozen_before_any_followup_transport(self):
        f=self.f;reader=f.reader();reader.read();f.client.url='http://other.invalid/feature-fixture/v1';before=len(f.calls)
        with self.assertRaises(NativeUIError):reader.read()
        self.assertEqual(before,len(f.calls))
    def test_original_read_barrier_cannot_precede_its_actual_activation(self):
        f=self.f
        f.edit=lambda path,value:value.update(sampleEpochMs=19999) if path=='/runs/'+RUN else None
        with self.assertRaises(NativeUIError):f.reader().read()
    def test_current_sample_cannot_reuse_an_old_provider_request_nonce(self):
        f=self.f;reader=f.reader();original=reader.read()['status'];actual=f.client.graphics_status
        f.client.graphics_status=lambda:deepcopy(original)
        with self.assertRaises(ValueError):reader.read()
        f.client.graphics_status=actual
    def test_explicit_recovery_floor_cannot_replace_a_newer_provider_history(self):
        f=self.f;reader=f.reader();old=reader.read()['status'];f.graphics.activate(RUN,'d'*32);f.journal.activate(RUN,'d'*32,'close',{})
        current=reader.read()['status'];other=deepcopy(current);other['activations'][0]['activatedEpochMs']-=1
        with self.assertRaises(ValueError):reader.status(other)
        self.assertEqual(current,reader.previous)

    def test_an_independent_sampler_can_advance_the_actual_client_provider_floor(self):
        f=self.f;reader=f.reader();reader.read();f.graphics.activate(RUN,'d'*32);f.journal.activate(RUN,'d'*32,'close',{})
        newer=f.client.graphics_status();value=reader.read(newer)
        self.assertEqual('d'*32,value['ticket']);self.assertEqual(newer['activations'],value['status']['activations'])


if __name__=='__main__':unittest.main()
