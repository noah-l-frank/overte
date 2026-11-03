"""The same operation CLI with the existing explicit PolyVox source actors.

No production factory is substituted and no requested state enters a reader.
The original twelve-action fixture and its retained Qt counter stay intact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
import create_operation_cli_host as host
import test_create_journey as original
import test_create_primitives_owner as primitive
import test_create_voxel_owner as voxel


class VoxelFixture(original.CreateJourneyTests):
    def _before_prepare(self):
        primitive.initialize(self.b)
        # The existing v5 producer already records real model/voxel births.
        # Preserve its complete source instead of the Model-only v4 facade.
        self.b.domain_births=self.b.creation_times
        voxel.CreateVoxelJourneyTests._before_prepare(self)
        from unittest.mock import patch
        boundary=original.NativeBoundary
        source=patch.object(original,'NativeBoundary',lambda path:boundary(path,clock_ms=self.b.epoch))
        source.start();self.addCleanup(source.stop)

    def setUp(self):primitive.CreatePrimitiveJourneyTests.setUp(self)


class VoxelAdapter(host.ModelAdapter):
    def pico_input_session(self,target):
        return self.fixture.adapter.pico_input_session(target)


class Binding:
    @staticmethod
    def create_adapter(_args,_base):return VoxelAdapter()


if __name__=='__main__':
    host.make_fixture=VoxelFixture
    host.android.cli=lambda argv=None:(host.args,Binding)
    try:raise SystemExit(host.android.main([]))
    except Exception as error:
        import traceback
        seen=set()
        while error is not None and id(error) not in seen:
            seen.add(id(error));traceback.print_exception(error,chain=False)
            error=error.__context__
        raise SystemExit(2)
