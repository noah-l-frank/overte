"""Closed actual native Snapshot multipart and story request grammar.

These parsers accept original HTTP bytes only. They accept no expected hashes,
resource identities or desired backend state and never retain credentials.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import re
from email.message import Message
from feature_journeys.contract import json_document

IMAGE_LIMIT=8*1024*1024
MULTIPART_LIMIT=IMAGE_LIMIT+8192
STORY_LIMIT=16384
PRIVATE_PNG=re.compile(r'parity-([0-9a-f]{16})-still-png-snap_[0-9]{1,20}_[0-9]{1,10}\.png\Z')


def parameters(value,header):
    if type(value) is not str or len(value)>4096 or not value.isascii() or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Invalid original Snapshot MIME header')
    message=Message();message[header]=value;params=message.get_params(header=header,failobj=[])
    if not params or any(type(key) is not str or type(item) is not str for key,item in params):
        raise ValueError('Invalid original Snapshot MIME parameters')
    result={}
    for key,item in params:
        key=key.lower()
        if key in result:raise ValueError('Duplicate original Snapshot MIME parameter')
        result[key]=item
    return result


def multipart(content_type,raw):
    if type(raw) is not bytes or not 0<len(raw)<=MULTIPART_LIMIT:
        raise ValueError('Original Snapshot multipart exceeds its bound')
    params=parameters(content_type,'Content-Type')
    if set(params)!={'multipart/form-data','boundary'} or params['multipart/form-data']!='' or not re.fullmatch(r"[A-Za-z0-9'()+_,./:=?-]{1,70}",params['boundary']):
        raise ValueError('Original Snapshot multipart boundary is invalid')
    boundary=params['boundary'].encode('ascii');prefix=b'--'+boundary+b'\r\n';ending=b'\r\n--'+boundary+b'--'
    if not raw.startswith(prefix):raise ValueError('Original Snapshot multipart opening is invalid')
    end=len(raw)-len(ending)-(2 if raw.endswith(b'\r\n') else 0)
    if raw[end:end+len(ending)]!=ending:raise ValueError('Original Snapshot multipart closing is invalid')
    body=raw[len(prefix):end];divider=body.find(b'\r\n\r\n')
    if not 0<divider<=4096:raise ValueError('Original Snapshot image headers are unavailable')
    headers={}
    for line in body[:divider].split(b'\r\n'):
        if b':' not in line:raise ValueError('Invalid original Snapshot image header')
        key,value=line.split(b':',1)
        try:key=key.decode('ascii').lower();value=value.decode('ascii').strip(' ')
        except UnicodeError:raise ValueError('Invalid original Snapshot image header encoding') from None
        if key in headers:raise ValueError('Duplicate original Snapshot image header')
        headers[key]=value
    if set(headers)!={'content-type','content-disposition'} or headers['content-type']!='image/png':
        raise ValueError('Original Snapshot body is not one PNG image')
    disposition=parameters(headers['content-disposition'],'Content-Disposition')
    if set(disposition)!={'form-data','name','filename'} or disposition['form-data']!='' or disposition['name']!='image' or PRIVATE_PNG.fullmatch(disposition['filename']) is None:
        raise ValueError('Original Snapshot image ownership is unavailable')
    image=body[divider+4:]
    if not 8<len(image)<=IMAGE_LIMIT or not image.startswith(b'\x89PNG\r\n\x1a\n') or b'\r\n--'+boundary in image:
        raise ValueError('Original Snapshot PNG framing is invalid')
    return dict(filename=disposition['filename'],bytes=len(image),sha256=hashlib.sha256(image).hexdigest()),image


def story(raw):
    if type(raw) is not bytes or not 0<len(raw)<=STORY_LIMIT:raise ValueError('Original Snapshot story exceeds its bound')
    try:value=json_document(raw.decode('utf-8'))
    except UnicodeError:raise ValueError('Invalid original Snapshot story encoding') from None
    if type(value) is not dict or set(value)!={'user_story'}:raise ValueError('Invalid original Snapshot story envelope')
    row=value['user_story']
    if type(row) is not dict or set(row)!={'details','thumbnail_url','place_name','path','action','audience'} or row['action']!='snapshot' or row['audience']!='for_url':
        raise ValueError('Invalid original Snapshot story fields')
    for key in ('details','thumbnail_url','place_name','path'):
        if type(row[key]) is not str or len(row[key])>8192 or any(ord(c)<32 and c not in '\t\r\n' for c in row[key]):
            raise ValueError('Invalid original Snapshot story text')
    details=json_document(row['details'])
    required={'image_url','snapshot_id','original_image_file_name'}
    if type(details) is not dict or not required<=set(details)<=required|{'shareable_url'} or any(type(item) is not str or not item or len(item)>4096 for item in details.values()):
        raise ValueError('Invalid original Snapshot story details')
    return row,details
