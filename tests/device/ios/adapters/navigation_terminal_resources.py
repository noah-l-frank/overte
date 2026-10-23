"""Actual restored Qt-root groups retained until native process retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from ios.adapters.navigation_quiet_image import NavigationQuietImage
from ios.adapters.navigation_restoration import NavigationRestoration


def binding(value):
    """Privacy projection of the actual qualified SDK/process binding."""
    context(value)
    return {key:deepcopy(value[key]) for key in ('sourceRevision','artifactSha256','targetFingerprint','generation','processIdentity')}|dict(
        sessionSha256=hashlib.sha256(value['sessionId'].encode('utf-8')).hexdigest())


def held(owner):
    need(type(owner) is NavigationQuietImage)
    _rendered,proof,_raw=owner.archive();parts=owner.originals();rows=[]
    for root in proof['placesRoots']['roots']:
        need(root['status']=='retained' and root['drained'] is False)
        actual=[row for row in parts['model']['roots'] if all(row[key]==root[key] for key in ('rootId','qmlSource'))]
        need(len(actual)==1)
        alias='panel:navigation-places-'+digest({key:root[key] for key in ('rootId','qmlSource')})[:20]
        rows.append(dict(resource=alias,kind='qt-root',originalSha256=digest(dict(original=parts['model'],root=actual[0]))))
    root=proof['addressRoot']['root']
    if not root['drained']:
        actual=root['original']['navigationInventory']['roots'];need(len(actual)==1)
        need(any(row==actual[0] for row in parts['ui']['navigationInventory']['roots']))
        alias='panel:navigation-address-'+digest({key:actual[0][key] for key in ('rootId','qmlSource')})[:20]
        rows.append(dict(resource=alias,kind='qt-root',originalSha256=digest(dict(original=parts['ui'],root=actual[0]))))
    rows.sort(key=lambda row:row['resource'])
    need([row['resource'] for row in rows]==NavigationRestoration.resources(owner))
    return dict(binding=binding(owner.binding),heldResources=rows,originalSha256=digest(owner.previous))
