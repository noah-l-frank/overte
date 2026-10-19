"""Reproducible adapter handoff inventory; assertions remain in scenarios.py."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from .scenarios import SCENARIOS, FOUNDATIONS, VERSION, actions
from .witness import WITNESS_KEYS


def inventory():
    return dict(schemaVersion=1, contractVersion=VERSION,
        operationPattern='feature.<area>.act|observe|cleanup',
        qualification='Shared test logic only. Product adapters and independent target observers are not implemented by this inventory.',
        areas={area:dict(inputVerbs=actions(area),
                        observationFields={key:type(value).__name__ for key,value in scenario['baseline'].items()},
                        measuredBaselineFields=scenario.get('measuredBaselineFields', []),
                        independentFields=WITNESS_KEYS[area], existingModules=FOUNDATIONS[area])
               for area,scenario in sorted(SCENARIOS.items())})


if __name__ == '__main__':
    print(json.dumps(inventory(),indent=2,ensure_ascii=False))
