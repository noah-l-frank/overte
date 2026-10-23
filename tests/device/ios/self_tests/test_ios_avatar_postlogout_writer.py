"""Actual private writer crash boundaries, without replaying native queries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.script_feature.history import same,unpack
from ios.self_tests.test_ios_avatar_postlogout_reads import AvatarPostLogoutReadsTests


class AvatarPostLogoutWriterTests(AvatarPostLogoutReadsTests):
    def crash(self,phase,*,before=False):
        owner=self.owner();intent=owner.segments.intent;interrupted=[]
        def actual(parent):
            current=('empty' if not parent['chunks'] else 'complete' if parent['complete'] else parent['chunks'][-1]['phase'])
            if current==phase and not interrupted:
                interrupted.append(deepcopy(parent))
                if not before:intent(parent)
                raise OSError('Actual writer callback return lost')
            return intent(parent)
        owner.segments.intent=actual
        with self.assertRaises(OSError):owner.capture()
        self.assertEqual(1,len(interrupted));calls=deepcopy(self.calls)
        # Rebuild from the actual durable metadata, never the failed writer's
        # mutated in-memory parent. Recovery can only retain/abandon this query.
        retained={path:(path.stat().st_ino,path.read_bytes()) for path in self.artifacts.iterdir()}
        again=self.owner();pending=deepcopy(again.state['pending'])
        parent=pending['parts'].get('before')
        if phase=='empty' or before:
            self.assertIsNone(parent)
            self.assertEqual(1,again.state['nextSegment'])
        else:
            self.assertTrue(same(parent,interrupted[0]))
            ref=parent['chunks'][0];path=again.segments.store.path(ref)
            if phase=='planned':self.assertFalse(os.path.lexists(path))
            elif phase=='opened':self.assertEqual(b'',path.read_bytes())
            else:self.assertTrue(again.part_complete(parent))
            self.assertEqual(2,again.state['nextSegment'])
        old=again.recover();self.assertEqual('abandoned',old['status']);self.assertEqual(calls,self.calls)
        partial=again.row_partial(old)
        if parent is not None:
            self.assertTrue(same(parent,partial['parts']['before']))
            self.assertEqual(again.segments.inspect(parent),partial['files'][0])
        for path,original in retained.items():self.assertEqual(original,(path.stat().st_ino,path.read_bytes()))
        # A distinct fresh observation may follow; none of the previously
        # admitted native/nonces may be sent a second time.
        current=again.capture();again.proof(current)
        for query in calls:self.assertEqual(1,sum(same(query,row) for row in self.calls))
        for path,original in retained.items():self.assertEqual(original,(path.stat().st_ino,path.read_bytes()))

    def test_writer_lost_empty_parent_return_has_no_child_or_parent_to_adopt(self):self.crash('empty')
    def test_writer_before_planned_save_leaves_no_child_and_no_partial_parent(self):self.crash('planned',before=True)
    def test_writer_lost_planned_return_preserves_actual_absence(self):self.crash('planned')
    def test_writer_lost_opened_return_preserves_zero_bytes_and_inode(self):self.crash('opened')
    def test_writer_lost_saved_return_preserves_actual_complete_bytes(self):self.crash('saved')
    def test_writer_lost_complete_return_is_adopted_without_rewrite(self):self.crash('complete')

    def test_writer_first_child_plan_durably_contains_full_parent_before_exclusive_open(self):
        owner=self.owner();writes=[];write=self.store.write;open_=os.open;opens=[]
        def save(value,previous):
            state=unpack(value['payload'])[0];p=state['pending']
            if p is not None:
                parents=[p['parts'][key] for key in ('before','model','after') if key in p['parts']]
                parents += [row['packet'] for row in p['parts'].get('clocks',[]) if row['packet'] is not None]
                if p['partialOriginal'] is not None:parents.append(p['partialOriginal'])
                self.assertTrue(all(parent['chunks'] for parent in parents))
            write(value,previous);writes.append(deepcopy(value))
        def exclusive(path,flags,*args,**kwargs):
            if flags&os.O_EXCL and str(path).startswith(str(owner.segments.store.root/owner.segments.store.namespace)):
                state=unpack(self.store.read()['payload'])[0];p=state['pending']
                parents=owner.part_parents(p)+([p['partialOriginal']] if p['partialOriginal'] is not None else [])
                matches=[parent for parent in parents if any(owner.segments.store.path(ref)==path and ref['phase']=='planned'
                    for ref in parent['chunks'])]
                self.assertEqual(1,len(matches));parent=matches[0]
                owner.segments.parent(parent);self.assertEqual(owner.state['nextSegment']-1,parent['chunks'][-1]['index'])
                self.assertEqual(parent['label'],'partial' if parent is p['partialOriginal'] else 'parts')
                self.assertTrue(same(writes[-1],self.store.read()));opens.append(deepcopy(parent))
            return open_(path,flags,*args,**kwargs)
        with patch.object(self.store,'write',side_effect=save),patch('os.open',side_effect=exclusive):
            row=owner.capture()
        owner.proof(row);self.assertEqual(6,len(opens))


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarPostLogoutWriterTests(name) for name in loader.getTestCaseNames(AvatarPostLogoutWriterTests)
        if name.startswith('test_writer_'))


if __name__=='__main__':unittest.main()
