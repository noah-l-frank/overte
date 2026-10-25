"""Actual accept/remove recipe with private modeled-producer diagnostics.

The producer returns exactly the same raw bytes and every validator still
runs. Diagnostics retain a rejected HTTP source before the generic transport
error discards its Python traceback. They never supply a feature fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import traceback
import unittest
from feature_journeys.contract import VERSION
from ios.self_tests import test_ios_avatar_active_composed as active
from ios.self_tests.avatar_strong_domain import StrongDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from self_tests import test_account_provider as tls


class DiagnosticDomain(StrongDomain):
    def __init__(self,test):
        super().__init__(test)
        temporary=tempfile.TemporaryDirectory(prefix='avatar-http-diagnostic-');test.addCleanup(temporary.cleanup)
        self.diagnostic=Path(temporary.name);self.diagnostic.chmod(0o700);self.raw_count=0
        for role,scene in self.scenes.items():
            factory=scene.f.reader
            def reader(name,kind,role=role,factory=factory):
                result=factory(name,kind)
                if name!='http':return result
                original,validate=result.original,result._validate
                def raw():
                    value=original();self.raw_count+=1
                    path=self.diagnostic/(role+'-'+str(self.raw_count)+'.json')
                    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
                    with os.fdopen(descriptor,'wb') as stream:stream.write(value.encode('utf-8'))
                    return value
                def checked(*args,**kwargs):
                    try:return validate(*args,**kwargs)
                    except Exception:
                        path=self.diagnostic/(role+'-'+str(self.raw_count)+'-validation.txt')
                        descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
                        with os.fdopen(descriptor,'w') as stream:stream.write(traceback.format_exc())
                        raise
                result.original,result._validate=raw,checked;return result
            scene.f.reader=reader


class AvatarRemoveComposedTests(unittest.TestCase):
    domain_type=DiagnosticDomain
    prepare=active.AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def test_actual_accept_then_remove_keeps_original_http_history_valid(self):
        d=self.prepare();p,a=d.owners['primary'],d.owners['actor'];base=dict(contractVersion=VERSION,runId=RUN)
        print('PRIVATE_HTTP_DIAGNOSTICS '+str(d.diagnostic),flush=True)
        for owner in (p,a):owner.observe(dict(base,afterSequence=0))
        for number,verb in enumerate(('connection-request','peer-accept','connection-remove'),1):
            print('Actual social recipe '+verb,flush=True);ticket=f'{number:032x}'
            inputs=dict(peer='owned-peer') if verb!='peer-accept' else {};d.client.activate(ticket,verb,inputs)
            if verb=='peer-accept':a.consent(a.phase.read())
            self.assertEqual(dict(performed=True),p.act(dict(base,ticket=ticket,fixtureUrl=p.phase.fixture_url,verb=verb,inputs=inputs)))
        self.assertFalse(d.social.snapshot(RUN)['connected'])
        for owner in (p,a):
            public=owner.observe(dict(base,afterSequence=0));self.assertEqual('none',public['state']['connection'])


if __name__=='__main__':unittest.main()
