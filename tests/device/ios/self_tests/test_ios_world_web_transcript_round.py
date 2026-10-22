"""Pure transcript validation reuse never changes bytes, freshness or ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_source as source
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL


class WorldWebTranscriptRoundTests(unittest.TestCase):
    def test_exact_validated_original_reuse_is_synchronous_and_never_caches_freshness_or_outward_objects(self):
        producer=OriginalSources();value=producer.ledger();query=dict(schemaVersion=1,action=source.ACTION,commandId=value['commandId'],runId=RUN,fixtureUrl=URL)
        original=source.detail
        with patch.object(source,'detail',wraps=original) as checked:
            with source.validation_round():
                returned=source.validate(value,query,42,epoch=value['clockAfter']['epochMs']);count=checked.call_count
                self.assertGreater(count,0)
                self.assertIs(returned,value)
                equal=deepcopy(value);self.assertIs(source.validate(equal,query,42),equal);self.assertEqual(count,checked.call_count)
                with self.assertRaises(NativeUIError):source.validate(value,query,42,epoch=value['clockAfter']['epochMs']+1600)
                with source.validation_round():source.validate(value,query,42)
                self.assertEqual(count,checked.call_count)
            source.validate(value,query,42);self.assertGreater(checked.call_count,count)
    def test_warm_proofs_cannot_accept_changed_original_pid_query_or_predecessor(self):
        producer=OriginalSources();old=producer.ledger();value=producer.ledger()
        query=dict(schemaVersion=1,action=source.ACTION,commandId=value['commandId'],runId=RUN,fixtureUrl=URL)
        with source.validation_round():
            source.validate(value,query,42,previous=old)
            for fault in ('clock','detail','pid','query','predecessor'):
                changed=deepcopy(value);prior=deepcopy(old);request=deepcopy(query);pid=42
                if fault=='clock':changed['clockAfter']['epochMs']=0
                elif fault=='detail':changed['events'][0]['detail']['expected']=True
                elif fault=='pid':pid=43
                elif fault=='query':request['runId']='f'*32
                else:prior['events'][0]['eventId']='f'*32
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                    source.validate(changed,request,pid,previous=prior)
            # Mutation through the actual object returned by validate changes
            # its byte key; the earlier positive proof cannot validate it.
            returned=source.validate(value,query,42,previous=old);returned['events'][0]['detail']['expected']=True
            with self.assertRaises(NativeUIError):source.validate(value,query,42,previous=old)


if __name__=='__main__':unittest.main()
