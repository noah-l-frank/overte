"""Normal VR File-menu logout, with original native/UI input provenance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re

from adapters.native_account_origin import origin_text
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier

VERSION=1


class PicoAccountMenu:
    def __init__(self,ui,source,intent,run,origin,home):
        identifier(run);origin_text(origin);need(callable(intent))
        self.ui,self.source,self.intent,self.run=ui,source,intent,run;self.home=home
        self.endpoints={hashlib.sha256(text.encode()).hexdigest() for text in (origin,origin+'/')}
        self.principal=hashlib.sha256(('e2e-'+run).encode()).hexdigest()

    def native(self):
        value=self.source.read(self.source.sequence,require_account=True)
        account=value['account'];observed=account['observation']
        need(account['loggedIn'] and account['principalSha256']==self.principal
             and observed['credentialActive'] and observed['tokenPresent'] and observed['tokenValid']
             and not observed['loginPending'] and not observed['refreshPending']
             and observed['endpointSha256'] in self.endpoints)
        return value

    def logout(self):
        try:
            started=self.ui.now()
            def bound():need(self.ui.now()-started<20)
            def record(stage,identifier,value):
                original=self.native();bound()
                self.intent('account-menu-'+stage,dict(menuInputVersion=1,native=deepcopy(original),ui=deepcopy(value)),identifier)
                bound();need(self.source.guard() is not False)
            def click(stage,identifier):
                value=self.ui.capture();row=self.ui.control(value,identifier);need(row is not None)
                if identifier.startswith('account-menu.'):
                    need(row['inputReady'] and row['principalSha256']==self.principal and row['endpointSha256'] in self.endpoints)
                record(stage,identifier,value)
                self.ui.io.navigation.input(identifier,token=row['token']);bound()
            value=self.ui.capture()
            if not value['open']:
                record('open-tablet','tablet.open',value);self.ui.open_tablet();bound()
            self.home.ensure(self.intent);bound()
            value=self.ui.capture()
            pages=sorted((row['id'] for row in value['controls'] if re.fullmatch(r'tablet\.page\.(?:[1-9]|[12][0-9]|3[0-2])',row['id'])),
                key=lambda name:int(name.rsplit('.',1)[1]))
            for page in [None,*pages]:
                if page is not None:click('page-'+page.rsplit('.',1)[1],page)
                if self.ui.available('scripts.menu'):break
            click('open-menu','scripts.menu')
            self.ui.wait(lambda value:(self.ui.control(value,'account-menu.file') or {}).get('inputReady') is True);bound()
            click('file','account-menu.file')
            self.ui.wait(lambda value:(self.ui.control(value,'account-menu.logout') or {}).get('inputReady') is True);bound()
            click('logout','account-menu.logout')
            self.ui.wait(lambda value:self.ui.control(value,'account-menu.logout'),absent=True);bound()
            return {'performed':True} # UI disappearance only; the full owner proves revoked authority.
        except Exception:
            raise NativeUIError('Normal owned Pico logout failed; original intent is retained') from None
