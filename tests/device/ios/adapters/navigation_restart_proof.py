"""Original candidate restart proof bound to the actual Worlds owner files.

The existing iOS Graphics proof is pure numeric PID/birth/lifecycle/kernel and
candidate validation. It has no Graphics fixture, input or scene dependency.
This wrapper reuses it and additionally binds the independently chosen owners.
It does not transfer a scene, bookmark map or UI source across the process death.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.graphics_restart_proof import validate as candidate_restart

VERSION = 1
OWNERS = ('ios-navigation-scene-admission.json', 'ios-navigation-primary-0-samples.json',
          'ios-navigation-actor-0-samples.json')


def validate(value, owner_files):
    """owner_files must come from the actual runtime, never from the receipt."""
    need(type(owner_files) in (list, tuple) and len(owner_files) == len(OWNERS)
         and all(type(path) is str for path in owner_files))
    paths = [Path(path) for path in owner_files]
    need(tuple(path.name for path in paths) == OWNERS and len({path.parent for path in paths}) == 1
         and all(path.is_absolute() and str(path) == original and not any(part in ('.', '..') for part in path.parts)
                 for path, original in zip(paths, owner_files)))
    proof = candidate_restart(value)
    need(same(proof['input']['ownerFiles'], list(owner_files)))
    return proof
