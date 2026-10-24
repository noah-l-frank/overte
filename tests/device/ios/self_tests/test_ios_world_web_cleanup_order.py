"""Real role entry refuses an early retirement publication before local quiet."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import threading
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebCleanupOrderTests(unittest.TestCase):
    def test_actual_thread_role_baseline_acquires_its_own_os_lock_after_component_setup_ends(self):
        f=FeatureWorldWeb();self.addCleanup(f.close);f.allow_role_threads();values=[];errors=[]
        def primary():
            try:values.append(f.primary.observe(dict(contractVersion=16,runId=f.network.run,afterSequence=0)))
            except BaseException as error:errors.append(error)
        worker=threading.Thread(target=primary,daemon=True);worker.start();worker.join(60)
        self.assertFalse(worker.is_alive())
        if errors:raise errors[0]
        self.assertEqual(1,len(values));self.assertFalse(values[0]['state']['open'])
        self.assertIsNone(f.primary.lock._owner)
        self.assertIsNone(f.actor.lock._owner)
        # Reacquisition by the independent role remains a normal OS-lock
        # operation. The original lock implementation is never bypassed.
        actor=f.secondary.observe(dict(contractVersion=16,runId=f.network.run,afterSequence=0))
        self.assertFalse(actor['state']['open'])
        # Finalization constructs a distinct lock instance at this exact path.
        # Its ordinary flock must succeed after both setup contexts ended.
        with ScriptSourceLock(f.actor.lock.path).held():pass

    def test_actor_entry_cannot_publish_retirement_before_original_primary_local_cleaned_journal(self):
        f=FeatureWorldWeb();self.addCleanup(f.close)
        call=dict(contractVersion=16,runId=f.network.run,afterSequence=0)
        f.primary.observe(call);f.secondary.observe(call)
        with f.secondary.held():
            f.secondary.load();parts=f.secondary.parts()
            primary_source=deepcopy(parts['source'].previous);peer_source=deepcopy(parts['peer'].previous)
        f.sdk.activate('cleanup',{})
        inputs=deepcopy(f.whole.domain.io.actions)
        self.assertEqual(dict(performed=False),f.secondary.cleanup(dict(contractVersion=16,runId=f.network.run)))
        self.assertIsNone(f.secondary.state['retirement'])
        self.assertFalse(any(f.actor.root.glob('phase-retirement-world-web-*.json')))
        self.assertEqual(inputs,f.whole.domain.io.actions)
        with f.secondary.held():
            parts=f.secondary.parts()
            self.assertEqual(primary_source,parts['source'].previous);self.assertEqual(peer_source,parts['peer'].previous)


if __name__=='__main__':unittest.main()
