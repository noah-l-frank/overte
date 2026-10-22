#!/usr/bin/env python3
"""Admit an Android consumer only against measured, protected resource budgets.

This read-only check downloads nothing and changes no host or cgroup setting.
The caller must supply the capacity object from its qualified protected policy;
an unqualified policy, absent budget or unavailable measurement grants nothing.
"""
from pathlib import Path, PurePosixPath
import os
import re
import stat


KEYS = frozenset({"workspace_free_bytes", "docker_free_bytes", "free_inodes", "memory_available_bytes"})
MAX_BUDGET = 1 << 60
MAX_TEXT = 1_000_000


class CapacityError(ValueError):
    """Required Android consumer capacity was not established."""


def require(value, message):
    if not value:
        raise CapacityError(message)


def budget(value):
    require(type(value) is dict and set(value) == KEYS,
            "qualified Android capacity budget is unavailable or malformed")
    require(all(type(item) is int and 0 < item <= MAX_BUDGET for item in value.values()),
            "Android capacity budgets must be positive bounded integers")
    return dict(value)


def text(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        value = stream.read(MAX_TEXT + 1)
    require(len(value) <= MAX_TEXT, "capacity measurement exceeds its text bound")
    return value


def nearest_directory(value, stat_path=os.lstat):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts,
            "capacity path must be absolute and canonical")
    current = Path(path.anchor)
    info = stat_path(current)
    require(stat.S_ISDIR(info.st_mode), "capacity root is not an ordinary directory")
    for part in path.parts[1:]:
        child = current / part
        try:
            child_info = stat_path(child)
        except FileNotFoundError:
            break
        require(stat.S_ISDIR(child_info.st_mode) and not stat.S_ISLNK(child_info.st_mode),
                "capacity path contains an alias or nondirectory")
        current, info = child, child_info
    return current, info.st_dev


def filesystem(value, stat_path=os.lstat, statvfs_path=os.statvfs):
    root, device = nearest_directory(value, stat_path)
    measured = statvfs_path(root)
    values = (measured.f_frsize, measured.f_bavail, measured.f_files, measured.f_favail)
    require(all(type(item) is int for item in values) and values[0] > 0
            and all(item >= 0 for item in values[1:]), "invalid filesystem capacity measurement")
    closing = stat_path(root)
    require(stat.S_ISDIR(closing.st_mode) and closing.st_dev == device,
            "capacity filesystem changed during measurement")
    return {"device": device, "available_bytes": measured.f_frsize * measured.f_bavail,
            "available_inodes": measured.f_favail if measured.f_files else None}


def memory_available(read_text=text):
    matches = re.findall(r"^MemAvailable:\s+([0-9]+)\s+kB\s*$",
                         read_text("/proc/meminfo"), re.MULTILINE)
    require(len(matches) == 1, "Linux MemAvailable measurement is unavailable")
    return int(matches[0]) * 1024


def mount_path(value):
    # Linux mountinfo escapes spaces, tabs, newlines and backslashes as octal.
    return re.sub(r"\\(040|011|012|134)", lambda match: chr(int(match[1], 8)), value)


