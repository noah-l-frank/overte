#!/usr/bin/env python3
"""Phone Appium caller of the same verified installed-APK binding."""
# SPDX-License-Identifier: Apache-2.0
import ipaddress
import hashlib
import json
import os
import re
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapter import PhoneAdapter, main, require
from adapters.appium.adapter import AppiumAdapter
from contracts import validate_operation_arguments
from adapters.normal_ui import NativeUI
from adapters.phone_navigation import PhoneNavigation
from navigation_observation import OPERATIONS as NAVIGATION_OPERATIONS
from adapters.android_snapshot_files import AndroidSnapshotFiles
from overte_phone_snapshot import (PhoneSnapshot, PhoneSnapshotUI, PrivateSnapshotState,
                                   OPERATIONS as SNAPSHOT_OPERATIONS)


class PhoneAppiumAdapter(AppiumAdapter):
    def __init__(self, candidate=None):
        super().__init__("android")
        self.candidate = candidate

    def selected_target(self, requested, action):
        require(type(requested) is str and bool(requested), "PHONE_APPIUM_TARGET_REQUIRED")
        self.target(requested)
        return requested

    def cleanup_target(self, requested):
        return self.selected_target(requested, "cleanup")

    def installed_identity(self, selector):
        target = self.target(selector)
        capabilities = target["capabilities"]
        device = capabilities.get("appium:udid")
        require(target.get("appId") == "io.github.noah_be.overte.phone" and type(target.get("physical")) is bool,
                "PHONE_APPIUM_PACKAGE_AND_DEVICE_CLASS_REQUIRED")
        require(capabilities.get("appium:appPackage") == "io.github.noah_be.overte.phone",
                "PHONE_APPIUM_PACKAGE_MAPPING_REQUIRED")
        require(type(device) is str and bool(device) and device.lower() != "auto"
                and "appium:avd" not in capabilities
                and target.get("process", {}).get("kind") == "adb"
                and target["process"].get("selector") in (None, device),
                "PHONE_APPIUM_ADB_BINDING_REQUIRED")
        # Local ADB cannot prove which application a remote grid selected.
        # Keep bound mode local; the original adapter retains remote diagnostics.
        host = urlsplit(target["serverUrl"]).hostname
        local = host == "localhost"
        if not local:
            try:
                local = ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
        require(local, "PHONE_APPIUM_LOCAL_SERVER_REQUIRED")
        if "appium:app" in capabilities:
            # A capability-driven installation is still a candidate installation,
            # never an unrestricted URL/filename trusted on configuration alone.
            PhoneAdapter.require_bound_operation(self, "app.install", {"path": capabilities["appium:app"]})
        binding = PhoneAdapter(self.candidate)
        if target["physical"]:
            self.attest_android_phone_profile(target)
        else:
            # PH-003 is specifically x86_64 virtual smoke, never an ARM64 claim.
            # Read the selected target; its private configuration is expectation,
            # not evidence that a physical phone is an emulator (or vice versa).
            binding.adb.require_connected(device)
            sdk = binding.adb.prop(device, "ro.build.version.sdk")
            gles = binding.adb.prop(device, "ro.opengles.version")
            require(binding.adb.prop(device, "ro.kernel.qemu") == "1"
                    and binding.adb.prop(device, "ro.product.cpu.abi") == "x86_64"
                    and sdk.isdigit() and int(sdk) >= 26
                    and gles.isdigit() and int(gles) >= 196610,
                    "PHONE_APPIUM_X86_64_EMULATOR_REQUIRED")
        return binding.installed_identity(device)

    def describe(self, selector):
        result = super().describe(selector)
        if self.candidate is not None:
            result["executionIdentity"] = self.installed_identity(selector)
            if self.target(selector)["physical"] is False:
                result["role"] = "phone-emulator-e2e"
        return result

    def advertised_capabilities(self, target):
        values = super().advertised_capabilities(target)
        if (getattr(self, 'candidate', None) is not None
                and self.controlled_android_client(target)
                and target.get('controls', {}).get('normalNavigation') is not None):
            values = sorted(set(values) | NAVIGATION_OPERATIONS)
        if (os.environ.get('OVERTE_PHONE_NORMAL_SNAPSHOT') == '1'
                and getattr(self, 'candidate', None) is not None
                and target.get('appId') == 'io.github.noah_be.overte.phone'
                and self.controlled_android_client(target)):
            values = sorted(set(values) | SNAPSHOT_OPERATIONS)
        return values

    def snapshot_store(self, selector):
        return PrivateSnapshotState(self.state_path(selector).with_name('phone-snapshot-session.json'))

    @staticmethod
    def snapshot_fingerprint(target):
        return hashlib.sha256(json.dumps(target, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def normal_snapshot(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_SNAPSHOT_NOT_ENABLED')
        client, session, state = self.ensure_session(selector)
        installed = self.installed_identity(selector)
        process = self.process_state(selector, client, session, state, target)
        require(process.get('running') is True and isinstance(process.get('identity'), str)
                and re.fullmatch(r'[1-9][0-9]{0,9}:[0-9]{1,20}', process['identity']) is not None,
                'PHONE_NORMAL_SNAPSHOT_PID_AND_START_TICKS_REQUIRED')
        fingerprint = self.snapshot_fingerprint(target)
        require(state.get('targetFingerprint') == fingerprint, 'PHONE_NORMAL_SNAPSHOT_SESSION_TARGET_CHANGED')

        def check():
            current = self.read_session(selector)
            require(self.snapshot_fingerprint(self.target(selector)) == fingerprint
                    and current is not None and current.get('sessionId') == session
                    and current.get('generation') == state.get('generation')
                    and current.get('targetFingerprint') == fingerprint
                    and self.query_app_state(client, session, target) == 4
                    and self.process_state(selector, client, session, state, target) == process,
                    'PHONE_NORMAL_SNAPSHOT_PROCESS_OR_SESSION_CHANGED')

        check()
        context = {key: installed[key] for key in ('sourceRevision', 'artifactSha256')}
        context.update(processIdentity=process['identity'])
        binding = PhoneAdapter(self.candidate)
        files = AndroidSnapshotFiles(binding.adb, target['capabilities']['appium:udid'],
            target['appId'], context, check, os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR', ''))
        flow = PhoneSnapshot(PhoneSnapshotUI(client, session, check), files, self.snapshot_store(selector),
            context | {'sessionId': session, 'generation': state['generation'], 'targetFingerprint': fingerprint})
        result = flow.invoke(operation, arguments)
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_SNAPSHOT_INSTALL_CHANGED')
        return result

    def cleanup(self, selector):
        store = self.snapshot_store(selector)
        owned = store.read()
        if owned is not None:
            # Recovery must still work after candidate invalidation. Restrict it
            # to the unchanged private target and independently confirm stop;
            # shared Appium cleanup alone tolerates terminateApp errors.
            target = self.target(selector)
            device = target.get('capabilities', {}).get('appium:udid')
            require(target.get('appId') == 'io.github.noah_be.overte.phone'
                    and target.get('capabilities', {}).get('appium:appPackage') == target['appId']
                    and self.controlled_android_client(target)
                    and isinstance(device, str) and bool(device) and device.lower() != 'auto'
                    and target['process'].get('selector') in (None, device)
                    and self.snapshot_fingerprint(target) == owned['targetFingerprint'],
                    'PHONE_NORMAL_SNAPSHOT_CLEANUP_TARGET_CHANGED')
            binding = PhoneAdapter(None)
            binding.adb.require_connected(device)
            binding.adb.shell(device, 'am', 'force-stop', target['appId'])
            binding.wait_for_process_stopped(device)
        result = super().cleanup(selector)
        if owned is not None:
            require(result == {'cleaned': True}, 'PHONE_NORMAL_SNAPSHOT_CLEANUP_INCOMPLETE')
            store.discard()
        return result

    def normal_navigation(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_NAVIGATION_NOT_ENABLED')
        client, session, state = self.ensure_session(selector)
        installed = self.installed_identity(selector)
        process = self.process_state(selector, client, session, state, target)
        require(process.get('running') is True and isinstance(process.get('identity'), str)
                and bool(process['identity']), 'PHONE_NORMAL_NAVIGATION_PROCESS_REQUIRED')

        def check():
            require(self.query_app_state(client, session, target) == 4
                    and self.process_state(selector, client, session, state, target) == process,
                    'PHONE_NORMAL_NAVIGATION_PROCESS_CHANGED')

        ui = NativeUI(client, session, check)
        flow = PhoneNavigation(ui, target['controls']['normalNavigation'], state,
            installed, process['identity'], lambda: self.save_session(selector, state))
        result = flow.invoke(operation, arguments)
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_NAVIGATION_INSTALL_CHANGED')
        return result

    def ensure_session(self, selector):
        if self.candidate is not None:
            self.installed_identity(selector)
        result = super().ensure_session(selector)
        if self.candidate is not None:
            # Appium session creation can itself install an app from capabilities.
            # Recheck before any requested operation executes, not just at the
            # enclosing runner's initial/final describe boundaries.
            self.installed_identity(selector)
        return result

    def invoke(self, selector, operation, values):
        PhoneAdapter.require_bound_operation(self, operation, values)
        if operation.startswith('places.'):
            return self.normal_navigation(selector, operation, values)
        if operation in SNAPSHOT_OPERATIONS:
            return self.normal_snapshot(selector, operation, values)
        result = super().invoke(selector, operation, values)
        if self.candidate is not None and operation == "app.install":
            self.installed_identity(selector)
        return result


if __name__ == "__main__":
    raise SystemExit(main(adapter_class=PhoneAppiumAdapter))
