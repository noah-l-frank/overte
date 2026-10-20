"""Canonical iOS candidate preflight and physical original-bundle binding."""
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
VERIFIER = ROOT / "ios/tools/candidate/verify_candidate_handoff.py"
PHYSICAL_VERIFIER = ROOT / "ios/tools/candidate/verify_physical_e2e_handoff.py"
# Forward the existing iOS consumer's CLI; do not parse Common evidence here.
INPUT_FLAGS = (
    "artifact-root", "repository", "expected-source-sha", "shared-contract-root",
    "identity-contract-root", "sbom-contract-root", "identity-record", "expected-inputs", "minimum-version",
    "expected-channel", "bootstrapPackages", "hostPackages", "targetPackages",
    "generatedOutputs", "spdx", "cyclonedx",
)


def configure_parser(parser):
    # Optional at parse time so cleanup still works after losing candidate files.
    parser.add_argument("--candidate-manifest")
    parser.add_argument("--physical-candidate-metadata")
    parser.add_argument("--expected-artifact-sha256")
    for flag in INPUT_FLAGS:
        parser.add_argument("--" + flag)


def candidate_preflight(args):
    values = [getattr(args, name.replace("-", "_"), None) for name in INPUT_FLAGS]
    physical=getattr(args,'physical_candidate_metadata',None)
    if bool(args.candidate_manifest)==bool(physical) or any(not value for value in values):
        raise ValueError("OVT_IOS_CANDIDATE_INPUTS_REQUIRED")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_source_sha or "") or not re.fullmatch(
            r"[0-9a-f]{64}", args.expected_artifact_sha256 or ""):
        raise ValueError("OVT_IOS_CANDIDATE_EXPECTATIONS_REJECTED")
    verifier=PHYSICAL_VERIFIER if physical else VERIFIER
    if not verifier.is_file() or verifier.is_symlink():
        raise ValueError("OVT_IOS_CANDIDATE_VERIFIER_UNAVAILABLE")
    command = [sys.executable, "-B", str(verifier)]
    if physical:command.extend(['--terminal-candidate-metadata',physical,'--expected-artifact-sha256',args.expected_artifact_sha256])
    else:command.append(args.candidate_manifest)
    for name, value in zip(INPUT_FLAGS, values):
        command.extend(["--" + name, value])
    # Never forward stage/execute flags. No simulator/device action is possible
    # through this invocation. Retain no raw output in the result or on disk.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=errors, start_new_session=True)
        try:
            code = process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            raise ValueError("OVT_IOS_CANDIDATE_PREFLIGHT_TIMEOUT") from None
        if code != 0 or output.tell() > 1024 * 1024 or errors.tell() > 1024 * 1024:
            raise ValueError("OVT_IOS_CANDIDATE_PREFLIGHT_REJECTED")
        output.seek(0)
        try:
            result = json.loads(output.read(1024 * 1024 + 1))
        except (ValueError, UnicodeError):
            raise ValueError("OVT_IOS_CANDIDATE_PREFLIGHT_REJECTED") from None
    if (not isinstance(result, dict) or
            result.get("status") != ("IOS_PHYSICAL_CANDIDATE_BYTES_BOUND_VERIFICATION_PENDING" if physical else "IOS_CANDIDATE_BYTES_BOUND_VERIFICATION_PENDING") or
            result.get("sharedBuildInputJoin") != "BOUND_TO_INDEPENDENT_INPUTS" or
            result.get("simulator") != "NOT_EXECUTED" or
            not isinstance(result.get("sbomPair"), dict) or
            result["sbomPair"].get("status") != "SBOM_PAIR_VALID_CONTENT_VERIFICATION_PENDING" or
            result["sbomPair"].get("sourceRevision") != args.expected_source_sha or
            result["sbomPair"].get("artifactSha256") != args.expected_artifact_sha256 or
            not isinstance(result.get("artifactIdentity"), dict) or
            result["artifactIdentity"].get("artifactSha256") != args.expected_artifact_sha256):
        raise ValueError("OVT_IOS_CANDIDATE_PREFLIGHT_REJECTED")
    if physical:
        from ios.adapters.bundle_identity import compare
        runtime=result.get('runtime');bundle=result.get('bundleIdentity')
        if (type(result.get('physicalHandoffVersion')) is not int or result['physicalHandoffVersion']!=1
                or result.get('sharedEvidence')!='BOUND' or result.get('physicalDevice')!='NOT_EXECUTED'
                or type(runtime) is not dict or set(runtime)!={'platform','artifact','bundleIdentifier','appRoot'}
                or runtime['platform']!='iphoneos' or runtime['appRoot']!='Payload/Overte.app'
                or type(runtime['artifact']) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,180}\.ipa',runtime['artifact'])
                or result['artifactIdentity'].get('status')!='ARTIFACT_BYTES_BOUND_VERIFICATION_PENDING'
                or result['artifactIdentity'].get('sourceRevision')!=args.expected_source_sha):
            raise ValueError('OVT_IOS_CANDIDATE_PREFLIGHT_REJECTED')
        try:compare(bundle,bundle)
        except ValueError:raise ValueError('OVT_IOS_CANDIDATE_PREFLIGHT_REJECTED') from None
        if bundle['bundleId']!=runtime['bundleIdentifier']:
            raise ValueError('OVT_IOS_CANDIDATE_PREFLIGHT_REJECTED')
    # Candidate bytes alone never constitute the Common executionIdentity.
    # The physical adapter must independently compare original installed bytes.
    return result


def create_adapter(args, base_class):
    if args.platform != "ios":
        raise ValueError("OVT_IOS_NATIVE_PROFILE_REJECTED")
    if getattr(args, "physical_candidate_metadata", None) or args.action == "cleanup":
        from ios.adapters.installed_adapter import create_physical_adapter
        return create_physical_adapter(args, base_class, candidate_preflight, cleanup_only=args.action == "cleanup")
    if args.action != "cleanup":
        candidate_preflight(args)  # Fail before reading a target or opening I/O.

    class IOSCandidateAdapter(base_class):
        def describe(self, selector):
            candidate_preflight(args)  # Recheck mutable files at each observation.
            result = super().describe(selector)
            result.pop("executionIdentity", None)
            return result

        def ensure_session(self, selector):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _feature_observer(self, *args, **kwargs):
            # The unbound component's original native rows are not a reviewed
            # cryptographic/installation association with the selected IPA.
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _native_feature_observer(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _recorded_preview_evidence(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_execution_observer(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_files(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_runtime(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_file_manager(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_missing_manager(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_manager_status(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _bound_script_files(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_handoff(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_prepare(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_adopt(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_inputs(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_source(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_session(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart_stopped(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_restart(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _graphics_controls(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _account_origin(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _account_probe(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _world_render_capture(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _chat_capture(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _native_source_scope(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _navigation_replies(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _process_presence(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _pending_owner(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _web_dom(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _chat_view(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _private_login_input(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _chat_controls(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _create_controls(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _login_controls(self,*args,**kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _audio_controls(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def _script_file_picker(self, *args, **kwargs):
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        def invoke(self, selector, operation, values):
            # Includes operations that bypass ensure_session in the base class.
            # The v003 bound runner normally rejects missing identity earlier.
            raise ValueError("OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE")

        # Inherit original cleanup without candidate revalidation, including its
        # independent process-stop fallback and failure reporting.

    return IOSCandidateAdapter("ios")
