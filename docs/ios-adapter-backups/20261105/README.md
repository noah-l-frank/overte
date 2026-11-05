# Paused iOS adapter source backup, 2026-11-05

Development remains paused. Five of fourteen adapters were recorded complete at
source level: world/navigation, authentication, create, graphics, and scripts.
Native compilation and device acceptance have not been performed. This backup
preserves work in progress; it does not integrate or qualify unfinished features.

The source archives contain deduplicated source variants, source patches, test
code, required fixture inputs, notes and small preparation metadata from the
former local `.ios-host-tmp` directory. `paths.jsonl.gz` maps every preserved
original relative path to its exact SHA-256, mode and bytes. Files identical to
base commit `d483ba71b3adaf79e573d091ace82fa4a6598a68` reference that committed
file instead of duplicating its contents. Other contents are stored once in the
archives. Historical variants remain separately addressable through the index.
Existing backups in `20261029` and `20261103` remain available in Git.

Verify all preserved content without executing any adapter or test:

```sh
python3 -B docs/ios-adapter-backups/20261105/recover.py verify
```

The most recent coherent composition is the 292-file Stage7 repository snapshot.
Restore it into a new directory for review:

```sh
python3 -B docs/ios-adapter-backups/20261105/recover.py restore \
  --prefix .ios-host-tmp/root-stage7-pre-config13-shared-native-avatar-lifecycle-direct5-source-snapshot1-20261105/candidate \
  --destination /path/to/new-stage7-review
```

Use any indexed directory as `--prefix` to recover a separate proposal. The pause
packet under `root-pause-handoff-current-work-complete-20261105T0638` contains
`CURRENT-SOURCES.json`; its paths identify the latest proposals. Absolute paths
inside historical files describe the original workstation and are not rewritten.
A restored proposal must be reviewed before integration or execution.

Stage7 includes the shared native, Avatar, Lifecycle and Direct5 changes before
Config13. Newer Config13, Assets Source7/Bootstrap12, Actor restoration, TabletB10,
C10e and Avatar6 source proposals are preserved separately. They remain partly
unreviewed, unintegrated or nonrunnable. See `STATUS.md` for known failures and
remaining work.

Repeated whole-corpus inventories, runtime receipts, logs, ephemeral keys,
profiling data, caches and copied installed SDK environments are excluded from
this source backup and are locally disposable. The three modified Python SDK
payloads also exist in explicit source candidates and are preserved there.
Historical small manifests are retained as provenance, not as proof that removed
runtime artifacts still exist. Old launchers that require inode identities,
absolute paths or the entire historical corpus will need smaller, reproducible
prerequisites before reuse. Do not recreate the old cumulative inventory chain.
