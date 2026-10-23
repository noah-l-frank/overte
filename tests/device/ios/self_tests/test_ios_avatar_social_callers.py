"""Real provider bytes plus native2 indexed module selection, no legacy chain."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.avatar_social_provider import CONNECTIONS
from ios.adapters import avatar_social,avatar_code
from ios.self_tests import avatar_callers2_fixture as current
from self_tests import test_avatar_social_provider as provider_tests


class AvatarSocialCallersTests(unittest.TestCase):
    def produce(self):
        self.logic=provider_tests.SocialTests();self.logic.setUp();query='page=1&per_page=1000&sort=username%2CASC'
        with self.logic.provider.response('GET',CONNECTIONS,query,b'',self.logic.tokens['primary']) as response:
            status,raw,response_id,written=response
            written(dict(status=status,responseId=response_id,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        packet=current.http2(raw=raw,response_id=response_id,run=provider_tests.RUN,request_path=CONNECTIONS+'?'+query,
            caller_suffix='/system/request-service.js')
        source=current.scripts2(run=provider_tests.RUN,capture_offset=200)
        return dict(frame=dict(originals=dict(http=packet,scripts=source)))
    def consumed(self,row):
        return avatar_social.consumed(row,self.logic.provider.snapshot(provider_tests.RUN),role='primary',
            provider_instance=self.logic.provider.instance,owned_origin='https://owned.invalid',run=provider_tests.RUN,ticket=provider_tests.TICKET,
            barrier=dict(nativeEpochMs=current.EPOCH-100,providerEpochMs=current.EPOCH,httpEvent=0),expected_code=avatar_code.pins())
    def test_current2_selects_original_indexed_request_service_without_fabricating_a_legacy_chain(self):
        row=self.produce();before=deepcopy(row);receipts=self.consumed(row)
        self.assertEqual(1,len(receipts));self.assertEqual(row,before)
        self.assertNotIn('callerChain',receipts[0]['original']['nativeCreated']['details'])
        self.assertEqual('success',receipts[0]['response']['status'])
    def test_wrong_original_owner_module_cannot_substitute_a_matching_provider_response(self):
        row=self.produce();packet=row['frame']['originals']['http'];entry=packet['callerStacks'][0]
        actual,modules,_=current.original(('/modules/request.js','/system/pal.js'))
        entry.update(callerStack=actual,callerModules=modules)
        with self.assertRaises(NativeUIError):self.consumed(row)


if __name__=='__main__':unittest.main()
