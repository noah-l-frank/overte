"""Pure original-pixel ROI statistics; no requested settings or feature verdict."""
# Algorithm derives from frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import math
from adapters.graphics_subject_geometry import projected_box
from adapters.native_feature_observation import need

VERSION=1


def measure_pair(raw_before,raw_after,target,marker,view,extent,offset,image_extent,policy,bound):
    from PIL import Image
    def projected(row):
        box=projected_box(row,view,extent)
        return [box[0]+offset[0],box[1]+offset[1],box[2]+offset[0],box[3]+offset[1]]
    box=projected(target);card=projected(marker)
    dx=(box[2]-box[0])*.25;dy=(box[3]-box[1])*.25
    roi=[math.ceil(box[0]+dx),math.ceil(box[1]+dy),math.floor(box[2]-dx),math.floor(box[3]-dy)]
    need(roi[2]-roi[0]>=4 and roi[3]-roi[1]>=4)
    excluded=[[math.floor(card[0])-2,math.floor(card[1])-2,math.ceil(card[2])+2,math.ceil(card[3])+2],policy['marker']]
    count=changes=0;sums=[[0,0,0],[0,0,0]];orange_count=[0,0]
    with Image.open(BytesIO(raw_before)) as left,Image.open(BytesIO(raw_after)) as right:
        left.load();right.load();need(left.size==right.size==tuple(image_extent))
        for y in range(roi[1],roi[3]):
            if (y-roi[1])%64==0:bound()
            for x in range(roi[0],roi[2]):
                if any(r[0]<=x<r[2] and r[1]<=y<r[3] for r in excluded):continue
                pair=(left.getpixel((x,y)),right.getpixel((x,y)));count+=1
                changes+=max(abs(a-b) for a,b in zip(pair[0][:3],pair[1][:3]))>25
                for index in (0,1):
                    rgb=pair[index]
                    for channel in range(3):sums[index][channel]+=rgb[channel]
                    orange_count[index]+=rgb[0]>60 and rgb[0]-rgb[1]>12 and rgb[0]-rgb[2]>12
    need(64<=count<=8388608)
    means=[[v/count for v in row] for row in sums];orange=[v/count for v in orange_count]
    blue=[rgb[2]-rgb[0] for rgb in means]
    return dict(roi=roi,excluded=excluded,pixels=count,meanRgbBefore=means[0],meanRgbAfter=means[1],
        blueDominanceBefore=blue[0],blueDominanceAfter=blue[1],orangeFractionBefore=orange[0],orangeFractionAfter=orange[1],
        changedFraction=changes/count)
