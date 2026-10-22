"""Original partial marker execution/retirement without fabricated entity birth.

An actual submitted marker Script may fail to create its Web entity or be
stopped before painting. Those failures retain exact code/worker ownership but
must never be promoted to rendered fixture or full-feature admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import need
from adapters.native_script_observation import running_owned_engine
from adapters.native_script_terminal import terminal,validate as terminal_validate,ACTION as TERMINAL_ACTION
from ios.adapters.avatar_marker_files import originals
from ios.adapters.avatar_marker_measurements import body_preserved,view_preserved
from ios.adapters.avatar_world import original,preserve_unowned,owned_marker
from ios.adapters.web_closures import continuity,VERSION as WEB_VERSION

VERSION=1


def finished(before,after,files,directory,terminal_packet,*,after_sequence,after_epoch):
    """An actually submitted setup that ended before a stop could be issued.

    Its original worker birth and both terminal receipts must follow the
    original pre-load barrier. No running-only ScriptWork query is substituted
    for a terminal result, and no new stop is sent to an already ended worker.
    """
    body_preserved(before,after);need(not before['source']['markers'] and not after['source']['markers']
        and after['source']['tree']['entities']==before['source']['tree']['entities'])
    preserve_unowned(before,after,set());url=directory+'/script-bundle/main.js'
    terminal_validate(terminal_packet,dict(schemaVersion=1,commandId=terminal_packet['commandId'],action=TERMINAL_ACTION),
        after['processId'],terminal_packet['capturedEpochMs'])
    need(integer_floor(after_sequence) and integer_floor(after_epoch,positive=True))
    rows=[row for row in terminal_packet['source']['events'] if row['manager']['url']==url]
    need(len(rows)==3 and [row['kind'] for row in rows]==['thread-bound','shutdown-drained','thread-finished']
        and rows[0]['eventSequence']>after_sequence and all(row['capturedEpochMs']>=after_epoch for row in rows))
    manager=rows[0]['manager'];code=rows[1]['code'];need(all(row['manager']==manager for row in rows)
        and rows[2]['code']==code and manager['assigned'] and manager['assignedEpochMs']>=after_epoch)
    raw=originals(before['runId'],files['fixtureUrl'],files['ticket'],files['nonce'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')
    need(code['submitted'] and code['encoding']=='utf-16le-code-units' and code['codeUnits']==len(raw)//2
        and code['sha256']==hashlib.sha256(raw).hexdigest() and code['submittedEpochMs']>=manager['assignedEpochMs'])
    source=after['source']['scriptOriginal']['source'];membership=source.get('membership')
    need(source.get('membershipSourceVersion')==1 and membership['complete']
        and not any(row['url']==url or row['instance']==manager['instance'] for row in membership['managers'])
        and not any(row['url']==url or row['required']['instance']==manager['instance'] for row in source['engines']))
    return dict(iosAvatarPartialMarkerVersion=VERSION,manager=deepcopy(manager),code=deepcopy(code),sourceUrl=url,marker=None)


def integer_floor(value,positive=False):return type(value) is int and value>=(1 if positive else 0)


def executed(before,after,files,directory,*,after_epoch):
    body_preserved(before,after);need(not before['source']['markers'])
    source_url=directory+'/script-bundle/main.js';script=after['source']['scriptOriginal'];engine=running_owned_engine(script,source_url)
    membership=script['source'].get('membership');need(script['source'].get('membershipSourceVersion')==1 and membership['complete'])
    rows=[row for row in membership['managers'] if row['instance']==engine['required']['instance']]
    need(len(rows)==1);manager=rows[0];code=engine['code']
    need(manager['assigned'] and manager['url']==source_url and after_epoch<=manager['assignedEpochMs']<=code['submittedEpochMs'])
    raw=originals(before['runId'],files['fixtureUrl'],files['ticket'],files['nonce'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')
    need(code['submitted'] and code['encoding']=='utf-16le-code-units' and code['codeUnits']==len(raw)//2
        and code['sha256']==hashlib.sha256(raw).hexdigest())
    marker=None;markers=after['source']['markers']
    if markers:marker=owned_marker(after,files['nonce'],files['fixtureUrl']+'tickets/'+files['ticket']+'/graphics-marker.v1.html')
    old={row['id'] for row in before['source']['tree']['entities']};new={row['id'] for row in after['source']['tree']['entities']}
    owned=set() if marker is None else {marker['id']}
    need(new-old==owned and not old-new);preserve_unowned(before,after,owned)
    return dict(iosAvatarPartialMarkerVersion=VERSION,manager=deepcopy(manager),code=deepcopy(code),sourceUrl=source_url,marker=marker)


def restored(before,after,owned,terminal_packet,*,after_sequence,after_epoch):
    body_preserved(before,after);view_preserved(before,after)
    need(owned.get('iosAvatarPartialMarkerVersion')==VERSION and not after['source']['markers']
        and after['source']['tree']['entities']==before['source']['tree']['entities'])
    ids=set() if owned['marker'] is None else {owned['marker']['id']};preserve_unowned(before,after,ids)
    source=after['source']['scriptOriginal']['source'];membership=source.get('membership')
    need(source.get('membershipSourceVersion')==1 and membership['complete']
        and not any(row['instance']==owned['manager']['instance'] for row in membership['managers'])
        and not any(row['url']==owned['sourceUrl'] or row['required']['instance']==owned['manager']['instance'] for row in source['engines']))
    need(terminal_packet['processId']==after['processId'])
    return terminal(terminal_packet,owned['manager'],owned['code'],after_sequence=after_sequence,after_epoch=after_epoch)


def drained_partial(value,before):
    """Aborted setup: all traced lifetimes drain, even if none were created."""
    need(value['iosWebClosureVersion']==before['iosWebClosureVersion']==WEB_VERSION
        and value['complete'] is before['complete'] is True)
    continuity(before,value,value['processId'])
    need(all(counter['pending']==0 for row in value['contexts'] for group in ('callbacks','resources') for counter in row[group].values()))
    return deepcopy(value['contexts'])
