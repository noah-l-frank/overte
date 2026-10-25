"""Ordinary navigation from Tablet's separately owned actual Home surface.

Native Close returns to the previous Qt app. The generic Script manager does
not own that Home and must keep its flags unchanged. Callers supply only their
already decoded private input operations; current original ScriptUI2 controls
independently admit the next normal input. No VM or effect is inferred here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.script_ui_inventory import ui_state


def enter(manager,home_operations):
    manager.require_current();current=manager.ui.capture()
    if manager.state['tabletOwned'] or not current['open']:return manager.open()
    homes=[row for row in home_operations if row['label'].startswith('open-app-home-')]
    need(homes and homes[-1]['status']=='returned' and current['ready'])
    actual=ui_state(current)
    need(not actual['open'] and not actual['picker'] and not actual['systemPending']
        and any(manager.ui.control(current,name) is not None for name in ('scripts.entry','scripts.menu')))
    manager.ui.open_manager();manager.ui.wait_manager()


def leave(manager,open_operations,label):
    manager.require_current()
    if manager.state['tabletOwned']:return manager.close_tablet()
    opens=[row for row in open_operations if row['label']==label]
    need(len(opens)==1 and opens[0]['status']=='returned');current=manager.ui.capture()
    actual=ui_state(current);need(current['open'] and actual['open'] and not actual['picker'] and not actual['systemPending'])
    manager.ui.close_tablet();manager.ui.wait_tablet_absent()
