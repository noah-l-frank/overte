"""Closed scene-quiet publication; cached process resources remain unresolved."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import need
from feature_journeys.retirement_receipts import WEB_SCENE_CLASSES


def scene(public):
    # The scene contract explicitly leaves process resources unresolved.
    # Only native-holder aliases may remain; files/entities/inputs/callbacks
    # still cannot be hidden behind that terminal stage.
    need(public['artifacts']==[] and type(public['resources']) is list
        and public['resources']==sorted(set(public['resources']))
        and all(type(name) is str and re.fullmatch(r'panel:world-web-[a-z0-9-]{1,54}',name) for name in public['resources']))
    return dict(webMarkerSceneQuietVersion=1,runId=public['runId'],sequence=public['sequence'],
        capturedEpochMs=public['capturedEpochMs'],quiet=list(WEB_SCENE_CLASSES),
        remaining=['native-process-resources'],lifecycle=deepcopy(public['lifecycle']))
