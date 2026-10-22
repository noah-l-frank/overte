"""Closed Phone tablet-source additions: original held callbacks and leases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need
from feature_journeys.contract import identifier
from overte_phone_world_web_source import PhoneWorldWebIO,identity

HELD={'handle','creation','grant','page','url','token','revision','bodySha256','sourceSha256','payloadSha256','capturedEpochMs','origin','mainFrame','payloadBytes'}


def held(value,epoch):
    exact(value,HELD);identity(value);identifier(value['token'])
    origin=urlsplit(value['origin']);origin.port
    need(value['mainFrame'] is True and integer(value['payloadBytes'],1,65536) and origin.scheme=='http'
        and origin.hostname==value['token']+'.overte-inline.invalid' and origin.path in ('','/')
        and origin.username is None and origin.password is None and not origin.query and not origin.fragment)
    need(integer(value['revision'],1) and integer(value['capturedEpochMs'],1,epoch)
        and value['url']=='http://'+value['token']+'.overte-inline.invalid/index.html'
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]) for key in ('bodySha256','sourceSha256','payloadSha256')))


def deferred(value,epoch):
    exact(value,{'armed','pending','held','deliveries'})
    need(type(value['armed']) is bool and type(value['pending']) is bool and type(value['deliveries']) is list and len(value['deliveries'])<=16
        and not (value['armed'] and value['pending']))
    if value['held'] is not None:held(value['held'],epoch)
    need(not value['pending'] or value['held'] is not None)
    for row in value['deliveries']:
        exact(row,HELD|{'deliveredEpochMs','leaseCurrent','ownerAlive','accepted'})
        held({key:row[key] for key in HELD},epoch)
        need(integer(row['deliveredEpochMs'],row['capturedEpochMs'],epoch)
            and all(type(row[key]) is bool for key in ('leaseCurrent','ownerAlive','accepted')))


class PhoneTabletWebIO(PhoneWorldWebIO):
    action='phone-tablet-web'
