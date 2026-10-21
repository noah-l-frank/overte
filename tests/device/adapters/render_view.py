"""Original numeric recorded camera geometry; no guessed projection or pose."""
# Pure validator derived from frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need,number

VERSION=1


def recorded_view(value):
    exact(value,{'position','rotation','projection','fieldOfViewDegrees','aspectRatio','nearClip','farClip','perspective'})
    need(type(value['position']) is list and len(value['position'])==3 and all(number(v,-1e6,1e6) for v in value['position'])
         and type(value['rotation']) is list and len(value['rotation'])==4
         and all(number(v,-1.01,1.01) for v in value['rotation']) and abs(sum(v*v for v in value['rotation'])-1)<.02
         and number(value['fieldOfViewDegrees'],1,179) and number(value['aspectRatio'],.1,10)
         and number(value['nearClip'],1e-6,1e6) and number(value['farClip'],1e-6,1e9)
         and value['farClip']>value['nearClip'] and value['perspective'] is True
         and type(value['projection']) is list and len(value['projection'])==16
         and all(number(v,-1e12,1e12) for v in value['projection'])
         and sum(abs(v) for v in value['projection'][12:15])>1e-12 and abs(value['projection'][15])<1e-6)
    # Validate actual nonsingular numeric geometry, without replacing it with a
    # guessed FOV-derived matrix or requiring a centered/off-axis projection.
    matrix=[list(value['projection'][row*4:row*4+4]) for row in range(4)]
    for column in range(4):
        pivot=max(range(column,4),key=lambda row:abs(matrix[row][column]))
        need(abs(matrix[pivot][column])>1e-12)
        matrix[column],matrix[pivot]=matrix[pivot],matrix[column]
        for row in range(column+1,4):
            factor=matrix[row][column]/matrix[column][column]
            for index in range(column+1,4):matrix[row][index]-=factor*matrix[column][index]
    return value

