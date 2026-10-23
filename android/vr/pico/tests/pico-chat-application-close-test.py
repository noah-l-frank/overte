#!/usr/bin/env python3
"""Disjoint original Chat application release and archive checks; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'android/vr/pico/tests/device')]


def selected(part):
    if part=='cursor-stop':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_actor_stop')
    if part=='cursor-cleanup-consumption':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_cursor_cleanup_consumption')
    if part=='cursor-archive':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_cursor_archive')
    if part=='cursor-actor':return unittest.defaultTestLoader.loadTestsFromNames([
        'self_tests.test_pico_chat_cursor_actor','self_tests.test_chat_observer_process','self_tests.test_observer_return','self_tests.test_chat_remote_actor_graph','self_tests.test_chat_remote_actor_return'])
    if part=='cursor-source-seal':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_cursor_source_seal')
    if part=='observation-cursor':return unittest.defaultTestLoader.loadTestsFromNames([
        'self_tests.test_chat_observation_cursor','self_tests.test_chat_observation_publisher'])
    if part=='cleanup-consumption':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_cleanup_consumption')
    if part=='cleanup-baseline':return unittest.defaultTestLoader.loadTestsFromNames([
        'self_tests.test_chat_cleanup_baseline','self_tests.test_feature_cleanup_consumption'])
    if part=='baseline-composition':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_baseline_composition')
    seals={name:'self_tests.test_chat_source_seal.source_seal_'+name+'_tests' for name in ('positive','admission','freshness')}
    if part.startswith('seal-') and part[5:] in seals:return unittest.defaultTestLoader.loadTestsFromName(seals[part[5:]])
    if part=='cleanup-factory':return unittest.defaultTestLoader.loadTestsFromNames(['test_chat_observation_factory','self_tests.test_pico_chat_cleanup_witness'])
    if part=='cleanup-witness':return unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_cleanup_witness')
    if part=='archive':
        return unittest.defaultTestLoader.loadTestsFromNames([
            'self_tests.test_chat_evidence_archive','self_tests.test_chat_archive_files',
            'self_tests.test_chat_archive_plan','test_chat_application_close',
            'self_tests.test_chat_archive_unlink_fence',
            'self_tests.test_chat_archive_index','self_tests.test_chat_host_close',
            'self_tests.test_chat_warm_archive.warm_archive_component_tests',
            'self_tests.test_chat_observation',
            'self_tests.test_chat_compiled_dispatcher.CompiledDispatcherTests.test_original_compiled_prefix_uses_distinct_code_roles_and_independent_witness_sources'])
    from self_tests.test_pico_chat_application_close import _application_tests
    return _application_tests(part)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=('journey','recovery','admission','delivery','post-ipc','archive','cleanup-witness','cleanup-factory','cleanup-baseline','baseline-composition','cleanup-consumption','observation-cursor','cursor-source-seal','cursor-cleanup-consumption','cursor-archive','cursor-actor','cursor-stop','seal-positive','seal-admission','seal-freshness'))
    result=unittest.TextTestRunner(verbosity=2).run(selected(parser.parse_args().part))
    raise SystemExit(not result.wasSuccessful())
