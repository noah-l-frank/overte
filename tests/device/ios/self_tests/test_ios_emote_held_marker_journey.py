"""Normal marker Script/Node setup and actual v2 originals with cached model.

Only the native holder producer differs from the legacy all-zero model. Real
normal input recipes, staged JS/companion bytes, private journals and quiet
windows remain production host code. No process end is claimed by this scope.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope
from ios.adapters.emote_marker_disposition import disposition
from ios.self_tests.test_ios_emote_held_marker_scope import EmoteHeldMarkerScopeTests
from ios.self_tests.emote_marker_domain_fixture import RunningDomain
from ios.self_tests.test_ios_emote_marker_owner import Domain


class CachedMarkerDomain(RunningDomain):
    def stop(self):
        super().stop();self.closed_epoch=self.epoch()

    def web(self,run,url):
        value=Domain.web(self,run,url)
        if self.context is not None:
            row=deepcopy(self.context)
            if not self.running:
                row['updatedEpochMs']=max(row['updatedEpochMs'],self.closed_epoch)
                for counter in row['callbacks'].values():counter.update(retired=counter['created'],pending=0)
                counter=row['resources']['policy-grant'];counter.update(retired=counter['created'],pending=0)
            value['contexts']=[row]
        self.scope.web.last=deepcopy(value);return value


class EmoteHeldMarkerJourneyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=EmoteHeldMarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.scope=self.fixture.owner();self.domain=CachedMarkerDomain(self.scope)

    def prepare(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered()

    def assert_original_held(self,scope):
        self.assertEqual('released',scope.state['phase']);self.assertFalse(self.domain.running)
        self.assertFalse(self.domain.files.root.exists());self.assertGreaterEqual(len(scope.state['quiet']),3)
        baseline=scope.frames[scope.state['webAdmission']-1]['web']
        originals=[]
        for index in scope.state['quiet']:
            value=disposition(scope.frames[index-1]['web'],baseline);self.assertEqual('held',value['mode'])
            self.assertTrue(all(row['original']['counter']['pending']>0 for row in value['holders']));originals.append(value)
        first,last=(scope.frames[index-1] for index in (scope.state['quiet'][0],scope.state['quiet'][-1]))
        self.assertTrue(scope.quiet_interval(first,last))
        self.assertEqual(originals[0]['holders'],originals[-1]['holders'])
        shifted=deepcopy(last);shifted['clockJoin']['hostBeforeEpochMs']+=10000
        self.assertFalse(scope.quiet_interval(first,shifted))
        return originals

    def test_normal_cleanup_retains_actual_cached_holders_and_replays_original_v2_without_live_queries(self):
        self.prepare();self.assertEqual({'performed':True},self.scope.cleanup());expected=self.assert_original_held(self.scope)
        files={path:(path.stat().st_ino,path.read_bytes()) for path in self.scope.root.rglob('*') if path.is_file()}
        actions=list(self.domain.io.actions);self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertEqual(actions,self.domain.io.actions)
        historical=IOSEmoteHeldMarkerScope.archive(self.scope.previous,root=self.scope.root,binding=self.scope.binding,
            run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
        self.assertEqual(expected,self.assert_original_held(historical))
        changed=deepcopy(self.scope.previous);state=unpack(changed['payload'])[0]
        state['quiet']=[state['quiet'][-1],*state['quiet'][:-1]];changed['payload']=pack([state])
        with self.assertRaises(NativeUIError):IOSEmoteHeldMarkerScope.archive(changed,root=self.scope.root,binding=self.scope.binding,
            run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
        self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in files})

    def test_unknown_normal_script_stop_uses_actual_terminal_return_without_resending(self):
        self.prepare();activate=self.domain.io.activate
        def lost(identifier,**kwargs):
            activate(identifier,**kwargs)
            if identifier=='scripts.stop.0':raise NativeUIError('Actual delivered stop return lost')
        with patch.object(self.domain.io,'activate',side_effect=lost),self.assertRaises(NativeUIError):self.scope.cleanup()
        rebuilt=self.fixture.owner();self.domain.attach(rebuilt)
        self.assertEqual({'performed':True},rebuilt.cleanup());self.assert_original_held(rebuilt)
        self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))

    def test_new_real_modeled_holder_event_resets_the_existing_quiet_candidate(self):
        domain=self.domain;original=domain.web;activity=[]
        def event(run,url):
            if self.scope.state['phase']=='quiet' and len(self.scope.state['quiet'])==1 and not activity:
                counter=domain.context['resources']['native-bitmap'];counter['created']+=1;counter['pending']+=1
                domain.context['updatedEpochMs']=domain.epoch();activity.append(len(self.scope.frames)+1)
            return original(run,url)
        self.scope.web.read=event
        self.prepare();self.assertEqual({'performed':True},self.scope.cleanup());self.assert_original_held(self.scope)
        self.assertEqual(1,len(activity));self.assertTrue(all(index>activity[0] for index in self.scope.state['quiet']))
        value=disposition(self.scope.frames[-1]['web'],self.scope.frames[self.scope.state['webAdmission']-1]['web'])
        row=next(row for row in value['holders'] if row['original']['resourceKind']=='native-bitmap')
        self.assertEqual(2,row['original']['counter']['pending'])


if __name__=='__main__':unittest.main()
