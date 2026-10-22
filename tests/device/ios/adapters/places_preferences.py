"""Actual loaded Places preferences, exact restoration and ordinary admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same

VERSION=1
PINNED='placesAppPinnedMetaverse'
FETCHED='placesAppMetaverseToFetch'
MATURITY='placesAppMaturityFilter'
KEYS=frozenset((PINNED,FETCHED,MATURITY))
RATINGS=frozenset(('everyone','teen','mature','adult','unrated'))


def origin(value):
    need(type(value) is str and 0<len(value)<=4096 and all(ord(c)>32 and ord(c)!=127 for c in value))
    parsed=urlsplit(value);parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is None and parsed.password is None
         and parsed.path in ('','/') and not parsed.query and not parsed.fragment)
    return value


def validate(value):
    from ios.adapters.places_http import signature
    exact(value,{'placesPreferenceVersion','values','metaverseOrigin','protocolSignature'})
    need(type(value['placesPreferenceVersion']) is int and value['placesPreferenceVersion']==VERSION)
    origin(value['metaverseOrigin']);signature(value['protocolSignature']);exact(value['values'],KEYS)
    for entry in value['values'].values():
        exact(entry,{'present','kind','value','valueSha256'})
        need(type(entry['present']) is bool and entry['kind'] in ('absent','null','unsupported','list','string-list')
             and entry['present']==(entry['kind']!='absent') and type(entry['valueSha256']) is str
             and re.fullmatch('[a-f0-9]{64}',entry['valueSha256']))
        if entry['kind'] in ('list','string-list'):
            need(type(entry['value']) is list and len(entry['value'])<=1024)
            for text in entry['value']:
                need(type(text) is str and len(text)<=4096);text.encode('utf-8')
        else:need(entry['value'] is None)
    return value


def restored(baseline,current):
    validate(baseline);validate(current)
    # Includes Qt serialized type/presence digest, list order and exact values.
    # A missing key and an empty array, or QStringList and QVariantList, differ.
    return same(baseline,current)


def ordinary_maturity_plan(value):
    """One reversible normal checkbox change, or no change at all.

    No UI control can remove an originally absent setting key or restore a
    QStringList after the script's QVariantList write. Refuse such a mutation
    before input instead of manufacturing exact restoration.
    """
    validate(value);entry=value['values'][MATURITY]
    if entry['kind']=='absent':return dict(change=False,original=None)
    need(entry['kind'] in ('list','string-list'))
    ratings=entry['value'];need(len(set(ratings))==len(ratings) and all(rating in RATINGS for rating in ratings))
    if 'everyone' in ratings:return dict(change=False,original=deepcopy(entry))
    need(entry['kind']=='list')
    return dict(change=True,original=deepcopy(entry))
