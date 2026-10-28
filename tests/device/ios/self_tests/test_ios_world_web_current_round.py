"""Real current acquisition/Node originals; native/SDK remain host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile
import os
import pstats
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from adapters.script_feature.history import unpack
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebCurrentRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=FeatureWorldWeb();self.addCleanup(self.f.close)
        self.f.primary.observe(dict(contractVersion=16,runId=self.f.network.run,afterSequence=0))
        self.assertEqual(dict(performed=True),self.f.primary.act(self.f.sdk.activate('open',{})))
    @staticmethod
    def wal(owner):
        path=owner.store.path
        return None if not path.exists() else (path.stat().st_ino,path.read_bytes())
    def posts(self):return [row for row in self.f.requests if row[1]=='POST' and row[2].endswith('/actions')]
    def carrier(self,source):
        value=unpack(source.record_store(1).read()['payload'])[0]
        paths=source.parts.paths(value['originals']['keys']);self.assertTrue(paths)
        return paths[0]
    def test_current_retains_fresh_frame_once_and_independent_copy_without_input_or_action_wal(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();actions=parts['actions'];source=parts['source']
            before=[self.wal(owner) for owner in (actions,actions.inputs)]
            posts=self.posts();count=len(source.state['records']);profile=cProfile.Profile()
            profile.enable()
            try:first=actions.current('actual-passive-current')
            finally:profile.disable()
            code=WorldWebSources.validate_frame.__code__;stats=pstats.Stats(profile).stats
            key=(code.co_filename,code.co_firstlineno,code.co_name)
            # Existing warm historical frames still receive full byte reads;
            # only the freshly validated frame must avoid a second validation.
            self.assertEqual(1,stats[key][1]);self.assertEqual(count+1,first['index'])
            reference=deepcopy(source.state['records'][-1]);first['originals']['keys']['source']['complete']=False
            fresh=source.frame(reference);self.assertTrue(fresh['originals']['keys']['source']['complete'])
            second=actions.current('second-actual-passive-current')
            self.assertEqual(first['index']+1,second['index'])
            self.assertGreater(second['clockJoin']['nativeBefore']['sequence'],fresh['clockJoin']['nativeAfter']['sequence'])
            self.assertEqual(posts,self.posts());self.assertEqual(before,[self.wal(owner) for owner in (actions,actions.inputs)])
            self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_current_fresh_census_rejects_new_unknown_member_during_native_acquisition(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];posts=self.posts();before=len(source.state['records'])
            original=source.native.send;seen=[]
            def send(query):
                seen.append(deepcopy(query));value=original(query)
                if len(seen)==1:
                    foreign=source.store.path.parent/'world-current-unowned-original.bin';foreign.write_bytes(b'unknown');foreign.chmod(0o600)
                return value
            source.native.send=send
            with self.assertRaises(NativeUIError):parts['actions'].current('must-refuse-new-member')
            self.assertEqual(1,len(seen));self.assertEqual(before,len(source.state['records']));self.assertEqual(posts,self.posts())
            self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_current_same_bytes_new_original_inode_is_rejected_without_input(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];path=self.carrier(source);raw=path.read_bytes();old=path.stat().st_ino;posts=self.posts()
            replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
            self.assertNotEqual(old,path.stat().st_ino);self.assertEqual(raw,path.read_bytes())
            with self.assertRaises(NativeUIError):parts['actions'].current('changed-original-inode')
            self.assertEqual(posts,self.posts());self.assertIsNone(source._round)
    def test_current_actual_byte_mutation_after_capture_refuses_without_input(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];posts=self.posts();actual=source.frame
            def frame(reference):
                path=self.carrier(source);path.write_bytes(path.read_bytes()+b' ')
                return actual(reference)
            source.frame=frame
            with self.assertRaises(NativeUIError):parts['actions'].current('reject-changed-bytes')
            self.assertEqual(posts,self.posts());self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_current_header_drift_after_capture_refuses_without_input(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];posts=self.posts();actual=source.frame
            def frame(reference):source.pid+=1;return actual(reference)
            source.frame=frame
            with self.assertRaises(NativeUIError):parts['actions'].current('reject-current-header')
            self.assertEqual(posts,self.posts());self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_actual_normal_navigate_foreign_reads_focused_url_and_only_ordinary_declared_input(self):
        call=self.f.sdk.activate('navigate-foreign',dict(resource='reference.html'))
        self.assertEqual(dict(performed=True),self.f.primary.act(call))
        with self.f.primary.held():
            parts=self.f.primary.parts();actions=parts['actions'];rows=actions.state['calls']
            self.assertEqual('returned',rows[-1]['phase']);self.assertEqual(call,rows[-1]['call'])
            labels=[row['label'] for row in actions.inputs.state['records'] if row['ticket']==call['ticket']]
            self.assertEqual(['focus-foreign-url','type-foreign-url','navigate-foreign-url'],labels)
            frame=parts['source'].frame(rows[-1]['after'])
            from ios.adapters.world_web_measurements import current_document
            raw=frame['originals'];observed=current_document(raw['ledgerAfter'],raw['document'],raw['browser'],self.f.sdk.origins)
            self.assertEqual('foreign',observed['origin']);self.assertEqual('foreign',observed['page'])
            self.assertEqual(200,observed['response']['status'])
            self.assertIsNone(parts['source']._round);self.assertIsNone(parts['source']._write_round)

    def input_wal_fault(self,kind):
        if kind!='birth':
            self.assertEqual(dict(performed=True),self.f.primary.act(self.f.sdk.activate('focus-type',dict(text=context(self.f.sdk.run)['unicode']))))
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];inputs=parts['actions'].inputs;path=inputs.store.path
            if kind=='birth':self.assertFalse(path.exists())
            else:self.assertTrue(path.exists())
            posts=self.posts();actual=source.native.send;seen=[]
            def send(query):
                value=actual(query);seen.append(deepcopy(query))
                if len(seen)==1:
                    if kind=='birth':inputs.store.write(inputs.envelope(inputs.state),None)
                    elif kind=='bytes':path.write_bytes(path.read_bytes()+b' ')
                    else:
                        # No extra entry survives this atomic replacement;
                        # old mutable-WAL exclusion would conceal its inode.
                        replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
                return value
            source.native.send=send
            with self.assertRaises(NativeUIError):parts['actions'].current('reject-input-wal-'+kind)
            self.assertEqual(1,len(seen));self.assertEqual(posts,self.posts())
            self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_passive_current_refuses_actual_input_wal_byte_mutation_in_native_callback(self):self.input_wal_fault('bytes')
    def test_passive_current_refuses_same_bytes_input_wal_inode_replacement_in_native_callback(self):self.input_wal_fault('inode')
    def test_passive_current_refuses_birth_of_previously_absent_input_wal_in_native_callback(self):self.input_wal_fault('birth')


    def test_round_preserves_original_body_error_when_original_inventory_exit_also_fails(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];first=OSError('Declared original read failure');posts=self.posts()
            with self.assertRaises(OSError) as caught:
                with source.input_round(parts['actions'].inputs.store,passive=True):
                    path=source.store.path.parent/'unowned-born-before-original-error';path.write_bytes(b'actual original inventory drift');path.chmod(0o600)
                    raise first
            self.assertIs(first,caught.exception)
            self.assertEqual(['Source append-boundary validation also failed; original error preserved.'],first.__notes__)
            self.assertEqual(posts,self.posts());self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_round_exit_inventory_failure_without_body_error_still_refuses(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];posts=self.posts()
            with self.assertRaises(NativeUIError):
                with source.input_round(parts['actions'].inputs.store,passive=True):
                    path=source.store.path.parent/'unowned-born-before-normal-exit';path.write_bytes(b'actual inventory drift');path.chmod(0o600)
            self.assertEqual(posts,self.posts());self.assertIsNone(source._round);self.assertIsNone(source._write_round)
    def test_round_preserves_original_body_error_without_inventing_secondary_failure(self):
        with self.f.primary.held():
            parts=self.f.primary.parts();source=parts['source'];first=OSError('Declared body-only read failure');posts=self.posts()
            with self.assertRaises(OSError) as caught:
                with source.input_round(parts['actions'].inputs.store,passive=True):raise first
            self.assertIs(first,caught.exception);self.assertFalse(getattr(first,'__notes__',[]))
            self.assertEqual(posts,self.posts());self.assertIsNone(source._round);self.assertIsNone(source._write_round)


if __name__=='__main__':unittest.main()
