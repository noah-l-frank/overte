"""Pending versus running membership counterexamples, without a compiler."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_script_membership import validate, accept
from adapters.native_script_observation import running_owned_engine
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_observation import Boundary


def manager(instance='a'*32, url='file:///actual/private/owned/main.js', generation=1, epoch=15000):
    return dict(instance=instance,assigned=generation>0,url=url,loadGeneration=generation,assignedEpochMs=epoch)


def membership_source(packet, rows=None, revision=None):
    if rows is None:
        rows=[manager(engine['required']['instance'],engine['url']) for engine in packet['source']['engines']]
    packet['source'].update(membershipSourceVersion=1,membership=dict(complete=True,
        revision=len(rows) if revision is None else revision,managers=deepcopy(rows)))


class ScriptMembershipTests(unittest.TestCase):
    def source(self, rows=None, revision=1):
        boundary=Boundary();state=dict(rows=[manager()] if rows is None else rows,revision=revision)
        def measured(packet):
            if not state['rows']:packet['source']['engines']=[]
            membership_source(packet,state['rows'],state['revision'])
        boundary.mutate=measured
        return boundary,boundary.reader(),state

    def test_actual_pending_manager_is_present_even_when_no_public_engine_is_running(self):
        source,reader,state=self.source()
        def pending(packet):
            packet['source']['engines']=[];membership_source(packet,state['rows'],state['revision'])
        source.mutate=pending
        actual=reader.read(0,require_membership=True)
        self.assertEqual([manager()],actual['source']['membership']['managers'])
        with self.assertRaises(NativeUIError):running_owned_engine(actual,manager()['url'])
        self.assertEqual({'schemaVersion','commandId','action'},set(source.commands[0]))

    def test_unassigned_manager_is_an_explicit_observation_not_a_missing_extension(self):
        row=manager(url='',generation=0,epoch=0)
        source,reader,_state=self.source([row])
        self.assertEqual(row,reader.read(0,require_membership=True)['source']['membership']['managers'][0])

    def test_complete_current_empty_inventory_is_distinct_from_unsupported_or_partial_source(self):
        source,reader,state=self.source([],0)
        self.assertEqual([],reader.read(0,require_membership=True)['source']['membership']['managers'])
        for missing in ('absent','incomplete','boolean-version'):
            def mutate(packet):
                if missing=='incomplete':packet['source'].update(membershipSourceVersion=1,membership={'complete':False})
                elif missing=='boolean-version':membership_source(packet);packet['source']['membershipSourceVersion']=True
            source=Boundary();source.mutate=mutate
            with self.subTest(missing=missing),self.assertRaises(NativeUIError):source.reader().read(0,require_membership=True)

    def test_narrow_legacy_reader_can_parse_old_source_but_requirement_never_downgrades(self):
        source=Boundary();reader=source.reader();first=reader.read(0)
        with self.assertRaises(NativeUIError):reader.read(first['sequence'],require_membership=True)
        source.mutate=membership_source;second=reader.read(first['sequence'],require_membership=True)
        source.mutate=None
        with self.assertRaises(NativeUIError):reader.read(second['sequence'])

    def test_revision_must_advance_for_actual_membership_change_and_retired_instance_cannot_return(self):
        source,reader,state=self.source();first=reader.read(0,require_membership=True)
        state['rows']=[]
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        state['revision']=2;second=reader.read(first['sequence'])
        self.assertEqual({'a'*32},reader.retired_managers)
        state.update(rows=[manager()],revision=3)
        with self.assertRaises(NativeUIError):reader.read(second['sequence'])

    def test_load_url_and_epoch_are_immutable_for_an_original_generation(self):
        for edit in ({'url':'file:///foreign/main.js'},{'assignedEpochMs':16000},{'assigned':False}):
            source,reader,state=self.source();first=reader.read(0,require_membership=True)
            state['rows'][0].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_genuinely_new_load_generation_preserves_original_assignment_epoch(self):
        source,reader,state=self.source();first=reader.read(0,require_membership=True)
        state['rows'][0].update(url='file:///actual/private/owned/new.js',loadGeneration=3,assignedEpochMs=18000)
        packet=reader.read(first['sequence'])
        self.assertEqual(18000,packet['source']['membership']['managers'][0]['assignedEpochMs'])
        self.assertEqual(1,packet['source']['membership']['revision']) # URL assignment is not set membership.

    def test_generation_or_native_capture_clock_regression_is_not_fresh_membership(self):
        source,reader,state=self.source([manager(generation=3,epoch=18000)])
        first=reader.read(0,require_membership=True)
        for edit in ({'loadGeneration':1},{'assignedEpochMs':17000}):
            old=deepcopy(state['rows'][0]);state['rows'][0].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(first['sequence'])
            state['rows'][0]=old
        reader.clock_ms=lambda:19900
        def rewound(packet):
            membership_source(packet,state['rows'],state['revision'])
            packet.update(requestedEpochMs=19900,capturedEpochMs=19900)
        source.mutate=rewound
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_duplicate_instances_oversized_or_inconsistent_properties_fail(self):
        for changes in ({'instance':'invalid'},{'assigned':1},{'assignedEpochMs':20001},
                        {'loadGeneration':True},{'url':'file:///private/main.js?secret=token'},
                        {'url':'https://user:private@host/main.js'},{'url':'file:///private\0/main.js'},
                        {'url':'about:private-code'},{'extra':True}):
            value=dict(complete=True,revision=1,managers=[manager()|changes])
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):validate(value,20000)
        for value in (dict(complete=True,revision=1,managers=[manager(),manager()]),
                      dict(complete=True,revision=129,managers=[manager()]*129),
                      dict(complete=False,managers=[]),dict(complete=True,revision=0,managers=[manager()]),
                      dict(complete=True,revision=True,managers=[])):
            with self.subTest(value=value),self.assertRaises(NativeUIError):validate(value,20000)

    def test_observed_retirement_does_not_mutate_earlier_owned_snapshot(self):
        old=dict(complete=True,revision=1,managers=[manager()])
        result,retired=accept(old,dict(complete=True,revision=2,managers=[]),set(),20000)
        result['managers'].append(manager('b'*32))
        self.assertEqual([manager()],old['managers']);self.assertEqual({'a'*32},retired)


if __name__=='__main__':unittest.main()
