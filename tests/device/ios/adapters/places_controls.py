"""Original Places QML control identities, not arrival or saved-bookmark proof.

The full area additionally needs native/disk/network/lifetime originals. This
component never derives a feature state from an input acknowledgement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import uuid
from urllib.parse import urlsplit,unquote

from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same

VERSION=1
PROFILE='qt-places-qml-v1'
STATIC=frozenset(('places.page','places.search','places.bookmark-name','places.refresh','places.back','places.forward',
    'places.home','places.tab.places','places.tab.bookmarks','places.tab.servers','places.bookmark-add',
    'places.bookmark-save','places.bookmark-cancel'))
FIELDS=frozenset(('places.search','places.bookmark-name'))
MODAL=frozenset(('places.bookmark-name','places.bookmark-save','places.bookmark-cancel'))
EXTRA=frozenset(('profile','rootId','qmlSource','rowName','rowAddress','value','modal','inputReady'))
BASE=frozenset(('id','token','enabled','focused'))
ROW=re.compile(r'places\.(visit|bookmark-visit|bookmark-rename|bookmark-delete)\.([a-f0-9]{32})\Z')


def control_id(value):return type(value) is str and (value in STATIC or ROW.fullmatch(value) is not None)


def identity(value):
    need(type(value) is str)
    try:parsed=uuid.UUID(value)
    except ValueError:need(False)
    need(str(parsed)==value and parsed.int!=0)
    return value


def text(value,maximum=4096):
    need(type(value) is str and len(value)<=maximum and all(ord(char)>=32 and ord(char)!=127 for char in value))
    try:value.encode('utf-8')
    except UnicodeError:need(False)
    return value


def qml_source(value):
    text(value);parsed=urlsplit(value)
    try:path=unquote(parsed.path,encoding='utf-8',errors='strict')
    except UnicodeError:need(False)
    text(path)
    need(parsed.scheme in ('file','qrc') and not parsed.netloc and not parsed.query and not parsed.fragment
         and path.endswith('/system/places/PicoPlaces.qml') and not any(part in ('.','..') for part in path.split('/')))
    return value


def metadata(value):
    exact(value,BASE|EXTRA);need(control_id(value['id']) and value['profile']==PROFILE)
    identity(value['rootId']);identity(value['token']);qml_source(value['qmlSource'])
    for key in ('enabled','focused','modal','inputReady'):need(type(value[key]) is bool)
    for key in ('rowName','rowAddress','value'):text(value[key])
    row=ROW.fullmatch(value['id'])
    if row:
        need(bool(value['rowName']) and bool(value['rowAddress'])
             and hashlib.sha256(value['rowName'].encode('utf-8')).hexdigest()[:32]==row[2])
    else:need(value['rowName']==value['rowAddress']=='')
    if value['id'] not in FIELDS:need(value['value']=='')
    if value['inputReady']:
        need(value['enabled'] and value['id']!='places.page' and value['modal']==(value['id'] in MODAL))
    return value


def scope(value):
    exact(value,{'instance','processId','sequence','observationSequence','elapsedMs','sampleEpochMs'})
    identity(value['instance']);need(integer(value['processId'],1) and integer(value['sequence'],0)
        and integer(value['observationSequence'],1) and integer(value['elapsedMs'],0) and number(value['sampleEpochMs'],1,1e15))
    return value


def snapshot(value):
    exact(value,{'placesControlsVersion','open','ready','scope','controls'})
    need(type(value['placesControlsVersion']) is int and value['placesControlsVersion']==VERSION
         and type(value['open']) is bool and value['ready'] is True and type(value['controls']) is list and len(value['controls'])<=256)
    scope(value['scope'])
    ids=set();tokens=set();roots=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token']);roots.add(row['rootId'])
    need(not roots or len(roots)==1 and 'places.page' in ids)
    need(value['open'] or not value['controls'])
    return value


def project(original):
    need(type(original.get('placesControlsVersion')) is int and original['placesControlsVersion']==VERSION)
    rows=[]
    for row in original['controls']:
        # Legacy Back/Forward controls on another page remain component inputs;
        # they cannot borrow this selected Places root/profile.
        if control_id(row['id']) and row.get('profile')==PROFILE:
            current=deepcopy(row);current.pop('frame',None);rows.append(current)
    return snapshot(dict(placesControlsVersion=VERSION,open=original['tabletShown'],ready=original['ready'],
        scope={key:original[source] for key,source in (('instance','instance'),('processId','processId'),
            ('sequence','lastSequence'),('observationSequence','placesSourceSequence'),
            ('elapsedMs','elapsedMs'),('sampleEpochMs','sampleEpochMs'))},controls=rows))


def reference(value,identifier):
    snapshot(value);rows=[row for row in value['controls'] if row['id']==identifier];need(len(rows)==1)
    return dict(scope=deepcopy(value['scope']),control=deepcopy(rows[0]))


def same_reference(previous,current,identifier):
    snapshot(current);exact(previous,{'scope','control'});metadata(previous['control']);scope(previous['scope'])
    expected=reference(current,identifier)
    # Capturing again is read-only and cannot advance the input sequence. The
    # same page/row token is insufficient after another accepted input.
    old,new=previous['scope'],expected['scope']
    need(previous['control']['id']==identifier and all(same(old[key],new[key]) for key in ('instance','processId','sequence'))
         and new['observationSequence']>old['observationSequence']
         and old['elapsedMs']<=new['elapsedMs']<old['elapsedMs']+5000 and old['sampleEpochMs']<=new['sampleEpochMs']
         and same(previous['control'],expected['control']))
    return expected['control']


class IOSPlacesIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):return self.original.native.places_input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):return self.original.native.places_input(identifier,'replace',reference=reference,value=value)
