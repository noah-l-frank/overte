"""Actual historical upload original load; native/Qt/SDK remain host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.self_tests.snapshot_causal_parent_domain import CausalParentDomain
from ios.self_tests.snapshot_upload_flow_domain import SnapshotUploadFlowDomain


class FreshPhaseClock:
    """Declare a newly sampled phase clock before the first original capture."""
    def client(self):
        client=super().client();request=client.request;domain=self
        def current(*args,**kwargs):
            domain.advance()  # New request only; never edit a retained packet.
            return request(*args,**kwargs)
        client.request=current;return client


class CurrentCausalDomain(FreshPhaseClock,CausalParentDomain):pass
class CurrentLiteralDomain(FreshPhaseClock,SnapshotUploadFlowDomain):pass


@contextmanager
def tail_entries():
    # Observe actual code entries without replacing source functions/returns.
    previous=sys.getprofile();need(previous is None or callable(previous));calls=[]
    code=IOSSnapshotUploadOwner.capture_tail.__code__
    def observe(frame,event,arg):
        if previous is not None:previous(frame,event,arg)
        if frame.f_code is code and event=='call':calls.append(frame.f_locals['self'])
    sys.setprofile(observe)
    try:yield calls
    finally:sys.setprofile(previous)


class SnapshotUploadExistingTailTests(unittest.TestCase):
    def completed(self):
        d=CurrentCausalDomain(self);expected=d.prepare_native()
        with d.backend_owner() as backend:native=backend.native
        return d,native,expected

    @staticmethod
    def history(native):
        return IOSSnapshotUploadOwner.history(native.store,native.lock,native.binding,native.run,native.fixture_url,
            combined=native.combined,frontend_http=native.frontend_http,frontend_caller=native.frontend_caller)

    def test_actual_frontend4_history_loads_original_tail_once_and_keeps_result_without_SDK_or_input(self):
        d,native,expected=self.completed();commands=deepcopy(d.commands);private=deepcopy(d.private_calls);reads=deepcopy(d.ctx.files.reads)
        def forbidden(*_a,**_k):raise AssertionError('Historical replay reached SDK/native source')
        with native.lock.held(),patch.object(d.runtime,'_sources',forbidden),patch.object(d.ctx.files,'execute',forbidden),tail_entries() as entries:
            reader=self.history(native);self.assertEqual([reader],entries);self.assertEqual(expected,reader.proof())
        self.assertEqual(commands,d.commands);self.assertEqual(private,d.private_calls);self.assertEqual(reads,d.ctx.files.reads)
        self.assertEqual(1,d.upload_count)

    def test_new_literal_owner_still_acquires_real_capture_tail_and_saved_literal_history_matches(self):
        d=CurrentLiteralDomain(self);d.prepare()
        with tail_entries() as fresh:
            with d.upload_owner() as owner:
                self.assertEqual([owner],fresh);self.assertEqual(owner.capture.state['nativeTail'],owner.state['nativeTail'])
                owner.start('a'*32);expected=owner.finish()
        commands=deepcopy(d.commands)
        with owner.lock.held(),tail_entries() as loaded:
            reader=self.history(owner);self.assertEqual([reader],loaded);self.assertEqual(expected,reader.proof())
        self.assertEqual(commands,d.commands);self.assertEqual(1,d.upload_count)

    def copy_part(self,native):
        rows=[row for row in native.capture.state['slots'] if row['kind']=='filework' and row['label']=='copy-filework'];self.assertEqual(1,len(rows))
        child=native.capture.history('filework',rows[0]['index']);reference=child.state['rawParts']['chunks'][0]
        return child.parts().store.path(reference)

    def test_changed_actual_copy_original_bytes_are_refused_before_any_new_input_or_backend_query(self):
        d,native,_expected=self.completed()
        with native.lock.held():path=self.copy_part(native)
        commands=deepcopy(d.commands);private=deepcopy(d.private_calls);path.write_bytes(path.read_bytes()+b' ')
        with native.lock.held(),self.assertRaises(NativeUIError):self.history(native)
        self.assertEqual(commands,d.commands);self.assertEqual(private,d.private_calls);self.assertEqual(1,d.upload_count)

    def test_same_bytes_new_copy_original_inode_is_refused_with_old_inode_kept_outside_scope(self):
        d,native,_expected=self.completed()
        with native.lock.held():path=self.copy_part(native)
        before=path.stat();raw=path.read_bytes();commands=deepcopy(d.commands);private=deepcopy(d.private_calls)
        with tempfile.TemporaryDirectory(prefix='photo-upload-copy-old-inode-') as temporary:
            old=Path(temporary)/'original';path.rename(old);path.write_bytes(raw);path.chmod(0o600)
            self.assertEqual(before.st_ino,old.stat().st_ino);self.assertNotEqual(old.stat().st_ino,path.stat().st_ino)
            with native.lock.held(),self.assertRaises(NativeUIError):self.history(native)
            self.assertEqual(raw,old.read_bytes());self.assertEqual(raw,path.read_bytes())
        self.assertEqual(commands,d.commands);self.assertEqual(private,d.private_calls);self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
