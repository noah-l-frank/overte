"""Fixed private Graphics artifact and original-image policy admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.evidence import rectangle


def settings(value):
    exact(value,{'artifactRoot','imagePolicy'})
    need(type(value['artifactRoot']) is str)
    root=Path(value['artifactRoot'])
    need(root.is_absolute() and root.resolve()==root and root.is_dir())
    PrivateFeatureState(root/'graphics-configuration-check')._parent()
    policy=value['imagePolicy'];exact(policy,{'source','marker','subject'})
    need(policy['source']=='world-render-target')
    # Actual image extents are checked again against every original PNG. This
    # admission only bounds the external, preselected policy; it never derives
    # an ROI from a requested effect or an observed challenge.
    for key in ('marker','subject'):rectangle(policy[key],(16384,16384))
    return deepcopy(value)
