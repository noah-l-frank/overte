"""Owned OAuth/profile protocol fixture; actual requests, never desired facts.

This is a test provider for an explicitly configured trusted HTTPS origin. It
does not change client transport policy, act as a peer or establish UI success.
Secrets stay in private fixture memory/credential delivery and TLS responses.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hmac
import re
import secrets
import threading
import time
from urllib.parse import parse_qsl
from .contract import exact,identifier,number

VERSION=2
TOKEN_PATH='/oauth/token'
PROFILE_PATH='/api/v1/user/profile'
REQUEST_HEADER='X-Overte-E2E-Request'
RUN_HEADER='X-Overte-E2E-Run'
TICKET_HEADER='X-Overte-E2E-Ticket'


def request_id(value):
    if type(value) is not str or re.fullmatch('(?:ios-)?[0-9a-f]{32}',value) is None:
        raise ValueError('Invalid original profile request identity')
    return value


def form(raw):
    if type(raw) is not bytes or not 0<len(raw)<=4096:raise ValueError('Invalid bounded OAuth form')
    text=raw.decode('ascii')
    if re.search(r'%(?![0-9a-fA-F]{2})',text):raise ValueError('Invalid OAuth encoding')
    pairs=parse_qsl(text,keep_blank_values=True,strict_parsing=True,encoding='utf-8',errors='strict',max_num_fields=8)
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Duplicate OAuth form field')
        value[key]=item
    required={'grant_type','scope'}|({'refresh_token'} if value.get('grant_type')=='refresh_token' else {'username','password'})
    exact(value,required,'OAuth form')
    if value['scope']!='owner' or value['grant_type'] not in ('password','refresh_token'):
        raise ValueError('Unsupported OAuth grant')
    if any(not item or len(item)>512 or any(ord(c)<32 for c in item) for item in value.values()):
        raise ValueError('Invalid OAuth form value')
    return value


class AccountProvider:
    """Bounded provider state behind the existing fixture HTTP handler."""
    def __init__(self,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,hold_seconds=90):
        number(hold_seconds,.01,90)
        if not callable(epoch_ms) or not callable(monotonic):raise ValueError('Invalid provider clock')
        self.epoch_ms,self.monotonic,self.hold_seconds=epoch_ms,monotonic,hold_seconds
        self.changed=threading.Condition(threading.RLock())
        self.runs={};self.access={};self.refresh={};self.sequence=0;self.last_epoch=0
        self.instance=secrets.token_hex(16);self.retired=set();self.closed=False
        self._reserved=set();self._attached=False

    def _attach(self,reader,actor):
        with self.changed:
            if self._attached or self.closed:raise ValueError('Account provider already has an owner')
            for value in (reader,actor):
                if value in self.access or value in self.refresh or any(r['password']==value for r in self.runs.values()):
                    raise ValueError('Fixture role and account credentials must be separate')
            self._reserved.update((reader,actor));self._attached=True

    def now(self):
        value=self.epoch_ms();number(value,1)
        if type(value) is not int or value<self.last_epoch:raise ValueError('Provider clock is unavailable')
        self.last_epoch=value
        return value

    def provision(self,run):
        identifier(run)
        with self.changed:
            if self.closed or run in self.runs or run in self.retired or len(self.retired)>=256 or len(self.runs)>=32:
                raise ValueError('Owned account already exists or provider is full')
            password=secrets.token_urlsafe(32)
            if password in self._reserved:raise ValueError('Fixture credential entropy is unavailable')
            self.runs[run]=dict(username='e2e-'+run,password=password,active=True,
                ticket=None,events=[],droppedEvents=0,held=None,holdNext=False,closed=False,usedRequests=set(),inflight=0,
                grantsEnabled=True,delayed={},grantRequests=set())

    @contextmanager
    def transaction(self,*,run=None,username=None,refresh=None,authorization=None):
        with self.changed:
            if run is not None:identifier(run)
            elif type(username) is str and re.fullmatch('e2e-[0-9a-f]{32}',username):run=username[4:]
            elif refresh in self.refresh:run=self.refresh[refresh]['run']
            elif type(authorization) is str and authorization.startswith('Bearer ') and authorization[7:] in self.access:
                run=self.access[authorization[7:]]['run']
            row=self.runs.get(run)
            if row is not None:
                if row['inflight']>=16:raise ValueError('Owned account request limit reached')
                row['inflight']+=1
        try:yield
        finally:
            with self.changed:
                if row is not None:row['inflight']-=1
                self.changed.notify_all()

    def credentials(self,run,role):
        with self.changed:
            row=self.runs[identifier(run)]
            if not row['active'] or not row['grantsEnabled'] or role not in ('owned','invalid','delayed'):raise ValueError('Owned account is unavailable')
            # Invalid login uses a genuinely incorrect password. Delayed login
            # uses the same real account; only actual response delivery is held.
            return dict(username=row['username'],password=row['password'] if role!='invalid' else 'invalid-'+row['password'])

    def activate(self,run,ticket):
        with self.changed:self.runs[identifier(run)]['ticket']=identifier(ticket)

    def _record(self,run,kind,**facts):
        row=self.runs[run]
        self.sequence+=1
        event=dict(providerVersion=VERSION,instance=self.instance,eventSequence=self.sequence,capturedEpochMs=self.now(),
            kind=kind,runId=run,ticket=row['ticket'],**facts)
        row['events'].append(event)
        if len(row['events'])>1024:row['events'].pop(0);row['droppedEvents']+=1
        return event

    def control(self,run,operation):
        with self.changed:
            identifier(run)
            if run in self.retired and operation=='cleanup':return
            row=self.runs[identifier(run)]
            if operation=='hold-next':
                if not row['active'] or not row['grantsEnabled'] or row['ticket'] is None or row['holdNext'] or row['held'] is not None:raise ValueError('A delayed grant is already owned')
                row['holdNext']=True
            elif operation=='release-delayed':
                if row['held'] is None or row['held']['released'] or row['held']['cancelled']:raise ValueError('No actual delayed grant is waiting')
                row['held']['released']=True
                row['delayed'][row['held']['requestId']]['releasedEpochMs']=self.now()
                self._record(run,'grant-released',grantRequestId=row['held']['requestId']);self.changed.notify_all()
            elif operation=='revoke-issued':
                row.update(grantsEnabled=False,holdNext=False)
                if row['held'] is not None:row['held']['cancelled']=True
                self.access={k:v for k,v in self.access.items() if v['run']!=run}
                self.refresh={k:v for k,v in self.refresh.items() if v['run']!=run}
                self._record(run,'issued-authority-revoked');self.changed.notify_all()
            elif operation=='cleanup':
                row.update(active=False,closed=True,holdNext=False,grantsEnabled=False)
                if row['held'] is not None:row['held']['cancelled']=True
                row['username']=row['password']=None
                self.access={k:v for k,v in self.access.items() if v['run']!=run}
                self.refresh={k:v for k,v in self.refresh.items() if v['run']!=run}
                self._record(run,'account-cleaned');self.changed.notify_all()
            else:raise ValueError('Unknown owned account control')

    def grant(self,raw):
        value=form(raw)
        with self.changed:
            row=run=None
            if value['grant_type']=='password':
                for candidate,record in self.runs.items():
                    if record['active'] and hmac.compare_digest(value['username'].encode(),record['username'].encode()):
                        run,row=candidate,record
                if row is None or not hmac.compare_digest(value['password'].encode(),row['password'].encode()):
                    if run is not None:self._record(run,'grant-rejected',status=400)
                    return 400,dict(error='invalid_grant')
            else:
                token=self.refresh.get(value['refresh_token'])
                if token is not None and token['expires']>self.now() and self.runs[token['run']]['active']:
                    run=token['run'];row=self.runs[run]
                else:return 400,dict(error='invalid_grant')
            if not row['grantsEnabled']:return 503,dict(error='temporarily_unavailable')
            request=secrets.token_hex(16)
            if request in row['grantRequests'] or len(row['grantRequests'])>=4096:
                return 503,dict(error='temporarily_unavailable')
            row['grantRequests'].add(request)
            self._record(run,'grant-request',grantType=value['grant_type'],grantRequestId=request)
            delayed=None
            if row['holdNext']:
                if len(row['delayed'])>=64:return 503,dict(error='temporarily_unavailable')
                row['holdNext']=False;row['held']=dict(released=False,cancelled=False,requestId=request)
                delayed=dict(requestId=request,requestTicket=row['ticket'],startedEpochMs=self.now(),
                    releasedEpochMs=0,issuedEpochMs=0,status=0,state='held')
                row['delayed'][request]=delayed
                self._record(run,'grant-held',grantRequestId=request);self.changed.notify_all()
                started=self.monotonic();number(started);previous=started
                while not row['held']['released'] and not row['held']['cancelled'] and row['active']:
                    now=self.monotonic();number(now)
                    if now<previous or now-started>=self.hold_seconds:
                        row['held']=None;delayed.update(status=503,state='expired')
                        self._record(run,'grant-hold-expired',grantRequestId=request);self.changed.notify_all()
                        return 503,dict(error='temporarily_unavailable')
                    previous=now;self.changed.wait(min(.05,self.hold_seconds-(now-started)))
                cancelled=row['held']['cancelled'];row['held']=None;self.changed.notify_all()
                if cancelled or not row['active'] or not row['grantsEnabled']:
                    delayed.update(status=503,state='cancelled');return 503,dict(error='temporarily_unavailable')
            def unavailable():
                if delayed is not None:delayed.update(status=503,state='rejected')
                self._record(run,'grant-unavailable',status=503,grantRequestId=request)
                return 503,dict(error='temporarily_unavailable')
            if sum(t['run']==run for t in self.access.values())>=64:return unavailable()
            now=self.now();access=secrets.token_urlsafe(32);refresh=secrets.token_urlsafe(32)
            if (access==refresh or any(t in self.access or t in self.refresh or t in self._reserved
                    or any(r['password']==t for r in self.runs.values()) for t in (access,refresh))):return unavailable()
            self.access[access]=dict(run=run,expires=now+3600000,grantRequestId=request)
            self.refresh[refresh]=dict(run=run,expires=now+86400000,grantRequestId=request)
            if delayed is not None:delayed.update(issuedEpochMs=now,status=200,state='issued')
            self._record(run,'grant-issued',status=200,grantRequestId=request)
            return 200,dict(access_token=access,token_type='Bearer',expires_in=3600,refresh_token=refresh)

    def delayed_status(self,run):
        """Public sanitized original request/authority facts; no credentials or setters."""
        with self.changed:
            row=self.runs[identifier(run)];now=self.now()
            if not row['active']:raise ValueError('Retired account scope is unavailable')
            records=[]
            for request,original in row['delayed'].items():
                actual={}
                for kind,table in (('accessValid',self.access),('refreshValid',self.refresh)):
                    actual[kind]=any(t['run']==run and t['grantRequestId']==request and t['expires']>now for t in table.values())
                records.append(deepcopy(original)|actual)
            return dict(providerVersion=VERSION,instance=self.instance,runId=run,capturedEpochMs=now,
                eventSequence=self.sequence,grantsEnabled=row['grantsEnabled'],requests=records,
                delayedGrantOutstanding=any(r['accessValid'] or r['refreshValid'] for r in records))

    def profile(self,authorization,*,run=None,ticket=None,request=None):
        with self.changed:
            now=self.now();token=None
            if type(authorization) is str and authorization.startswith('Bearer '):token=self.access.get(authorization[7:])
            accepted=token is not None and token['expires']>now and self.runs[token['run']]['active']
            correlated=any(v is not None for v in (run,ticket,request))
            if correlated:
                identifier(run);identifier(ticket);request_id(request)
                row=self.runs[run]
                if not row['active'] or row['ticket']!=ticket or request in row['usedRequests'] or len(row['usedRequests'])>=4096:
                    raise ValueError('Profile request is not owned by this active challenge')
                row['usedRequests'].add(request)
                if accepted and token['run']!=run:accepted=False # A different run's real token is not this principal.
                self._record(run,'profile-request',requestId=request,status=200 if accepted else 401,
                    principal='owned' if accepted else 'anonymous',protectedAccess=bool(accepted))
            if not accepted:return 401,dict(status='fail',error='unauthorized')
            username=self.runs[token['run']]['username']
            return 200,dict(status='success',data=dict(user=dict(username=username)))

    def proof(self,run,ticket,request):
        with self.changed:
            identifier(run);identifier(ticket);request_id(request)
            row=self.runs[run]
            if row['ticket']!=ticket:raise ValueError('Retired account challenge')
            events=[e for e in row['events'] if e['kind']=='profile-request' and e['ticket']==ticket and e['requestId']==request]
            if len(events)!=1:raise ValueError('No independent actual correlated profile request')
            return deepcopy(events[0]) # Original time/status, never a newly stamped grant receipt.

    def snapshot(self,run):
        with self.changed:
            identifier(run)
            if run in self.retired:
                row=dict(active=False,held=None,holdNext=False,inflight=0,grantsEnabled=False)
            else:row=self.runs[run]
            return dict(providerVersion=VERSION,instance=self.instance,runId=run,capturedEpochMs=self.now(),eventSequence=self.sequence,
                accountExists=row['active'],grantsEnabled=row['grantsEnabled'],heldRequests=int(row['held'] is not None),armedHold=row['holdNext'],
                inflightRequests=row['inflight'],
                accessTokens=sum(t['run']==run for t in self.access.values()),
                refreshTokens=sum(t['run']==run for t in self.refresh.values()))

    def retire(self,run):
        with self.changed:
            row=self.snapshot(run)
            if (row['accountExists'] or row['heldRequests'] or row['armedHold'] or row['accessTokens']
                    or row['refreshTokens'] or row['inflightRequests']):
                raise ValueError('Owned account cleanup is incomplete')
            del self.runs[run]
            self.retired.add(run)

    def shutdown(self):
        # No success is reported by teardown. Wake pending handlers even when
        # a bad clock makes a normal observed cleanup unavailable.
        with self.changed:
            self.closed=True;self.access.clear();self.refresh.clear()
            for row in self.runs.values():row.update(active=False,closed=True,holdNext=False,grantsEnabled=False,username=None,password=None)
            self.changed.notify_all()
