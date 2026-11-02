#!/usr/bin/env python3
"""Exercise normal SNAP controls and decode the actual fresh saved files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import secrets
import time

from module_support import (ARTIFACT_DIR, AssertionFailure, InfrastructureError,
    assert_foreground, assert_process, contract_operation, module_main,
    process_identity, write_json)
from overte_session import OverteSession
from snapshot_journey import snapshot_journey
from snapshot_observation import MAX_BYTES


def main():
    OverteSession().ensure_controlled_scene()
    identity = process_identity()

    def continuity(phase):
        assert_process(identity, phase)
        assert_foreground(phase)

    def read_artifact(relative):
        source = ARTIFACT_DIR / relative
        if (source.parent != ARTIFACT_DIR or source.is_symlink() or not source.is_file()
                or not 0 <= source.stat().st_size <= MAX_BYTES):
            raise InfrastructureError('Original snapshot must be a bounded direct run artifact')
        with source.open('rb') as stream:
            return stream.read(MAX_BYTES + 1)

    try:
        snapshot_journey(secrets.token_hex(8), invoke=contract_operation,
            read_artifact=read_artifact, assert_session=continuity,
            monotonic=time.monotonic, sleep=time.sleep,
            report=lambda value: write_json('snapshot-output-observation.json', value))
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except ValueError as error:
        raise InfrastructureError(str(error)) from error
    print('Fresh SNAP PNG, JPEG, GIF, panorama and cubemap output bytes decoded.')


module_main(main)
