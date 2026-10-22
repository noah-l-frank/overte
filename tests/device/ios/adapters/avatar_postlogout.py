"""Closed postlogout property join; active Avatar readers remain nonnull-only.

Ordinary logout may clear the actual session UUID. This decoder accepts that
original value only alongside independently retained native account causality.
It supplies no peer, UI, pixel, resource-retirement or whole-feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need,validate as native
from adapters.normal_feature_state import context
from adapters.native_account_observation import accept
from adapters.script_feature.history import same
from ios.adapters import avatar_state,avatar_bookmarks
from ios.adapters.authentication_causality import check as account_causality
from ios.adapters.emote_native_prefix import follow as native_prefix

VERSION=1


def restored(value,baseline,account_before,account_after,logout_before,*,binding,child_run,fixture_url,ticket):
    """Actual account-before/model/account-after originals, without retiming."""
    context(binding);pid=int(binding['processIdentity']);avatar_state.original(baseline)
    need(value.get('iosAvatarStateVersion')==3 and baseline['iosAvatarStateVersion']>=2 and baseline['processId']==pid)
    query=dict(schemaVersion=1,commandId=value.get('requestId'),action=avatar_state.ACTION,runId=value.get('runId'))
    avatar_state._validate(value,query,pid,postlogout=True)
    need(value['instance']==baseline['instance'] and value['sequence']>baseline['sequence']
        and value['requestId']!=baseline['requestId'] and value['runId']==baseline['runId'])
    for packet in (account_before,account_after,logout_before):
        native(packet,packet.get('requestId'),pid,packet.get('capturedEpochMs'),require_account=True)
    native_prefix(logout_before,account_before);native_prefix(account_before,account_after)
    call=dict(contractVersion=16,runId=child_run,fixtureUrl=fixture_url,ticket=ticket,verb='logout',inputs={})
    account_causality(call,logout_before,account_before,account_before['capturedEpochMs'])
    account_causality(call,logout_before,account_after,account_after['capturedEpochMs'])
    old,new=account_before['account'],account_after['account'];accept(accept(None,old),new)
    need(all(old['observation'][key]==new['observation'][key] for key in ('instance','credentialGeneration','endpointSha256',
        'credentialActive','loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent'))
        and old['loggedIn']==new['loggedIn'] is False and old['principalSha256']==new['principalSha256'])
    need(account_before['capturedEpochMs']<=value['clockBefore']['epochMs']<=value['clockAfter']['epochMs']<=account_after['capturedEpochMs']
        and account_after['capturedEpochMs']-account_before['capturedEpochMs']<1500)
    before,after=baseline['source'],value['source']
    need(all(same(before[key],after[key]) for key in ('requestedUrl','resourceUrl','defaultResourceUrl','geometryLoaded','rigReady',
        'shouldRender','targetScale','modelScale','jointNames')) and after['geometryLoaded'] and after['rigReady'] and after['shouldRender']
        and after['requestedUrl']==after['resourceUrl'] and abs(after['targetScale']-after['modelScale'])<.0001)
    avatar_state.history(after['modelHistory'],pid,value['clockAfter']['epochMs'],before['modelHistory']);need(after['modelHistory']['complete'])
    for source in (before,after):need(not source['bookmarks']['loadError'])
    need(same(before['bookmarks'],after['bookmarks']))
    # A previously absent empty product bookmark file may legitimately become
    # an empty persisted map through ordinary favorite save/delete. Preserve
    # all actual bytes as originals, while comparing the actual loaded maps.
    entries=[]
    for source in (before,after):
        actual=avatar_bookmarks.entries(source['bookmarkFile'])
        if actual['status']=='absent':need(not source['bookmarks']['entries']);entries.append({})
        else:entries.append(avatar_bookmarks.persisted(source['bookmarkFile'],source['bookmarks']))
    need(same(*entries))
    return dict(iosAvatarPostLogoutVersion=VERSION,modelSha256=digest(value),baselineSha256=digest(baseline),
        accountBeforeSha256=digest(account_before),accountAfterSha256=digest(account_after),logoutBeforeSha256=digest(logout_before),
        sessionPresent=after['sessionPresent'],actualSessionId=after['sessionId'],source=deepcopy(after))
