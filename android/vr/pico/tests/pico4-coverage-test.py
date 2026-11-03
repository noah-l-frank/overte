#!/usr/bin/env python3
"""Validate and summarize the risk-based Pico 4 test coverage matrix."""

from pathlib import Path
import ast
import json
import unittest


TEST_DIR = Path(__file__).resolve().parent
MATRIX = json.loads((TEST_DIR / "pico4-coverage.json").read_text(encoding="utf-8"))
RUNNER_TREE = ast.parse((TEST_DIR / "pico4-test-suite.py").read_text(encoding="utf-8"))
EXPECTED_CATALOG_CASES = 379


def catalog_entries() -> list[str]:
    names = []
    for node in ast.walk(RUNNER_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "test":
            if node.args and isinstance(node.args[0], ast.Constant):
                names.append(node.args[0].value)
    return names


def catalog_names() -> set[str]:
    return set(catalog_entries())


def result_exit_code(result: unittest.TestResult) -> int:
    return 0 if result.wasSuccessful() else 1


class CoverageMatrixTests(unittest.TestCase):
    def test_scene_wrappers_keep_exact_retention_correct_counter_partition(self):
        selected=[]
        for name,count in (('test_navigation_scene_probe',4),('test_navigation_scene_raw',7),
                           ('test_navigation_scene_memory_retention',3)):
            tree=ast.parse((TEST_DIR/'device'/(name+'.py')).read_text())
            assignment=next(node for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id=='CASE_NAMES' for target in node.targets))
            names=ast.literal_eval(assignment.value)
            self.assertEqual(count,len(names));selected.extend(names)
        self.assertEqual(14,len(selected));self.assertEqual(14,len(set(selected)))
        self.assertFalse(any('complete_scene' in name or 'full_recipe' in name for name in selected))

    def test_current_keyboard_groups_keep_the_timed_out_prefix_out_of_defaults(self):
        expected={
            'world-current-keyboard-reader':('device/test_world_current_keyboard_reader.py',[]),
            'world-current-keys-originals':('device/test_world_current_keys_originals.py',[]),
            'world-current-keys-host-pass':('device/test_world_current_keys_host_pass.py',[]),
            'world-current-key-joins':('device/test_world_current_keys_parent.py',['WorldCurrentKeyJoinTests']),
            'world-current-keyboard-refusals':('device/test_world_current_keys_parent.py',[
                'WorldCurrentKeysParentTests.test_late_two_second_ack_old_current_ray_refuses_without_replay',
                'WorldCurrentKeysParentTests.test_ignored_key_retains_actual_input_and_raw_without_second_send'])}
        selected={}
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test':
                name=node.args[0].value
                if len(node.args)>3 and node.args[3].value=='device/test_world_current_keys_parent.py':
                    self.assertIn(name,expected)
                if name in expected:
                    self.assertNotIn(name,selected)
                    selected[name]=(node.args[3].value,[item.value for item in node.args[4:]])
        self.assertEqual(expected,selected)

    def test_remote_emote_wrappers_select_every_case_once_and_keep_legacy_separate(self):
        root=TEST_DIR.parents[3]
        tree=ast.parse((root/'tests/device/self_tests/test_pico_emote_capture.py').read_text())
        classes={'PicoEmoteRemoteCaptureTests','PicoEmoteRemoteBindingTests'}
        expected={'self_tests.test_pico_emote_capture.'+owner.name+'.'+method.name
            for owner in tree.body if isinstance(owner,ast.ClassDef) and owner.name in classes
            for method in owner.body if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')}
        selected=[]
        for module in ('test_emote_remote_capture','test_emote_remote_capacity','test_emote_remote_binding'):
            wrapper=ast.parse((TEST_DIR/'device'/(module+'.py')).read_text())
            value=next(node.value for node in wrapper.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id=='CASE_NAMES' for target in node.targets))
            selected.extend(ast.literal_eval(value))
        self.assertEqual(17,len(expected));self.assertEqual(17,len(selected));self.assertEqual(expected,set(selected))
        legacy=(TEST_DIR/'pico-emote-stereo-capture-test.py').read_text()
        self.assertIn("'self_tests.test_pico_emote_capture.PicoEmoteCaptureTests'",legacy)
        self.assertNotIn("'self_tests.test_pico_emote_capture'",legacy)

    def test_actor_storage_capacity_does_not_enter_default_bounded_groups(self):
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test':
                self.assertNotIn('test_lifecycle_actor_storage_capacity.py',ast.unparse(node))
                if node.args[0].value=='lifecycle-actor-storage':selected.append(node)
        self.assertEqual(1,len(selected));self.assertEqual(4,len(selected[0].args))
        self.assertEqual('device/test_lifecycle_actor_storage.py',selected[0].args[3].value)
        for path in ('test_lifecycle_actor_storage.py','test_lifecycle_independent_actor.py'):
            tree=ast.parse((TEST_DIR/'device'/path).read_text())
            imports=[node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
            self.assertFalse(any('storage_capacity' in module for module in imports))

    def test_navigation_frame_wrappers_keep_each_owning_case_once(self):
        expected={
            'navigation-generation-frames':'device/test_navigation_generation_frames.py',
            'navigation-generation-frame-fences':'device/test_navigation_generation_frame_fences.py'}
        selected={}
        for node in ast.walk(RUNNER_TREE):
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test'
                    and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value in expected):
                self.assertEqual(4,len(node.args));selected[node.args[0].value]=node.args[3].value
        self.assertEqual(expected,selected)
        cases=[]
        for path in selected.values():
            tree=ast.parse((TEST_DIR/path).read_text())
            declarations=[node for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id=='CASE_NAMES' for target in node.targets)]
            self.assertEqual(1,len(declarations));cases.extend(ast.literal_eval(declarations[0].value))
        self.assertEqual(10,len(cases));self.assertEqual(len(cases),len(set(cases)))

    def test_process_handoff_partitions_keep_each_complete_case_once(self):
        root=TEST_DIR.parents[3]
        tree=ast.parse((root/'tests/device/self_tests/test_lifecycle_operations_process.py').read_text())
        expected={'LifecycleOperationsProcessTests.'+method.name for owner in tree.body
            if isinstance(owner,ast.ClassDef) and owner.name=='LifecycleOperationsProcessTests' for method in owner.body
            if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')}
        names={'lifecycle-primary-launch-phase', 'lifecycle-primary-stop-lost', 'lifecycle-primary-process-memo', 'lifecycle-primary-process-presence', 'lifecycle-primary-process-pending', 'lifecycle-primary-stop-phase', 'lifecycle-primary-process-clock', 'lifecycle-primary-launch-lost', 'lifecycle-primary-process', 'lifecycle-primary-process-exit', 'lifecycle-primary-process-ui-span', 'lifecycle-primary-process-pending-span', 'lifecycle-primary-process-quiet', 'lifecycle-primary-process-quiet-exit'}
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and node.args[0].value in names:
                self.assertEqual('device/test_lifecycle_primary_process.py',node.args[3].value)
                selected.extend(item.value for item in node.args[4:])
        self.assertEqual(expected,set(selected));self.assertEqual(len(expected),len(selected))
    def test_avatar_parent_owning_selections_are_disjoint(self):
        expected={
            'avatar-parent-native-ui':('device/test_avatar_parent_native.py',
                'AvatarParentNativeTests.test_common_v16_parent_cached_favorite_live_preferences_and_retained_normal_return'),
            'avatar-parent-model-native-ui':('device/test_avatar_parent_native.py',
                'AvatarParentNativeTests.test_common_v16_parent_real_fst_fbx_loader_and_original_geometry_return'),
            'avatar-parent-fences':('device/test_avatar_parent_owner.py','AvatarParentOwnerTests')}
        selected={}
        for node in ast.walk(RUNNER_TREE):
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test'
                    and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value in expected):
                self.assertEqual(5,len(node.args));selected[node.args[0].value]=(node.args[3].value,node.args[4].value)
        self.assertEqual(expected,selected)
        for path,selection in selected.values():
            tree=ast.parse((TEST_DIR/path).read_text());owner=selection.split('.')[0]
            classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==owner]
            self.assertEqual(1,len(classes))
            methods=[node.name for node in classes[0].body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
            self.assertEqual(2 if '.' in selection else 6,len(methods))
            if '.' in selection:self.assertIn(selection.split('.')[1],methods)
        native=[selection for path,selection in selected.values() if path=='device/test_avatar_parent_native.py']
        owner_tree=ast.parse((TEST_DIR/'device/test_avatar_parent_native.py').read_text())
        expected_native={'AvatarParentNativeTests.'+method.name for owner in owner_tree.body
            if isinstance(owner,ast.ClassDef) and owner.name=='AvatarParentNativeTests' for method in owner.body
            if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')}
        self.assertEqual(expected_native,set(native));self.assertEqual(len(native),len(set(native)))

    def test_avatar_native_profiles_select_each_owning_method_once(self):
        path='device/test_avatar_people_controls_native.py';tree=ast.parse((TEST_DIR/path).read_text())
        expected={'AvatarPeopleControlsNativeTests.'+method.name for owner in tree.body if isinstance(owner,ast.ClassDef)
            and owner.name=='AvatarPeopleControlsNativeTests' for method in owner.body
            if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')}
        selected=[];groups=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and len(node.args)>3 and isinstance(node.args[3],ast.Constant) and node.args[3].value==path:
                groups.append(node.args[0].value);self.assertEqual(5,len(node.args));selected.append(node.args[4].value)
        self.assertEqual({'avatar-people-native-ui','avatar-persistence-native-ui'},set(groups));self.assertEqual(2,len(groups))
        self.assertEqual(len(expected),len(selected));self.assertEqual(expected,set(selected))

    def test_primary_restore_partitions_retain_every_new_case_once(self):
        root=TEST_DIR.parents[3]
        sources=((root/'tests/device/self_tests/test_pico_lifecycle_operations.py','LifecycleOperationsRestoreTests'),
            (root/'tests/device/self_tests/test_lifecycle_pending_historical_quiet.py','LifecyclePendingHistoricalQuietTests'))
        methods={name:{name+'.'+method.name for owner in ast.parse(path.read_text()).body
            if isinstance(owner,ast.ClassDef) and owner.name==name for method in owner.body
            if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')} for path,name in sources}
        names={'lifecycle-primary-restore','lifecycle-primary-close-phase','lifecycle-primary-restore-phase','lifecycle-primary-closure-history'}
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and node.args[0].value in names:
                self.assertEqual('device/test_lifecycle_primary_restore.py',node.args[3].value)
                for item in node.args[4:]:selected.extend(methods[item.value] if item.value in methods else (item.value,))
        expected=set().union(*methods.values())
        self.assertEqual(expected,set(selected));self.assertEqual(len(expected),len(selected))

    def test_pending_operation_partitions_retain_every_new_case_once(self):
        root=TEST_DIR.parents[3]
        sources=(
            (root/'tests/device/self_tests/test_pico_lifecycle_operations.py','LifecycleOperationsPendingTests'),
            (root/'tests/device/self_tests/test_lifecycle_pending_reply_versions.py','LifecyclePendingReplyVersionTests'),
            (TEST_DIR/'device/test_lifecycle_pending_phase_transport.py','LifecyclePendingPhaseTransportTests'))
        methods={name:{name+'.'+method.name for owner in ast.parse(path.read_text()).body
            if isinstance(owner,ast.ClassDef) and owner.name==name for method in owner.body
            if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')} for path,name in sources}
        selected=[]
        groups={'lifecycle-pending-operations','lifecycle-pending-publication',
            'lifecycle-pending-deadlines','lifecycle-pending-versions'}
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and node.args[0].value in groups:
                self.assertEqual('device/test_lifecycle_pending_operations.py',node.args[3].value)
                for item in node.args[4:]:selected.extend(methods[item.value] if item.value in methods else (item.value,))
        expected=set().union(*methods.values())
        self.assertEqual(expected,set(selected));self.assertEqual(len(expected),len(selected))

    def test_avatar_owner_partitions_retain_every_original_case_once(self):
        path=TEST_DIR/'device/test_avatar_urls_owner.py';tree=ast.parse(path.read_text())
        expected={'AvatarUrlsTests.'+node.name for owner in tree.body if isinstance(owner,ast.ClassDef) and owner.name=='AvatarUrlsTests'
            for node in owner.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')}
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and isinstance(node.args[0],ast.Constant) and node.args[0].value.startswith('avatar-urls-'):
                selected.extend(arg.value for arg in node.args[4:] if isinstance(arg,ast.Constant))
        self.assertEqual(len(expected),len(selected));self.assertEqual(expected,set(selected))

    def test_avatar_favorite_partitions_retain_every_original_case_once(self):
        tree=ast.parse((TEST_DIR/'device/test_avatar_favorites_owner.py').read_text())
        expected={'AvatarFavoritesTests.'+node.name for owner in tree.body if isinstance(owner,ast.ClassDef) and owner.name=='AvatarFavoritesTests'
            for node in owner.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')}
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and isinstance(node.args[0],ast.Constant) and node.args[0].value.startswith('avatar-favorites-'):
                selected.extend(arg.value for arg in node.args[4:] if isinstance(arg,ast.Constant))
        self.assertEqual(len(expected),len(selected));self.assertEqual(expected,set(selected))

    def test_graphics_partitions_retain_every_original_class_once(self):
        tree=ast.parse((TEST_DIR/'device/test_graphics_sources.py').read_text())
        expected={alias.name for node in tree.body if isinstance(node,ast.ImportFrom)
            for alias in node.names if alias.name.endswith('Tests')}
        groups={'graphics-sources','graphics-scene-owners','graphics-lifecycle-owners','graphics-feature-flow'}
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and isinstance(node.args[0],ast.Constant) and node.args[0].value in groups:
                self.assertEqual(node.args[3].value,'device/test_graphics_sources.py')
                selected.extend(arg.value for arg in node.args[4:])
        self.assertEqual(len(expected),len(selected));self.assertEqual(expected,set(selected))

    def test_assets_cancel_partitions_retain_every_original_case_once(self):
        tree=ast.parse((TEST_DIR/'device/test_assets_cancel_owner.py').read_text())
        expected={'AssetsCancelOwnerTests.'+node.name for owner in tree.body if isinstance(owner,ast.ClassDef) and owner.name=='AssetsCancelOwnerTests'
            for node in owner.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')}
        selected=[]
        for node in ast.walk(RUNNER_TREE):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='test' and isinstance(node.args[0],ast.Constant) and node.args[0].value.startswith('assets-cancel-'):
                selected.extend(arg.value for arg in node.args[4:])
        self.assertEqual(len(expected),len(selected));self.assertEqual(expected,set(selected))

    def test_process_exit_code_reflects_test_result(self):
        class Result:
            def __init__(self, successful):
                self.successful = successful

            def wasSuccessful(self):
                return self.successful

        self.assertEqual(result_exit_code(Result(True)), 0)
        self.assertEqual(result_exit_code(Result(False)), 1)

    def test_catalog_contains_expected_unique_cases(self):
        entries = catalog_entries()
        self.assertEqual(len(entries), EXPECTED_CATALOG_CASES)
        self.assertEqual(len(set(entries)), EXPECTED_CATALOG_CASES)

    def test_every_capability_has_multiple_independent_checks(self):
        for capability in MATRIX["capabilities"]:
            self.assertGreaterEqual(len(set(capability["tests"])), 2, capability["id"])

    def test_all_matrix_tests_exist_in_suite_catalog(self):
        known = catalog_names()
        referenced = {name for item in MATRIX["capabilities"] for name in item["tests"]}
        self.assertEqual(referenced - known, set())

    def test_every_functional_suite_test_is_mapped_to_a_capability(self):
        infrastructure = {"suite-runner", "coverage-matrix", "shell-syntax"}
        known = catalog_names() - infrastructure
        referenced = {name for item in MATRIX["capabilities"] for name in item["tests"]}
        self.assertEqual(known - referenced, set())

    def test_critical_capabilities_have_at_least_two_tests(self):
        critical = [item for item in MATRIX["capabilities"] if item["risk"] == "critical"]
        self.assertGreaterEqual(len(critical), 4)
        for capability in critical:
            self.assertGreaterEqual(len(capability["tests"]), 2, capability["id"])


if __name__ == "__main__":
    result = unittest.main(exit=False)
    if result.result.wasSuccessful():
        capabilities = MATRIX["capabilities"]
        print(f"Coverage: {len(capabilities)}/{len(capabilities)} risk capabilities mapped")
    raise SystemExit(result_exit_code(result.result))
