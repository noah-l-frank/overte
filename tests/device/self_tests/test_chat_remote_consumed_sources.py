"""Historical literal grammar only; these are not native source or release facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import unittest

from adapters.chat_journey.remote_consumed_sources import literal
from adapters.normal_ui import NativeUIError


class ChatRemoteConsumedLiteralTests(unittest.TestCase):
    def packet(self,raw):
        return dict(rawBase64=base64.b64encode(raw).decode('ascii'),sha256=hashlib.sha256(raw).hexdigest(),stamp=[1]*8)

    def test_literal_requires_original_canonical_bytes_without_duplicate_or_escaped_aliases(self):
        raw=b'{"x":1}\n';self.assertEqual(({'x':1},raw),literal(self.packet(raw)))
        for changed in (b'{"x":1,"x":1}\n',b'{"\\u0078":1}\n',b'{ "x":1}\n'):
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):literal(self.packet(changed))

    def test_literal_cannot_adopt_same_json_tuple_stamp_or_changed_bytes(self):
        value=self.packet(b'{"x":1}\n')
        for changed in ({**value,'stamp':tuple(value['stamp'])},{**value,'sha256':'0'*64},
            {**value,'stamp':[True]*8},{**value,'requestedSuccess':True}):
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):literal(changed)


if __name__=='__main__':unittest.main()
