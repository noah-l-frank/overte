"""Immutable original ScriptCache callback history; never an execution verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, integer, need

VERSION = 1
STATUSES = {'Success', 'Cached', 'Inline', 'Error', 'Timeout', 'ServerUnavailable',
            'AccessDenied', 'InvalidByteRange', 'InvalidURL', 'NotFound', 'RedirectFail', 'Cancelled'}


def identifier(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{32}', value) is not None


def private_url(value):
    if type(value) is not str or not 0 < len(value) <= 4096 or any(ord(c) < 32 for c in value): return False
    try:
        parts = urlsplit(value)
        return (parts.scheme in {'file', 'http', 'https', 'atp'} and parts.username is None
                and parts.password is None and not parts.query and not parts.fragment
                and '?' not in value and '#' not in value)
    except ValueError: return False


def validate(value, captured):
    exact(value, {'complete', 'instance', 'sequence', 'events'})
    need(value['complete'] is True and identifier(value['instance'])
         and integer(value['sequence'], 0, 256) and type(value['events']) is list
         and len(value['events']) == value['sequence'] and integer(captured, 1))
    seen, generations, previous = set(), {}, 0
    for index, event in enumerate(value['events'], 1):
        exact(event, {'sequence', 'eventId', 'managerInstance', 'url', 'loadGeneration',
                      'isURL', 'success', 'status', 'callbackEpochMs'})
        need(integer(event['sequence'], 1, 256) and event['sequence'] == index
             and identifier(event['eventId']) and event['eventId'] not in seen
             and identifier(event['managerInstance'])
             and integer(event['loadGeneration'], 1)
             and event['loadGeneration'] > generations.get(event['managerInstance'], 0)
             and type(event['isURL']) is bool and type(event['success']) is bool
             and type(event['status']) is str and event['status'] in STATUSES
             and event['success'] == (event['status'] in {'Success', 'Cached', 'Inline'})
             and event['isURL'] == (event['status'] != 'Inline')
             and (private_url(event['url']) if event['isURL'] else event['url'] == '')
             and integer(event['callbackEpochMs'], 1)
             and previous <= event['callbackEpochMs'] <= captured)
        seen.add(event['eventId']); generations[event['managerInstance']] = event['loadGeneration']
        previous = event['callbackEpochMs']
    return value


def result(packet, source_url, *, after_sequence, after_epoch, manager_instance=None):
    """Return one actual full-URL callback after an independently frozen barrier.

    All statuses are preserved, including failures. The caller must separately
    evaluate the returned status and original running-engine/effect/peer data.
    """
    source = packet['source']
    need(type(source.get('loadSourceVersion')) is int and source['loadSourceVersion'] == VERSION
         and private_url(source_url)
         and integer(after_sequence, 0, 256) and integer(after_epoch, 1)
         and (manager_instance is None or identifier(manager_instance)))
    loads = validate(source['loads'], packet['capturedEpochMs'])
    need(loads['sequence'] >= after_sequence)
    rows = [event for event in loads['events'] if event['url'] == source_url
            and event['sequence'] > after_sequence and event['callbackEpochMs'] >= after_epoch
            and (manager_instance is None or event['managerInstance'] == manager_instance)]
    need(len(rows) == 1)
    return deepcopy(rows[0])
