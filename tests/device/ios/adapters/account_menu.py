"""Normal iOS tablet File/logout controls, bound to original QAction delegates."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,need
from adapters.native_account_origin import origin_text
from adapters.normal_ui import Locator,NativeUIError
from feature_journeys.contract import identifier

VERSION=1
IDS=frozenset({'account.menu-file','account.logout'})
FIELDS={'menuSourceVersion','sourceType','labelSha256'}


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS)
    need(FIELDS<=set(row) and type(row['menuSourceVersion']) is int and row['menuSourceVersion']==VERSION
         and type(row['sourceType']) is int and row['sourceType']==(2 if row['id']=='account.menu-file' else 1)
         and type(row['labelSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['labelSha256']))


class IOSAccountMenu:
    def __init__(self,io,native,intent,run,origin):
        identifier(run);origin_text(origin);need(callable(intent))
        self.io,self.native,self.intent,self.run=io,native,intent,run
        self.bound=None
        self.endpoints={hashlib.sha256(value.encode()).hexdigest() for value in (origin,origin+'/')}
        self.principal=hashlib.sha256(('e2e-'+run).encode()).hexdigest()

    def _native(self):
        packet=self.native.read(self.native.sequence,require_account=True)
        account=packet['account'];observed=account['observation']
        need(account['loggedIn'] and account['principalSha256']==self.principal
             and observed['endpointSha256'] in self.endpoints and observed['credentialActive']
             and observed['tokenPresent'] and observed['tokenValid']
             and not observed['loginPending'] and not observed['refreshPending'])
        return packet

    def _click(self,identifier,stage,*,label=None):
        need(callable(self.bound));self.bound()
        packet=self._native();value=self.io.capture();self.bound()
        need(value.get('accountMenuControlsVersion')==VERSION)
        rows=[row for row in value['controls'] if row['id']==identifier and row['enabled']]
        need(len(rows)==1);row=rows[0]
        if identifier in IDS:
            metadata(row);need(label is not None and row['labelSha256']==hashlib.sha256(label.encode()).hexdigest())
        self.intent('account-menu-'+stage,deepcopy(packet),stage)
        need(self.native.guard() is not False)
        self.io.ui.click_with_token(Locator('accessibility id','OverteNavigation.'+identifier),row['token']);self.bound()

    def logout(self):
        try:
            started=self.io.ui._now()
            def bound():need(self.io.ui._now()-started<20)
            self.bound=bound
            self._native();bound()
            if not self.io.capture()['tabletShown']:
                packet=self._native();self.intent('account-menu-open-tablet',packet,'open-tablet')
                self.io.ui.click(Locator('accessibility id','OverteTabletOpen'))
            value=self.io.capture()
            if any(row['id']=='tablet.home' for row in value['controls']):self._click('tablet.home','home')
            for page in [None,*range(1,33)]:
                bound()
                if page is not None:
                    identifier='tablet.page.'+str(page)
                    if any(row['id']==identifier for row in self.io.capture()['controls']):self._click(identifier,'page-'+str(page))
                if any(row['id']=='scripts.menu' for row in self.io.capture()['controls']):break
            self._click('scripts.menu','open-menu')
            self.io.ui.wait_control(Locator('accessibility id','OverteNavigation.account.menu-file'))
            self._click('account.menu-file','file',label='File')
            logout=Locator('accessibility id','OverteNavigation.account.logout')
            self.io.ui.wait_control(logout)
            self._click('account.logout','logout',label='Directory Service: Logout e2e-'+self.run)
            self.io.ui.wait_absent(logout)
            return {'performed':True} # Input only; protected access is independently observed.
        except Exception:raise NativeUIError('Normal owned iOS logout input failed; original intent is retained') from None
