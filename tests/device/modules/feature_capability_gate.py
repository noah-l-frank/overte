#!/usr/bin/env python3
"""A missing mandatory feature seam must fail even without --require-complete."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import json
from pathlib import Path
from feature_journeys.scenarios import SCENARIOS
from module_support import InfrastructureError, advertised_capabilities, module_main


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--area', choices=sorted(SCENARIOS), required=True)
    args = parser.parse_args()
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'catalog.json').read_text())
    suite = 'feature-' + args.area
    required = set().union(*(set(module['requires']) for module in catalog['modules'] if suite in module['suites']))
    missing = sorted(required - advertised_capabilities())
    if missing:
        raise InfrastructureError('Mandatory common feature capabilities missing: ' + ', '.join(missing))


module_main(main)
