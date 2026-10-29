"""Actual Callback8 terminal factory over existing genuine typed role parts.

The assembly seam supplies no observation, effect, receipt or end result. It
uses the same original Native/SDK declared models and actual JS/UDP/HTTP/PNG.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from unittest.mock import patch
from adapters.native_feature_observation import need
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_callback_terminal import IOSEmoteCallbackTerminalFeature,IOSEmoteCallbackTerminal
from ios.self_tests import emote_callback_paired_fixture as pair_fixture


def paired(test):
    # The explicit new feature class and original pair are selected before
    # the existing paired fixture creates its FIRST owner or raw callback.
    with patch.object(pair_fixture,'IOSEmoteCallbackLiveFeature',IOSEmoteCallbackTerminalFeature):
        result=pair_fixture.paired(test)
    roles=dict(primary=result,actor=result.actor)
    original={role:item.runtime for role,item in roles.items()}
    class Runtime(IOSEmoteRuntime):
        def state_path(self,selector):
            need(selector in roles);return original[selector].state_path(selector)
        def _sources(self,selector):
            need(selector in roles);return original[selector]._sources(selector)
        def _existing(self,selector):return original['primary']._existing(selector)
        def _emote_actions(self,selector,sources):return original['primary']._emote_actions(selector,sources)
        def _emote_sources(self,selector,client,run,role,root,lock):
            need(role in roles);return original[role]._emote_sources(selector,client,run,role,root,lock)
        def _avatar_receive(self,selector):return original['actor']._avatar_receive(selector)
        @contextmanager
        def existing_input_session(self,selector):
            need(selector in roles)
            with original[selector].existing_input_session(selector):yield
        def _emote_callback_terminal(self,primary,actor=None):
            need(primary is roles['primary'].flow and (actor is None or actor is roles['actor'].flow))
            # Only the typed assembly endpoint differs from the normal
            # constructor; the actual terminal implementation is unchanged.
            return IOSEmoteCallbackTerminal(primary,roles['actor'].flow)
    runtime=object.__new__(Runtime);runtime.adapter=original['primary'].adapter
    primary_lock=result.target.lock
    for role,item in roles.items():
        old=item.flow;need(old.state is None and old.store.read() is None and old.FORMAT_VERSION==8)
        flow=IOSEmoteCallbackTerminalFeature(runtime,role,old.client,old.run,role,old.root,old.policy,
            primary_selector='primary' if role=='actor' else None,actor_selector='actor' if role=='primary' else None,
            epoch_ms=old.epoch_ms,monotonic=old.monotonic,sleep=old.sleep,target_pair=result.callback_selected_pair)
        flow.lock=item.target.lock;flow.primary_lock=primary_lock
        def components(flow=flow,item=item):
            own,primary=flow.bindings();need(flow.state is not None
                and flow.state['phaseInstance']==flow.phase.previous['instance'])
            parts=item.parts
            need(parts['scope'].lock is flow.lock and parts['scope'].binding==own['binding']
                and parts['sources'].binding==primary['binding'] and parts['observer'].binding==own['binding'])
            own['check']();primary['check']();return parts
        flow.components=components;item.flow,item.runtime=flow,runtime
    return result
