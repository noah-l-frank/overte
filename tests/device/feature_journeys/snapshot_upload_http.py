"""Closed optional Snapshot routes on the original trusted fixture listener."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import ssl
from feature_journeys.contract import exact,identifier
from feature_journeys.snapshot_upload_protocol import MULTIPART_LIMIT,STORY_LIMIT
from feature_journeys.snapshot_upload_provider import UPLOAD,STORIES,BODY


def handle(handler,parsed):
    if parsed.path not in (UPLOAD,STORIES) and not re.fullmatch(re.escape(STORIES)+r'/[1-9][0-9]{0,9}',parsed.path) and not re.fullmatch(re.escape(BODY)+r'[0-9a-f]{32}/image',parsed.path):return False
    provider=getattr(handler.server,'snapshot_upload_provider',None);handler.close_connection=True
    if provider is None or not isinstance(handler.connection,ssl.SSLSocket) or handler.connection.version() not in ('TLSv1.2','TLSv1.3'):
        handler.send(404,dict(error='not-found'));return True
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:raise ValueError('Invalid original Snapshot route')
    auth=handler.headers.get_all('Authorization',[]);lengths=handler.headers.get_all('Content-Length',[]);types=handler.headers.get_all('Content-Type',[]);hosts=handler.headers.get_all('Host',[])
    if len(auth)!=1 or len(auth[0])>512 or len(lengths)>1 or len(types)>1 or len(hosts)!=1 or not hosts[0].isascii() or len(hosts[0])>512 or handler.headers.get('Transfer-Encoding') or handler.headers.get('Content-Encoding'):
        raise ValueError('Invalid bounded original Snapshot headers')
    size=0
    if lengths:
        bound=MULTIPART_LIMIT if parsed.path==UPLOAD else STORY_LIMIT
        if not lengths[0].isdigit() or not 0<=int(lengths[0])<=bound:raise ValueError('Original Snapshot request exceeds its bound')
        size=int(lengths[0])
    if handler.command=='POST':
        if not size or len(types)!=1:raise ValueError('Original Snapshot POST body is unavailable')
    elif size:raise ValueError('Original Snapshot read/delete cannot carry a body')
    from feature_journeys.server import read_account_body
    raw=read_account_body(handler.rfile,handler.connection,size) if size else b''
    with provider.response(handler.command,parsed.path,types[0] if types else '',raw,auth[0],'https://'+hosts[0]) as response:
        status,body,response_id,written=response
        handler.send(status,body,content_type='image/png' if status==200 and parsed.path.endswith('/image') else 'application/json',response_id=response_id,observe_write=written)
    return True


def run_handle(handler,parts,body,*,reader,actor,adapter_reader):
    if len(parts)<3 or parts[0]!='runs' or parts[2]!='snapshots':return False
    provider=getattr(handler.server,'snapshot_upload_provider',None);run=identifier(parts[1]);journal=handler.server.journal
    if provider is None or run not in journal.runs or journal.runs[run]['area']!='snapshots':
        handler.send(404,dict(error='not-found'));return True
    route=parts[3:]
    if handler.command=='POST' and route==['prepare'] and reader:
        exact(body,{'accountRun'},'Snapshot original account binding');provider.provision(run,identifier(body['accountRun']))
        ticket=journal.runs[run]['ticket']
        if ticket is not None:provider.activate(run,ticket)
        handler.send(200,{});return True
    if run not in provider.runs:handler.send(503,dict(error='snapshot-provider-unprepared'));return True
    if handler.command=='GET' and route==['source'] and (reader or actor or adapter_reader):
        nonces=handler.headers.get_all('X-Overte-Snapshot-Read',[])
        if len(nonces)!=1:raise ValueError('One original Snapshot read nonce is required')
        handler.send(200,provider.original(run,identifier(nonces[0]),'source'));return True
    if handler.command=='GET' and len(route)==3 and route[0]=='bodies' and (reader or actor or adapter_reader):
        nonces=handler.headers.get_all('X-Overte-Snapshot-Read',[])
        if len(nonces)!=1 or not re.fullmatch('0|[1-9][0-9]{0,7}',route[2]):raise ValueError('One exact original Snapshot body query is required')
        handler.send(200,provider.original(run,identifier(nonces[0]),'body',identity=identifier(route[1]),offset=int(route[2])));return True
    if handler.command=='POST' and route==['retire'] and reader:
        exact(body,{'operation','identity'},'Snapshot fixture resource retirement')
        if body['operation']=='fence':
            if body['identity'] is not None:raise ValueError('Snapshot fence has no selected outcome')
            provider.fence(run)
        elif body['operation']=='story':provider.retire_story(run,body['identity'])
        elif body['operation']=='upload':provider.retire_upload(run,body['identity'])
        else:raise ValueError('Unknown owned Snapshot resource retirement')
        handler.send(200,{});return True
    handler.send(403,dict(error='forbidden'));return True
