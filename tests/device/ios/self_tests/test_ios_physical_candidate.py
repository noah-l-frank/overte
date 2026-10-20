"""Physical consumer logic with original runtime/identity/terminal validators.

IPA/Mach-O/receipts are synthetic format fixtures, never builds or acceptance.
Immutable release packaging and official SBOM-format validation are injected
test boundaries; production still requires the original pinned releases/tools.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'ios/tools/candidate'))
sys.path.insert(0,str(ROOT/'provenance'))
sys.path.insert(0,str(ROOT/'tests/device/schema'))
import artifact_identity as identity
import verify_physical_e2e_handoff as consumer
from adapters.ios import binding


def load(path,key):
    spec=importlib.util.spec_from_file_location(key,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


class PhysicalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.repo=self.root/'source';self.repo.mkdir()
        subprocess.run(['git','init','-q','-b','test/main/physical-candidate-fixture',str(self.repo)],check=True,capture_output=True,timeout=5)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
            'commit','-q','--allow-empty','-m','Synthetic source fixture'],check=True,capture_output=True,timeout=5)
        self.sha=subprocess.check_output(['git','-C',str(self.repo),'rev-parse','HEAD'],text=True,timeout=5).strip()
        runtime_fixture=load(ROOT/'ios/tests/runtime-candidate-verifier-test.py','physical_runtime_fixture')
        runtime_fixture.REVISION=self.sha
        self.runtime_fixture=runtime_fixture
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir()
        self.metadata,self.digest=runtime_fixture.write_candidate(self.artifacts,'ipad',info_updates={
            'OverteE2ETestBuildContractVersion':1,'UIFileSharingEnabled':True})
        terminal_fixture=load(ROOT/'tests/device/schema/test_terminal_evidence.py','physical_terminal_fixture')
        terminal_fixture.SOURCE=self.sha
        terminal_fixture.ARTIFACT=self.digest
        self.terminal=terminal_fixture.ContractTests();self.terminal.setUp();self.addCleanup(self.terminal.doCleanups)
        self.inputs={key:'c'*64 for key in identity.INPUT_KEYS}
        normalized=identity.normalized_inputs(self.inputs)
        self.terminal.manifest['normalizedInputsSha256']=normalized
        for row in self.terminal.receipts.values():
            if row['provenance']:row['provenance']['normalizedInputsSha256']=normalized
        self.terminal.publish()
        self.files={key:self.root/(key+'.json') for key in identity.EVIDENCE_KEYS}
        for key,path in self.files.items():path.write_text(json.dumps({'syntheticFormatBoundary':key}))
        self.record=dict(contract='overte-sh009-identity-v1',sourceRevision=self.sha,product='ios',versionCode=2,
            channel='source-proof',artifactSha256=self.digest,inputs=self.inputs,normalizedInputsSha256=normalized,
            evidence={key:identity.digest_file(path) for key,path in self.files.items()},
            signature=dict(state='not-applicable-source-proof',receiptSha256=None),upgrade=dict(state='pending',receiptSha256=None))
        self.record_path=self.root/'identity.json';self.record_path.write_text(json.dumps(self.record))
        self.input_path=self.root/'inputs.json';self.input_path.write_text(json.dumps(self.inputs))
        self.args=argparse.Namespace(artifact_root=self.artifacts,repository=self.repo,expected_source_sha=self.sha,
            expected_artifact_sha256=self.digest,identity_record=self.record_path,expected_inputs=self.input_path,
            identity_contract_root=self.root/'identity-release',shared_contract_root=self.root/'terminal-release',
            sbom_contract_root=self.root/'sbom-release',minimum_version=1,expected_channel='source-proof',
            terminal_candidate_metadata=self.terminal.candidate,**self.files)
        # The exact published identity source bytes are used, not an alternate
        # implementation or a copied/relaxed identity schema.
        self.assertEqual(consumer.shared.IDENTITY_SOURCE,hashlib.sha256((ROOT/'provenance/artifact_identity.py').read_bytes()).hexdigest())
        self.sbom_calls=[];self.bad_sbom=False
        def pair(*values):
            self.sbom_calls.append(values)
            for key in ('spdx','cyclonedx'):
                if identity.digest_file(self.files[key])!=values[-1][key]:raise ValueError('replaced original SBOM bytes')
            return dict(status='SBOM_PAIR_VALID_CONTENT_VERIFICATION_PENDING',
                sourceRevision='f'*40 if self.bad_sbom else self.sha,artifactSha256=self.digest)
        for boundary in (patch.object(consumer.shared,'identity_contract',return_value=identity),
            patch.object(consumer.shared,'pinned_adapter',return_value=ROOT/'ios/ci/evidence/verify-shared-evidence.py'),
            patch.object(consumer,'verify_pair',side_effect=pair)):
            boundary.start();self.addCleanup(boundary.stop)

    def test_original_physical_runtime_identity_and_all_terminal_tiers_compose(self):
        value=consumer.verify(self.args)
        self.assertEqual('IOS_PHYSICAL_CANDIDATE_BYTES_BOUND_VERIFICATION_PENDING',value['status'])
        self.assertEqual('BOUND',value['sharedEvidence']);self.assertEqual('iphoneos',value['runtime']['platform'])
        self.assertEqual(self.digest,value['artifactIdentity']['artifactSha256'])
        self.assertEqual('NOT_EXECUTED',value['physicalDevice']);self.assertEqual('NOT_EXECUTED',value['simulator'])
        self.assertEqual(1,len(self.sbom_calls));self.assertEqual(self.digest,self.sbom_calls[0][5])
        self.assertNotEqual(self.digest,value['bundleIdentity']['bundleSha256'])

    def test_original_terminal_cli_rejects_skipped_cold_tier_and_foreign_input_cohort(self):
        self.terminal.receipts['cold-full-client-build']['skipped']=1;self.terminal.publish()
        with self.assertRaises(ValueError):consumer.verify(self.args)
        self.terminal.receipts['cold-full-client-build']['skipped']=0
        self.terminal.manifest['normalizedInputsSha256']='f'*64
        for row in self.terminal.receipts.values():
            if row['provenance']:row['provenance']['normalizedInputsSha256']='f'*64
        self.terminal.publish()
        with self.assertRaises(ValueError):consumer.verify(self.args)
        self.assertFalse(self.sbom_calls)

    def test_missing_tier_receipt_or_terminal_metadata_never_becomes_reader_source_only_success(self):
        self.terminal.sidecar.unlink()
        with self.assertRaises(ValueError):consumer.verify(self.args)
        self.assertFalse(self.sbom_calls)

    def test_actual_provenance_rejects_changed_source_inputs_evidence_or_version(self):
        for edit in ({'product':'pico4'},{'channel':'internal-candidate'},{'sourceRevision':'f'*40},{'versionCode':1}):
            self.record_path.write_text(json.dumps(self.record|edit))
            with self.assertRaises(ValueError):consumer.verify(self.args)
        self.record_path.write_text(json.dumps(self.record))
        self.files['targetPackages'].write_bytes(b'foreign evidence')
        with self.assertRaises(ValueError):consumer.verify(self.args)

    def test_dirty_actual_source_repository_and_foreign_sbom_summary_fail(self):
        self.bad_sbom=True
        with self.assertRaisesRegex(ValueError,'SBOM_CONTEXT'):consumer.verify(self.args)
        self.bad_sbom=False;(self.repo/'uncommitted').write_text('unreviewed source')
        with self.assertRaises(ValueError):consumer.verify(self.args)

    def test_legacy_simulator_runtime_is_not_accepted_as_a_physical_package(self):
        _metadata,self.args.expected_artifact_sha256=self.runtime_fixture.write_candidate(self.artifacts,'simulator')
        with self.assertRaises(ValueError):consumer.verify(self.args)
        self.assertFalse(self.sbom_calls)

    def preflight(self,summary):
        # Actual binding subprocess framing; only its executed verifier is a
        # supplied format boundary. No target/session/base adapter is created.
        args=argparse.Namespace(candidate_manifest=None,physical_candidate_metadata=str(self.terminal.candidate),
            expected_source_sha=self.sha,expected_artifact_sha256=self.digest)
        for key in binding.INPUT_FLAGS:setattr(args,key.replace('-','_'),str(getattr(self.args,key.replace('-','_'))))
        commands=[]
        class Process:
            def wait(self,timeout):
                if timeout!=90:raise AssertionError('unbounded candidate wait')
                return 0
        def start(command,**options):
            commands.append(command);options['stdout'].write(json.dumps(summary).encode());return Process()
        with patch.object(binding.subprocess,'Popen',side_effect=start):value=binding.candidate_preflight(args)
        return value,commands,args

    def test_bound_preflight_selects_physical_reader_but_does_not_create_installed_identity(self):
        summary=consumer.verify(self.args);value,commands,args=self.preflight(summary)
        self.assertEqual(summary,value);self.assertIn(str(binding.PHYSICAL_VERIFIER),commands[0])
        self.assertIn('--terminal-candidate-metadata',commands[0]);self.assertNotIn('--execute',commands[0])
        with patch.object(binding,'candidate_preflight',return_value=summary):
            class Base:
                def __init__(self,platform):self.platform=platform
                def describe(self,_):return {'executionIdentity':{'untrusted':True}}
                def target(self,_):return {'platform':'ios','physical':True,'artifactMode':'signed-ipa'}
            args.platform='ios';args.action='describe';adapter=binding.create_adapter(args,Base)
            self.assertIsInstance(adapter,Base)
            # A physical candidate still cannot use a session that may install
            # artifacts, or create identity before actual native measurements.
            with self.assertRaisesRegex(ValueError,'INSTALLED_CODE_BINDING_REJECTED'):adapter.ensure_session('test-only')

    def test_preflight_rejects_foreign_runtime_missing_shared_tiers_or_forged_bundle(self):
        summary=consumer.verify(self.args)
        variants=[dict(summary,physicalHandoffVersion=True),dict(summary,sharedEvidence='DEFERRED'),dict(summary,physicalDevice='PASS'),
            dict(summary,runtime=dict(summary['runtime'],platform='iphonesimulator')),
            dict(summary,runtime=dict(summary['runtime'],artifact='../secret.ipa')),
            dict(summary,bundleIdentity=dict(summary['bundleIdentity'],fileCount=True))]
        for value in variants:
            with self.assertRaises(ValueError):self.preflight(value)


if __name__=='__main__':unittest.main()
