"""Closed ordinary input and pure host publication admission counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner,original


class CancelOwnerGuardTests(unittest.TestCase):
    def test_closed_qml_intents_cannot_dispatch_capture_cancel_upload_or_requested_effects(self):
        owner=object.__new__(PicoSnapshotCancelOwner);owner.binding=dict(sessionId='own-bridge');owner.prefix='parity-'+('a'*16)+'-animated'
        command=dict(schemaVersion=1,commandId='a2adeab3-1577-4180-8e5d-6db6380e9025',bridgeId='own-bridge',generation='0ea69326-d92f-4fda-9b2f-ce986e7bf804',
            sequence=1,observedElapsedMs=0,controlId='snapshot.name',controlToken='b8d16de6-3c99-48be-8d56-7111b3dd496f',action='replace',text=owner.prefix)
        owner.allowed(command,'cancel-issued')
        for field,value in (('schemaVersion',True),('text','foreign'),('bridgeId','foreign'),('sequence',True),
                ('controlId','snapshot.capture'),('controlId','snapshot.cancel'),('controlId','snapshot.upload'),('expectedCancelled',True)):
            broken=deepcopy(command);broken[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(NativeUIError):owner.allowed(broken,'cancel-issued')

    def test_saved_original_bytes_cannot_gain_new_fields_duplicate_keys_or_a_retimed_digest(self):
        raw='{"original":1}';row=dict(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest());self.assertEqual(dict(original=1),original(row,100))
        for broken in (dict(row,expectedComplete=True),dict(row,raw=raw+' '),dict(raw='{"x":1,"x":2}',sha256=hashlib.sha256(b'{"x":1,"x":2}').hexdigest())):
            with self.subTest(broken=broken),self.assertRaises((NativeUIError,ValueError)):original(broken,100)

    def test_controller_publication_uses_only_the_original_host_anchor_and_exact_envelope(self):
        owner=object.__new__(PicoSnapshotCancelOwner);clock=[1.];calls=[]
        owner.native=SimpleNamespace(monotonic=lambda:(calls.append('monotonic'),clock[0])[1]);owner.controller_anchor=(1.,0)
        owner.controller_envelope=dict(original='envelope');owner.before_publish(dict(original='envelope'))
        clock[0]=3.
        with self.assertRaises(NativeUIError):owner.before_publish(dict(original='envelope'))
        clock[0]=1.
        with self.assertRaises(NativeUIError):owner.before_publish(dict(original='foreign'))
        self.assertEqual(['monotonic','monotonic'],calls)


if __name__=='__main__':unittest.main()
