"""Compile original Application/Keyboard/Native trace; Java/DOM remain seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import json
import test_world_current_input_native as current_input


class WorldCurrentConsumptionNativeTests(unittest.TestCase):
    def test_original_keyboard_application_qt_jni_and_missing_java_callback(self):
        stage=current_input.WorldCurrentInputNativeTests.run_native(self, consumption=True)
        from adapters.pico4.world_current_consumption import validate
        from adapters.normal_ui import NativeUIError
        for directory in (stage,stage/'ime'):
            focus=json.loads((directory/'current-input-focus.json').read_bytes())
            original=dict(raw=json.dumps(focus['packet'],separators=(',',':')),
                request=focus['request'],documentOriginal=focus['documentOriginal'])
            arm=json.loads((directory/'consumption-arm.json').read_bytes());value=arm['packet']
            validate(value,arm['request'],value['processId'],value['capturedEpochMs'],original)
            proof=json.loads((directory/'consumption-originals.json').read_bytes())
            for frame in proof['frames']:
                value=frame['packet']
                validate(value,frame['request'],value['processId'],value['capturedEpochMs'],original,attempt=arm['packet'])
            value=proof['expired']
            validate(value,proof['expiredRequest'],value['processId'],value['capturedEpochMs'],original,attempt=arm['packet'])
        for fault in ('death','context','window','grant','page','source'):
            directory=stage/fault
            focus=json.loads((directory/'current-input-focus.json').read_bytes())
            original=dict(raw=json.dumps(focus['packet'],separators=(',',':')),
                request=focus['request'],documentOriginal=focus['documentOriginal'])
            arm=json.loads((directory/'consumption-arm.json').read_bytes())['packet']
            counter=json.loads((directory/'consumption-counter.json').read_bytes());value=counter['packet']
            if fault=='grant':
                # The actual changed native grant is retained in the raw
                # unavailable packet. The strict Host additionally refuses
                # that foreign authority; do not weaken its focus identity.
                with self.assertRaises(NativeUIError):
                    validate(value,counter['request'],value['processId'],value['capturedEpochMs'],original,attempt=arm)
            else:
                validate(value,counter['request'],value['processId'],value['capturedEpochMs'],original,attempt=arm)


if __name__ == '__main__': unittest.main()
