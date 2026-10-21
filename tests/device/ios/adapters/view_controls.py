"""Original generic View-menu metadata, never requested camera state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from adapters.native_feature_observation import need

VERSION=1
LABELS={'view.menu':'View','view.first-person':'First Person','view.third-person':'Third Person','view.selfie':'Selfie'}
MODES={'first person look at':'view.first-person','look at':'view.third-person','selfie':'view.selfie'}
IDS=frozenset(LABELS)
FIELDS={'viewMenuSourceVersion','sourceType','labelSha256','checked'}


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS and FIELDS<=set(row))
    menu=row['id']=='view.menu'
    need(type(row['viewMenuSourceVersion']) is int and row['viewMenuSourceVersion']==VERSION
         and type(row['sourceType']) is int and row['sourceType']==(2 if menu else 1)
         and row['labelSha256']==hashlib.sha256(LABELS[row['id']].encode()).hexdigest()
         and (row['checked'] is None if menu else type(row['checked']) is bool))
