"""Explicit Worlds artifact ownership; all image qualification uses whole PNGs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState


def settings(value):
    exact(value,{'artifactRoot'});need(type(value['artifactRoot']) is str)
    root=Path(value['artifactRoot']);need(root.is_absolute() and root.resolve()==root and root.is_dir())
    PrivateFeatureState(root/'navigation-configuration-check')._parent();return deepcopy(value)
