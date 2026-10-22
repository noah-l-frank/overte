"""Two real owned OAuth account scopes for Avatar/People fixture preparation.

Credentials are input material. This authority owner neither performs client
login nor supplies peer consent, native state, pixels or a feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
import threading

from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import AccountAuthenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider, session
from feature_journeys.contract import identifier

VERSION=1
ROLES=('primary','actor')


class AvatarAccountScopes:
    def __init__(self,accounts,social):
        if (not isinstance(accounts,AccountProvider) or not isinstance(social,AvatarSocialProvider)
                or type(social.authenticate) is not AccountAuthenticator or social.authenticate.provider is not accounts):
            raise ValueError('Avatar accounts require the actual original social OAuth authority')
        self.accounts,self.social=accounts,social;self.instance=secrets.token_hex(16)
        self.lock=threading.RLock();self.runs={};self.retired=set()

    def provision(self,run):
        identifier(run)
        with self.lock:
            if run in self.runs or run in self.retired or len(self.runs)>=16 or len(self.retired)>=256:
                raise ValueError('Avatar account scope already exists or provider is full')
            row=dict(ticket=None,phase='allocating',children={},created=[],retired=[],socialPrepared=False,
                     socialRevoked=False,socialRetired=False,sessions=None,domain=None)
            self.runs[run]=row
            try:
                for role in ROLES:
                    # Collision does not adopt another account. A provider request
                    # racing allocation still fails its original atomic provision.
                    for _ in range(16):
                        child=secrets.token_hex(16)
                        if child==run or child in row['children'].values():continue
                        try:self.accounts.snapshot(child)
                        except KeyError:break
                    else:raise ValueError('Independent account allocation entropy is unavailable')
                    row['children'][role]=child
                    self.accounts.provision(child);row['created'].append(role)
            except Exception:
                # No credential has been exposed: roll back only accounts whose
                # actual provision returned. Any failed rollback remains owned.
                self.revoke(run);self.retire(run)
                raise
            row['phase']='allocated'

    def activate(self,run,ticket):
        identifier(run);identifier(ticket)
        with self.lock:
            row=self.runs[run]
            if row['phase'] not in ('allocated','ready'):raise ValueError('Avatar account scope is not active')
            for role in row['created']:self.accounts.activate(row['children'][role],ticket)
            if row['socialPrepared']:self.social.activate(run,ticket)
            row['ticket']=ticket

    def credentials(self,run,role):
        identifier(run)
        with self.lock:
            row=self.runs[run]
            if role not in ROLES or row['phase'] not in ('allocated','ready') or row['ticket'] is None:
                raise ValueError('Owned Avatar account credentials are unavailable')
            return self.accounts.credentials(row['children'][role],'owned')

    def bind_sessions(self,run,sessions,domain):
        """Bind controlled session inputs; never treat these inputs as peer facts."""
        identifier(run);session(domain)
        if type(sessions) is not dict or set(sessions)!=set(ROLES) or len(set(sessions.values()))!=2:
            raise ValueError('Two independent owned avatar sessions are required')
        for value in sessions.values():session(value)
        with self.lock:
            row=self.runs[run]
            if row['phase']!='allocated' or row['socialPrepared'] or row['ticket'] is None:
                raise ValueError('Original Avatar session scope cannot be replaced')
            principals={role:self.accounts.credentials(row['children'][role],'owned')['username'] for role in ROLES}
            self.social.provision(run,principals,sessions,domain);row.update(socialPrepared=True,sessions=deepcopy(sessions),domain=domain)
            self.social.activate(run,row['ticket']);row['phase']='ready'

    def profile_proof(self,run,role,ticket,nonce):
        identifier(run);identifier(ticket);identifier(nonce)
        with self.lock:
            row=self.runs[run]
            if role not in ROLES or row['ticket']!=ticket:raise ValueError('Avatar account proof scope is unavailable')
            return self.accounts.proof(row['children'][role],ticket,nonce)

    def snapshot(self,run):
        identifier(run)
        with self.lock:
            row=self.runs[run]
            return dict(avatarAccountsVersion=VERSION,instance=self.instance,runId=run,ticket=row['ticket'],phase=row['phase'],
                providerInstance=self.accounts.instance,socialInstance=self.social.instance,
                accounts={role:self.accounts.snapshot(row['children'][role]) for role in row['created']},
                social=self.social.snapshot(run) if row['socialPrepared'] and not row['socialRetired'] else None)

    def revoke(self,run):
        identifier(run)
        with self.lock:
            row=self.runs[run]
            # Original pending relationships/requests/unwritten responses must
            # be removed normally before any of their login authority is lost.
            if row['socialPrepared'] and not row['socialRevoked']:
                self.social.revoke(run);row['socialRevoked']=True
            row['phase']='revoking'
            for role in row['created']:self.accounts.control(row['children'][role],'cleanup')
            return self.snapshot(run)

    def retire(self,run):
        identifier(run)
        with self.lock:
            row=self.runs[run]
            if row['phase']!='revoking':raise ValueError('Avatar authority has not been revoked')
            for role in row['created']:
                if role not in row['retired']:
                    self.accounts.retire(row['children'][role]);row['retired'].append(role)
            if row['socialPrepared'] and not row['socialRetired']:
                self.social.retire(run);row['socialRetired']=True
            del self.runs[run];self.retired.add(run)
