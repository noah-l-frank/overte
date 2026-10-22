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
from feature_journeys.scenarios import SCENARIOS,VERSION as CONTRACT_VERSION
from feature_journeys.session import prepare
from feature_journeys.audio_cleanup import identity as audio_cleanup_identity
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
    audio_cleanup_restarted=False
    used_adapter=False
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
            nonlocal identity,audio_cleanup_restarted,used_adapter
            used_adapter=True
            prefix, area, kind = operation.split('.')
            value=session.feature_operation(area, kind, fields)
            if area=='audio' and kind=='cleanup':
                # The immutable native preview history has no reset input.
                # Its documented cleanup uses one explicit normal restart;
                # independently reacquire OS identity before further reads.
                identity,audio_cleanup_restarted=audio_cleanup_identity(identity,process_identity(),audio_cleanup_restarted)
            return value

        Journey(args.area, run, url, invoke=invoke, witness=client.observe, activate=client.activate,
            read_artifact=lambda name: read_private_artifact(ARTIFACT_DIR, name), image_policy=policy,
            continuity=continuity, monotonic=time.monotonic, epoch_ms=lambda: time.time() * 1000,
            sleep=time.sleep, report=lambda value: write_json('feature-journey-observation.json', value),
            navigation_source=client.navigation_status if args.area=='world-navigation' else None).execute()
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except (ValueError, OSError, KeyError) as error:
        raise InfrastructureError('Common feature contract or fixture failed') from error
    finally:
        already_failing = sys.exc_info()[0] is not None
        try:
            client.close()
            if used_adapter:
                # The preceding common quiet checkpoint still needed the live
                # peer/provider. Now retire their original measurement journals
                # before another feature can change the world or process. This
                # uses the same idempotent v18 cleanup operation and run scope.
                session.feature_operation(args.area,'cleanup',dict(contractVersion=CONTRACT_VERSION,runId=run))
                if identity is not None:
                    assert_process(identity,'after owned feature journal retirement')
                    assert_foreground('after owned feature journal retirement')
        except Exception:
            try:
                write_json('feature-fixture-cleanup.json', {'cleanupSucceeded': False})
            except (OSError,ValueError):
                # Preserve an earlier product failure even if diagnostics fail.
                if not already_failing:
                    raise InfrastructureError('Owned feature retirement diagnostics failed') from None
            if not already_failing:
                raise InfrastructureError('Owned feature fixture or measurement retirement failed') from None
    print('Common feature journey completed; physical acceptance requires separate governed evidence.')


module_main(main)
