#!/usr/bin/env python3
"""Normal Create Cube editing, history and JSON import with real entity reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import sys
import time

from create_fixture_client import CreateFixtureClient
from create_journey import create_journey
from module_support import (AssertionFailure, InfrastructureError,
    assert_foreground, assert_process, contract_operation, module_main,
    process_identity, write_json)
from overte_session import OverteSession


def main():
    try:
        fixture = CreateFixtureClient(os.environ.get('OVERTE_E2E_CREATE_FIXTURE_URL', ''),
                                      os.environ.get('OVERTE_E2E_CREATE_CONTROL_TOKEN', ''))
        registration = fixture.register()
    except (ValueError, OSError) as error:
        raise InfrastructureError(str(error)) from error
    try:
        # The ordinary controlled serverless scene grants avatar-entity rights
        # through the existing application path. Never override permissions in
        # the observer or classify an arbitrary public domain as a test fixture.
        OverteSession().ensure_controlled_scene()
        identity = process_identity()

        def continuity(phase):
            assert_process(identity, phase)
            assert_foreground(phase)

        create_journey(registration['observerUrl'], registration['importUrl'], registration['missingUrl'],
            invoke=contract_operation, observe=fixture.observe, assert_session=continuity,
            monotonic=time.monotonic, sleep=time.sleep,
            report=lambda value: write_json('create-management-observation.json', value))
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except (ValueError, OSError) as error:
        raise InfrastructureError(str(error)) from error
    finally:
        already_failing = sys.exc_info()[0] is not None
        try:
            fixture.close()
        except (ValueError, OSError) as error:
            write_json('create-fixture-cleanup.json', {'controlCleanupSucceeded': False})
            if not already_failing:
                raise InfrastructureError('Owned Create fixture cleanup failed') from error
    print('Normal owned Cube creation/edit/history/delete and parent-child JSON import observed.')


module_main(main)
