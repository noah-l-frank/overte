"""Original assigned World Web Script, returned Web Entity and terminal joins.

The existing EmoteWorld source observes genuine Domain/body/view/entity/Script
inventories. Reusing those inventories does not reinterpret an Emote as a Web
effect: current documents, input and echoes have their separate Web sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import integer,need
from adapters.native_script_observation import running_owned_engine,loaded_relative_modules
from adapters.native_script_terminal import terminal,validate as terminal_validate,ACTION as TERMINAL_ACTION
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.emote_marker_partial import drained_partial
from ios.adapters.emote_world import owned_marker,preserve_unowned
from ios.adapters.world_web_files import originals

VERSION=1
FULL_KEY='iosWorldWebMarkerVersion'
PARTIAL_KEY='iosWorldWebPartialMarkerVersion'


def source_bytes(files):
    return originals(files['runId'],files['fixtureUrl'],files['ticket'],files['nonce'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')


def code_owned(manager,code,files,directory,after_epoch):
    need(integer(after_epoch,1) and manager['assigned'] and manager['url']==directory+'/script-bundle/main.js'
        and after_epoch<=manager['assignedEpochMs']<=code['submittedEpochMs'])
    raw=source_bytes(files)
    need(code['submitted'] and code['encoding']=='utf-16le-code-units' and code['codeUnits']==len(raw)//2
        and code['sha256']==hashlib.sha256(raw).hexdigest())


def executed(before,after,files,directory,*,after_epoch):
    """Retain an actual running worker even when addEntity returned no Entity."""
    body_preserved(before,after);view_preserved(before,after)
    need(not before['source']['markers'] and files['runId']==before['runId'])
    script=after['source']['scriptOriginal'];engine=running_owned_engine(script,directory+'/script-bundle/main.js')
    membership=script['source'].get('membership')
    need(script['source'].get('membershipSourceVersion')==1 and membership['complete'])
    rows=[row for row in membership['managers'] if row['instance']==engine['required']['instance']];need(len(rows)==1)
    manager=rows[0];code=engine['code'];code_owned(manager,code,files,directory,after_epoch)
    marker=None
    if after['source']['markers']:
        marker=owned_marker(after,files['nonce'],files['fixtureUrl']+'tickets/'+files['ticket']+'/reference.html')
    old={row['id'] for row in before['source']['tree']['entities']};new={row['id'] for row in after['source']['tree']['entities']}
    owned=set() if marker is None else {marker['id']}
    need(new-old==owned and not old-new);preserve_unowned(before,after,owned)
    return {PARTIAL_KEY:VERSION,'marker':deepcopy(marker),'manager':deepcopy(manager),'code':deepcopy(code),'sourceUrl':directory+'/script-bundle/main.js'}


def admitted(before,after,files,directory,*,after_epoch):
    result=executed(before,after,files,directory,after_epoch=after_epoch)
    need(result['marker'] is not None)
    engine=running_owned_engine(after['source']['scriptOriginal'],result['sourceUrl'])
    need(loaded_relative_modules(engine)==['companion.js'])
    result.pop(PARTIAL_KEY);result[FULL_KEY]=VERSION;return result


def finished(before,after,files,directory,terminal_packet,*,after_sequence,after_epoch):
    """Submitted code that actually exited before ordinary Stop was possible."""
    body_preserved(before,after);view_preserved(before,after)
    need(files['runId']==before['runId'] and not before['source']['markers'] and not after['source']['markers']
        and before['source']['tree']['entities']==after['source']['tree']['entities'])
    preserve_unowned(before,after,set());need(integer(after_sequence,0) and integer(after_epoch,1))
    terminal_validate(terminal_packet,dict(schemaVersion=1,commandId=terminal_packet['commandId'],action=TERMINAL_ACTION),
        after['processId'],terminal_packet['capturedEpochMs'])
    url=directory+'/script-bundle/main.js';rows=[row for row in terminal_packet['source']['events'] if row['manager']['url']==url]
    need(len(rows)==3 and [row['kind'] for row in rows]==['thread-bound','shutdown-drained','thread-finished']
        and rows[0]['eventSequence']>after_sequence and all(row['capturedEpochMs']>=after_epoch for row in rows))
    manager=rows[0]['manager'];code=rows[1]['code']
    need(all(row['manager']==manager for row in rows) and rows[2]['code']==code)
    code_owned(manager,code,files,directory,after_epoch);absent_worker(after,manager,url)
    return {PARTIAL_KEY:VERSION,'marker':None,'manager':deepcopy(manager),'code':deepcopy(code),'sourceUrl':url}


def absent_worker(after,manager,url):
    source=after['source']['scriptOriginal']['source'];membership=source.get('membership')
    need(source.get('membershipSourceVersion')==1 and membership['complete']
        and not any(row['instance']==manager['instance'] or row['url']==url for row in membership['managers'])
        and not any(row['required']['instance']==manager['instance'] or row['url']==url for row in source['engines']))


def _restored(before,after,owned,terminal_packet,after_sequence,after_epoch,key):
    body_preserved(before,after);view_preserved(before,after)
    need(type(owned) is dict and type(owned.get(key)) is int and owned[key]==VERSION and not after['source']['markers']
        and after['source']['tree']['entities']==before['source']['tree']['entities'])
    marker=owned['marker'];preserve_unowned(before,after,set() if marker is None else {marker['id']})
    absent_worker(after,owned['manager'],owned['sourceUrl']);need(terminal_packet['processId']==after['processId'])
    return terminal(terminal_packet,owned['manager'],owned['code'],after_sequence=after_sequence,after_epoch=after_epoch)


def restored(before,after,owned,terminal_packet,*,after_sequence,after_epoch):
    need(owned.get('marker') is not None)
    return _restored(before,after,owned,terminal_packet,after_sequence,after_epoch,FULL_KEY)


def partial_restored(before,after,owned,terminal_packet,*,after_sequence,after_epoch):
    return _restored(before,after,owned,terminal_packet,after_sequence,after_epoch,PARTIAL_KEY)