def cgroup_remaining(read_text=text):
    """Return the tightest visible memory headroom, or None if unbounded.

    Check ancestors as well as the current cgroup. A parent shared with other
    processes may impose a tighter limit than the consumer's immediate group.
    Missing files are optional only at the hierarchy root, where the kernel
    does not expose a controller limit. Other unreadable measurements fail.
    """
    groups = []
    membership = read_text("/proc/self/cgroup")
    require(bool(membership.strip()), "current cgroup measurement is unavailable")
    for line in membership.splitlines():
        parts = line.split(":", 2)
        require(len(parts) == 3, "invalid current cgroup measurement")
        if parts[0] == "0" and not parts[1]:
            groups.append(("cgroup2", parts[2]))
        elif "memory" in parts[1].split(","):
            groups.append(("cgroup", parts[2]))
    # Hybrid hosts may expose a unified hierarchy without its memory
    # controller alongside the v1 memory hierarchy. The explicit memory
    # controller is authoritative in that case.
    memory_groups = [row for row in groups if row[0] == "cgroup"]
    groups = memory_groups or groups
    require(len(groups) <= 1, "ambiguous current memory cgroup")
    if not groups:
        return None
    kind, group = groups[0]
    require(len(group) <= 4096, "current cgroup path exceeds its bound")
    group = PurePosixPath(group)
    require(group.is_absolute() and ".." not in group.parts, "invalid current cgroup path")
    mounts = []
    for line in read_text("/proc/self/mountinfo").splitlines():
        before, separator, after = line.partition(" - ")
        fields, system = before.split(), after.split()
        require(separator and len(fields) >= 6 and len(system) >= 3, "invalid cgroup mount measurement")
        if system[0] == kind and (kind == "cgroup2" or "memory" in system[2].split(",")):
            root, mount = PurePosixPath(mount_path(fields[3])), Path(mount_path(fields[4]))
            require(root.is_absolute() and mount.is_absolute() and ".." not in root.parts
                    and ".." not in mount.parts, "invalid memory cgroup mount")
            if group.is_relative_to(root):
                mounts.append((mount, mount / str(group.relative_to(root))))
    require(len(mounts) == 1, "current memory cgroup mount is unavailable or ambiguous")
    mount, current = mounts[0]
    headroom = []
    for _depth in range(128):
        limit_name, usage_name = (("memory.max", "memory.current") if kind == "cgroup2"
                                  else ("memory.limit_in_bytes", "memory.usage_in_bytes"))
        try:
            limit = read_text(current / limit_name).strip()
        except FileNotFoundError:
            require(current == mount, "current cgroup memory limit is unavailable")
            break
        if limit != "max":
            require(re.fullmatch(r"[0-9]+", limit), "invalid cgroup memory limit")
            usage = read_text(current / usage_name).strip()
            require(re.fullmatch(r"[0-9]+", usage), "invalid cgroup memory usage")
            headroom.append(max(0, int(limit) - int(usage)))
        if current == mount:
            break
        current = current.parent
    else:
        raise CapacityError("current cgroup ancestor depth exceeds its bound")
    return min(headroom) if headroom else None


def admit(policy_capacity, destination, cache, docker_root, *, stat_path=os.lstat,
          statvfs_path=os.statvfs, read_text=text, read_cgroup_remaining=None):
    """Reject unavailable capacity before downloading or executing anything."""
    required = budget(policy_capacity)
    try:
        workspace = filesystem(destination, stat_path, statvfs_path)
        cached = filesystem(cache, stat_path, statvfs_path)
        docker = filesystem(docker_root, stat_path, statvfs_path)
        require(workspace["device"] == cached["device"],
                "Android workspace and cache on separate filesystems are unsupported")
        groups = {}
        for row in (workspace, cached, docker):
            group = groups.setdefault(row["device"], {"available_bytes": row["available_bytes"],
                                                       "available_inodes": row["available_inodes"]})
            group["available_bytes"] = min(group["available_bytes"], row["available_bytes"])
            if row["available_inodes"] is not None:
                prior = group["available_inodes"]
                group["available_inodes"] = min(prior, row["available_inodes"]) if prior is not None else row["available_inodes"]
        for device, row in groups.items():
            need = (required["workspace_free_bytes"] if device == workspace["device"] else 0)
            need += required["docker_free_bytes"] if device == docker["device"] else 0
            require(row["available_bytes"] >= need, "insufficient Android filesystem free bytes")
            require(row["available_inodes"] is None or row["available_inodes"] >= required["free_inodes"],
                    "insufficient Android filesystem free inodes")
        available = memory_available(read_text)
        remaining = (read_cgroup_remaining or cgroup_remaining)(read_text)
        require(remaining is None or type(remaining) is int and remaining >= 0,
                "invalid cgroup memory headroom")
        if remaining is not None:
            available = min(available, remaining)
        require(available >= required["memory_available_bytes"], "insufficient Android available memory")
        return {"kind": "overte-android-capacity-admission-v1", "result": "admitted",
                "budget": required, "workspace_and_docker_share_filesystem": workspace["device"] == docker["device"],
                "filesystems": list(groups.values()), "memory_available_bytes": available}
    except (OSError, ValueError, TypeError, AttributeError) as error:
        if isinstance(error, CapacityError):
            raise
        raise CapacityError("Android capacity measurement is unavailable: " + type(error).__name__) from error
