"""Join absent-cache and active originals without resetting source ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.chat_journey.samples import SOURCES


def initial(frame):
    for key in ('primary','peer'):
        packet=frame[key];source=packet['source']
        need(packet['chatVersion']==3 and not source['scopePresent'] and not source['retired']
            and not source['openedCommandId'] and not source['retiredCommandId'])


def opened(before,current):
    """Original native instances/PID/domain/view/keyboard survive first Open.

    The one allowed cache birth starts from actual absence. The v3 native first
    mutation fence is immutable for that same run/source instance, even after
    retirement; neither another observer nor an input ACK can replace it.
    QML page/generation is intentionally measured independently at each Open.
    """
    initial(before)
    need(current['primaryEpochMs']>=before['primaryEpochMs'] and current['peerEpochMs']>=before['peerEpochMs'])
    for key in SOURCES:
        old,new=before[key],current[key]
        need(new['instance']==old['instance'] and new['processId']==old['processId']
            and new['sequence']>old['sequence'] and new['capturedEpochMs']>=old['capturedEpochMs'])
        nonce='requestId' if key=='lifecycle' else 'commandId';need(new[nonce]!=old[nonce])
        if key in ('primary','peer'):
            source,previous=new['source'],old['source']
            need(new['chatVersion']==3 and source['scopePresent'] and not source['retired']
                and source['selfSha256']==previous['selfSha256'] and source['openedCommandId'] and not source['retiredCommandId']
                and source['openedEpochMs']>=old['capturedEpochMs']
                and source['openedCommandId'] not in (before['primary']['commandId'],before['peer']['commandId'])
                and source['mixerPresent']==previous['mixerPresent'] and source['mixerSha256']==previous['mixerSha256']
                and all(source['session'][field]==previous['session'][field] for field in
                    ('instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs')))
        elif key=='view':
            source,previous=new['source'],old['source']
            need(new['chatViewVersion']>=old['chatViewVersion'] and source['storage']['configSha256']==previous['storage']['configSha256']
                and source['storage']['events'][:len(previous['storage']['events'])]==previous['storage']['events']
                and source['keyboard']['instance']==previous['keyboard']['instance'] and source['keyboard']['sequence']>previous['keyboard']['sequence'])
        else:need(all(new['lifecycle'][field]>=old['lifecycle'][field] for field in old['lifecycle']))
    need(current['primary']['source']['openedCommandId']!=current['peer']['source']['openedCommandId'])
