"""Existing cleanup operation in contract v18 across active and actually retired fixture phases.

Phase metadata selects an owner entry point. Only that owner's independent
original-source checks can prove full retirement; metadata is no verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from feature_journeys.contract import arguments,operation_parts,result
from feature_journeys.phase_fixture import PhaseFixtureReader


def invoke(operation,values,factory,fixture_client):
    area,kind=operation_parts(operation);values=arguments(operation,values)
    need(callable(factory) and callable(fixture_client))
    if kind=='cleanup':
        # Never infer closure from a local cleaned flag, an input receipt, a
        # missing peer process or a missing journal. Acquire the real provider's
        # nonce-bound, fresh, versioned original phase first. The finalizer then
        # independently checks its own original provider/actor/native/files.
        status=PhaseFixtureReader(fixture_client(),values['runId'],area).status()
        if not status['active']:
            owner=factory(True)
            need(owner.finalize() is not False)
            return result(operation,{'performed':True})
    return getattr(factory(False),kind)(values)
