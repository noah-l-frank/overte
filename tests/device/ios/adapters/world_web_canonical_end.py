"""Pure canonical post-end guard for the exact completed World Web owner.

The installed adapter uses this after a terminal finish instead of obtaining a
new physical session. No public result, seal hash or SDK acknowledgement can
replace the existing whole historical Scene/OS/SDK original decoder.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from feature_journeys import terminal
from ios.adapters.world_web_feature import IOSWorldWebFeature
from ios.adapters.world_web_terminal import WorldWebTerminal


def verify(flow,call,result):
    need(type(flow) is IOSWorldWebFeature and flow.role=='primary')
    call=terminal.arguments('world-web',call)
    need(call['stage']=='finish' and call['runId']==flow.run)
    exact(result,{'stage','end'});need(result['stage']=='finish')
    owner=WorldWebTerminal(flow)
    need(owner.state is not None and owner.state['phase']=='complete'
        and same(call['seal'],owner.state['seal']) and same(result['end'],owner.state['end']))
    # finish's complete branch reopens both original role graphs, the sealed
    # private window, actual OS quiet and SDK-deletion/archive files. It never
    # consults the fixture or reconstructs a current session after process end.
    actual=owner.finish(call['seal'])
    need(same(actual,result))
    return actual
