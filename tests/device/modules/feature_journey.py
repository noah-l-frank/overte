#!/usr/bin/env python3
"""Execute one common feature extension through the existing OverteSession seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import json
import os
from pathlib import Path
import sys
import time
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.session import prepare
from feature_journeys.witness import Client
from module_support import (ARTIFACT_DIR, AssertionFailure, InfrastructureError,
    assert_foreground, assert_process, module_main, process_identity, write_json)
from overte_session import OverteSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--area', choices=sorted(SCENARIOS), required=True)
    args = parser.parse_args()
    client = Client(os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL', ''),
                    os.environ.get('OVERTE_E2E_FEATURE_READER_TOKEN', ''))
    run, url = client.register(args.area)
    session = OverteSession()
    identity = old_identity = None
    try:
        prepare(session, args.area)
        identity = process_identity()
        policy = json.loads(Path(os.environ['OVERTE_E2E_FEATURE_IMAGE_POLICY']).read_text())[args.area]

        def continuity(phase, verb):
            nonlocal identity, old_identity
            if phase == 'before':
                assert_process(identity, 'before normal feature input')
                old_identity = identity
            if phase == 'after' and verb == 'restart-app':
                identity = process_identity()
                if identity == old_identity:
                    raise AssertionFailure('Normal restart did not replace the application process')
            assert_process(identity, 'normal feature observation')
            assert_foreground('normal feature observation')

        def invoke(operation, fields):
            prefix, area, kind = operation.split('.')
            return session.feature_operation(area, kind, fields)

        Journey(args.area, run, url, invoke=invoke, witness=client.observe, activate=client.activate,
            read_artifact=lambda name: read_private_artifact(ARTIFACT_DIR, name), image_policy=policy,
            continuity=continuity, monotonic=time.monotonic, epoch_ms=lambda: time.time() * 1000,
            sleep=time.sleep, report=lambda value: write_json('feature-journey-observation.json', value)).execute()
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except (ValueError, OSError, KeyError) as error:
        raise InfrastructureError('Common feature contract or fixture failed') from error
    finally:
        already_failing = sys.exc_info()[0] is not None
        try:
            client.close()
        except (ValueError, OSError):
            write_json('feature-fixture-cleanup.json', {'cleanupSucceeded': False})
            if not already_failing:
                raise InfrastructureError('Owned feature fixture cleanup failed')
    print('Common feature journey completed; physical acceptance requires separate governed evidence.')


module_main(main)
