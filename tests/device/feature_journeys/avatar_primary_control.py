"""Run/primary/purpose-bound Avatar input-control handoff on existing HTTPS.

This authority admits only existing session inputs and provider revocation.
Neither its grant, transport return nor checkpoint receipt is a product fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hmac
import secrets
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import exact,identifier,json_document
from feature_journeys.witness import Client
from feature_journeys.avatar_accounts import session_binding

VERSION=1
PURPOSES=['bind-sessions','revoke-authority']


def check(value):
    if not value:raise ValueError('Original Avatar primary control handoff is unavailable')


def grant(value,run,request):
    exact(value,{'avatarPrimaryControlGrantVersion','runId','role','purposes','requestId','token'},'Avatar primary control grant')
    check(type(value['avatarPrimaryControlGrantVersion']) is int and value['avatarPrimaryControlGrantVersion']==VERSION
        and value['runId']==identifier(run) and value['role']=='primary' and value['purposes']==PURPOSES
        and value['requestId']==identifier(request) and type(value['token']) is str and len(value['token'])==64)
    check(all(char in '0123456789abcdef' for char in value['token']));return value


def issuer(value,run,url):
    exact(value,{'avatarPrimaryControlIssuerVersion','runId','role','purposes','requestId','fixtureUrl','phase','grant'},'Avatar control issuer')
    check(type(value['avatarPrimaryControlIssuerVersion']) is int and value['avatarPrimaryControlIssuerVersion']==VERSION
        and value['runId']==identifier(run) and value['role']=='primary' and value['purposes']==PURPOSES
        and value['fixtureUrl']==url and type(url) is str and url.startswith('https://') and value['phase'] in ('issued','saved'))
    identifier(value['requestId'])
    if value['phase']=='issued':check(value['grant'] is None)
    else:grant(value['grant'],run,value['requestId'])
    return value


def prepare(client,store,run):
    """Runner-only durable original request; known-request GET, never resend."""
    check(type(client) is Client and isinstance(store,PrivateFeatureState))
    run=identifier(run);check(store.path.name=='avatar-primary-control-'+run+'.json' and store.path.is_absolute())
    with ScriptSourceLock(store.path.with_suffix('.lock')).held():return _prepare(client,store,run)


def _prepare(client,store,run):
    check(type(client) is Client and isinstance(store,PrivateFeatureState))
    run=identifier(run);check(store.path.name=='avatar-primary-control-'+run+'.json' and store.path.is_absolute())
    old=store.read();born=old is None
    if born:
        old=dict(avatarPrimaryControlIssuerVersion=VERSION,runId=run,role='primary',purposes=deepcopy(PURPOSES),
            requestId=secrets.token_hex(16),fixtureUrl=client.url,phase='issued',grant=None)
        issuer(old,run,client.url);store.write(old,None);check(store.read()==old)
    issuer(old,run,client.url)
    if old['phase']=='saved':return deepcopy(old)
    prefix='/runs/'+run+'/avatar/control-handoff'
    if born:
        request=dict(avatarPrimaryControlRequestVersion=VERSION,runId=run,role='primary',purposes=deepcopy(PURPOSES),requestId=old['requestId'])
        current=client.request(prefix,request,method='POST')
    else:
        # A missing response is NOT permission to create another authority.
        current=client.request(prefix+'/'+old['requestId'])
    grant(current,run,old['requestId']);check(store.read()==old)
    saved=dict(old,phase='saved',grant=deepcopy(current));store.write(saved,old);check(store.read()==saved);return deepcopy(saved)


def intercept(handler,parts,*,reader,actor,adapter_reader):
    if len(parts)<4 or parts[0]!='runs' or parts[2]!='avatar':return False
    route=parts[3:]
    recognized=(route==['control-handoff'] or len(route)==2 and route[0]=='control-handoff'
        or route in (['sessions'],['control']) or len(route)==3 and route[0]=='control-admission')
    if not recognized or route in (['sessions'],['control']) and reader:return False
    body=None
    if handler.command=='POST':
        size=int(handler.headers.get('Content-Length','0'));check(0<size<=16384)
        body=json_document(handler.rfile.read(size))
    return handle(handler,parts,body,reader=reader,actor=actor,adapter_reader=adapter_reader)


def handle(handler,parts,body,*,reader,actor,adapter_reader):
    """Called before the generic auth rejection, ONLY for exact owned routes."""
    if len(parts)<4 or parts[0]!='runs' or parts[2]!='avatar':return False
    route=parts[3:]
    recognized=(route==['control-handoff'] or len(route)==2 and route[0]=='control-handoff'
        or route in (['sessions'],['control']) or len(route)==3 and route[0]=='control-admission')
    if not recognized:return False
    if route in (['sessions'],['control']) and reader:return False # Exact legacy Reader path remains its old owner.
    server=handler.server;run=identifier(parts[1])
    with server.journal.lock:
        if server.avatar_accounts is None or run not in server.journal.runs or server.journal.runs[run]['area']!='avatar-people':
            handler.send(404,{'error':'not-found'});return True
        if route==['control-handoff'] and handler.command=='POST':
            if not reader:handler.send(403,{'error':'forbidden'});return True
            exact(body,{'avatarPrimaryControlRequestVersion','runId','role','purposes','requestId'},'Avatar control request')
            check(type(body['avatarPrimaryControlRequestVersion']) is int and body['avatarPrimaryControlRequestVersion']==VERSION
                and body['runId']==run and body['role']=='primary' and body['purposes']==PURPOSES)
            request=identifier(body['requestId']);grants=server.avatar_control_handoffs
            # Retired grants cannot authorize a new run or consume unbounded space.
            for old_run in tuple(grants):
                if old_run not in server.journal.runs:del grants[old_run]
            if run in grants:check(grants[run]['grant']['requestId']==request)
            else:
                check(len(grants)<64);value=dict(avatarPrimaryControlGrantVersion=VERSION,runId=run,role='primary',
                    purposes=deepcopy(PURPOSES),requestId=request,token=secrets.token_hex(32))
                grants[run]=dict(grant=value,used=[])
            handler.send(200,deepcopy(grants[run]['grant']));return True
        if len(route)==2 and route[0]=='control-handoff' and handler.command=='GET':
            if not reader:handler.send(403,{'error':'forbidden'});return True
            request=identifier(route[1]);row=server.avatar_control_handoffs.get(run)
            if row is None or row['grant']['requestId']!=request:handler.send(404,{'error':'not-found'});return True
            handler.send(200,deepcopy(row['grant']));return True
        if len(route)==3 and route[0]=='control-admission' and handler.command=='GET':
            request=identifier(route[1]);nonce=identifier(route[2]);row=server.avatar_control_handoffs.get(run)
            authorization=handler.headers.get('Authorization','')
            if row is None or row['grant']['requestId']!=request or not hmac.compare_digest(authorization,'Bearer '+row['grant']['token']):
                handler.send(403,{'error':'forbidden'});return True
            handler.send(200,dict(avatarPrimaryControlAdmissionVersion=VERSION,runId=run,role='primary',purposes=deepcopy(PURPOSES),
                requestId=request,nonce=nonce,usedPurposes=deepcopy(row['used'])))
            return True
        if route not in (['sessions'],['control']) or handler.command!='POST':
            handler.send(403,{'error':'forbidden'});return True
        authorization=handler.headers.get('Authorization','');row=server.avatar_control_handoffs.get(run)
        if row is None or not hmac.compare_digest(authorization,'Bearer '+row['grant']['token']):
            handler.send(403,{'error':'forbidden'});return True
        purpose='bind-sessions' if route==['sessions'] else 'revoke-authority'
        if route==['sessions']:
            exact(body,{'sessions','domain'},'Avatar session control');session_binding(dict(avatarSessionBindingVersion=1,**body))
        else:
            exact(body,{'operation'},'Avatar authority control');check(body['operation']=='revoke')
        check(purpose not in row['used'])
        # Responsibility is consumed BEFORE provider execution. An uncertain
        # effect is reconciled through existing read-only status, not reissued.
        row['used'].append(purpose)
        if purpose=='bind-sessions':server.avatar_accounts.bind_sessions(run,body['sessions'],body['domain'])
        else:server.avatar_accounts.revoke(run)
        handler.send(200,{});return True
