#!/usr/bin/env python3
"""Independent Pico Script publisher for an owned Proxmox run.

This entrypoint never discovers targets, launches/repairs an application or
submits input. The lab owner must provision and bind the candidate beforehand.
Do not run this program against workstation devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import argparse
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests/device')]
from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.script_journey.feature import ScriptPhasePending, ScriptRunRetired
from adapters.script_journey.lock import ScriptSourceBusy
from feature_journeys.witness import Client
from adapters.owned_observer import run as publish_owned

VERSION = 1


def configuration(path):
    value = PrivateFeatureState(path).read()
    exact(value, {'picoScriptObserverVersion', 'target', 'candidateArguments', 'fixtureUrl',
                  'actorToken', 'durationSeconds'})
    need(type(value['picoScriptObserverVersion']) is int and value['picoScriptObserverVersion'] == VERSION
         and type(value['target']) is str and 1 <= len(value['target']) <= 256
         and all(33 <= ord(c) < 127 for c in value['target'])
         and type(value['candidateArguments']) is list and 1 <= len(value['candidateArguments']) <= 80
         and all(type(item) is str and bool(item) for item in value['candidateArguments'])
         and number(value['durationSeconds'], 30, 1800))
    Client(value['fixtureUrl'], value['actorToken'])  # Closed shape, no network.
    return value


def run(journey, config, *, monotonic=time.monotonic, sleep=time.sleep):
    return publish_owned(config,owner=lambda:journey.script_feature_store(config['target']).read(),
        retirement=lambda:journey.script_retirement_store(config['target']).read(),
        actor=lambda run,client:journey._script_feature(config['target'],run,role='actor',client=client),
        pending=(ScriptPhasePending,ScriptSourceBusy),retired=ScriptRunRetired,monotonic=monotonic,sleep=sleep)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        config = configuration(args.config)
        from adapters.android import adapter
        candidate, binding = adapter.cli(['--kind', 'pico', '--native-binding',
            *config['candidateArguments'], 'describe', '--target', config['target']])
        need(candidate.native_binding and candidate.kind == 'pico' and candidate.action == 'describe'
             and candidate.target == config['target'] and candidate.operation is None and candidate.arguments == '{}')
        os.environ['OVERTE_PICO_FEATURE_SCRIPTS'] = '0'
        os.environ['OVERTE_PICO_FEATURE_AUTHENTICATION'] = '0'
        original = binding.create_adapter(candidate, adapter.AndroidAdapter)
        return run(PicoScriptJourney(original), config)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, RecursionError):
        print('OVT_PICO_SCRIPT_OBSERVER_REJECTED', file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
