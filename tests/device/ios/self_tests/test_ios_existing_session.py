"""Lost existing-session counterexamples; the WebDriver boundary is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters import appium_adapter as backend
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSExistingSessionTests(unittest.TestCase):
    def source(self,*,lost=False):
        target=dict(serverUrl='http://sdk.invalid:4723',platform='ios')
        fingerprint=hashlib.sha256(json.dumps(target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        state=dict(sessionId='owned-session',generation=1,targetFingerprint=fingerprint,physicalTargetAttested=True)
        calls=[]
        class Client:
            def call(self,method,path,*_):
                calls.append((method,path))
                if lost:raise RuntimeError('synthetic lost session')
                return {}
        fake=SimpleNamespace(platform='ios',_session_recreation_forbidden=True,target=lambda _:deepcopy(target),
            read_session=lambda _:deepcopy(state),state_path=lambda _:self.fail('must not unlink ownership'),
            attest_physical_target=lambda *_:self.fail('unexpected attestation input'),
            save_session=lambda *_:self.fail('must not rewrite ownership'),
            validate_ios_artifact_receipt=lambda *_a,**_kw:self.fail('must not install'),
            create_appium_session=lambda *_:self.fail('must not create session'))
        return fake,Client(),state,calls

    def test_healthy_existing_channel_keeps_original_session_and_generation(self):
        fake,client,state,calls=self.source()
        with patch.object(backend,'WebDriver',return_value=client):
            actual=backend.AppiumAdapter.ensure_session(fake,'owned')
        self.assertEqual((client,'owned-session',state),actual)
        self.assertEqual([('GET','/session/owned-session')],calls)

    def test_lost_channel_cannot_delete_create_install_or_rewrite_owner(self):
        fake,client,_state,calls=self.source(lost=True)
        with patch.object(backend,'WebDriver',return_value=client),self.assertRaises((RuntimeError,ValueError)):
            backend.AppiumAdapter.ensure_session(fake,'owned')
        self.assertEqual([('GET','/session/owned-session')],calls)

    def test_changed_target_or_missing_session_fail_before_any_sdk_call(self):
        for state in (None,dict(sessionId='owned-session',generation=1,targetFingerprint='f'*64)):
            fake,client,_old,calls=self.source();fake.read_session=lambda _:deepcopy(state)
            with patch.object(backend,'WebDriver',return_value=client),self.assertRaises((RuntimeError,ValueError)):
                backend.AppiumAdapter.ensure_session(fake,'owned')
            self.assertEqual([],calls)

    def test_component_adapter_cannot_construct_candidate_qualified_runtime(self):
        with self.assertRaises(RuntimeError):IOSScriptRuntime(SimpleNamespace())


if __name__=='__main__':unittest.main()
