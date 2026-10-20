"""Source-reviewed ordinary Phone File-menu logout; no account service setter."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.native_account_origin import origin_text
from adapters.native_feature_observation import NativeFeatureObservation, need
from adapters.normal_ui import Locator, NativeUI, NativeUIError
from feature_journeys.contract import identifier
from overte_phone_script_ui import PhoneScriptUI

VERSION=1


class PhoneAccountMenu:
    def __init__(self,ui,source,intent,run,origin):
        need(isinstance(ui,NativeUI) and isinstance(source,NativeFeatureObservation) and callable(intent))
        identifier(run);origin_text(origin)
        self.ui,self.source,self.intent,self.run=ui,source,intent,run
        self.tablet=PhoneScriptUI(ui,'io.github.noah_be.overte.phone')
        self.endpoints={hashlib.sha256(value.encode()).hexdigest() for value in (origin,origin+'/')}
        self.principal=hashlib.sha256(('e2e-'+run).encode()).hexdigest()

    def _native(self):
        original=self.source.read(self.source.sequence,require_account=True)
        account=original['account'];native=account['observation']
        need(account['loggedIn'] and account['principalSha256']==self.principal
             and native['endpointSha256'] in self.endpoints and native['credentialActive']
             and native['tokenPresent'] and native['tokenValid']
             and not native['loginPending'] and not native['refreshPending'])
        return original

    def _control(self,locator):
        root=self.tablet.tree()
        key='resource-id' if locator.using=='id' else None
        rows=[row for row in root.iter() if row.get('package')==self.tablet.package
            and row.get('displayed','true')=='true' and row.get('enabled','true')=='true'
            and (row.get(key)==locator.value if key else locator.value in (row.get('content-desc'),row.get('text')))]
        # Qt accessibility can map its custom menu rows to different Android
        # view classes. Package, unique actual identity and the SDK's actual
        # displayed/enabled checks bind input without guessing a class name.
        need(len(rows)==1)

    def logout(self):
        """Input delivery plus actual row disappearance; not logout authority proof.

        The complete owner must independently verify native credentials, current
        protected access and peer facts. It must retain issued intent on error.
        """
        try:
            started=self.ui._now()
            def bound():need(self.ui._now()-started<20)
            def click(stage,locator):
                original=self._native();bound()
                self._control(locator);bound()
                self.intent('account-menu-'+stage,deepcopy(original),stage)
                bound();need(self.source.guard() is not False);self.ui.click(locator);bound()
            self._native();bound()
            if not self.tablet.tablet_visible():
                click('open-tablet',self.tablet.resource('tablet.open'))
                self.ui.wait_control(self.tablet.resource('nav.close'));bound()
            if self.ui.available(self.tablet.resource('nav.home')):
                click('home',self.tablet.resource('nav.home'))
            menu=Locator('accessibility id','MENU')
            if not self.ui.available(menu):
                for page in range(1,9):
                    button=self.tablet.resource('tabletPage.'+str(page))
                    if self.ui.available(button):click('page-'+str(page),button)
                    if self.ui.available(menu):break
            click('open-menu',menu)
            file=Locator('accessibility id','File')
            self.ui.wait_control(file);bound();click('file',file)
            # LoginDialog::toggleAction owns this ordinary menu label. It is
            # an input selector for the guarded owned account, not a measured
            # principal or a return value supplied to the observation pipeline.
            logout=Locator('accessibility id','Directory Service: Logout e2e-'+self.run)
            self.ui.wait_control(logout);bound();click('logout',logout)
            self.ui.wait_absent(logout);bound()
            return {'performed':True}
        except Exception:
            raise NativeUIError('Normal owned Phone logout input failed; issued intent must be retained') from None
