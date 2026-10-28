"""Same-QObject observed-load cuts. No URL, code hash or end authority.

The native producer reads the existing zeroing weak object twice on its owner
thread. This codec requires the complete current root census and both reads;
it does not infer a birth from a source URL, a pointer or an input receipt.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact, integer, need
from adapters import chat_root_ownership as roots

PROFILE = 'loaded-qml-object'
FIELDS = ('observerInstance', 'loadSequence', 'loadId', 'objectId', 'processId', 'clockDomain')


def identity(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{32}', value))


def clock(value):
    exact(value, {'epochMs', 'monotonicMs'})
    need(integer(value['epochMs'], 1) and integer(value['monotonicMs'], 0))


def observed(value, pid, completed):
    exact(value, {'qmlObservedLoadObjectIdentityVersion', *FIELDS, 'readBefore', 'readAfter'})
    need(type(value['qmlObservedLoadObjectIdentityVersion']) is int
        and value['qmlObservedLoadObjectIdentityVersion'] == 1
        and integer(value['loadSequence'], 1, 64) and type(value['processId']) is int
        and value['processId'] == pid and value['clockDomain'] == 'native-main-qml-load')
    for field in ('observerInstance', 'loadId', 'objectId'): identity(value[field])
    a, b = value['readBefore'], value['readAfter']; clock(a); clock(b)
    epoch, elapsed = b['epochMs'] - a['epochMs'], b['monotonicMs'] - a['monotonicMs']
    need(0 <= epoch < 1500 and 0 <= elapsed < 1500 and abs(epoch - elapsed) <= 250
        and b['epochMs'] <= completed)
    return value


def signature(value):
    return tuple(value[field] for field in FIELDS)


def validate(cut, ownership, *, pid, captured, previous=None):
    exact(cut, {'chatViewLoadedObjectIdentityCutVersion', 'objectLinks', 'cutCompletedEpochMs'})
    need(type(cut['chatViewLoadedObjectIdentityCutVersion']) is int
        and cut['chatViewLoadedObjectIdentityCutVersion'] == 1
        and integer(cut['cutCompletedEpochMs'], captured, captured + 1499))
    roots.validate(ownership, pid=pid, epoch=captured); need(roots.complete(ownership))
    value = cut['objectLinks']
    exact(value, {'chatRootLoadedObjectLinksVersion', 'census', 'links', 'rootSourceInstance', 'rootObservationSequence'})
    need(type(value['chatRootLoadedObjectLinksVersion']) is int and value['chatRootLoadedObjectLinksVersion'] == 1
        and type(value['census']) is str and re.fullmatch('[1-9][0-9]{0,19}', value['census'])
        and int(value['census']) <= 2**64 - 1
        and value['rootSourceInstance'] == ownership['instance']
        and type(value['rootObservationSequence']) is int and value['rootObservationSequence'] == ownership['sequence']
        and type(value['links']) is list and len(value['links']) <= 64)
    expected = {page['page'] for page in ownership['pages']}; found = set(); births = set()
    for row in value['links']:
        exact(row, {'rootIdentity', 'atWalk', 'atRead'}); identity(row['rootIdentity'])
        need(row['rootIdentity'] not in found); found.add(row['rootIdentity'])
        a, b = [observed(row[key], pid, cut['cutCompletedEpochMs']) for key in ('atWalk', 'atRead')]
        need(signature(a) == signature(b)
            and a['readAfter']['epochMs'] <= b['readBefore']['epochMs']
            and a['readAfter']['monotonicMs'] <= b['readBefore']['monotonicMs'])
        # Two different actual pages cannot claim one observed QObject birth.
        need(signature(b) not in births); births.add(signature(b))
    need(found == expected)
    if previous is not None:
        need(value['rootSourceInstance'] == previous['objectLinks']['rootSourceInstance']
            and int(value['census']) > int(previous['objectLinks']['census'])
            and cut['cutCompletedEpochMs'] >= previous['cutCompletedEpochMs'])
        preserve(value['links'], previous['objectLinks']['links'])
    return cut


def preserve(current, historical):
    """A disappearing cached root cannot acquire another load on reappearance."""
    old = {row['rootIdentity']: signature(row['atRead']) for row in historical}
    for row in current:
        need(row['rootIdentity'] not in old or signature(row['atRead']) == old[row['rootIdentity']])


def match(cut, loaded):
    """Join typed loaded-source identity, never a matching URL or digest."""
    links = cut['objectLinks']['links']
    # The existing LoadedQML getter has one unambiguous completed object. This
    # bounded profile refuses a multiple-page census instead of selecting one.
    need(len(links) == 1)
    value = links[0]['atRead']; first = links[0]['atWalk']
    need(value['observerInstance'] == loaded['instance']
        and all(value[key] == loaded[key] for key in ('loadSequence', 'loadId', 'objectId', 'processId', 'clockDomain')))
    for field in ('epochMs', 'monotonicMs'):
        need(loaded['loadCompleted'][field] <= first['readBefore'][field])
    return links[0]['rootIdentity']
