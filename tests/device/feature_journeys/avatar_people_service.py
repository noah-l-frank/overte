"""Default-off real two-principal HTTPS relationship service for Avatar/People.

Only actual authenticated reciprocal submissions establish a relationship.
Fixture control owns credentials and the domain. Original authenticated
POST bodies bind the session pair; no requested relationship outcome is accepted. Original completed wire receipts stay private.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import re
import secrets
from urllib.parse import parse_qsl,unquote
from .account_provider import AccountProvider
from .contract import exact,identifier

REQUEST='/api/v1/user/connection_request'
USERS=('/api/v1/users','/api/v1/users/connections')
DELETE='/api/v1/user/connections/'
ROLES=('primary','peer')


def session(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value) or value=='00000000-0000-0000-0000-000000000000':
        raise ValueError('An original non-null session UUID is required')
    return value


def query(value):
    if type(value) is not str or len(value)>2048 or re.search(r'%(?![0-9A-Fa-f]{2})',value):raise ValueError('Invalid social query')
    rows=parse_qsl(value,keep_blank_values=True,strict_parsing=True,max_num_fields=8)
    result={}
    for key,item in rows:
        if key in result or len(item)>256:raise ValueError('Duplicate or oversized social query')
        result[key]=item
    return result


class AvatarPeopleService:
    VERSION=1
    def __init__(self,accounts,domain_id):
        if not isinstance(accounts,AccountProvider):raise ValueError('Social service requires its original account provider')
        self.domain_id=session(domain_id)
        self.accounts=accounts;self.instance=secrets.token_hex(16);self.runs={};self.retired={};self.sequence=0

    def has_run(self,run):return run in self.runs or run in self.retired

    def provision(self,run):
        identifier(run)
        with self.accounts.changed:
            if self.accounts.closed or self.has_run(run) or self.runs or len(self.retired)>=64:
                raise ValueError('One isolated Avatar/People scope is required')
            peer=hashlib.sha256((run+':avatar-peer-v1').encode()).hexdigest()[:32]
            if peer==run or peer in self.accounts.runs or peer in self.accounts.retired:raise ValueError('Peer account identity collision')
            self.accounts.provision(run)
            try:self.accounts.provision(peer)
            except BaseException:
                self.accounts.control(run,'cleanup');self.accounts.retire(run);raise
            self.runs[run]=dict(active=True,ticket=None,accounts=dict(primary=run,peer=peer),binding=None,
                principals={role:self.accounts.runs[auth]['username'] for role,auth in dict(primary=run,peer=peer).items()},relationship=False,pending={},responses=[],inflight=0,failedResponses=0)

    def credentials(self,run,role):
        if role not in ROLES:raise ValueError('Unknown owned social principal')
        with self.accounts.changed:return self.accounts.credentials(self.runs[identifier(run)]['accounts'][role],'owned')

    def activate(self,run,ticket):
        with self.accounts.changed:
            row=self.runs[identifier(run)]
            if not row['active']:raise ValueError('Social scope is retired')
            row['ticket']=identifier(ticket)
            for auth_run in row['accounts'].values():self.accounts.activate(auth_run,ticket)

    def _expire(self,row):
        now=self.accounts.now()
        row['pending']={role:value for role,value in row['pending'].items() if value['expiresEpochMs']>now}

    def _principal(self,authorization):
        if type(authorization) is not str or len(authorization)>512 or not authorization.startswith('Bearer '):return None
        token=self.accounts.access.get(authorization[7:]);now=self.accounts.now()
        if token is None or token['expires']<=now:return None
        for run,row in self.runs.items():
            for role,auth_run in row['accounts'].items():
                account=self.accounts.runs.get(auth_run)
                if token['run']==auth_run and account is not None and account['active']:return run,row,role
        return None

    def _user(self,row,role):
        username=self.accounts.runs[row['accounts'][role]]['username']
        return dict(username=username,connection='connection',images=dict(thumbnail=''),
            location=dict(node_id=row['binding'][role+'Session'],domain=dict(id=self.domain_id,name='Owned domain')))

    def _apply(self,row,role,method,path,parameters,body):
        if row['ticket'] is None:return 409,dict(status='fail',error='scope-unbound')
        self._expire(row);other='peer' if role=='primary' else 'primary'
        if path==REQUEST:
            if method=='POST':
                exact(body,{'user_connection_request'},'social POST');values=body['user_connection_request']
            elif method=='GET':values=parameters
            else:return 405,dict(status='fail',error='method-not-allowed')
            exact(values,{'node_id','proposed_node_id'},'social session pair')
            for value in values.values():session(value)
            if values['node_id']==values['proposed_node_id']:return 403,dict(status='fail',error='self-request')
            if row['binding'] is None and method=='POST':
                row['binding']=dict(domainId=self.domain_id,**{role+'Session':values['node_id'],other+'Session':values['proposed_node_id']})
            if row['binding'] is None:return 409,dict(status='fail',error='session-unbound')
            if values['node_id']!=row['binding'][role+'Session'] or values['proposed_node_id']!=row['binding'][other+'Session']:
                return 403,dict(status='fail',error='foreign-session')
            if method=='POST' and not row['relationship']:
                row['pending'][role]=dict(ticket=row['ticket'],createdEpochMs=self.accounts.now(),expiresEpochMs=self.accounts.now()+12000)
                if other in row['pending'] and row['pending'][other]['ticket']==row['ticket']:
                    row['relationship']=True;row['pending']={}
            if row['relationship']:return 200,dict(status='success',connection=dict(username=self._user(row,other)['username']))
            return 200,dict(status='success',connection='pending')
        if path in USERS and method=='GET':
            if set(parameters)-{'filter','status','per_page','page','search','sort'}:raise ValueError('Unsupported bounded relationship query')
            if 'filter' in parameters and parameters['filter']!='connections':raise ValueError('Unsupported relationship filter')
            if 'status' in parameters and parameters['status'] not in ('online',self.domain_id):raise ValueError('Foreign domain query')
            for key in ('per_page','page'):
                if key in parameters and (not parameters[key].isdigit() or not 1<=int(parameters[key])<=1000):raise ValueError('Invalid relationship page')
            user=self._user(row,other) if row['binding'] is not None else None
            users=[user] if user is not None and row['relationship'] and parameters.get('search',user['username']) in user['username'] and parameters.get('page','1')=='1' else []
            return 200,dict(status='success',data=dict(users=users,total_entries=len(users),total_pages=1,current_page=1))
        if path.startswith(DELETE) and method=='DELETE':
            if parameters or unquote(path[len(DELETE):])!=self._user(row,other)['username']:return 403,dict(status='fail',error='foreign-account')
            row['relationship']=False;row['pending']={}
            return 200,dict(status='success')
        return 405,dict(status='fail',error='method-not-allowed')

    @contextmanager
    def response(self,authorization,method,path,parameters,body):
        row=run=role=None;completed=False
        with self.accounts.changed:
            actual=self._principal(authorization)
            if actual is None:
                yield 401,dict(status='fail',error='unauthorized'),None,None;return
            run,row,role=actual
            if not row['active'] or row['inflight']>=8 or len(row['responses'])+row['inflight']>=512:
                yield 503,dict(status='fail',error='scope-unavailable'),None,None;return
            started=self.accounts.now();ticket=row['ticket'];row['inflight']+=1
            try:status,value=self._apply(row,role,method,path,parameters,body)
            except BaseException:row['inflight']-=1;raise
            response_id=secrets.token_hex(16);raw=json.dumps(value).encode()
        def observed(value):
            nonlocal completed
            exact(value,{'status','responseId','bytes','sha256'},'original social wire response')
            with self.accounts.changed:
                if completed or value!=dict(status=status,responseId=response_id,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()):
                    raise ValueError('Incomplete original social response')
                self.sequence+=1;row['responses'].append(dict(sequence=self.sequence,responseId=response_id,role=role,ticket=ticket,
                    method=method,path=path,startedEpochMs=started,completedEpochMs=self.accounts.now(),**{k:value[k] for k in ('status','bytes','sha256')}))
                completed=True
        try:yield status,raw,response_id,observed
        finally:
            with self.accounts.changed:
                row['inflight']-=1
                if not completed:row['failedResponses']+=1
                self.accounts.changed.notify_all()

    def snapshot(self,run,nonce):
        identifier(run);identifier(nonce)
        with self.accounts.changed:
            row=self.runs.get(run) or self.retired[run];self._expire(row)
            principals=deepcopy(row['principals']) if row['active'] else dict(primary=None,peer=None)
            authority={role:self.accounts.snapshot(auth) for role,auth in row['accounts'].items()}
            return dict(avatarPeopleServiceVersion=1,instance=self.instance,runId=run,requestId=nonce,capturedEpochMs=self.accounts.now(),
                active=row['active'],ticket=row['ticket'],domainId=self.domain_id,binding=deepcopy(row['binding']),principals=principals,accounts=authority,
                relationships={role:[principals['peer' if role=='primary' else 'primary']] if row['relationship'] else [] for role in ROLES},
                pending=deepcopy(row['pending']),inflightResponses=row['inflight'],failedResponses=row['failedResponses'],responses=deepcopy(row['responses']))

    def cleanup_accounts(self,run):
        with self.accounts.changed:
            row=self.runs[identifier(run)]
            if row['relationship'] or row['inflight']:raise ValueError('Original relationship must be removed before authority retirement')
            for auth in row['accounts'].values():self.accounts.control(auth,'cleanup')
            # Revoked principals cannot submit or complete pending requests.
            row['pending']={}

    def retire(self,run):
        with self.accounts.changed:
            row=self.runs[identifier(run)];self._expire(row)
            if row['relationship'] or row['pending'] or row['inflight']:raise ValueError('Social cleanup is unresolved')
            for auth in row['accounts'].values():
                status=self.accounts.snapshot(auth)
                if any(status[k] for k in ('accountExists','accessTokens','refreshTokens','inflightRequests','heldRequests','armedHold')):
                    raise ValueError('Owned authority remains live')
            for auth in row['accounts'].values():self.accounts.retire(auth)
            row.update(active=False,ticket=None);self.retired[run]=self.runs.pop(run)


def validate_status(value,*,run,request,instance,previous=None):
    from .contract import typed_equal,number
    exact(value,{'avatarPeopleServiceVersion','instance','runId','requestId','capturedEpochMs','active','ticket','domainId','binding','principals','accounts','relationships','pending','inflightResponses','failedResponses','responses'},'original social status')
    def integer(v,lo=0,hi=9007199254740991):return type(v) is int and lo<=v<=hi
    if type(value['avatarPeopleServiceVersion']) is not int or value['avatarPeopleServiceVersion']!=1 or value['instance']!=identifier(instance) or value['runId']!=identifier(run) or value['requestId']!=identifier(request) or not integer(value['capturedEpochMs'],1) or type(value['active']) is not bool:
        raise ValueError('Invalid original social source identity')
    session(value['domainId'])
    if value['active']:identifier(value['ticket'])
    elif value['ticket'] is not None:raise ValueError('Retired social source retained its input challenge')
    if value['binding'] is not None:
        exact(value['binding'],{'domainId','primarySession','peerSession'},'social pair')
        for item in value['binding'].values():session(item)
        if value['binding']['domainId']!=value['domainId'] or value['binding']['primarySession']==value['binding']['peerSession']:raise ValueError('Invalid original social pair')
    exact(value['principals'],set(ROLES),'owned principals');exact(value['accounts'],set(ROLES),'owned accounts');exact(value['relationships'],set(ROLES),'relationships')
    for role in ROLES:
        principal=value['principals'][role]
        if value['active'] and (type(principal) is not str or not re.fullmatch('e2e-[0-9a-f]{32}',principal)):raise ValueError('Missing original owned principal')
        if not value['active'] and principal is not None:raise ValueError('Retired principal remains active')
        rows=value['relationships'][role]
        if type(rows) is not list or len(rows)>1 or rows and rows!=[value['principals']['peer' if role=='primary' else 'primary']]:raise ValueError('Foreign relationship original')
        account=value['accounts'][role]
        exact(account,{'providerVersion','instance','runId','capturedEpochMs','eventSequence','accountExists','grantsEnabled','heldRequests','armedHold','inflightRequests','accessTokens','refreshTokens'},'original account authority')
        if type(account['providerVersion']) is not int or account['providerVersion']!=2 or not all(type(account[k]) is bool for k in ('accountExists','grantsEnabled','armedHold')) or not all(integer(account[k]) for k in ('capturedEpochMs','eventSequence','heldRequests','inflightRequests','accessTokens','refreshTokens')):raise ValueError('Invalid original account authority')
        identifier(account['runId']);identifier(account['instance'])
    if bool(value['relationships']['primary'])!=bool(value['relationships']['peer']) or value['principals']['primary'] is not None and value['principals']['primary']==value['principals']['peer']:raise ValueError('Mutual distinct principals are required')
    if type(value['pending']) is not dict or set(value['pending'])-set(ROLES):raise ValueError('Invalid original pending requests')
    for pending in value['pending'].values():
        exact(pending,{'ticket','createdEpochMs','expiresEpochMs'},'pending original');identifier(pending['ticket'])
        if not integer(pending['createdEpochMs'],1,value['capturedEpochMs']) or not integer(pending['expiresEpochMs'],pending['createdEpochMs'],pending['createdEpochMs']+12000):raise ValueError('Invalid original pending clock')
    if not integer(value['inflightResponses'],0,8) or not integer(value['failedResponses']) or type(value['responses']) is not list or len(value['responses'])>512:raise ValueError('Invalid bounded social history')
    sequence=0;seen=set()
    for row in value['responses']:
        exact(row,{'sequence','responseId','role','ticket','method','path','startedEpochMs','completedEpochMs','status','bytes','sha256'},'completed social wire original')
        identifier(row['responseId']);identifier(row['ticket'])
        if not integer(row['sequence'],sequence+1) or row['responseId'] in seen or row['role'] not in ROLES or row['method'] not in ('GET','POST','DELETE') or row['path'] not in (REQUEST,*USERS) and not row['path'].startswith(DELETE) or not integer(row['status'],100,599) or not integer(row['bytes'],1,65536) or not re.fullmatch('[0-9a-f]{64}',row['sha256']) or not integer(row['startedEpochMs'],1,row['completedEpochMs']) or not integer(row['completedEpochMs'],1,value['capturedEpochMs']):raise ValueError('Invalid completed social wire source')
        sequence=row['sequence'];seen.add(row['responseId'])
    if not value['active'] and (value['pending'] or value['inflightResponses'] or any(value['relationships'].values())):raise ValueError('Retired social scope remains live')
    if previous is not None:
        validate_status(previous,run=run,request=previous['requestId'],instance=instance)
        if value['requestId']==previous['requestId'] or value['capturedEpochMs']<previous['capturedEpochMs'] or not typed_equal(value['responses'][:len(previous['responses'])],previous['responses']) or previous['binding'] is not None and not typed_equal(previous['binding'],value['binding']) or not previous['active'] and value['active']:
            raise ValueError('Original social history regressed')
    return value
