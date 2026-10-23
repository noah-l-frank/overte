#!/usr/bin/env python3
"""Local controlled resources and authenticated independent-observer journal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import base64
from contextlib import ExitStack
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import stat
import time
import sys
import threading
from urllib.parse import urlsplit

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feature_journeys.contract import exact, identifier, json_document
from feature_journeys.fixtures import check, companion, payload
from feature_journeys.witness import Journal
from feature_journeys.create_permissions import CreatePermissionProvider
from feature_journeys.account_provider import AccountProvider,form,TOKEN_PATH,PROFILE_PATH,REQUEST_HEADER,RUN_HEADER,TICKET_HEADER
from feature_journeys.browser_fixture import BrowserResources
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY
from feature_journeys.script_fixture import ScriptResources
from feature_journeys.graphics_resources import GraphicsResources, RESOURCE as GRAPHICS_SCENE,ALL_RESOURCES as GRAPHICS_RESOURCES,profile_name as graphics_profile
from feature_journeys.graphics_fixture import LEGACY_PROFILE as LEGACY_GRAPHICS_PROFILE

from feature_journeys.snapshot_upload_service import SnapshotUploadService,SNAPSHOTS as SNAPSHOT_UPLOAD,STORIES as SNAPSHOT_STORIES,MAX_BODY as SNAPSHOT_MAX_BODY

PREFIX = '/feature-fixture/v1'


def read_account_body(stream,connection,size,*,monotonic=time.monotonic):
    # Socket inactivity alone must not permit an indefinitely trickled form.
    from feature_journeys.contract import number
    previous=number(monotonic());deadline=previous+2
    chunks=[];received=0
    try:
        while received<size:
            now=number(monotonic())
            if now<previous:raise ValueError('Account form clock regressed')
            previous=now;remaining=deadline-now
            if remaining<=0:raise ValueError('Account form deadline expired')
            connection.settimeout(remaining)
            chunk=stream.read1(size-received)
            if type(chunk) is not bytes or not chunk or len(chunk)>size-received:
                raise ValueError('Partial bounded account body')
            chunks.append(chunk);received+=len(chunk)
        now=number(monotonic())
        if now<previous or now>=deadline:raise ValueError('Account form deadline expired or clock regressed')
        return b''.join(chunks)
    finally:connection.settimeout(2)


def read_snapshot_body(stream,connection,size,received,*,monotonic=time.monotonic):
    # Preserve the existing two-second absolute transport bound while exposing
    # only actual received chunks to the private partial-body owner.
    from feature_journeys.contract import number
    previous=number(monotonic());deadline=previous+2;count=0
    try:
        while count<size:
            now=number(monotonic());remaining=deadline-now
            if now<previous or remaining<=0:raise ValueError('Snapshot body deadline expired')
            previous=now;connection.settimeout(remaining);chunk=stream.read1(size-count)
            if type(chunk) is not bytes or not chunk or len(chunk)>size-count:raise ValueError('Partial Snapshot body')
            received.append(chunk);count+=len(chunk)
        now=number(monotonic())
        if now<previous or now>=deadline:raise ValueError('Snapshot body deadline expired')
        return b''.join(received)
    finally:connection.settimeout(2)


class Handler(BaseHTTPRequestHandler):
    def handle(self):
        try:super().handle()
        except (BrokenPipeError,ConnectionResetError,ssl.SSLEOFError,TimeoutError):
            if getattr(self.server,'snapshot_upload_service',None) is None:raise
            # Qt can close an unused speculative TLS connection before any
            # HTTP request line exists. Actual Snapshot request/body ownership
            # is tracked separately by ingress, including partial-body errors.
            self.close_connection=True


    def log_message(self, *args):
        pass  # No private URLs, tokens, account aliases or request bodies in logs.

    def send(self, status, value, content_type='application/json', *, response_id=None, observe_write=None):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if response_id is not None:self.send_header('X-Overte-Fixture-Response',identifier(response_id))
        # Preserve the actual serialized header bytes before the original
        # end_headers flush. The requested status is not a measured response.
        if observe_write is not None:
            headers=b''.join(self._headers_buffer).split(b'\r\n')
            status_fields=headers[0].split(b' ',2)
            identities=[line.split(b':',1)[1].strip().decode('ascii') for line in headers
                if line.lower().startswith(b'x-overte-fixture-response:')]
            if len(status_fields)!=3 or not status_fields[1].isdigit() or len(identities)!=1:
                raise ValueError('Original Script response headers are unavailable')
            actual_status,actual_id=int(status_fields[1]),identifier(identities[0])
        self.end_headers()
        written=self.wfile.write(body)
        if observe_write is not None:
            if type(written) is not int or written!=len(body):raise ValueError('Original Script response write is incomplete')
            observe_write(dict(status=actual_status,responseId=actual_id,bytes=written,sha256=hashlib.sha256(body).hexdigest()))

    def resource(self,run,ticket,name):
        if name in GRAPHICS_RESOURCES:
            provider=self.server.graphics_resources
            if provider is None:return self.send(503,{'error':'graphics-provider-unavailable'})
            with self.server.journal.lock:
                if run not in self.server.journal.runs or not self.server.journal.has_ticket(run,ticket):
                    return self.send(404,{'error':'not-found'})
            self.connection.settimeout(2)
            authorities=self.headers.get_all('Host',[])
            if len(authorities)!=1:raise ValueError('One original Graphics request authority is required')
            with provider.response(run,ticket,request_authority=authorities[0],
                    request_scheme='https' if isinstance(self.connection,ssl.SSLSocket) else 'http',resource=name) as response:
                if response is None:return self.send(404,{'error':'not-found'})
                return self.send(response[0],response[1],
                    'application/json' if name.endswith('.json') else 'image/png' if name.endswith('.png') else 'text/html; charset=utf-8',
                    response_id=response[2],observe_write=response[3])
        if name=='missing.js' and self.server.script_resources is not None and self.server.script_resources.has_run(run):
            self.connection.settimeout(2)
            authorities=self.headers.get_all('Host',[])
            if len(authorities)!=1:raise ValueError('One original Script request authority is required')
            with self.server.script_resources.response(run,ticket,request_authority=authorities[0],
                    request_scheme='https' if isinstance(self.connection,ssl.SSLSocket) else 'http') as response:
                if response is None:return self.send(404,{'error':'not-found'})
                return self.send(response[0],response[1],response_id=response[2],observe_write=response[3])
        if name=='reference.mp4' and self.server.browser_resources.has_run(run):
            from fixture.parity_http import load_reference,send_reference
            if not hasattr(self.server,'parity_payload'):
                self.server.parity_manifest,self.server.parity_payload=load_reference(Path(__file__).resolve().parents[1]/'fixture')
            return send_reference(self)
        data=self.server.browser_resources.resource(run,ticket,name,
            origin='foreign' if self.server.browser_peer else 'primary')
        if data is not None:
            status,content_type,body,response=data
            return self.send(status,body,content_type,response_id=response)
        if self.server.browser_peer and not self.server.browser_resources.has_run(run):
            return self.send(404,{'error':'not-found'})
        data=payload(name,run,ticket)
        if data is None:
            try:data=('application/octet-stream',companion(name))
            except ValueError:return self.send(404,{'error':'not-found'})
        return self.send(200,data[1],data[0])

    def navigation_scene_request(self,parsed):
        provider=self.server.navigation_resources
        if provider is None or provider.scene_profile is None or parsed.path!=urlsplit(provider.inputs['sceneUrl']).path:return False
        authorities=self.headers.get_all('Host',[])
        if self.command!='GET' or parsed.scheme or parsed.netloc or parsed.fragment or len(authorities)!=1:
            self.send(404,{'error':'not-found'});return True
        self.connection.settimeout(2)
        with provider.scene_response(parsed.path,parsed.query,request_authority=authorities[0],
                request_scheme='https' if isinstance(self.connection,ssl.SSLSocket) else 'http') as response:
            if response is None:self.send(404,{'error':'not-found'})
            else:self.send(response[0],response[1],'application/json',response_id=response[2],observe_write=response[3])
        return True

    def navigation_request(self,parsed):
        if parsed.path!=DIRECTORY and not parsed.path.startswith(DIRECTORY+'/'):return False
        provider=self.server.navigation_resources
        if (self.command!='GET' or provider is None or parsed.scheme or parsed.netloc or parsed.fragment):
            self.send(404,{'error':'not-found'});return True
        self.connection.settimeout(2)
        with provider.response(parsed.path,parsed.query) as response:
            if response is None:self.send(404,{'error':'not-found'})
            else:self.send(response[0],response[1],response_id=response[2])
        return True

    def account_request(self,parsed):
        if parsed.path not in (TOKEN_PATH,PROFILE_PATH):return False
        provider=self.server.account_provider
        self.close_connection=True
        if (provider is None or not isinstance(self.connection,ssl.SSLSocket)
                or self.connection.version() not in ('TLSv1.2','TLSv1.3')):
            self.send(404,{'error':'not-found'});return True
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            self.send(400,{'error':'invalid-account-request'});return True
        if any(len(self.headers.get_all(name,[]))>1 for name in ('Authorization',REQUEST_HEADER,RUN_HEADER,TICKET_HEADER)):
            raise ValueError('Duplicate account header')
        if parsed.path==TOKEN_PATH and self.command=='POST':
            lengths=self.headers.get_all('Content-Length',[])
            if (len(lengths)!=1 or not lengths[0].isdigit() or not 0<int(lengths[0])<=4096
                    or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Encoding')
                    or self.headers.get('Content-Type','').split(';')[0].lower().strip()!='application/x-www-form-urlencoded'):
                raise ValueError('Invalid bounded account body')
            raw=read_account_body(self.rfile,self.connection,int(lengths[0]))
            if len(raw)!=int(lengths[0]):raise ValueError('Partial account body')
            values=form(raw)
            with provider.transaction(username=values.get('username'),refresh=values.get('refresh_token')):
                status,value=provider.grant(raw)
                self.send(status,value)
            return True
        elif parsed.path==PROFILE_PATH and self.command=='GET':
            authorization=self.headers.get('Authorization','')
            if len(authorization)>512:raise ValueError('Account authorization exceeds its bound')
            with provider.transaction(run=self.headers.get(RUN_HEADER),authorization=authorization):
                status,value=provider.profile(authorization,run=self.headers.get(RUN_HEADER),
                    ticket=self.headers.get(TICKET_HEADER),request=self.headers.get(REQUEST_HEADER))
                self.send(status,value)
            return True
        else:status,value=405,{'error':'method-not-allowed'}
        self.send(status,value)
        return True

    def snapshot_upload_request(self,parsed):
        if parsed.path not in (SNAPSHOT_UPLOAD,SNAPSHOT_STORIES) and not parsed.path.startswith(SNAPSHOT_STORIES+'/'):return False
        provider=self.server.snapshot_upload_service;self.close_connection=True
        if provider is None or not isinstance(self.connection,ssl.SSLSocket) or self.connection.version() not in ('TLSv1.2','TLSv1.3'):
            self.send(404,{'error':'not-found'});return True
        authorities=self.headers.get_all('Host',[])
        if authorities!=[urlsplit(provider.origin).netloc] or len(self.headers.get_all('Authorization',[]))>1:raise ValueError('Original Snapshot HTTPS authority is required')
        with provider.ingress(self.headers.get('Authorization','')):
            raw=b''
            if self.command=='POST':
                lengths=self.headers.get_all('Content-Length',[])
                if len(lengths)!=1 or not lengths[0].isdigit() or not 0<int(lengths[0])<=SNAPSHOT_MAX_BODY or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Encoding'):raise ValueError('Invalid bounded Snapshot upload body')
                received=[]
                try:raw=read_snapshot_body(self.rfile,self.connection,int(lengths[0]),received)
                except (ValueError,OSError):
                    provider.incomplete(self.headers.get('Authorization',''),self.command,self.path,self.headers.get('Content-Type',''),b''.join(received))
                    raise ValueError('Original Snapshot body was incomplete') from None
            elif self.headers.get('Content-Length') not in (None,'0') or self.headers.get('Transfer-Encoding'):raise ValueError('Unexpected Snapshot request body')
            with provider.response(self.headers.get('Authorization',''),self.command,self.path,self.headers.get('Content-Type',''),raw) as response:
                if response[0]==0:
                    try:self.connection.shutdown(2)
                    except OSError:pass
                else:self.send(response[0],response[1],response_id=response[2],observe_write=response[3])
        return True


    def send_snapshot_original(self,metadata,body):
        # A distinct binary route preserves the existing 1 MiB JSON Client
        # limit. The service measured these bytes from its retained multipart.
        encoded=base64.b64encode(json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()).decode('ascii')
        if len(encoded)>8192 or type(body) is not bytes or not 0<len(body)<=SNAPSHOT_MAX_BODY:
            raise ValueError('Original Snapshot binary response exceeds its bound')
        self.send_response(200)
        self.send_header('Content-Type',metadata['image']['mime'])
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Overte-Snapshot-Original',encoded)
        self.end_headers()
        if self.wfile.write(body)!=len(body):raise ValueError('Incomplete original Snapshot binary response')


    def handle_request(self):
        try:
            parsed = urlsplit(self.path)
            if self.server.browser_peer:
                # The second actual listener is resource-only, even with an
                # accidental reader/publisher token. It cannot mutate runs or
                # reach account endpoints.
                pieces=parsed.path[len(PREFIX)+1:].split('/') if parsed.path.startswith(PREFIX+'/') else []
                asset=(self.command=='GET' and len(pieces)>=5 and pieces[0]=='runs' and pieces[2]=='tickets')
                current=(self.command=='GET' and len(pieces)==3 and pieces[0]=='runs' and pieces[2]=='current')
                if not (asset or current) or len(pieces)<2 or not self.server.browser_resources.has_run(pieces[1]):
                    return self.send(404,{'error':'not-found'})
            adapter_token=getattr(self.server,'adapter_token',None)
            adapter_reader=(adapter_token is not None and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+adapter_token))
            # This includes native account/resource routes handled below. The
            # adapter credential cannot issue grants, publish peers or control
            # fixture state through an earlier route.
            adapter_markers=self.headers.get_all('X-Overte-Fixture-Adapter-Read',[])
            if adapter_markers and (adapter_markers!=['1'] or not adapter_reader):return self.send(403,{'error':'forbidden'})
            if adapter_reader and self.command!='GET':return self.send(403,{'error':'forbidden'})
            if self.snapshot_upload_request(parsed):return
            if self.account_request(parsed):return
            if self.navigation_scene_request(parsed):return
            if self.navigation_request(parsed):return
            if parsed.query or parsed.fragment or not parsed.path.startswith(PREFIX + '/'):
                return self.send(404, {'error': 'not-found'})
            parts = parsed.path[len(PREFIX) + 1:].split('/')
            auth = self.headers.get('Authorization', '')
            reader = hmac.compare_digest(auth, 'Bearer ' + self.server.reader_token)
            actor = hmac.compare_digest(auth, 'Bearer ' + self.server.actor_token)
            if self.command == 'GET' and len(parts) >= 6 and parts[:1] == ['runs'] and parts[2] == 'tickets':
                run, ticket = identifier(parts[1]), identifier(parts[3])
                # Resource access is public only for an unpredictable active run;
                # tickets bind actual resource bytes, never desired observations.
                if not self.server.journal.has_ticket(run, ticket):
                    return self.send(404, {'error': 'not-found'})
                resource = '/'.join(parts[4:])
                return self.resource(run,ticket,resource)
            if self.command == 'GET' and len(parts) == 3 and parts[0] == 'runs' and parts[2] == 'current':
                return self.send(200, {'ticket': self.server.journal.active(identifier(parts[1]))['ticket']})
            # Flat resource paths have exactly five components.
            if self.command == 'GET' and len(parts) == 5 and parts[0] == 'runs' and parts[2] == 'tickets':
                run, ticket = identifier(parts[1]), identifier(parts[3])
                if parts[4] in GRAPHICS_RESOURCES:return self.resource(run,ticket,parts[4])
                if parts[4]=='missing.js' and self.server.script_resources is not None and self.server.script_resources.has_run(run):
                    return self.resource(run,ticket,parts[4])
                if not self.server.journal.has_ticket(run, ticket):
                    return self.send(404, {'error': 'not-found'})
                return self.resource(run,ticket,parts[4])
            if self.command=='GET' and len(parts)==4 and parts[0]=='runs' and parts[2:]==['account','delayed']:
                run=identifier(parts[1])
                if (self.server.account_provider is None or run not in self.server.journal.runs
                        or self.server.journal.runs[run]['area']!='authentication'):
                    return self.send(404,{'error':'not-found'})
                return self.send(200,self.server.account_provider.delayed_status(run))
            if not reader and not actor and not adapter_reader:
                return self.send(403, {'error': 'forbidden'})
            if self.command=='GET' and parts==['adapter-reader']:
                if not adapter_reader:return self.send(403,{'error':'forbidden'})
                return self.send(200,dict(fixtureAdapterAccessVersion=1,role='adapter',canMutate=False,
                    canPublish=False,peerFactsVisible=False))
            if self.command=='GET' and parts==['account-provider']:
                if self.server.account_provider is None:return self.send(503,{'error':'account-provider-unavailable'})
                return self.send(200,dict(providerVersion=2,instance=self.server.account_provider.instance,
                    transport='https',tlsVersion=self.connection.version(),internalErrors=self.server.internal_errors))
            if self.command=='GET' and parts==['navigation-provider']:
                if self.server.navigation_resources is None:return self.send(503,{'error':'navigation-provider-unavailable'})
                return self.send(200,dict(self.server.navigation_resources.ready(),internalErrors=self.server.internal_errors))
            if self.command=='GET' and parts==['script-provider']:
                if self.server.script_resources is None:return self.send(503,{'error':'script-provider-unavailable'})
                return self.send(200,dict(self.server.script_resources.ready(),internalErrors=self.server.internal_errors))
            if self.command=='GET' and parts==['graphics-provider']:
                if self.server.graphics_resources is None:return self.send(503,{'error':'graphics-provider-unavailable'})
                return self.send(200,dict(self.server.graphics_resources.ready(),internalErrors=self.server.internal_errors))
            if self.command=='GET' and parts==['snapshot-upload-provider']:
                provider=self.server.snapshot_upload_service
                if provider is None:return self.send(503,{'error':'snapshot-upload-provider-unavailable'})
                return self.send(200,dict(snapshotUploadServiceVersion=provider.VERSION,instance=provider.instance,domainId=provider.domain_id,origin=provider.origin,internalErrors=self.server.internal_errors))
            body = None
            if self.command == 'POST':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Invalid bounded body')
                body = json_document(self.rfile.read(size))
            if self.command == 'POST' and parts == ['runs'] and reader:
                exact(body, {'area'}|({'graphicsProfile'} if type(body) is dict and 'graphicsProfile' in body else set()), 'fixture registration')
                selected=graphics_profile(body.get('graphicsProfile',LEGACY_GRAPHICS_PROFILE))
                if 'graphicsProfile' in body and body['area']!='graphics':raise ValueError('Graphics profile belongs to a different feature area')
                if body['area']=='authentication' and self.server.account_provider is None:
                    return self.send(503,{'error':'account-provider-unavailable'})
                if body['area']=='world-navigation' and self.server.navigation_resources is None:
                    return self.send(503,{'error':'navigation-provider-unavailable'})
                if body['area']=='scripts' and self.server.script_resources is None:
                    return self.send(503,{'error':'script-provider-unavailable'})
                run=self.server.journal.register(body['area'])
                if body['area']=='create' and self.server.create_permissions is not None:
                    try:self.server.create_permissions.provision(run)
                    except (OSError,RuntimeError):return self.send(503,{"error":"create-permissions-unavailable"})
                if body['area']=='snapshots' and self.server.snapshot_upload_service is not None:
                    try:self.server.snapshot_upload_service.provision(run)
                    except BaseException:self.server.journal.close(run);raise
                if body['area']=='graphics' and self.server.graphics_resources is not None:
                    try:self.server.graphics_resources.provision(run,profile=selected)
                    except Exception:
                        self.server.journal.close(run)
                        raise
                if body['area']=='world-navigation':
                    try:self.server.navigation_resources.provision(run)
                    except Exception:
                        self.server.journal.close(run)
                        raise
                if body['area'] in ('world-web','tablet-web'):self.server.browser_resources.open(run,area=body['area'])
                if body['area']=='scripts':
                    try:self.server.script_resources.provision(run)
                    except Exception:
                        self.server.journal.close(run)
                        raise
                if body['area']=='authentication' and self.server.account_provider is not None:
                    try:self.server.account_provider.provision(run)
                    except Exception:
                        self.server.journal.close(run)
                        raise
                return self.send(200, {'runId': run})
            if len(parts) < 2 or parts[0] != 'runs':
                return self.send(404, {'error': 'not-found'})
            run = identifier(parts[1])
            if parts[2:]==['create-permissions']:
                if self.command!='GET':return self.send(403,{'error':'forbidden'})
                provider=self.server.create_permissions
                if provider is None:return self.send(503,{'error':'create-permissions-unavailable'})
                requests=self.headers.get_all('X-Overte-Phase-Read',[])
                if len(requests)!=1:raise ValueError('Original Create Settings snapshot nonce is required')
                nonce=identifier(requests[0])
                with self.server.journal.lock:
                    phase=self.server.journal.phase(run,nonce)
                    if phase['area']!='create':return self.send(403,{'error':'forbidden'})
                    try:source=provider.snapshot(run,nonce,phase)
                    except (OSError,RuntimeError):return self.send(503,{"error":"create-permissions-unavailable"})
                return self.send(200,source)
            if parts[2:]==['snapshot-upload']:
                provider=self.server.snapshot_upload_service
                if self.command!='GET' or provider is None:return self.send(503,{'error':'snapshot-upload-provider-unavailable'})
                nonces=self.headers.get_all('X-Overte-Snapshot-Upload-Read',[])
                if len(nonces)!=1:raise ValueError('Fresh original Snapshot upload nonce is required')
                return self.send(200,provider.snapshot(run,identifier(nonces[0])))
            if len(parts)==6 and parts[2:4]==['snapshot-upload','original']:
                if (self.command!='GET' or self.server.snapshot_upload_service is None or len(self.headers.get_all('Authorization',[]))!=1
                        or not isinstance(self.connection,ssl.SSLSocket) or self.connection.version() not in ('TLSv1.2','TLSv1.3')):return self.send(403,{'error':'forbidden'})
                if parsed.query or self.headers.get('Content-Length') not in (None,'0') or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Unexpected original Snapshot binary query body')
                metadata,payload=self.server.snapshot_upload_service.image_original(run,identifier(parts[4]),identifier(parts[5]))
                return self.send_snapshot_original(metadata,payload)
            if parts[2:]==['snapshot-upload','credentials']:
                if (self.command!='GET' or not (reader or adapter_reader) or self.server.snapshot_upload_service is None
                        or not isinstance(self.connection,ssl.SSLSocket) or self.connection.version() not in ('TLSv1.2','TLSv1.3')):
                    return self.send(403,{'error':'forbidden'})
                # Only the primary adapter's normal owned login needs these
                # private inputs. Actor publishing stays credential-free and
                # cannot borrow an unrelated account run through this route.
                original=self.server.journal.runs.get(run)
                if (original is None or original['area']!='snapshots'
                        or not self.server.snapshot_upload_service.has_run(run)):
                    return self.send(404,{'error':'not-found'})
                return self.send(200,self.server.snapshot_upload_service.credentials(run))
            if parts[2:]==['snapshot-upload','control']:
                if self.command!='POST' or not reader or self.server.snapshot_upload_service is None:return self.send(403,{'error':'forbidden'})
                exact(body,{'operation'},'Snapshot upload fixture control');self.server.snapshot_upload_service.control(run,body['operation']);return self.send(200,{})
            if parts[2:]==['phase']:
                if self.command!='GET':return self.send(403,{'error':'forbidden'})
                requests=self.headers.get_all('X-Overte-Phase-Read',[])
                if len(requests)!=1:raise ValueError('Original phase snapshot nonce is required')
                return self.send(200,self.server.journal.phase(run,identifier(requests[0])))
            if parts[2:]==['graphics']:
                if self.command=='GET' and self.server.graphics_resources is not None:
                    requests=self.headers.get_all('X-Overte-Graphics-Read',[])
                    if len(requests)!=1:raise ValueError('Original Graphics snapshot nonce is required')
                    nonce=identifier(requests[0])
                    with self.server.journal.lock:
                        source=self.server.graphics_resources.snapshot(run,nonce)
                        if source['active'] and (run not in self.server.journal.runs or source['ticket']!=self.server.journal.runs[run]['ticket']):
                            return self.send(503,{'error':'graphics-provider-ownership-inconsistent'})
                    return self.send(200,source)
                return self.send(503,{'error':'graphics-provider-unavailable'})
            if parts[2:]==['scripts']:
                if self.command=='GET' and self.server.script_resources is not None:
                    requests=self.headers.get_all('X-Overte-Script-Read',[])
                    if len(requests)!=1:raise ValueError('Original Script snapshot nonce is required')
                    nonce=identifier(requests[0])
                    with self.server.journal.lock:
                        source=self.server.script_resources.snapshot(run,nonce)
                        if source['active'] and (run not in self.server.journal.runs or source['ticket']!=self.server.journal.runs[run]['ticket']):
                            return self.send(503,{'error':'script-provider-ownership-inconsistent'})
                    return self.send(200,source)
                return self.send(503,{'error':'script-provider-unavailable'})
            if parts[2:]==['navigation']:
                if self.command=='GET' and self.server.navigation_resources is not None:
                    return self.send(200,self.server.navigation_resources.snapshot(run))
                return self.send(503,{'error':'navigation-provider-unavailable'})
            if parts[2:]==['browser']:

                if self.command=='GET':return self.send(200,self.server.browser_resources.snapshot(run))
                return self.send(403,{'error':'forbidden'})
            if parts[2:]==['browser','control']:
                if self.command=='POST' and reader:
                    self.server.browser_resources.control(run,body)
                    return self.send(200,{}) # Read status independently; ACK is not client recovery.
                return self.send(403,{'error':'forbidden'})
            if len(parts)>=3 and parts[2]=='account':
                provider=self.server.account_provider
                if provider is None:return self.send(503,{'error':'account-provider-unavailable'})
                if self.command=='GET' and parts[3:]==['status']:
                    return self.send(200,provider.snapshot(run))
                if self.command=='GET' and len(parts)==5 and parts[3]=='credentials' and (reader or adapter_reader):
                    return self.send(200,provider.credentials(run,parts[4]))
                if self.command=='GET' and len(parts)==6 and parts[3]=='proof' and actor:
                    return self.send(200,provider.proof(run,parts[4],parts[5]))
                if self.command=='POST' and parts[3:]==['control'] and reader:
                    exact(body,{'operation'},'account fixture control')
                    provider.control(run,body['operation'])
                    return self.send(200,{}) # Read status separately; an ACK proves no cleanup.
                return self.send(403,{'error':'forbidden'})
            if self.command == 'POST' and parts[2:] == ['active'] and reader:
                exact(body, {'ticket', 'verb', 'inputs'}, 'fixture challenge')
                if self.server.journal.runs[run]['area']=='create' and self.server.create_permissions is not None:
                    with self.server.journal.lock:
                        self.server.journal.activate(run,body['ticket'],body['verb'],body['inputs'])
                        try:self.server.create_permissions.activate(run,self.server.journal.runs[run]['phaseActivations'][-1])
                        except (OSError,RuntimeError):return self.send(503,{"error":"create-permissions-unavailable"})
                elif (self.server.journal.runs[run]['area']=='graphics' and self.server.graphics_resources is not None):
                    with self.server.journal.lock:
                        self.server.journal.activate(run,body['ticket'],body['verb'],body['inputs'])
                        self.server.graphics_resources.activate(run,body['ticket'])
                elif self.server.journal.runs[run]['area']=='scripts':
                    with self.server.journal.lock:
                        self.server.journal.activate(run, body['ticket'], body['verb'], body['inputs'])
                        self.server.script_resources.activate(run,body['ticket'])
                elif self.server.journal.runs[run]['area']=='snapshots' and self.server.snapshot_upload_service is not None:
                    with self.server.journal.lock:
                        self.server.journal.activate(run,body['ticket'],body['verb'],body['inputs'])
                        self.server.snapshot_upload_service.activate(run,body['ticket'],body['verb'])
                else:self.server.journal.activate(run, body['ticket'], body['verb'], body['inputs'])
                if self.server.journal.runs[run]['area']=='world-navigation':
                    self.server.navigation_resources.activate(run,body['ticket'])
                if body['verb']=='restore-resource' and self.server.browser_resources.has_run(run):
                    self.server.browser_resources.control(run,{'operation':'restore-resource'})
                if (self.server.account_provider is not None and run in self.server.account_provider.runs
                        and not (self.server.snapshot_upload_service is not None and self.server.snapshot_upload_service.has_run(run))):
                    self.server.account_provider.activate(run,body['ticket'])
                    stimulus=self.server.journal.active(run)['stimulus']
                    if stimulus['verb']=='login-submit' and stimulus['inputs'].get('account')=='delayed':
                        self.server.account_provider.control(run,'hold-next')
                    elif stimulus['verb']=='release-stale-response':
                        self.server.account_provider.control(run,'release-delayed')
                    elif stimulus['verb']=='cleanup':
                        self.server.account_provider.control(run,'revoke-issued')
                return self.send(200, {})
            if self.command == 'GET' and parts[2:] == ['active']:
                return self.send(200, self.server.journal.active(run))
            if self.command == 'POST' and parts[2:] == ['samples'] and actor:
                self.server.journal.publish(run, body)
                return self.send(200, {})
            if self.command == 'GET' and len(parts) == 2:
                original=self.server.journal.snapshot(run)
                if adapter_reader:original['entries']=[] # Only the original phase/read clock, never independent peer facts.
                return self.send(200,original)
            if self.command == 'DELETE' and len(parts) == 2 and reader:
                if self.server.journal.runs.get(run,{}).get('area')=='create' and self.server.create_permissions is not None:
                    with self.server.journal.lock:
                        try:self.server.create_permissions.retire(run)
                        except (OSError,RuntimeError):return self.send(503,{"error":"create-permissions-unavailable"})
                        self.server.journal.close(run)
                    return self.send(200,{})
                if self.server.snapshot_upload_service is not None and self.server.snapshot_upload_service.has_run(run):
                    with self.server.journal.lock:
                        self.server.snapshot_upload_service.retire(run)
                        if run in self.server.journal.runs:self.server.journal.close(run)
                    return self.send(200,{})
                if self.server.graphics_resources is not None and self.server.graphics_resources.has_run(run):
                    with self.server.journal.lock:
                        self.server.graphics_resources.retire(run)
                        if run in self.server.journal.runs:self.server.journal.close(run)
                    return self.send(200,{})
                if self.server.script_resources is not None and self.server.script_resources.has_run(run):
                    with self.server.journal.lock:
                        self.server.script_resources.retire(run)
                        if run in self.server.journal.runs:self.server.journal.close(run)
                    return self.send(200,{})
                if self.server.navigation_resources is not None and run in self.server.navigation_resources.runs:
                    self.server.navigation_resources.retire(run)
                if self.server.account_provider is not None and run in self.server.account_provider.runs:
                    self.server.account_provider.retire(run)
                self.server.journal.close(run)
                self.server.browser_resources.close(run)
                return self.send(200, {})
            return self.send(403, {'error': 'forbidden'})
        except (ValueError, KeyError, TypeError,UnicodeError):
            self.send(400, {'error': 'invalid-owned-fixture-request'})
        except (BrokenPipeError,ConnectionResetError,ssl.SSLEOFError,TimeoutError):
            self.close_connection=True # A real cancelled client connection is not an internal fixture error.

    do_GET = handle_request
    do_POST = handle_request
    do_DELETE = handle_request


class FixtureServer(ThreadingHTTPServer):
    def get_request(self):
        connection,address=super().get_request()
        if self.tls_context is not None:
            connection.settimeout(2)
            try:connection=self.tls_context.wrap_socket(connection,server_side=True)
            except Exception:
                connection.close()
                raise
        return connection,address

    def handle_error(self,*_args):
        # No exception/raw request/credential material in public service logs.
        self.internal_errors+=1

    def server_close(self):
        if getattr(self,'account_provider',None) is not None:self.account_provider.shutdown()
        super().server_close()


def make_server(reader_token, actor_token, address=('127.0.0.1', 0),*,account_provider=None,tls_context=None,browser_peer_of=None,navigation_resources=None,graphics_resources=None,adapter_token=None,create_permissions=None,snapshot_upload_service=None):
    if adapter_token is not None and (type(adapter_token) is not str or not 32<=len(adapter_token)<=256
            or not adapter_token.isascii() or any(not 33<=ord(c)<=126 for c in adapter_token)
            or adapter_token in (reader_token,actor_token)):
        raise ValueError('A separate private adapter-only read credential is required')
    if (type(reader_token) is not str or type(actor_token) is not str
            or min(len(reader_token), len(actor_token)) < 32 or reader_token == actor_token):
        raise ValueError('Separate private reader and independent publisher tokens are required')
    if (type(address) is not tuple or len(address)!=2 or type(address[0]) is not str or not 0<len(address[0])<=253
            or any(ord(c)<32 for c in address[0]) or type(address[1]) is not int or not 0<=address[1]<=65535):
        raise ValueError('Invalid bounded fixture listener')
    if tls_context is not None and (not isinstance(tls_context,ssl.SSLContext)
            or tls_context.protocol!=ssl.PROTOCOL_TLS_SERVER or tls_context.minimum_version<ssl.TLSVersion.TLSv1_2):
        raise ValueError('A TLS 1.2+ server context is required')
    if account_provider is not None and (not isinstance(account_provider,AccountProvider) or tls_context is None):
        raise ValueError('Account credentials require an explicitly trusted HTTPS fixture')
    if browser_peer_of is not None and (not isinstance(browser_peer_of,FixtureServer) or browser_peer_of.browser_peer
            or account_provider is not None):raise ValueError('Browser second listener needs the original primary owner')
    if navigation_resources is not None and (not isinstance(navigation_resources,NavigationResources) or browser_peer_of is not None):
        raise ValueError('Navigation provider requires its original primary owner')
    if account_provider is not None:account_provider._attach(reader_token,actor_token)
    if graphics_resources is not None and (not isinstance(graphics_resources,GraphicsResources) or browser_peer_of is not None):
        raise ValueError('Graphics provider requires its original primary owner')
    if create_permissions is not None and (not isinstance(create_permissions,CreatePermissionProvider) or browser_peer_of is not None):
        raise ValueError("Create Settings provider requires its original primary owner")
    if snapshot_upload_service is not None and (not isinstance(snapshot_upload_service,SnapshotUploadService) or snapshot_upload_service.accounts is not account_provider or tls_context is None or browser_peer_of is not None):
        raise ValueError('Snapshot service requires its original HTTPS account owner')
    server = FixtureServer(address, Handler)
    server.account_provider,server.tls_context=account_provider,tls_context
    server.navigation_resources=navigation_resources
    server.graphics_resources=graphics_resources
    server.create_permissions=create_permissions
    server.snapshot_upload_service=snapshot_upload_service
    server.script_resources=ScriptResources() if browser_peer_of is None else browser_peer_of.script_resources
    server.internal_errors=0
    server.reader_token, server.actor_token = reader_token, actor_token
    server.adapter_token=adapter_token
    server.journal = Journal() if browser_peer_of is None else browser_peer_of.journal
    server.browser_resources = BrowserResources() if browser_peer_of is None else browser_peer_of.browser_resources
    server.browser_peer = browser_peer_of is not None
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--private-config', type=Path)
    args = parser.parse_args()
    count = check()
    if args.check:
        print(f'PASS: {count} pinned companions and feature fixture generators')
        return
    if args.private_config is None:
        parser.error('--private-config is required to serve')
    from adapters.normal_feature_state import PrivateFeatureState
    config=PrivateFeatureState(args.private_config.absolute()).read()
    fields={'readerToken','actorToken','host','port'}|({'adapterToken'} if 'adapterToken' in config else set())|({'tls'} if 'tls' in config else set())|({'accountProvider'} if 'accountProvider' in config else set())|({'browserPeer'} if 'browserPeer' in config else set())|({'navigationProvider'} if 'navigationProvider' in config else set())|({'graphicsProvider'} if 'graphicsProvider' in config else set())|({'navigationSceneProfile'} if 'navigationSceneProfile' in config else set())|({'createPermissionProvider'} if 'createPermissionProvider' in config else set())
    fields|=({'snapshotUploadService'} if 'snapshotUploadService' in config else set())
    exact(config,fields,'private fixture configuration')
    tls=None;provider=None
    if 'tls' in config:
        exact(config['tls'],{'certificateFile','privateKeyFile'},'private TLS configuration')
        for key in ('certificateFile','privateKeyFile'):
            path=Path(config['tls'][key]);info=path.lstat()
            if (not path.is_absolute() or path.resolve()!=path or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                    or key=='privateKeyFile' and (info.st_mode&0o077 or os.name!='nt' and info.st_uid!=os.geteuid())):
                raise ValueError('TLS fixture files must have private original ownership')
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2
        def no_password_prompt():raise ValueError('Encrypted fixture keys require prepared private runtime material')
        tls.load_cert_chain(config['tls']['certificateFile'],config['tls']['privateKeyFile'],password=no_password_prompt)
    if 'accountProvider' in config:
        if config['accountProvider'] is not True:raise ValueError('Explicit account provider opt-in is required')
        provider=AccountProvider()
    if 'navigationSceneProfile' in config and 'navigationProvider' not in config:raise ValueError('Navigation scene requires its original provider')
    navigation=NavigationResources(config['navigationProvider'],scene_profile=config.get('navigationSceneProfile')) if 'navigationProvider' in config else None
    graphics=None
    if 'graphicsProvider' in config:
        exact(config['graphicsProvider'],{'fixtureUrl'},'actual Graphics fixture input')
        graphics=GraphicsResources(config['graphicsProvider']['fixtureUrl'])
    create_permissions=None
    if "createPermissionProvider" in config:
        details=config["createPermissionProvider"]
        exact(details,{"controlUrl","controlToken","domainId","stateFile"},"private Create Settings provider")
        create_permissions=CreatePermissionProvider({k:v for k,v in details.items() if k!="stateFile"},PrivateFeatureState(Path(details["stateFile"])))
    snapshot_upload=None
    if 'snapshotUploadService' in config:
        exact(config['snapshotUploadService'],{'domainId','root','origin'},'owned Snapshot HTTPS service')
        values=config['snapshotUploadService'];snapshot_upload=SnapshotUploadService(provider,values['domainId'],values['root'],values['origin'])
    with ExitStack() as owned:
        server=owned.enter_context(make_server(config['readerToken'],config['actorToken'],(config['host'],config['port']),
            account_provider=provider,tls_context=tls,navigation_resources=navigation,graphics_resources=graphics,adapter_token=config.get('adapterToken'),create_permissions=create_permissions,snapshot_upload_service=snapshot_upload))
        peer=None;worker=None
        if 'browserPeer' in config:
            exact(config['browserPeer'],{'host','port'},'private second browser listener')
            peer=owned.enter_context(make_server(config['readerToken'],config['actorToken'],
                (config['browserPeer']['host'],config['browserPeer']['port']),tls_context=tls,browser_peer_of=server))
            worker=threading.Thread(target=peer.serve_forever,daemon=True);worker.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if peer is not None:
                peer.shutdown();worker.join(timeout=2)
                if worker.is_alive():raise ValueError('Owned second browser listener failed to stop')


if __name__ == '__main__':
    try:main()
    except Exception:raise SystemExit('Controlled feature fixture configuration or service is unavailable') from None
