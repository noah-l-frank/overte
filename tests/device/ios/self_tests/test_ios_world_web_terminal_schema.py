"""Actual private original carrier grammar, without native/SDK effect models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.original_frame_store import OriginalFrameStore
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_terminal import WorldWebTerminal
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebTerminalPrivateSchemaTests(unittest.TestCase):
    def owner(self,bodies):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700)
        store=OriginalFrameStore(root,BINDING,'a'*32,'primary',lambda:True,lambda *_args:None,
            namespace='ios-world-web-terminal',schema_prefix='iosWorldWebTerminal')
        owner=object.__new__(WorldWebTerminal);owner.frames=store
        owner.state=dict(records=[store.write(index,body) for index,body in enumerate(bodies,1)])
        return owner

    def bodies(self):
        # Payloads are explicit grammar-only sentinels. No roles, live window
        # or OS proof is qualified by this carrier-boundary test.
        return [dict(iosWorldWebTerminalRolesVersion=1,roles={}),
            dict(iosWorldWebTerminalSealOriginalVersion=1,samples=[],measured={},seal={}),
            dict(iosWorldWebTerminalEndOriginalVersion=1,end={})]

    def test_actual_original_carriers_preserve_the_exact_three_closed_bodies(self):
        bodies=self.bodies();owner=self.owner(bodies)
        for index,body in enumerate(bodies,1):self.assertEqual(body,owner.private(index))
        returned=owner.private(1);returned['roles']['foreign']='mutated caller'
        self.assertEqual(bodies[0],owner.private(1))
        for index in (True,False,0,4):
            with self.subTest(index=index),self.assertRaises(NativeUIError):owner.private(index)

    def test_actual_hashed_carrier_cannot_supply_boolean_or_unknown_inner_schema(self):
        bodies=self.bodies()
        for index,body in enumerate(bodies):
            version=next(key for key in body if key.endswith('Version'))
            for mode in ('bool','future','missing','extra'):
                rows=deepcopy(bodies);changed=rows[index]
                if mode=='bool':changed[version]=True
                elif mode=='future':changed[version]=2
                elif mode=='missing':changed.pop(version)
                else:changed['requestedEffect']='ack'
                owner=self.owner(rows)
                with self.subTest(index=index,mode=mode),self.assertRaises(NativeUIError):owner.private(index+1)


if __name__=='__main__':unittest.main()
