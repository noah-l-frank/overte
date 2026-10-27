"""Real factory/Scope reads; model clocks supply no CPU/native qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import cProfile
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import pstats
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.original_marker_scope import OriginalMarkerScope
from ios.adapters import world_web_factories as factories
from ios.adapters import world_web_scope_archive as scope_archive
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


def reject_archive(cls,value,*,require_ready=False,**kwargs):
    raise NativeUIError('Changed Scope archive reached')


def reject_frame(self,frame,previous=None):
    raise NativeUIError('Changed Scope frame validator reached')


class ScopeArchiveCounts:
    def count_archives(self,action):
        code=IOSWorldWebScope.archive.__func__.__code__;profile=cProfile.Profile()
        value=profile.runcall(action)
        row=pstats.Stats(profile).stats.get((code.co_filename,code.co_firstlineno,code.co_name))
        return value,0 if row is None else row[1]

    def originals(self,*roots):
        rows={}
        for root in roots:
            for path in root.rglob('*'):
                info=path.lstat()
                if path.is_file():
                    rows[str(path)]=(info.st_dev,info.st_ino,info.st_mode,info.st_nlink,
                        info.st_size,info.st_mtime_ns,info.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return rows


class WorldWebScopeConstructionRoundTests(ScopeArchiveCounts,unittest.TestCase):
    def prepared(self):
        fixture=FeatureWorldWeb();self.addCleanup(fixture.close)
        fixture.primary.observe(dict(contractVersion=16,runId=fixture.network.run,afterSequence=0))
        self.assertEqual(dict(performed=True),fixture.primary.act(fixture.sdk.activate('open',{})))
        return fixture

    def test_actual_factory_uses_one_archive_vs_literal_and_returns_independent_values(self):
        fixture=self.prepared();flow=fixture.primary
        with flow.held():
            before=self.originals(fixture.whole.scope.root,fixture.actor.root)
            with patch.object(scope_archive,'original_round',nullcontext):
                literal,literal_count=self.count_archives(flow.parts)
            own,count=self.count_archives(flow.parts)
            self.assertEqual(2,literal_count);self.assertEqual(1,count)
            expected=literal['lease'].packet()
            self.assertEqual(expected,own['lease'].packet())
            reference=own['source'].state['records'][0]
            expected_frame=deepcopy(own['source'].frame(reference))
            own['source'].frame(reference)['label']='returned-frame-only'
            own['source'].frames[0]['label']='public-history-only'
            state=own['lease'].scope_state();state['phase']='new';state['manifests'].clear()
            again,count=self.count_archives(flow.parts)
            self.assertEqual(1,count)
            self.assertEqual(expected,again['lease'].packet())
            self.assertEqual(expected_frame,again['source'].frame(reference))
            self.assertNotEqual('new',again['lease'].scope_state()['phase'])
            self.assertEqual(before,self.originals(fixture.whole.scope.root,fixture.actor.root))

    def test_same_bytes_new_scope_inode_during_real_factory_callback_is_refused(self):
        for fresh in (False,True):
            with self.subTest(fresh_read_census=fresh):
                fixture=self.prepared();literal=factories.actions;callbacks=[]
                retention=tempfile.TemporaryDirectory(prefix='world-web-scope-retained-inode-')
                self.addCleanup(retention.cleanup);retained_root=Path(retention.name)
                self.assertFalse(retained_root.is_relative_to(fixture.whole.scope.root))
                def changing(runtime,selector,source,scope,origins,entity):
                    callbacks.append(scope)
                    path=scope.store.path;retained=retained_root/path.name
                    self.assertFalse(retained.is_relative_to(scope.root))
                    members={member.relative_to(scope.root) for member in scope.root.rglob('*')}
                    body=path.read_bytes();original=path.stat().st_ino
                    self.assertEqual(path.stat().st_dev,retained_root.stat().st_dev)
                    path.rename(retained);path.write_bytes(body);path.chmod(0o600)
                    self.assertNotEqual(original,path.stat().st_ino)
                    self.assertEqual(original,retained.stat().st_ino)
                    self.assertEqual(retained.read_bytes(),path.read_bytes())
                    self.assertEqual(members,{member.relative_to(scope.root) for member in scope.root.rglob('*')})
                    with read_scope(fresh=True) if fresh else nullcontext():
                        # A new real census must neither overwrite old pins
                        # nor erase their immutable-original responsibility.
                        scope_archive.archived(scope,source)
                    return literal(runtime,selector,source,scope,origins,entity)
                with fixture.primary.held(),patch.object(factories,'actions',changing):
                    with self.assertRaises(NativeUIError):fixture.primary.parts()
                self.assertEqual(1,len(callbacks))

    def test_unknown_scope_member_during_real_factory_callback_is_refused(self):
        fixture=self.prepared();literal=factories.actions;callbacks=[]
        def changing(runtime,selector,source,scope,origins,entity):
            callbacks.append(scope)
            path=scope.root/'unexpected-construction-member';path.write_bytes(b'new-member');path.chmod(0o600)
            return literal(runtime,selector,source,scope,origins,entity)
        with fixture.primary.held(),patch.object(factories,'actions',changing):
            with self.assertRaises(NativeUIError):fixture.primary.parts()
        self.assertEqual(1,len(callbacks))

    def test_fresh_and_cleared_memberships_in_real_callback_execute_original_scope_reads(self):
        fixture=self.prepared();literal=factories.actions;observed=[]
        def checking(runtime,selector,source,scope,origins,entity):
            with read_scope(fresh=True) as reads:
                first,count=self.count_archives(lambda:scope_archive.archived(scope,source))
                self.assertEqual(1,count);self.assertTrue(reads);paths=set(reads)
                returned,count=self.count_archives(lambda:scope_archive.archived(scope,source))
                self.assertEqual(0,count);self.assertEqual(paths,reads);self.assertEqual(first.state,returned.state)
                reads.clear()
                returned,count=self.count_archives(lambda:scope_archive.archived(scope,source))
                self.assertEqual(1,count);self.assertEqual(paths,reads);self.assertEqual(first.state,returned.state)
                observed.append(paths)
            return literal(runtime,selector,source,scope,origins,entity)
        with fixture.primary.held(),patch.object(factories,'actions',checking):fixture.primary.parts()
        self.assertEqual(1,len(observed));self.assertIn(fixture.whole.scope.store.path,observed[0])

    def test_changed_source_binding_in_real_callback_cannot_borrow_warm_scope(self):
        fixture=self.prepared();literal=factories.actions;callbacks=[]
        def changing(runtime,selector,source,scope,origins,entity):
            callbacks.append(scope);saved=source.binding['sessionId']
            try:
                source.binding['sessionId']='foreign-session'
                with self.assertRaises(NativeUIError):scope_archive.archived(scope,source)
            finally:source.binding['sessionId']=saved
            return literal(runtime,selector,source,scope,origins,entity)
        with fixture.primary.held(),patch.object(factories,'actions',changing):fixture.primary.parts()
        self.assertEqual(1,len(callbacks))

    def test_changed_native_clock_context_in_real_callback_reopens_scope_archive(self):
        fixture=self.prepared();literal=factories.actions;callbacks=[]
        def changing(runtime,selector,source,scope,origins,entity):
            callbacks.append(scope);saved=source.native.instance
            try:
                source.native.instance='different-native-clock-context'
                _dto,count=self.count_archives(lambda:scope_archive.archived(scope,source))
                self.assertEqual(1,count)
            finally:source.native.instance=saved
            return literal(runtime,selector,source,scope,origins,entity)
        with fixture.primary.held(),patch.object(factories,'actions',changing):fixture.primary.parts()
        self.assertEqual(1,len(callbacks))

    def test_changed_archive_callback_executes_literal_archive_instead_of_warm_dto(self):
        fixture=self.prepared();literal=factories.actions;callbacks=[]
        def changing(runtime,selector,source,scope,origins,entity):
            callbacks.append(scope)
            with patch.object(IOSWorldWebScope,'archive',classmethod(reject_archive)):
                with self.assertRaisesRegex(NativeUIError,'Changed Scope archive reached'):
                    scope_archive.archived(scope,source)
            return literal(runtime,selector,source,scope,origins,entity)
        with fixture.primary.held(),patch.object(factories,'actions',changing):fixture.primary.parts()
        self.assertEqual(1,len(callbacks))


class WorldWebScopeParserEpochTests(ScopeArchiveCounts,unittest.TestCase):
    def prepared(self):
        whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close)
        actions=whole.actions();actions.act(whole.sdk.activate('open',{}))
        entry=actions.state['calls'][-1]
        WorldWebLease(whole.scope,whole.source,entry['before'],entry['after'])
        return whole

    def test_changed_inherited_validator_dispatch_executes_current_literal_validator(self):
        whole=self.prepared()
        with scope_archive.original_round():
            scope_archive.archived(whole.scope,whole.source)
            with patch.object(OriginalMarkerScope,'validate_frame',reject_frame):
                with self.assertRaisesRegex(NativeUIError,'Changed Scope frame validator reached'):
                    scope_archive.archived(whole.scope,whole.source)

    def test_inplace_validator_code_change_executes_current_literal_validator(self):
        whole=self.prepared();function=OriginalMarkerScope.validate_frame
        with scope_archive.original_round():
            scope_archive.archived(whole.scope,whole.source)
            original_code=function.__code__
            try:
                function.__code__=reject_frame.__code__
                with self.assertRaisesRegex(NativeUIError,'Changed Scope frame validator reached'):
                    scope_archive.archived(whole.scope,whole.source)
            finally:function.__code__=original_code
            self.assertIs(original_code,function.__code__)

    def test_changed_supported_or_unknown_defaults_execute_literal_archive(self):
        whole=self.prepared();function=OriginalMarkerScope.validate_frame
        for defaults in ((True,),(object(),)):
            with self.subTest(known=type(defaults[0]) is bool),scope_archive.original_round():
                expected=scope_archive.archived(whole.scope,whole.source)
                # The literal decoder passes previous explicitly. Its value
                # semantics remain valid even with these changed defaults.
                original_defaults=function.__defaults__
                try:
                    function.__defaults__=defaults
                    current,count=self.count_archives(lambda:scope_archive.archived(whole.scope,whole.source))
                finally:function.__defaults__=original_defaults
                self.assertIs(original_defaults,function.__defaults__)
                self.assertEqual(1,count);self.assertEqual(expected.state,current.state)
                self.assertEqual(expected.frames,current.frames)


if __name__=='__main__':unittest.main()
