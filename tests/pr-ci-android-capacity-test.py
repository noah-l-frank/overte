#!/usr/bin/env python3
"""Deterministic resource admission tests; no downloads, Docker or builds."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import stat
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("capacity", ROOT / "tools/repository-checks/pr_ci_android_capacity.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.budget = {"workspace_free_bytes": 500, "docker_free_bytes": 300,
                       "free_inodes": 20, "memory_available_bytes": 1024}
        self.paths = {"/": 1, "/workspace": 1, "/workspace/cache": 1, "/docker": 1}
        self.space = {"/workspace": (1000, 100, 80), "/workspace/cache": (1000, 100, 80),
                      "/docker": (1000, 100, 80)}
        self.mounts = None
        self.documents = {"/proc/meminfo": "MemTotal: 999999 kB\nMemAvailable: 2 kB\n",
                          "/proc/self/cgroup": "0::/job\n",
                          "/proc/self/mountinfo": "21 20 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n",
                          "/sys/fs/cgroup/job/memory.max": "max\n",
                          "/sys/fs/cgroup/memory.max": "max\n"}

    def read(self, path):
        try:
            value = self.documents[str(path)]
        except KeyError as error:
            raise FileNotFoundError(str(path)) from error
        if str(path) == "/proc/self/mountinfo":
            mounts = self.mounts if self.mounts is not None else "".join(
                f"{index} 0 0:{device} / {name} rw - ext4 /dev/example rw\n"
                for index, (name, device) in enumerate(self.paths.items(), 1))
            return mounts + value
        return value

    def st(self, path):
        path = str(path)
        if path not in self.paths:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_dev=self.paths[path])

    def fs(self, path):
        available, total_inodes, free_inodes = self.space[str(path)]
        return SimpleNamespace(f_frsize=1, f_bavail=available,
                               f_files=total_inodes, f_favail=free_inodes)

    def admit(self, **overrides):
        args = dict(stat_path=self.st, statvfs_path=self.fs, read_text=self.read)
        args.update(overrides)
        return C.admit(self.budget, "/workspace/future", "/workspace/cache/future", "/docker", **args)

    def test_remaining_prepare_budget_does_not_charge_completed_setup_and_cache_staging(self):
        # Scaled explicit lifecycle model, not actual build capacity evidence.
        build, transport, extracted, setup, docker = 100, 30, 60, 40, 20
        bootstrap = build + 2 * transport + extracted + setup
        prepare = build + transport + extracted
        for shared in (True, False):
            self.paths['/docker'] = 1 if shared else 2
            for restored in (False, True):
                with self.subTest(shared=shared, cache_restored=restored):
                    initial = bootstrap + (docker if shared else 0)
                    self.space = {name: (initial if shared or name != '/docker' else docker, 100, 80)
                                  for name in self.space}
                    self.budget.update(workspace_free_bytes=bootstrap, docker_free_bytes=docker)
                    self.admit()
                    remaining = initial - setup - (transport if restored else 0)
                    self.space = {name: (remaining if shared or name != '/docker' else docker, 100, 80)
                                  for name in self.space}
                    with self.assertRaisesRegex(C.CapacityError, 'free bytes'):
                        self.admit()  # Reusing bootstrap here was the false failure.
                    self.budget['workspace_free_bytes'] = prepare
                    self.admit()
                    required = prepare + (docker if shared else 0)
                    self.space['/workspace/cache'] = (required - 1, 100, 80)
                    with self.assertRaisesRegex(C.CapacityError, 'free bytes'):
                        self.admit()  # Downloads/extraction still require admission.

    def test_same_device_combines_budgets_and_deduplicates_measurements(self):
        result = self.admit()
        self.assertTrue(result["workspace_and_docker_share_filesystem"])
        self.assertEqual(len(result["filesystems"]), 1)
        self.assertEqual(result["memory_available_bytes"], 2048)
        self.space["/workspace/cache"] = (799, 100, 80)
        with self.assertRaisesRegex(C.CapacityError, "free bytes"):
            self.admit()

    def test_different_docker_device_requires_each_budget(self):
        self.paths["/docker"] = 2
        self.space["/workspace"] = self.space["/workspace/cache"] = (500, 100, 20)
        self.space["/docker"] = (300, 100, 20)
        self.assertFalse(self.admit()["workspace_and_docker_share_filesystem"])
        self.space["/docker"] = (299, 100, 20)
        with self.assertRaisesRegex(C.CapacityError, "free bytes"):
            self.admit()

    def test_separate_workspace_cache_is_explicitly_unsupported(self):
        self.paths["/workspace/cache"] = 3
        with self.assertRaisesRegex(C.CapacityError, "cache on separate filesystems"):
            self.admit()

    def btrfs(self, same_source=True, kind="btrfs"):
        # Actual workstation observation: /home st_dev53, Docker st_dev37,
        # both kernel mounts report the same /dev/nvme0n1p6 Btrfs source.
        self.paths["/workspace"] = self.paths["/workspace/cache"] = 53
        self.paths["/docker"] = 37
        self.mounts = (f"1 0 0:{35 if kind == 'btrfs' else 53} /home /workspace rw - {kind} /dev/nvme0n1p6 rw\n"
                       f"2 0 0:{35 if kind == 'btrfs' else 37} /docker /docker rw - {kind} " +
                       ("/dev/nvme0n1p6" if same_source else "/dev/nvme1n1p6") + " rw\n")

    def test_btrfs_same_backing_source_combines_distinct_subvolume_devices(self):
        self.btrfs()
        self.assertTrue(self.admit()["workspace_and_docker_share_filesystem"])
        self.space = {key: (799, 100, 80) for key in self.space}
        with self.assertRaisesRegex(C.CapacityError, "free bytes"):
            self.admit()

    def test_btrfs_distinct_backing_sources_remain_separate_even_with_equal_counters(self):
        self.btrfs(same_source=False)
        self.space = {key: (600, 100, 80) for key in self.space}
        self.assertFalse(self.admit()["workspace_and_docker_share_filesystem"])

    def test_equal_counters_or_source_do_not_conflate_other_filesystem_types(self):
        for kind in ("ext4", "tmpfs"):
            with self.subTest(kind=kind):
                self.btrfs(kind=kind)
                self.space = {key: (600, 100, 80) for key in self.space}
                self.assertFalse(self.admit()["workspace_and_docker_share_filesystem"])

    def test_unknown_btrfs_source_or_device_mount_mismatch_rejects(self):
        self.btrfs()
        self.mounts = self.mounts.replace("/dev/nvme0n1p6", "none")
        with self.assertRaisesRegex(C.CapacityError, "canonical device"):
            self.admit()
        self.btrfs(kind="ext4")
        self.mounts = self.mounts.replace("0:53", "0:54")
        with self.assertRaisesRegex(C.CapacityError, "device differ"):
            self.admit()

    def test_inode_exhaustion_and_insufficient_inodes_reject(self):
        for free in (0, 19):
            with self.subTest(free=free):
                self.space["/docker"] = (1000, 100, free)
                with self.assertRaisesRegex(C.CapacityError, "free inodes"):
                    self.admit()

    def test_inode_unreporting_is_not_mistaken_for_exhaustion(self):
        self.space = {key: (1000, 0, 0) for key in self.space}
        self.assertIsNone(self.admit()["filesystems"][0]["available_inodes"])

    def test_memavailable_required_and_not_memtotal(self):
        for value in ("MemTotal: 9999999 kB\n", "MemAvailable: 0 kB\n",
                      "MemAvailable: 2 kB\nMemAvailable: 2 kB\n"):
            with self.subTest(value=value):
                self.documents["/proc/meminfo"] = value
                with self.assertRaises(C.CapacityError):
                    self.admit()

    def test_current_finite_cgroup_reduces_memory(self):
        self.documents.update({"/sys/fs/cgroup/job/memory.max": "3000",
                               "/sys/fs/cgroup/job/memory.current": "2000"})
        with self.assertRaisesRegex(C.CapacityError, "available memory"):
            self.admit()
        self.documents["/sys/fs/cgroup/job/memory.current"] = "1500"
        self.assertEqual(self.admit()["memory_available_bytes"], 1500)

    def test_parent_finite_cgroup_also_limits_current_unbounded_group(self):
        self.documents.update({"/sys/fs/cgroup/memory.max": "2000",
                               "/sys/fs/cgroup/memory.current": "1500"})
        with self.assertRaisesRegex(C.CapacityError, "available memory"):
            self.admit()

    def test_cgroup_never_increases_linux_available_memory(self):
        self.documents.update({"/sys/fs/cgroup/job/memory.max": "999999999",
                               "/sys/fs/cgroup/job/memory.current": "1"})
        self.assertEqual(self.admit()["memory_available_bytes"], 2048)

    def test_cgroup_usage_above_limit_is_zero_not_underflow(self):
        self.documents.update({"/sys/fs/cgroup/job/memory.max": "100",
                               "/sys/fs/cgroup/job/memory.current": "200"})
        with self.assertRaisesRegex(C.CapacityError, "available memory"):
            self.admit()

    def test_cgroup_unreadable_or_missing_current_measurement_fails(self):
        for path in ("/proc/self/cgroup", "/proc/self/mountinfo", "/sys/fs/cgroup/job/memory.max"):
            with self.subTest(path=path):
                prior = self.documents.pop(path)
                with self.assertRaises(C.CapacityError):
                    self.admit()
                self.documents[path] = prior
        self.documents["/sys/fs/cgroup/job/memory.max"] = "2000"
        with self.assertRaisesRegex(C.CapacityError, "unavailable"):
            self.admit()

    def test_absent_root_controller_limit_or_no_memory_controller_is_unbounded(self):
        del self.documents["/sys/fs/cgroup/memory.max"]
        self.assertEqual(self.admit()["memory_available_bytes"], 2048)
        self.documents["/proc/self/cgroup"] = "1:cpu:/job\n"
        self.assertEqual(self.admit()["memory_available_bytes"], 2048)

    def test_cgroup_v1_and_subtree_mount_are_resolved(self):
        self.documents.update({"/proc/self/cgroup": "4:cpu,memory:/tenant/job\n",
                               "/proc/self/mountinfo": "21 20 0:1 /tenant /memory rw - cgroup cgroup rw,memory\n",
                               "/memory/job/memory.limit_in_bytes": "3000",
                               "/memory/job/memory.usage_in_bytes": "1500"})
        self.assertEqual(self.admit()["memory_available_bytes"], 1500)

    def test_hybrid_host_uses_explicit_v1_memory_controller(self):
        self.documents.update({"/proc/self/cgroup": "0::/unified/job\n4:memory:/tenant/job\n",
                               "/proc/self/mountinfo": self.documents["/proc/self/mountinfo"] +
                               "22 20 0:2 /tenant /memory rw - cgroup cgroup rw,memory\n",
                               "/memory/job/memory.limit_in_bytes": "3000",
                               "/memory/job/memory.usage_in_bytes": "1500"})
        self.assertEqual(self.admit()["memory_available_bytes"], 1500)

    def test_malformed_cgroup_limits_and_ambiguous_mount_fail(self):
        self.documents["/sys/fs/cgroup/job/memory.max"] = "-1"
        with self.assertRaisesRegex(C.CapacityError, "invalid cgroup"):
            self.admit()
        self.documents["/sys/fs/cgroup/job/memory.max"] = "max"
        self.documents["/proc/self/mountinfo"] *= 2
        with self.assertRaisesRegex(C.CapacityError, "ambiguous"):
            self.admit()

    def test_empty_unknown_cgroup_measurement_and_excessive_path_reject(self):
        self.documents["/proc/self/cgroup"] = ""
        with self.assertRaisesRegex(C.CapacityError, "unavailable"):
            self.admit()
        self.documents["/proc/self/cgroup"] = "0::/" + "a" * 4096
        with self.assertRaisesRegex(C.CapacityError, "bound"):
            self.admit()

    def test_raw_unqualified_absent_unknown_boolean_and_huge_budgets_fail(self):
        for value in (None, {}, {"status": "awaiting-local-qualification"},
                      dict(self.budget, extra=1), dict(self.budget, free_inodes=True),
                      dict(self.budget, free_inodes=0), dict(self.budget, free_inodes=-1),
                      dict(self.budget, free_inodes=C.MAX_BUDGET + 1)):
            with self.subTest(value=value), self.assertRaises(C.CapacityError):
                C.admit(value, "/workspace/new", "/workspace/cache", "/docker")

    def test_real_nearest_existing_parent_and_symlink_alias_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(C.nearest_directory(root / "absent/a/b")[0], root)
            (root / "alias").symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(C.CapacityError, "alias"):
                C.nearest_directory(root / "alias/absent")
            (root / "file").write_text("ordinary")
            with self.assertRaisesRegex(C.CapacityError, "nondirectory"):
                C.nearest_directory(root / "file/new")
        for value in ("relative/path", "/workspace/../docker"):
            with self.assertRaisesRegex(C.CapacityError, "canonical"):
                C.nearest_directory(value, self.st)

    def test_measurement_io_and_invalid_fs_values_fail_clear(self):
        def denied(_path):
            raise PermissionError("measurement denied")
        with self.assertRaisesRegex(C.CapacityError, "unavailable: PermissionError"):
            self.admit(statvfs_path=denied)
        self.space["/docker"] = (1000, -1, 100)
        with self.assertRaisesRegex(C.CapacityError, "invalid filesystem"):
            self.admit()

    def test_changed_filesystem_device_is_rejected(self):
        calls = {}
        def changing(path):
            result = self.st(path)
            calls[str(path)] = calls.get(str(path), 0) + 1
            if str(path) == "/workspace" and calls[str(path)] > 1:
                result.st_dev = 8
            return result
        with self.assertRaisesRegex(C.CapacityError, "changed"):
            self.admit(stat_path=changing)

    def test_filesystem_changed_to_same_device_alias_is_rejected(self):
        calls = {}
        def changing(path):
            result = self.st(path)
            calls[str(path)] = calls.get(str(path), 0) + 1
            if str(path) == "/workspace" and calls[str(path)] > 1:
                result.st_mode = stat.S_IFLNK | 0o777
            return result
        with self.assertRaisesRegex(C.CapacityError, "changed"):
            self.admit(stat_path=changing)


if __name__ == "__main__":
    unittest.main(verbosity=2)
