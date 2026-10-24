#!/usr/bin/env python3
"""Prove native video play, pause, seek and resume on a normal Web surface."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import json
import os
import time

from module_support import (ARTIFACT_DIR, AssertionFailure, InfrastructureError,
    assert_foreground, assert_process, contract_operation, module_main,
    operation, process_identity, write_json)
from web_video_journey import video_journey


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surface', choices=('world', 'tablet'), required=True)
    surface = parser.parse_args().surface
    script_url = os.environ.get('OVERTE_E2E_WEB_REFERENCE_SCRIPT_URL', '')
    try:
        rectangles = json.loads(os.environ.get('OVERTE_E2E_WEB_VIDEO_ROIS', '{}'))
        roi = rectangles[surface]
    except (ValueError, KeyError, TypeError):
        raise InfrastructureError('Explicit world/tablet native-video rectangles are required') from None
    identity = process_identity()

    def continuity(phase):
        assert_process(identity, phase)
        assert_foreground(phase)

    def capture():
        value = operation('artifact.screenshot', {})
        relative = value.get('artifact')
        if not isinstance(relative, str):
            raise InfrastructureError('Native screenshot artifact is missing')
        source = ARTIFACT_DIR / relative
        if (source.parent != ARTIFACT_DIR or source.is_symlink() or not source.is_file()
                or not 0 < source.stat().st_size <= 32 * 1024 * 1024):
            raise InfrastructureError('Native screenshot must be a bounded direct run artifact')
        return source.read_bytes()

    def retain(index, content):
        destination = ARTIFACT_DIR / f'{surface}-video-{index:02d}.png'
        destination.write_bytes(content)
        destination.chmod(0o600)
        return destination.name

    try:
        video_journey(surface, script_url, roi, invoke=contract_operation, capture=capture,
            retain=retain, assert_session=continuity, monotonic=time.monotonic, sleep=time.sleep,
            report=lambda value: write_json(f'{surface}-video-observation.json', value))
    except AssertionError as error:
        raise AssertionFailure(str(error)) from error
    except ValueError as error:
        raise InfrastructureError(str(error)) from error
    print(f'Native video play, pause, seek and resumed motion observed on normal {surface} Web surface.')


module_main(main)
