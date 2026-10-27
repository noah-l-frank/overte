"""Actual weak Chat QObjects and current aliases; no callback/end authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,need
from adapters.script_ui_root_ownership import validate as original_roots,HEX

FIELDS={'page':'page','editor':'editor','localModel':'local-model','domainModel':'domain-model','list':'list'}


def complete(value):
    return value['available'] and value['complete'] and value['wholeTreeReady']


def validate(value,*,pid=None,epoch=None,previous=None):
    original_roots(value,pid=pid,epoch=epoch,previous=previous,profile='chat')
    if not value['available']:return value
    need(type(value['pages']) is list and len(value['pages'])<=64)
    roots={row['observedIdentity']:row for row in value['roots']};pages=set()
    for page in value['pages']:
        exact(page,set(FIELDS)|{'listModel','visible'});need(type(page['visible']) is bool)
        need(page['page'] not in pages);pages.add(page['page'])
        source=None
        for field,identity in page.items():
            if field=='visible':continue
            need(type(identity) is str and (re.fullmatch(HEX,identity) is not None or identity=='' and not complete(value)))
            if not identity or identity not in roots:
                need(not value['complete'] or not identity);continue
            row=roots[identity]
            need(row['weakAlive'] and (row['kind']==FIELDS[field] if field in FIELDS else row['kind'] in ('local-model','domain-model','other-model')))
            need(source in (None,row['componentSource']));source=row['componentSource']
        if complete(value):need(all(identity in roots for field,identity in page.items() if field!='visible'))
    need(sum(page['visible'] for page in value['pages'])<=1)
    return value


def selected(value,identity):
    validate(value);need(complete(value) and type(identity) is str)
    rows=[row for row in value['pages'] if row['page']==identity];need(len(rows)==1 and rows[0]['visible']);return rows[0]


def weakly_absent(value):
    """Only these actually observed QObjects; no whole-process/callback claim."""
    validate(value);need(complete(value));return value['pages']==[] and all(not row['weakAlive'] for row in value['roots'])
