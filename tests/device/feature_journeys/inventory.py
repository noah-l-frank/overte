"""Reproducible adapter handoff inventory; assertions remain in scenarios.py."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from .scenarios import SCENARIOS, FOUNDATIONS, VERSION, actions
from .witness import WITNESS_KEYS


def inventory():
    return dict(schemaVersion=1, contractVersion=VERSION,
        operationPattern='feature.<area>.act|observe|cleanup',
        cleanupLifecycle=dict(version=1,normalSuccessCleanupCalls=2,postFixtureCloseCleanupCalls=1,
            order=['restore-owned-product-resources','independent-three-second-quiet-checkpoint',
                   'close-original-fixture-run','retire-original-measurement-responsibilities'],
            retirementRequires=['original-provider-closed','original-actor-terminated','fresh-native-file-absence',
                                'owned-host-journals-retired','unchanged-application-process']),
        qualification='Shared test logic only. Product adapters and independent target observers are not implemented by this inventory.',
        areas={area:dict(inputVerbs=actions(area),
                        observationFields={key:type(value).__name__ for key,value in scenario['baseline'].items()},
                        measuredBaselineFields=scenario.get('measuredBaselineFields', []),
                        sourceProfiles=['photos-add-only','media-store','document-picker'] if area=='snapshots' else
                            ['mobile-defaults-only-v1'] if area=='scripts' else [],
                        systemUiVerbs=sorted({step['verb'] for step in scenario['steps'] if step.get('systemUi')}),
                        conditionalSteps=[dict(index=n+1,verb=step['verb'],backends=step['backends']) for n,step in enumerate(scenario['steps']) if 'backends' in step],
                        documentTransitions=[dict(index=n+1,verb=step['verb'],transition=step['documentTransition']) for n,step in enumerate(scenario['steps']) if 'documentTransition' in step],
                        independentFields=WITNESS_KEYS[area], existingModules=FOUNDATIONS[area])
               for area,scenario in sorted(SCENARIOS.items())})


if __name__ == '__main__':
    print(json.dumps(inventory(),indent=2,ensure_ascii=False))
