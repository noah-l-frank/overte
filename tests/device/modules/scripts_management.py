#!/usr/bin/env python3
"""Observe normal Running Scripts URL execution, restart, stop and failure."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import sys
import time

from module_support import (AssertionFailure, InfrastructureError,
    assert_foreground, assert_process, contract_operation, module_main,
    process_identity, write_json)
from script_fixture_client import ScriptFixtureClient
from scripts_journey import scripts_journey


def main():
    try:
        fixture = ScriptFixtureClient(os.environ.get('OVERTE_E2E_SCRIPTS_FIXTURE_URL', ''),
                                     os.environ.get('OVERTE_E2E_SCRIPTS_CONTROL_TOKEN', ''))
        registration = fixture.register()
    except (ValueError, OSError) as error:
        raise InfrastructureError(str(error)) from error
    try:
        identity = process_identity()

        def continuity(phase):
            assert_process(identity, phase)
            assert_foreground(phase)

        scripts_journey(registration['scriptUrl'], registration['missingUrl'],
            invoke=contract_operation, observe=fixture.observe, assert_session=continuity,
            monotonic=time.monotonic, sleep=time.sleep,
            report=lambda value: write_json('scripts-management-observation.json', value))
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except (ValueError, OSError) as error:
        raise InfrastructureError(str(error)) from error
    finally:
        already_failing = sys.exc_info()[0] is not None
        try:
            fixture.close()
        except (ValueError, OSError) as error:
            write_json('scripts-fixture-cleanup.json', {'controlCleanupSucceeded': False})
            if not already_failing:
                raise InfrastructureError('Owned script fixture cleanup failed') from error
    print('Normal URL script execution, new restart instances, stop and failed-load cleanup observed.')


module_main(main)
