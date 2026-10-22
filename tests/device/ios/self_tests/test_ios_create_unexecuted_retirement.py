"""Lost raw native read before any Script setup, using actual durable owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.create_whole_fixture import ComposedCreate
from ios.self_tests.test_ios_create_state import RUN


class UnexecutedRetirementTests(unittest.TestCase):
    def test_lost_pre_marker_gpu_read_is_not_replayed_and_can_retire_only_wholly_unexecuted_scope(self):
        f=ComposedCreate(self,baseline_image=False);sdk=f.worlds[f.before.request];send=sdk.send
        def lost(query):
            send(query)
            if query['operation']=='read':raise OSError('Lost actual raw GPU capture before any Script input')
        sdk.send=lost
        with self.assertRaises(NativeUIError):f.before.capture('1'*32,f.domain.epoch())
        self.assertEqual('reading',f.before.state['phase']);self.assertEqual('new',f.scope.state['phase']);sdk.send=send
        f.journal.activate(RUN,'2'*32,'cleanup',{});f.retirement.admit(unexecuted=True)
        original=f.retirement.cleanup('2'*32);value=f.retirement.validate_original(original)
        self.assertEqual([],value['public']['resources']);self.assertEqual([],f.domain.io.actions)
        self.assertEqual(1,sum(query['operation']=='read' for query in sdk.commands))
        self.assertEqual('released',f.before.frame_owner.store.read()['phase']);self.assertEqual([],f.retirement.state['images'])
        self.assertEqual('reading',f.before.state['phase']);self.assertIsNone(f.before.state['clockJoin'])


if __name__=='__main__':unittest.main()
