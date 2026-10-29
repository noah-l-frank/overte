"""Actual original private-login WAL/FD/input producer with a forward clock.

The clock is declared before constructing Native. No credentials are printed,
no existing packet is retimed and the literal status validator is unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from urllib.request import Request
from adapters.private_login_input import PrivateLoginInput
from ios.adapters import feature_observation
from ios.self_tests.authentication_native_boundary import Native


class ForwardNative(Native):
    def __init__(self,*args,**kwargs):
        self.host_ticks=1700000000000
        super().__init__(*args,**kwargs)
    def host_epoch(self):
        self.host_ticks+=2
        return self.host_ticks


class AvatarPrivateStatusCaptureOrderTests(unittest.TestCase):
    def test_actual_private_owner_delivery_and_cleanup_preserve_integer_status_before_final_packet_capture(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);root.chmod(0o700)
        native=ForwardNative(root,'https://controlled.invalid',None);self.addCleanup(native.close)
        # Declared native UI state before first credential/input acquisition.
        native.login.dialog=True;native.login.focused='login.username';native.login.server=native.origin
        observed=native.observed();row=next(row for row in observed['controls'] if row['id']=='login.username')
        def send(command):
            def post(request,timeout):return native.post(request,timeout)
            with patch.object(feature_observation,'post_request',side_effect=post):
                feature_observation.send_original_command('http://controlled.invalid:49121',command,4096)
        transport=SimpleNamespace(pid=native.pid,guard=native.private.guard,send=send,
            read=native.private.read,original=native.private.original,write=native.private.write,drain=native.private.drain)
        owner=PrivateLoginInput(transport,native.private.store,dict(native.scope(),processIdentity=str(native.pid)),
            'c'*32,component_only=False,monotonic=time.monotonic,sleep=time.sleep)
        value=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=native.instance,sequence=native.sequence+1,
            observedElapsedMs=observed['elapsedMs'],fieldToken=row['token'],operation='replace',text='declared-fixture-only')
        owner.replace(value)
        self.assertEqual(1,native.private.deliveries);self.assertIsNone(native.private.store.read())
        self.assertEqual([],list(native.private.root.glob('feature-login-input-*')))
        self.assertTrue(all(row['fd'] is None and row['retired'] for row in native.private.rows.values()))
        status=native.private.value['source']['inputStatus'];packet=native.private.value
        for field in ('schemaVersion','sequence','processId','sampleEpochMs'):self.assertIs(type(status[field]),int)
        self.assertIs(type(status['performed']),bool);self.assertTrue(status['performed'])
        self.assertLessEqual(status['sampleEpochMs'],packet['capturedEpochMs'])
        self.assertIs(type(packet['capturedEpochMs']),int)
        # Actual owner requires the earlier deliver response too: the old
        # producer stamps that packet before the later sample and fails before
        # replace() returns. Successful real cleanup here cannot mask it.
        self.assertIsNone(owner.previous)


if __name__=='__main__':unittest.main()
