"""Lossless original PC query carrier; no cached process or capture verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from feature_journeys.contract import identifier
VERSION=2
COMMON={'audioPreviewSourceVersion','producerSha256','instance','provider','clientProcess','physicalAudioHardwareTested'}
ROW={'requestId','sequence','captureId','requestedEpochMs','capturedEpochMs','source'}
def packets(value):
    version=value.get('audioPreviewSourceBatchVersion') if type(value) is dict else None
    need(type(version) is int and version in (1,VERSION))
    exact(value,{'audioPreviewSourceBatchVersion','requestId','packets'}|({'authority'} if version==VERSION else set()))
    identifier(value['requestId']);need(type(value['packets']) is list and 1<=len(value['packets'])<=9)
    if version==1:return deepcopy(value['packets'])
    exact(value['authority'],COMMON);out=[]
    for row in value['packets']:
        exact(row,ROW);out.append(dict(deepcopy(value['authority']),**deepcopy(row)))
    return out
