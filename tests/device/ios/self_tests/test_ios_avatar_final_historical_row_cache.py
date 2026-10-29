"""Real postlogout prefix files and Final2 wiring; native edges are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import scope as read_scope
from ios.adapters.avatar_api_entry import scope as api_scope
from ios.adapters.avatar_postlogout_reads import IOSAvatarPostLogoutReads
from ios.adapters import avatar_state as state_source
from feature_journeys import contract as feature_contract
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.self_tests import test_ios_avatar_postlogout_reads as fixture
from ios.self_tests import test_ios_avatar_held_final as final_fixture


class AvatarHistoricalRowCacheTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarPostLogoutReadsTests();self.addCleanup(self.f.doCleanups);self.f.setUp()
        self.owner=self.f.owner();self.rows=[];self.prefixes=[]
        for _index in range(2):
            self.rows.append(self.owner.capture());self.prefixes.append(deepcopy(self.owner.previous))
        self.cache=AvatarRecordCache()

    def archive(self,value,cache):
        o=self.owner
        return IOSAvatarPostLogoutReads.archive(value,o.store,o.root,o.binding,o.run,o.role,o.subject,o.lock,
            child_run=o.inputs['childRunId'],fixture_url=o.inputs['fixtureUrl'],ticket=o.inputs['ticket'],
            baseline=o.inputs['baseline'],logout_before=o.inputs['logoutBefore'],historical_rows=cache)

    def account_path(self,history):
        parts=history.row_material(history.state['rows'][0])['parts'];before=parts['before'];o=self.owner
        originals=OriginalFrameStore(o.root,o.binding,o.run,o.role,lambda:True,lambda *_:None,
            namespace='avatar-'+o.subject+'-account-read',schema_prefix='avatar'+o.subject.capitalize()+'AccountRead')
        return originals.path(before['row']['original'])

    def test_growing_actual_prefix_reuses_completed_old_row_and_preserves_literal_membership_and_proof(self):
        literal=self.archive(self.prefixes[-1],None);expected=literal.proof(literal.state['rows'][-1]);queries=deepcopy(self.f.calls)
        first=self.archive(self.prefixes[0],self.cache)
        monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
        monitor.use_tool_id(tool,'avatar-actual-row-fields');seen=[];code=IOSAvatarPostLogoutReads._record_fields.__code__
        def call(actual,_offset):seen.append(actual)
        monitor.register_callback(tool,monitor.events.PY_START,call);monitor.set_local_events(tool,code,monitor.events.PY_START)
        try:
            # Only the genuinely new second row cold-decodes twice. The old
            # first row still receives the primitive's fresh original guards.
            second=self.archive(self.prefixes[-1],self.cache);self.assertEqual([code,code],seen)
            seen.clear();self.archive(self.prefixes[-1],self.cache);self.assertEqual([],seen)
            self.archive(self.prefixes[-1],None);self.assertEqual([code,code],seen);seen.clear()
            with read_scope(fresh=True) as a:actual=second.proof(second.state['rows'][-1])
            self.assertEqual([code],seen);seen.clear()
            with read_scope(fresh=True) as b:again=second.proof(second.state['rows'][-1])
            self.assertEqual([code],seen)
            self.assertEqual(expected,actual);self.assertEqual(actual,again);self.assertEqual(a,b)
            self.assertEqual(queries,self.f.calls)
            # Caller mutation cannot alter another archived state or input.
            second.state['rows'].clear();self.assertEqual(1,len(first.state['rows']))
            self.assertEqual(2,len(self.archive(self.prefixes[-1],self.cache).state['rows']))
        finally:
            monitor.set_local_events(tool,code,0);monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)

    def test_same_inode_account_bytes_changed_after_warm_prefix_refuse_without_transport(self):
        history=self.archive(self.prefixes[-1],self.cache);path=self.account_path(history);raw=path.read_bytes();before=path.stat();queries=deepcopy(self.f.calls)
        directory=TemporaryDirectory();self.addCleanup(directory.cleanup);outside=Path(directory.name);outside.chmod(0o700)
        saved=outside/'original-account-bytes';saved.write_bytes(raw);saved.chmod(0o600)
        path.write_bytes(raw[:-1]+(b' ' if raw[-1:]!=b' ' else b'\n'));self.assertEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):history.parse(self.prefixes[-1])
        self.assertEqual(raw,saved.read_bytes());self.assertEqual(queries,self.f.calls)

    def test_same_bytes_replaced_account_inode_refuses_without_unknown_membership_mask(self):
        history=self.archive(self.prefixes[-1],self.cache);path=self.account_path(history);raw=path.read_bytes();before=path.stat();queries=deepcopy(self.f.calls)
        directory=TemporaryDirectory();self.addCleanup(directory.cleanup);outside=Path(directory.name);outside.chmod(0o700)
        saved=outside/'original-account-inode';os.replace(path,saved)
        with path.open('xb') as stream:stream.write(raw)
        path.chmod(0o600);self.assertEqual(before.st_ino,saved.stat().st_ino);self.assertNotEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):history.parse(self.prefixes[-1])
        self.assertEqual(raw,saved.read_bytes());self.assertEqual(queries,self.f.calls)

    def test_wrong_previous_model_and_changed_actual_parser_do_not_borrow_old_row(self):
        history=self.archive(self.prefixes[-1],self.cache);row=history.state['rows'][1];material=history.row_material(row)
        previous=deepcopy(history.row_parts(history.state['rows'][0])['model'])
        previous['sequence']=material['parts']['model']['sequence'];queries=deepcopy(self.f.calls)
        with self.assertRaises(NativeUIError):history._historical_row(row,material,previous,2)
        function=IOSAvatarPostLogoutReads.part;code=function.__code__;defaults=function.__defaults__
        def reject(self,value,previous=None):raise RuntimeError('Actual changed postlogout parser')
        try:
            function.__code__=reject.__code__
            with self.assertRaisesRegex(RuntimeError,'Actual changed postlogout parser'):history.parse(self.prefixes[-1])
        finally:
            function.__code__=code;function.__defaults__=defaults
            self.assertIs(function.__code__,code);self.assertIs(function.__defaults__,defaults)
        # A metadata/default change must take the literal decoder even when
        # this explicit call's successful result would otherwise be identical.
        monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
        monitor.use_tool_id(tool,'avatar-row-current-defaults');seen=[];observed=IOSAvatarPostLogoutReads._record_fields.__code__
        def call(actual,_offset):seen.append(actual)
        monitor.register_callback(tool,monitor.events.PY_START,call);monitor.set_local_events(tool,observed,monitor.events.PY_START)
        try:
            function.__defaults__=([],)
            history.parse(self.prefixes[-1]);self.assertEqual([observed,observed],seen);seen.clear()
            hooks=[]
            class ForeignMeta(type):
                def __eq__(cls,other):hooks.append('metaclass-equality');raise AssertionError('Metadata may not dispatch a foreign equality hook')
            class OpaqueDefault(metaclass=ForeignMeta):
                def __iter__(self):hooks.append('opaque-iteration');raise AssertionError('Metadata may not iterate an opaque default')
            function.__defaults__=(OpaqueDefault(),)
            history.parse(self.prefixes[-1]);self.assertEqual([observed,observed],seen);seen.clear();self.assertEqual([],hooks)
            function.__defaults__=defaults
            history.parse(self.prefixes[-1]);self.assertEqual([],seen)
            reads=state_source.READS
            try:
                state_source.READS=(1,2)
                with self.assertRaises(NativeUIError):history.parse(self.prefixes[-1])
            finally:state_source.READS=reads
            steps=feature_contract.SCENARIOS['authentication']['steps'];saved=list(steps)
            try:
                # Actual mutable input inventory, not a changed decoder hook.
                steps[:]=[step for step in steps if step['verb']!='logout']
                with self.assertRaisesRegex(ValueError,'Unsupported ordinary feature action'):history.parse(self.prefixes[-1])
            finally:steps[:]=saved
            scenarios=feature_contract.SCENARIOS;items=list(scenarios.items());armed=[False];origins=[]
            class ForeignKey:
                def __hash__(self):return hash('authentication')
                def __eq__(self,other):
                    if not armed[0]:return False
                    caller=sys._getframe(1).f_code;origins.append(caller)
                    if caller is not feature_contract.operation_parts.__code__:raise AssertionError('Policy metadata dispatched a foreign key hook')
                    raise RuntimeError('Literal original contract encountered the foreign key')
            try:
                area=scenarios.pop('authentication');scenarios[ForeignKey()]=area;scenarios['authentication']=area;armed[0]=True
                with self.assertRaisesRegex(RuntimeError,'Literal original contract encountered the foreign key'):history.parse(self.prefixes[-1])
                self.assertEqual([feature_contract.operation_parts.__code__],origins)
            finally:
                armed[0]=False;scenarios.clear();scenarios.update(items)
        finally:
            function.__defaults__=defaults
            monitor.set_local_events(tool,observed,0);monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)
        self.assertEqual(queries,self.f.calls)


class AvatarFinalHistoricalRowWiringTests(unittest.TestCase):
    def test_existing_Final2_archive_borrows_original_API_cache_and_still_computes_quiet_from_three_actual_groups(self):
        f=final_fixture.AvatarHeldFinalTests();self.addCleanup(f.doCleanups);f.setUp()
        with api_scope(lambda:f.f.clock[0]):
            owner=f.owner();references=[]
            for sequence in (1,2,3):
                if references:f.f.clock[0]+=1.7
                references.append(f.f.capture(owner,sequence))
            expected=owner.quiet(references,sequence=4);queries={subject:list(boundary.commands) for subject,boundary in f.web.items()}
            monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
            monitor.use_tool_id(tool,'avatar-final-real-row-wiring');seen=[];code=IOSAvatarPostLogoutReads._record_fields.__code__
            def call(actual,_offset):seen.append(actual)
            monitor.register_callback(tool,monitor.events.PY_START,call);monitor.set_local_events(tool,code,monitor.events.PY_START)
            try:
                archive=f.archive(owner)
                # Six actual archived subject/groups retain both selected-row
                # reads (proof + record); old-prefix parse interpretations hit.
                self.assertEqual(12,len(seen));self.assertEqual(expected,archive.quiet(references,sequence=4))
                self.assertEqual(queries,{subject:list(boundary.commands) for subject,boundary in f.web.items()})
            finally:
                monitor.set_local_events(tool,code,0);monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)
