#!/usr/bin/env python3
"""Compose the existing physical runtime, SH-009 and SBOM byte/input verifiers.

Offline consumer only. No simulator stage, native compilation, installation,
device connection, signing or acceptance status is available through this CLI.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import importlib.util
import json
from pathlib import Path
import sys

import verify_candidate_handoff as shared
from sbom_pair import verify_pair

REPOSITORY=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPOSITORY/'tests/device'))
from execution_identity import file_digest
from ios.adapters.bundle_identity import artifact_bundle


def runtime_verifier():
    source=Path(__file__).resolve().parents[1]/'verify-runtime-candidate.py'
    if not source.is_file() or source.is_symlink():raise ValueError('IOS_PHYSICAL_RUNTIME_VERIFIER_UNAVAILABLE')
    spec=importlib.util.spec_from_file_location('overte_physical_runtime_candidate',source)
    if spec is None or spec.loader is None:raise ValueError('IOS_PHYSICAL_RUNTIME_VERIFIER_UNAVAILABLE')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def verify(args):
    identity=shared.identity_contract(args.identity_contract_root)
    adapter=shared.pinned_adapter(args.shared_contract_root)
    runtime=runtime_verifier()
    plan=runtime.verify_candidate(args.artifact_root,'ipad',args.expected_source_sha,args.expected_artifact_sha256)
    runtime.require_e2e_contract(args.artifact_root/plan['artifact'],plan['appRoot'])
    if (plan.get('platform')!='iphoneos' or plan.get('mode')!='ipad' or plan.get('appRoot')!='Payload/Overte.app'
            or plan.get('sourceRevision')!=args.expected_source_sha or plan.get('sha256')!=args.expected_artifact_sha256):
        raise ValueError('IOS_PHYSICAL_RUNTIME_CONTEXT')
    artifact=shared.candidate._safe_artifact_path(args.artifact_root,plan['artifact'])
    record=identity.read_record(args.identity_record);inputs=identity.read_record(args.expected_inputs)
    if record.get('product')!='ios' or record.get('channel')!=args.expected_channel:
        raise ValueError('IOS_PHYSICAL_IDENTITY_CONTEXT')
    result=identity.validate(record,artifact,{key:getattr(args,key) for key in identity.EVIDENCE_KEYS},
        args.expected_source_sha,inputs,args.minimum_version)
    if result.get('artifactSha256')!=args.expected_artifact_sha256:raise ValueError('IOS_PHYSICAL_ARTIFACT_CHANGED')
    # Consume the original opaque General terminal-evidence API. All mandatory
    # tiers must bind to THIS physical IPA and independently frozen inputs;
    # merely verifying the reader bytes is never a build-evidence substitute.
    bound=shared.candidate.bind_shared_evidence(adapter,args.terminal_candidate_metadata,
        args.expected_source_sha,args.expected_artifact_sha256,
        expected_normalized_inputs_sha256=identity.normalized_inputs(inputs),expected_toolchain_sha256=inputs['toolchain'])
    if bound!='BOUND':raise ValueError('IOS_PHYSICAL_SHARED_EVIDENCE_REQUIRED')
    sbom=verify_pair(args.sbom_contract_root,args.identity_contract_root,args.spdx,args.cyclonedx,
        args.expected_source_sha,args.expected_artifact_sha256,record['evidence'])
    if (type(sbom) is not dict or sbom.get('status')!='SBOM_PAIR_VALID_CONTENT_VERIFICATION_PENDING'
            or sbom.get('sourceRevision')!=args.expected_source_sha or sbom.get('artifactSha256')!=args.expected_artifact_sha256):
        raise ValueError('IOS_PHYSICAL_SBOM_CONTEXT')
    bundle=artifact_bundle(artifact,args.expected_artifact_sha256)
    if bundle['bundleId']!=plan['bundleIdentifier']:raise ValueError('IOS_PHYSICAL_BUNDLE_CONTEXT')
    # Re-read the original producer selector after byte/provenance inspection.
    # A replaced LATEST/numbered manifest cannot select another installed app.
    repeated=runtime.verify_candidate(args.artifact_root,'ipad',args.expected_source_sha,args.expected_artifact_sha256)
    if repeated!=plan or file_digest(artifact)!=args.expected_artifact_sha256:raise ValueError('IOS_PHYSICAL_CANDIDATE_CHANGED')
    shared.candidate._verify_repository_head(args.repository,args.expected_source_sha)
    return dict(physicalHandoffVersion=1,status='IOS_PHYSICAL_CANDIDATE_BYTES_BOUND_VERIFICATION_PENDING',
        sharedBuildInputJoin='BOUND_TO_INDEPENDENT_INPUTS',sharedEvidence=bound,
        artifactIdentity=result,sbomPair=sbom,bundleIdentity=bundle,
        runtime=dict(platform=plan['platform'],artifact=plan['artifact'],bundleIdentifier=plan['bundleIdentifier'],appRoot=plan['appRoot']),
        physicalDevice='NOT_EXECUTED',simulator='NOT_EXECUTED')


def main(argv):
    preliminary=argparse.ArgumentParser(add_help=False)
    preliminary.add_argument('--identity-contract-root',type=Path,required=True)
    known,_=preliminary.parse_known_args(argv)
    try:identity=shared.identity_contract(known.identity_contract_root)
    except Exception:
        print('IOS_PHYSICAL_CANDIDATE_HANDOFF_REJECTED',file=sys.stderr);return 1
    parser=argparse.ArgumentParser(description=__doc__,parents=[preliminary])
    for flag in ('artifact-root','repository','shared-contract-root','identity-record','sbom-contract-root','expected-inputs','terminal-candidate-metadata'):
        parser.add_argument('--'+flag,type=Path,required=True)
    parser.add_argument('--expected-source-sha',required=True)
    parser.add_argument('--expected-artifact-sha256',required=True)
    parser.add_argument('--minimum-version',type=int,required=True)
    parser.add_argument('--expected-channel',choices=('source-proof','internal-candidate'),required=True)
    for key in identity.EVIDENCE_KEYS:parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(argv)
    try:value=verify(args)
    except Exception:
        print('IOS_PHYSICAL_CANDIDATE_HANDOFF_REJECTED',file=sys.stderr);return 1
    print(json.dumps(value,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
