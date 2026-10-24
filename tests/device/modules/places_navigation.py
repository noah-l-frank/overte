#!/usr/bin/env python3
"""Exercise ordinary Go To and history without a navigation probe command."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import time

from module_support import (AssertionFailure, InfrastructureError,
    assert_foreground, assert_process, contract_operation, module_main,
    process_identity, write_json)
from navigation_journey import navigation_journey
from navigation_observation import project_probe, viewpoint_urls
from overte_session import OverteSession


def main():
    try:
        scene_url = os.environ.get('OVERTE_E2E_SCENE_URL', '')
        viewpoint_urls(scene_url)  # Reject unsuitable fixtures before UI work.
        session = OverteSession()
        session.ensure_controlled_scene()
        identity = process_identity()

        def continuity(phase):
            assert_process(identity, phase)
            assert_foreground(phase)

        navigation_journey(scene_url, invoke=contract_operation,
            observe=lambda: project_probe(session.snapshot()), assert_session=continuity,
            monotonic=time.monotonic, sleep=time.sleep,
            report=lambda value: write_json('places-navigation-observation.json', value))
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except (ValueError, OSError) as error:
        raise InfrastructureError(str(error)) from error
    print('Normal controlled Go To and history produced actual stable scene/viewpoint arrivals.')


module_main(main)
