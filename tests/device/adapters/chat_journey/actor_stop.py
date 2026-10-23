"""Closed original Chat Actor Stop grammar; requests are not consumed proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re

from adapters.chat_journey.source_chunks import digest
from adapters.chat_journey.observation_cursor import plain
from adapters.native_feature_observation import exact,integer,need
from adapters.script_journey.history import MAX_FRAMES,same
from feature_journeys.contract import identifier

VERSION=2
BASE={'picoChatCursorActorStopVersion','commandId','instance','runId','ticket'}


def shape(value):
    need(type(value) is dict and type(value.get('picoChatCursorActorStopVersion')) is int
        and value['picoChatCursorActorStopVersion'] in (1,VERSION))
    version=value['picoChatCursorActorStopVersion']
    exact(value,BASE|({'afterSequence'} if version==1 else
        {'consumedSequence','consumedPayloadSha256','cleanupConsumptionSha256'}))
    for key in ('commandId','instance','runId','ticket'):identifier(value[key])
    need(integer(value['afterSequence' if version==1 else 'consumedSequence'],1,MAX_FRAMES))
    if version==VERSION:
        for key in ('consumedPayloadSha256','cleanupConsumptionSha256'):
            need(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]))
    return version


def validate(value,*,instance,run,published):
    version=shape(value)
    need(type(published) is list and 1<=len(published)<=MAX_FRAMES
        and value['instance']==instance and value['runId']==run and value['ticket']==published[-1]['payload']['ticket'])
    if version==1:need(value['afterSequence']==len(published))
    else:
        index=value['consumedSequence']-1;need(index<len(published))
        need(value['consumedPayloadSha256']==digest(published[index]['payload'])
            and all(row['payload']['ticket']==value['ticket'] for row in published[index:]))
    return version


def publication_return(sequence,row,publisher,cursor,publisher_stamp,cursor_stamp):
    """Certificate emitted only after the actual core publisher returned."""
    return dict(picoChatPublicationReturnVersion=1,sequence=sequence,rowSha256=digest(row),
        publisherSha256=digest(publisher),cursorSha256=digest(cursor),publisherStamp=publisher_stamp,
        cursorStamp=cursor_stamp,ticket=row['payload']['ticket'])


def validate_publication_return(value,*,publisher,cursor,rows,publisher_stamp,cursor_stamp):
    for original in (value,publisher,cursor,rows,publisher_stamp,cursor_stamp):plain(original)
    exact(value,{'picoChatPublicationReturnVersion','sequence','rowSha256','publisherSha256','cursorSha256',
        'publisherStamp','cursorStamp','ticket'})
    need(type(value['picoChatPublicationReturnVersion']) is int and value['picoChatPublicationReturnVersion']==1
        and type(value['sequence']) is int and value['sequence']==len(rows) and rows
        and same(value,publication_return(len(rows),rows[-1],publisher,cursor,publisher_stamp,cursor_stamp)))
