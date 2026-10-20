"""Original-source joins with synthetic boundaries; no product/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tests/device'))
sys.path.insert(0, str(ROOT / 'tests/device/adapters/android-phone'))
from overte_phone_script_measurements import compose, PhoneScriptMeasurements
from overte_phone_script_file_scope import join as file_scope
from self_tests.test_native_script_files import Boundary as FileStorage
from overte_phone_script_files import PhoneScriptFileIO
from script_file_native_boundary import FileNativeBoundary
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_files import originals
from adapters.token_script_file_ui import file_url
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_observation import Boundary as Execution, code_source, effect_source, RUN
from self_tests.test_native_script_loads import history, event
from self_tests.test_native_script_membership import membership_source, manager
from self_tests.test_native_feature_observation import Boundary as Lifecycle
from self_tests.test_script_ui_inventory import inventory, picker
from self_tests.test_script_manager_status import observed

TICKET = 'b' * 32
FIXTURE = 'http://fixture.test:12345/feature-fixture/v1/runs/' + RUN + '/'
MISSING = FIXTURE + 'tickets/' + TICKET + '/missing.js'


class ScriptMeasurementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / ('feature-script-' + RUN); self.root.mkdir()
        for name, body in originals(RUN).items():
            path = self.root / name; path.parent.mkdir(exist_ok=True); path.write_bytes(body)
        self.directory = self.root.as_uri()
        source = Execution(); source.engine['url'] = self.directory + '/script.js'
        source.engine['required']['modules'][0]['url'] = self.directory + '/companion.js'
        def measured(packet):
            code_source(packet, originals(RUN)['script.js'].decode()); effect_source(packet); history(packet, [])
            membership_source(packet)
        source.mutate = measured
        self.execution_source, self.execution_reader = source, source.reader()
        self.execution = self.execution_reader.read(0, require_effects=True, require_code_identity=True, require_load_history=True)
        self.file_birth=self.execution['instance']
        file_ui = FileNativeBoundary(self.root)
        file_ui.mutate = lambda packet: packet.update(scriptInventory=inventory([observed(statusText='', labelText='', labelVisible=False)]))
        self.ui_source = file_ui
        self.ui_reader = PhoneScriptFileIO(file_ui.send, lambda: json.dumps(file_ui.value), lambda: 20000,
            lambda: True, 31, monotonic=lambda: file_ui.ui.clock, sleep=file_ui.ui.sleep)
        self.ui = self.ui_reader.capture()
        self.service = dict(schemaVersion=1, instance='f' * 32, sampleSequence=1, sampleEpochMs=20000,
                            complete=True, scripts=[dict(url=source.engine['url'], path=file_url(source.engine['url']))])
        lifecycle = Lifecycle(); lifecycle.mutate = lambda packet: packet.update(processId=31,instance=self.execution['instance'])
        self.lifecycle_source = lifecycle
        self.lifecycle_reader = NativeFeatureObservation(lifecycle.send, lifecycle.original, lambda: 20000,
            lifecycle.guard, 31, monotonic=lambda: lifecycle.clock, sleep=lifecycle.sleep)
        self.lifecycle = self.lifecycle_reader.read(0)
        self.okay, self.clock = True, 0.0

    def measured(self, **changes):
        values = dict(run=RUN, ticket=TICKET, directory=self.directory, fixture_url=FIXTURE, pid=31,
                      execution=self.execution, ui=self.ui, service=self.service, lifecycle=self.lifecycle,
                      epoch=20000, after_epoch=19000) | changes
        return compose(**values)

    def empty(self):
        self.execution['source']['engines'] = []; self.execution['source']['effects']['entities'] = []
        self.service['scripts'] = []
        membership_source(self.execution,[],2)

    def reader(self, **changes):
        def service(after):
            self.service['sampleSequence'] = after + 1
            return deepcopy(self.service), 20000
        values = dict(run=RUN, directory=self.directory, fixture_url=FIXTURE, execution=self.execution_reader,
            ui=self.ui_reader, service=service, lifecycle=self.lifecycle_reader,
            verify_directory=lambda: self.directory, guard=lambda: self.okay,
            file_instance=lambda:self.file_birth,monotonic=lambda: self.clock) | changes
        return PhoneScriptMeasurements(**values)

    def test_live_reader_reacquires_all_original_sources_and_preserves_original_lifecycle(self):
        reader = self.reader()
        first = reader.read(TICKET, 19000); second = reader.read(TICKET, 19000)
        self.assertEqual(first, second)
        self.assertEqual(2, reader.service_sequence)
        self.assertEqual(3, self.execution_reader.sequence)
        self.assertEqual(3, self.lifecycle_reader.sequence)
        self.assertTrue(all(command['action'] == 'feature-script-observe' for command in self.execution_source.commands))
        self.assertEqual([], self.ui_source.input_requests)

    def test_live_reader_missing_extension_never_substitutes_a_closed_ui(self):
        self.ui_source.mutate = None
        with self.assertRaisesRegex(NativeUIError, '^Phone Script measurement sources are unavailable or inconsistent$'):
            self.reader().read(TICKET, 19000)

    def test_live_reader_ignored_original_source_cannot_retime_previous_result(self):
        self.execution_source.ignore = True
        with self.assertRaises(NativeUIError): self.reader().read(TICKET, 19000)
        self.assertEqual([], self.ui_source.input_requests)

    def test_live_reader_wrong_original_directory_or_candidate_loss_blocks_new_capture(self):
        for guard, directory in ((False, self.directory), (True, 'file:///foreign/owned')):
            before = len(self.execution_source.commands)
            reader = self.reader(guard=lambda: guard, verify_directory=lambda: directory)
            with self.subTest(guard=guard, directory=directory), self.assertRaises(NativeUIError): reader.read(TICKET, 19000)
            self.assertEqual(before, len(self.execution_source.commands))

    def test_live_reader_foreign_or_missing_actual_file_source_birth_cannot_mix_with_execution(self):
        for instance in ('f'*32,None):
            reader=self.reader(file_instance=lambda:instance)
            with self.subTest(instance=instance),self.assertRaises(NativeUIError):reader.read(TICKET,19000)

    def test_live_reader_whole_acquisition_deadline_includes_original_fixture_check(self):
        def late():
            self.clock = 21
            return self.directory
        before = len(self.execution_source.commands)
        with self.assertRaises(NativeUIError): self.reader(verify_directory=late).read(TICKET, 19000)
        self.assertEqual(before, len(self.execution_source.commands))

    def test_live_reader_rewritten_service_instance_or_replayed_cursor_is_rejected(self):
        for fault in ('instance', 'cursor'):
            self.service['instance'] = 'f' * 32
            reader = self.reader(); reader.read(TICKET, 19000)
            original = reader.service
            def rewrite(after):
                value, epoch = original(after)
                if fault == 'instance': value['instance'] = 'd' * 32
                else: value['sampleSequence'] = after
                return value, epoch
            reader.service = rewrite
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): reader.read(TICKET, 19000)

    def file_packet(self, operation='observe'):
        if not hasattr(self,'file_storage'):
            self.file_storage=FileStorage(self.root.parent);self.file_storage.root=self.root
            self.file_storage.owner='9'*64
            self.file_storage.mutate=lambda packet:packet.update(instance=self.execution['instance'])
            self.file_native=self.file_storage.native()
        self.file_native.request(operation,RUN,'9'*64)
        return deepcopy(self.file_native.last_packet)

    def scoped(self, **changes):
        values=dict(run=RUN,ticket=TICKET,directory=self.directory,fixture_url=FIXTURE,pid=31,
            sources=dict(epochMs=20000,execution=self.execution,ui=self.ui,service=self.service,lifecycle=self.lifecycle),
            files=changes['files'] if 'files' in changes else self.file_packet(),epoch=20000,after_epoch=19000)
        return file_scope(**(values|changes))

    def test_file_scope_uses_actual_bytes_presence_and_physical_resources_without_host_intent(self):
        actual=self.scoped()
        self.assertEqual(['entity:script-effect','file:script-fixtures','panel:script-manager','script:owned-script'],actual['resources'])
        self.assertEqual(self.measured(),actual['measurement'])
        self.assertEqual(1,actual['fileCursor']['sequence'])
        self.assertEqual(self.directory,actual['fileCursor']['directory'])

    def test_file_scope_original_absence_after_release_does_not_hide_unclosed_ui(self):
        self.empty();self.file_packet();self.file_native.request('release',RUN,'9'*64)
        packet=self.file_packet('locate')
        actual=self.scoped(files=packet)
        self.assertEqual(['panel:script-manager'],actual['resources'])
        self.assertTrue(actual['measurement']['state']['open'])
        self.ui['scriptInventory']=inventory(tabletPresent=False,tabletShown=False)
        self.assertEqual([],self.scoped(files=packet)['resources'])

    def test_file_scope_oldest_original_file_epoch_is_preserved_without_retiming(self):
        packet=self.file_packet();packet.update(capturedEpochMs=19980,requestedEpochMs=19980)
        actual=self.scoped(files=packet)
        self.assertEqual(19980,actual['measurement']['capturedEpochMs'])
        self.assertEqual(19980,actual['fileCursor']['capturedEpochMs'])

    def test_file_scope_missing_zero_tick_effect_data_cannot_prove_resource_absence(self):
        from self_tests.test_native_script_observation import effect_source
        effect_source(self.execution,ticks=0)
        actual=self.scoped()
        self.assertEqual(0,actual['measurement']['state']['effects'])
        self.assertIn('entity:script-effect',actual['resources'])
        self.execution['source']['effects']['entities'][0]['userData']=''
        with self.assertRaises(NativeUIError):self.scoped()

    def test_file_scope_replayed_cursor_regressed_clock_or_foreign_birth_is_rejected(self):
        first=self.scoped();packet=self.file_packet()
        for previous in (first['fileCursor']|dict(sequence=packet['sequence']),
                         first['fileCursor']|dict(capturedEpochMs=20001),
                         first['fileCursor']|dict(instance='f'*32),
                         first['fileCursor']|dict(directory='file:///foreign/private'),
                         first['fileCursor']|dict(fileScopeVersion=True)):
            with self.subTest(fields=list(previous)),self.assertRaises(NativeUIError):self.scoped(files=packet,previous=previous)
        actual=self.scoped(files=packet,previous=first['fileCursor'])
        self.assertEqual(packet['sequence'],actual['fileCursor']['sequence'])

    def test_file_scope_foreign_stale_prebarrier_missing_and_ack_only_sources_cannot_be_substituted(self):
        packet=self.file_packet()
        for changes in (dict(instance='f'*32),dict(processId=32),dict(runId='f'*32),
                        dict(schemaVersion=True),dict(requestId='foreign'),
                        dict(requestedEpochMs=18000,capturedEpochMs=18000),
                        dict(requestedEpochMs=18999,capturedEpochMs=18999),
                        dict(requestedEpochMs=20000,capturedEpochMs=20300),
                        dict(operation='stage',source=dict(performed=True)),
                        dict(source=dict(locationVersion=1,exists=False)),dict(source={})):
            with self.subTest(fields=list(changes)),self.assertRaises((ValueError,RuntimeError)):
                self.scoped(files=packet|changes)

    def test_file_scope_original_changed_companion_and_missing_file_fail_instead_of_becoming_empty_resources(self):
        self.file_packet();(self.root/'companion.js').write_bytes(b'actual foreign companion bytes')
        with self.assertRaises(NativeUIError):self.scoped()
        (self.root/'companion.js').unlink()
        with self.assertRaises(NativeUIError):self.scoped()

    def test_file_scope_location_presence_alone_cannot_prove_controlled_file_bytes(self):
        packet=self.file_packet('locate')
        with self.assertRaises(NativeUIError):self.scoped(files=packet)

    def failure(self):
        self.empty()
        status = 'Failed to load ' + MISSING + ': server returned 404'
        self.ui['scriptInventory']['managers'] = [observed(statusText=status, labelText=status)]
        history(self.execution, [event(url=MISSING)])

    def test_live_original_engine_code_loaded_companion_and_local_effect_supply_six_actual_fields(self):
        actual = self.measured()
        self.assertEqual(dict(running=['owned-script'], picker=False, error='none', effects=2,
                              open=True, companions=['companion.js']), actual['state'])
        self.assertEqual(self.execution['source']['engines'][0]['required']['instance'], actual['engineInstance'])
        self.assertEqual(2, actual['effect']['ticks'])
        self.assertEqual(self.lifecycle['lifecycle'], actual['lifecycle'])
        actual['lifecycle']['launches'] = 999
        self.assertEqual(1, self.lifecycle['lifecycle']['launches'])

    def test_oldest_original_capture_is_preserved_without_retiming(self):
        self.ui['capturedEpochMs'] = 19980
        self.assertEqual(19980, self.measured()['capturedEpochMs'])

    def test_same_pid_with_a_different_native_lifecycle_birth_cannot_mix_sources(self):
        self.lifecycle['instance']='f'*32
        with self.assertRaises(NativeUIError):self.measured()

    def test_original_android_service_path_has_no_file_scheme(self):
        self.assertTrue(self.service['scripts'][0]['path'].startswith('/'))
        self.assertEqual(['owned-script'], self.measured()['state']['running'])
        self.service['scripts'][0]['path'] = self.service['scripts'][0]['url']
        with self.assertRaises(NativeUIError): self.measured()

    def test_complete_current_absence_can_measure_closed_baseline(self):
        self.empty(); self.ui['scriptInventory'] = inventory(tabletPresent=False, tabletShown=False)
        self.assertEqual(dict(running=[], picker=False, error='none', effects=0, open=False, companions=[]), self.measured()['state'])

    def test_actual_picker_without_input_carrier_is_independent_of_execution(self):
        self.empty(); self.ui['controls'] = []; self.ui['scriptInventory']['pickers'] = [picker()]
        self.assertTrue(self.measured()['state']['picker']); self.assertEqual([], self.measured()['state']['running'])

    def test_module_not_loaded_or_missing_effect_is_not_replaced_with_expected_result(self):
        self.execution['source']['engines'][0]['required']['modules'][0]['loaded'] = False
        self.execution['source']['effects']['entities'] = []
        self.assertEqual([], self.measured()['state']['companions']); self.assertEqual(0, self.measured()['state']['effects'])

    def test_wrong_submitted_code_units_or_digest_cannot_borrow_owned_source_url(self):
        original = deepcopy(self.execution)
        for key, value in (('sha256', 'f' * 64), ('codeUnits', 1), ('submitted', False)):
            self.execution = deepcopy(original); self.execution['source']['engines'][0]['code'][key] = value
            with self.subTest(key=key), self.assertRaises(NativeUIError): self.measured()

    def test_unknown_owned_source_alias_duplicate_or_retiring_engine_is_not_empty(self):
        original = deepcopy(self.execution)
        for fault in ('unknown', 'encoded', 'query', 'duplicate', 'stopping', 'finished'):
            self.execution = deepcopy(original); engine = self.execution['source']['engines'][0]
            if fault == 'unknown': engine['url'] = self.directory + '/foreign.js'
            elif fault == 'encoded': engine['url'] = self.directory + '/%73cript.js'
            elif fault == 'query': engine['url'] += '?stale=1'
            elif fault == 'duplicate':
                other = deepcopy(engine); other['required']['instance'] = '9' * 32
                self.execution['source']['engines'].append(other)
            else: engine[fault] = True
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.measured()

    def test_mismatched_engine_and_service_or_wrong_native_row_path_fails(self):
        original = deepcopy(self.service)
        for rows in ([], [original['scripts'][0] | {'path': '/foreign/script.js'}],
                     [original['scripts'][0] | {'url': 'file:///foreign/script.js'}]):
            self.service['scripts'] = rows
            with self.subTest(rows=rows), self.assertRaises(NativeUIError): self.measured()

    def test_foreign_engine_cannot_execute_a_companion_from_owned_tree(self):
        other = deepcopy(self.execution['source']['engines'][0]); other['url'] = 'file:///foreign/main.js'
        other['required']['instance'] = '9' * 32
        self.execution['source']['engines'].append(other)
        with self.assertRaises(NativeUIError): self.measured()

    def test_unexpected_or_cached_companion_is_not_projected_to_expected_alias(self):
        module = self.execution['source']['engines'][0]['required']['modules'][0]
        for edit in ({'url': self.directory + '/unexpected.js'}, {'cached': True}):
            original = deepcopy(module); module.update(edit)
            with self.subTest(edit=edit), self.assertRaises(NativeUIError): self.measured()
            module.clear(); module.update(original)

    def test_extra_foreign_module_is_not_dropped_from_an_otherwise_valid_companion_result(self):
        required = self.execution['source']['engines'][0]['required']
        required['modules'].append(required['modules'][0] | dict(url='https://foreign.test/extra.js', sequence=2))
        required['sequence'] = 2
        with self.assertRaises(NativeUIError): self.measured()

    def test_foreign_effect_color_userdata_or_heap_cannot_prove_execution(self):
        row = self.execution['source']['effects']['entities'][0]
        for edit in ({'hostType': 'domain'}, {'type': 'Sphere'}, {'color': [0, 0, 0]},
                     {'userData': json.dumps(dict(runId='a' * 32, ticks=2))}, {'userData': ''}):
            original = deepcopy(row); row.update(edit)
            with self.subTest(edit=edit), self.assertRaises(NativeUIError): self.measured()
            row.clear(); row.update(original)

    def test_orphan_effect_after_stop_is_not_clean_absence(self):
        self.execution['source']['engines'] = []; self.service['scripts'] = []
        with self.assertRaises(NativeUIError): self.measured()

    def test_pending_known_manager_cannot_be_mistaken_for_clean_cancelled_or_stopped_execution(self):
        self.empty()
        membership_source(self.execution,[manager(url=self.directory+'/script.js')],3)
        with self.assertRaises(NativeUIError):self.measured()

    def test_running_engine_requires_original_matching_assigned_manager_identity_and_url(self):
        original=deepcopy(self.execution)
        for rows in ([],[manager('b'*32,self.directory+'/script.js')],
                     [manager(url='',generation=0,epoch=0)],
                     [manager(url=self.directory+'/script-bundle/main.js')]):
            self.execution=deepcopy(original);membership_source(self.execution,rows,3)
            with self.subTest(rows=rows),self.assertRaises(NativeUIError):self.measured()

    def test_actual_not_found_requires_current_original_callback_and_independent_visible_label(self):
        self.failure()
        self.assertEqual('not-found', self.measured()['state']['error'])
        self.assertEqual([], self.measured()['state']['running'])

    def test_missing_callback_wrong_status_old_callback_or_foreign_ticket_cannot_borrow_label(self):
        self.failure(); original = deepcopy(self.execution)
        for fault in ('missing', 'denied', 'stale', 'foreign-ticket', 'success'):
            self.execution = deepcopy(original)
            callback = self.execution['source']['loads']['events'][0]
            if fault == 'missing': history(self.execution, [])
            elif fault == 'denied': callback['status'] = 'AccessDenied'
            elif fault == 'stale': callback['callbackEpochMs'] = 18999
            elif fault == 'foreign-ticket': callback['url'] = MISSING.replace(TICKET, 'c' * 32)
            else: callback.update(success=True, status='Success')
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.measured()

    def test_historical_or_foreign_label_broken_binding_and_hidden_error_fail(self):
        self.failure(); original = deepcopy(self.ui)
        for edit in ({'labelText': 'old error'}, {'labelVisible': False},
                     {'statusText': 'Failed to load missing.js', 'labelText': 'Failed to load missing.js'},
                     {'statusText': 'Failed to load ' + MISSING.replace('fixture.test', 'foreign.test'),
                      'labelText': 'Failed to load ' + MISSING.replace('fixture.test', 'foreign.test')}):
            self.ui = deepcopy(original); self.ui['scriptInventory']['managers'][0].update(edit)
            with self.subTest(edit=edit), self.assertRaises(NativeUIError): self.measured()
        self.ui = deepcopy(original)
        with self.assertRaises(NativeUIError): self.measured(ticket='c' * 32)

    def test_closing_actual_page_does_not_republish_retained_old_error(self):
        self.failure(); self.ui['scriptInventory']['tabletShown'] = False
        self.assertEqual('none', self.measured()['state']['error']); self.assertFalse(self.measured()['state']['open'])

    def test_empty_root_status_with_a_still_visible_old_error_is_not_measured_as_none(self):
        self.ui['scriptInventory']['managers'][0].update(statusText='', labelText='Failed to load ' + MISSING, labelVisible=True)
        with self.assertRaises(NativeUIError): self.measured()

    def test_missing_mandatory_extensions_are_not_green_empty_defaults(self):
        original = deepcopy(self.execution)
        for version, data in (('sourceIdentityVersion', 'code'), ('effectSourceVersion', 'effects'), ('loadSourceVersion', 'loads'),
                              ('membershipSourceVersion','membership')):
            self.execution = deepcopy(original); del self.execution['source'][version]
            if data == 'code':
                for engine in self.execution['source']['engines']: del engine[data]
            else: del self.execution['source'][data]
            with self.subTest(version=version), self.assertRaises(NativeUIError): self.measured()

    def test_stale_prebarrier_foreign_process_and_incomplete_inventories_fail(self):
        originals_tuple = deepcopy((self.execution, self.ui, self.service, self.lifecycle))
        for fault in ('execution-clock', 'ui-clock', 'service-clock', 'lifecycle-clock', 'prebarrier', 'ui-pid', 'lifecycle-pid', 'incomplete'):
            self.execution, self.ui, self.service, self.lifecycle = deepcopy(originals_tuple)
            if fault == 'execution-clock': self.execution['capturedEpochMs'] = 18000
            elif fault == 'ui-clock': self.ui['capturedEpochMs'] = 18000
            elif fault == 'service-clock': self.service['sampleEpochMs'] = 18000
            elif fault == 'lifecycle-clock': self.lifecycle['capturedEpochMs'] = 18000
            elif fault == 'prebarrier': self.ui['capturedEpochMs'] = 18999
            elif fault == 'ui-pid': self.ui['processId'] = 32
            elif fault == 'lifecycle-pid': self.lifecycle['processId'] = 32
            else: self.ui['scriptInventory'].update(complete=False, managers=[])
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.measured()

    def test_system_request_unknown_status_or_fixture_scope_never_becomes_none(self):
        self.ui['scriptInventory']['pickers'] = [picker(visible=False, requestId='original-system-request')]
        with self.assertRaises(NativeUIError): self.measured()
        self.ui['scriptInventory']['pickers'] = []
        self.ui['scriptInventory']['managers'][0]['statusText'] = 'Client scripts cannot be loaded over ATP.'
        with self.assertRaises(NativeUIError): self.measured()
        for fixture in (FIXTURE + '?private=token', FIXTURE.replace(RUN, 'a' * 32), 'file:///private/'):
            with self.subTest(fixture=fixture), self.assertRaises((NativeUIError, ValueError)): self.measured(fixture_url=fixture)


if __name__ == '__main__': unittest.main()
