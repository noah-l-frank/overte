"""Atomic read ordering/guards over real bytes; no typed Inventory authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError

from ios.adapters import snapshot_photos_end_read_area as proposal

class Original:
    def __init__(self,path):
        self.path=path;self.log=[];self.reads=0;self.state={'generation':0};self.mode=True
        self.on_original=self.on_proof=self.on_bound=None;self.clock_error=None;self.bound_calls=0
    def original(self):
        self.log.append('original');self.reads+=1;raw=self.path.read_bytes()
        if self.on_original:self.on_original()
        return {'rawSha':'metadata-only'},raw
    def bound(self):
        self.log.append('bound');self.bound_calls+=1
        if self.on_bound:self.on_bound(self.bound_calls)
    def proof(self):
        value,raw=self.original();return self._proof_from_original(value,raw)
    def _proof_from_original(self,value,raw):
        self.log.extend(('source-qualified','action-qualified','frame-read','clock-check'))
        if self.clock_error:raise self.clock_error
        if self.on_proof:self.on_proof()
        return {'qualifiedBytes':len(raw),'fresh':deepcopy(value)}

class Area:
    def __init__(self,owner):
        self.owner=owner;self.counts={};self.cache={'inventory':dict(owner=owner,headers=self.inventory_headers(owner),value={'rawSha':'metadata-only'},raw=owner.path.read_bytes(),paths={owner.path})}
    inventory_current=proposal.ReadArea.inventory_current
    def check(self):self.owner.log.append('area-check')
    def reread(self,paths):
        for path in paths:path.read_bytes()
    def inventory_key(self,owner):
        if owner is not self.owner or owner.mode is not True:raise NativeUIError('Wrong metadata protocol scope')
        return 'inventory'
    @staticmethod
    def inventory_headers(owner):return deepcopy(owner.state)

class AtomicInventoryProtocolTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'metadata-only.bytes';self.path.write_bytes(b'actual private metadata bytes')
    def owner(self):return Original(self.path)
    def active(self,owner):
        token=proposal._ACTIVE.set(Area(owner));self.addCleanup(lambda:proposal._ACTIVE.reset(token))
    def test_default_retains_two_actual_reads_and_original_proof_order(self):
        owner=self.owner();value,raw,proof=proposal.inventory_original_with_fresh_proof(owner)
        self.assertEqual(2,owner.reads);self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(['original','original','source-qualified','action-qualified','frame-read','clock-check'],owner.log)
        self.assertEqual(len(raw),proof['qualifiedBytes'])
    def test_active_atomic_calls_each_read_again_and_execute_fresh_checks(self):
        owner=self.owner();self.active(owner)
        first=proposal.inventory_original_with_fresh_proof(owner);second=proposal.inventory_original_with_fresh_proof(owner)
        self.assertEqual(2,owner.reads);self.assertEqual(first,second);self.assertIsNot(first[2],second[2])
        one=['area-check','original','bound','source-qualified','action-qualified','frame-read','clock-check','bound','area-check']
        self.assertEqual(one+one,owner.log)
    def test_mode_or_memory_change_before_or_after_proof_is_rejected(self):
        for stage in ('mode-before','memory-before','memory-after','bound-first-memory','bound-second-memory','bound-first-mode','bound-second-mode'):
            with self.subTest(stage=stage):
                owner=self.owner();token=proposal._ACTIVE.set(Area(owner))
                try:
                    if stage=='mode-before':owner.on_original=lambda:setattr(owner,'mode',False)
                    elif stage=='memory-before':owner.on_original=lambda:owner.state.update(generation=1)
                    elif stage=='memory-after':owner.on_proof=lambda:owner.state.update(generation=1)
                    else:
                        at=1 if 'first' in stage else 2
                        def changed_bound(index):
                            if index==at:
                                if stage.endswith('mode'):owner.mode=False
                                else:owner.state.update(generation=1)
                        owner.on_bound=changed_bound
                    with self.assertRaises(NativeUIError):proposal.inventory_original_with_fresh_proof(owner)
                    self.assertEqual(1,owner.reads)
                finally:proposal._ACTIVE.reset(token)
        # Exercise the original() hit path itself, including its first bound
        # and each bound inside the shared post-callback header check.
        for at in (1,2,3):
            with self.subTest(original_hit_bound=at):
                owner=self.owner();area=Area(owner)
                def changed_bound(index):
                    if index==at:owner.state.update(generation=1)
                owner.on_bound=changed_bound
                with self.assertRaises(NativeUIError):
                    proposal.ReadArea.inventory_original(area,owner,lambda:self.fail('Hit decoded again'))
    def test_original_proof_error_survives_without_retry_or_result(self):
        owner=self.owner();self.active(owner);error=NativeUIError('Declared clock mismatch');owner.clock_error=error
        with self.assertRaises(NativeUIError) as caught:proposal.inventory_original_with_fresh_proof(owner)
        self.assertIs(error,caught.exception);self.assertEqual(1,owner.reads)
        self.assertEqual(['area-check','original','bound','source-qualified','action-qualified','frame-read','clock-check'],owner.log)

if __name__=='__main__':unittest.main()
