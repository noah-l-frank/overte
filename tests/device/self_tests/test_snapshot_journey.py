"""Exercise actual SNAP file assertions with only native UI/files/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import ast
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
from contracts import validate_operation_arguments, validate_operation_result
from snapshot_journey import snapshot_journey
from snapshot_observation import inspect_snapshot

NONCE = '0123456789abcdef'


def encoded(size=(320, 180), file_format='PNG', *, color='blue'):
    image = Image.new('RGB', size, color)
    ImageDraw.Draw(image).rectangle((10, 10, size[0] // 2, size[1] // 2), fill='red')
    output = BytesIO()
    image.save(output, format=file_format)
    return output.getvalue()


def gif(*, duration=600, frozen=False):
    frames = [Image.new('P', (320, 180), 0) for _ in range(2)]
    for index, frame in enumerate(frames):
        frame.putpalette([0, 0, 200, 200, 0, 0] + [0] * (768 - 6))
        x = 10 if frozen else 10 + index * 80
        ImageDraw.Draw(frame).rectangle((x, 10, x + 40, 80), fill=1)
    output = BytesIO()
    frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=False)
    return output.getvalue()


class NativeBoundary:
    def __init__(self, fixtures, mutation=''):
        self.fixtures = fixtures
        self.mutation = mutation
        self.actions, self.reports, self.checks = [], [], []
        self.saved = {}
        self.pending = None
        self.now = 0.0
        self.poll_count = 0

    def invoke(self, name, arguments):
        self.actions.append((name, arguments))
        if name == 'snapshot.open' and self.mutation == 'open-error':
            raise RuntimeError('native entry unavailable')
        if name == 'snapshot.close' and self.mutation in {'close-error', 'open-close-error'}:
            raise RuntimeError('native close unavailable')
        if name == 'snapshot.open' and self.mutation == 'open-close-error':
            raise RuntimeError('native entry unavailable')
        if name == 'snapshot.capture':
            self.pending = arguments
            self.poll_count = 0
        if name != 'snapshot.files':
            return {'performed': True}
        if self.pending is None or self.pending['name'] != arguments['prefix']:
            files = ([{'basename': arguments['prefix'] + '-previous.png', 'artifact': 'old.png'}]
                     if self.mutation == 'stale' else [])
            return {'files': files}
        self.poll_count += 1
        if self.mutation == 'ack-only' or self.mutation == 'clock-backwards' and self.poll_count == 1:
            return {'files': []}
        mode = self.pending['mode']
        file_format = self.pending['format']
        label = 'still-' + file_format if mode == 'still' else mode
        keys = [file_format, 'gif'] if mode == 'animated' else [file_format]
        if self.mutation == 'missing-gif' and mode == 'animated':
            keys = [file_format]
        files = []
        for extension in keys:
            ticket = 'different-ticket' if self.mutation == 'wrong-ticket' and extension == 'gif' else 'capture-1'
            basename = self.pending['name'] + '-' + ticket + '.' + extension
            if self.mutation == 'foreign-prefix':
                basename = 'other-' + basename
            artifact = label + '.' + extension
            payload = self.fixtures['gif' if extension == 'gif' else label]
            if self.mutation == 'corrupt':
                payload = b'not an image'
            if self.mutation == 'partial-first-read' and self.poll_count == 1:
                payload = payload[:16]
            self.saved[artifact] = payload
            files.append({'basename': basename, 'artifact': artifact})
        return {'files': files}

    def sleep(self, seconds):
        self.now += -seconds if self.mutation == 'clock-backwards' else seconds

    def continuity(self, phase):
        self.checks.append(phase)
        if self.mutation == 'restart' and self.pending is not None:
            raise AssertionError('application process restarted')

    def run(self):
        return snapshot_journey(NONCE, invoke=self.invoke, read_artifact=self.saved.__getitem__,
            assert_session=self.continuity, monotonic=lambda: self.now,
            sleep=self.sleep, report=self.reports.append)


class SnapshotJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {'still-png': encoded(), 'still-jpg': encoded(file_format='JPEG'),
                        'animated': encoded(), 'gif': gif(),
                        'panorama': encoded((8192, 4096)),
                        'cubemap': encoded((8192, 6144))}

    def test_all_normal_capture_modes_decode_actual_original_bytes(self):
        native = NativeBoundary(self.fixtures)
        results = native.run()
        self.assertEqual(['still-png', 'still-jpg', 'animated', 'panorama', 'cubemap'],
                         [row['case'] for row in results])
        self.assertEqual(6, sum(len(row['outputs']) for row in results))
        self.assertTrue(native.reports[0]['outputSequenceCompleted'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertEqual('snapshot.close', native.actions[-1][0])
        self.assertTrue(all(not output['deviceAcceptance']
                            for row in results for output in row['outputs']))

    def test_acknowledged_tap_without_new_output_cannot_pass(self):
        native = NativeBoundary(self.fixtures, 'ack-only')
        with self.assertRaisesRegex(AssertionError, 'did not produce complete fresh output'):
            native.run()
        self.assertEqual(65, len(native.reports[0]['polls']))
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_stale_foreign_and_corrupt_files_cannot_pass(self):
        for mutation in ('stale', 'foreign-prefix', 'corrupt'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(self.fixtures, mutation)
                with self.assertRaises(AssertionError):
                    native.run()
                self.assertFalse(native.reports[0]['outputSequenceCompleted'])
                self.assertEqual('snapshot.close', native.actions[-1][0])

    def test_missing_gif_and_mismatched_ticket_fail_even_with_valid_still(self):
        for mutation in ('missing-gif', 'wrong-ticket'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(self.fixtures, mutation)
                with self.assertRaisesRegex(AssertionError, 'SNAP animated'):
                    native.run()
                self.assertEqual(2, len(native.reports[0]['cases']))

    def test_partial_encode_can_settle_without_accepting_truncated_bytes(self):
        native = NativeBoundary(self.fixtures, 'partial-first-read')
        native.run()
        self.assertTrue(native.reports[0]['outputSequenceCompleted'])
        self.assertEqual(5, sum('pendingReason' in row for row in native.reports[0]['polls']))

    def test_actual_module_reader_preserves_empty_pending_file_and_path_guards(self):
        # Execute the original nested module reader without its device runner.
        # Only the artifact directory and infrastructure exception are seams.
        path = DEVICE / 'modules/snapshot_capture.py'
        source = ast.parse(path.read_text())
        main = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        reader = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == 'read_artifact')
        with tempfile.TemporaryDirectory(prefix='snapshot-module-original-') as temporary:
            directory = Path(temporary)
            namespace = {'ARTIFACT_DIR': directory, 'MAX_BYTES': 256 * 1024 * 1024,
                         'InfrastructureError': RuntimeError}
            exec(compile(ast.Module(body=[reader], type_ignores=[]), str(path), 'exec'), namespace)
            read = namespace['read_artifact']
            (directory / 'original.png').touch()
            self.assertEqual(read('original.png'), b'')
            with self.assertRaises(ValueError): inspect_snapshot(read('original.png'), mode='still', file_format='png')
            (directory / 'original.png').write_bytes(self.fixtures['still-png'])
            self.assertEqual(read('original.png'), self.fixtures['still-png'])
            self.assertEqual(inspect_snapshot(read('original.png'), mode='still', file_format='png')['format'], 'png')
            (directory / 'alias.png').symlink_to(directory / 'original.png')
            for name in ('../outside.png', 'alias.png', 'missing.png'):
                with self.subTest(name=name), self.assertRaises(RuntimeError): read(name)

    def test_restart_and_clock_failures_keep_cleanup(self):
        for mutation, expected in (('restart', AssertionError), ('clock-backwards', ValueError)):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(self.fixtures, mutation)
                with self.assertRaises(expected):
                    native.run()
                self.assertEqual('snapshot.close', native.actions[-1][0])
                self.assertFalse(native.reports[0]['outputSequenceCompleted'])

    def test_entry_cleanup_failure_preserves_the_original_error(self):
        native = NativeBoundary(self.fixtures, 'open-close-error')
        with self.assertRaisesRegex(RuntimeError, 'entry unavailable'):
            native.run()
        self.assertFalse(native.reports[0]['normalCloseSucceeded'])

    def test_close_failure_prevents_success_after_valid_outputs(self):
        native = NativeBoundary(self.fixtures, 'close-error')
        with self.assertRaisesRegex(RuntimeError, 'close unavailable'):
            native.run()
        self.assertEqual(5, len(native.reports[0]['cases']))
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])

    def test_decoder_checks_real_encoding_projection_dimensions_and_empty_pixels(self):
        for content, mode, file_format in (
                (self.fixtures['still-png'], 'still', 'jpg'),
                (self.fixtures['still-png'], 'panorama', 'png'),
                (self.fixtures['panorama'], 'cubemap', 'png'),
                (self.fixtures['gif'][:-1], 'animated', 'gif'),
                (self.fixtures['still-jpg'][:-2], 'still', 'jpg')):
            with self.subTest(mode=mode, file_format=file_format), self.assertRaises(ValueError):
                inspect_snapshot(content, mode=mode, file_format=file_format)
        flat = BytesIO()
        Image.new('RGB', (320, 180), 'black').save(flat, format='PNG')
        with self.assertRaisesRegex(ValueError, 'single-color'):
            inspect_snapshot(flat.getvalue(), mode='still', file_format='png')
        # Hidden RGB garbage in a fully transparent image is not visible scene
        # content. A direct RGB conversion would falsely accept this output.
        transparent = Image.new('RGBA', (320, 180), (0, 0, 255, 0))
        ImageDraw.Draw(transparent).rectangle((10, 10, 100, 80), fill=(255, 0, 0, 0))
        output = BytesIO()
        transparent.save(output, format='PNG')
        with self.assertRaisesRegex(ValueError, 'single-color'):
            inspect_snapshot(output.getvalue(), mode='still', file_format='png')

    def test_gif_requires_all_decoded_frames_and_meaningful_encoded_duration(self):
        observed = inspect_snapshot(self.fixtures['gif'], mode='animated', file_format='gif')
        self.assertEqual(2, len(observed['decodedFrames']))
        self.assertEqual(1200, observed['durationMilliseconds'])
        self.assertFalse(observed['deviceAcceptance'])
        # The fixture writer collapses identical frames to one encoded frame;
        # this is a frame-count rejection, not a claim of observed motion.
        for content in (gif(duration=10), gif(frozen=True)):
            with self.assertRaises(ValueError):
                inspect_snapshot(content, mode='animated', file_format='gif')

    def test_contract_rejects_private_paths_wildcards_extra_verdicts_and_unsafe_modes(self):
        good = {'mode': 'still', 'format': 'png', 'name': f'parity-{NONCE}-still-png'}
        self.assertEqual(good, validate_operation_arguments('snapshot.capture', good))
        for update in ({'mode': 'other'}, {'mode': []}, {'format': {}},
                       {'name': '../private'}, {'name': good['name'] + '*'},
                       {'name': good['name'].replace('-still-', '-animated-')},
                       {'format': 'webp'}, {'expectedValid': True}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_operation_arguments('snapshot.capture', good | update)
        for operation in ('snapshot.open', 'snapshot.capture', 'snapshot.close'):
            with self.assertRaises(ValueError):
                validate_operation_result(operation, {'performed': True, 'outputValid': True})
        for files in ([{'basename': '/private/Snapshots/test.png', 'artifact': 'test.png'}],
                      [{'basename': 'test.png', 'artifact': '../test.png'}],
                      [{'basename': 'test.png', 'artifact': 'test.png', 'valid': True}],
                      [{'basename': 'test.png', 'artifact': 'test.png'}] * 2):
            with self.subTest(files=files), self.assertRaises(ValueError):
                validate_operation_result('snapshot.files', {'files': files})

    def test_execution_plan_requires_scene_and_closed_snapshot_actions(self):
        from acceptance_policy import load_policy
        from execution_plan import compile_plan, load_profiles
        catalog = DEVICE / 'catalog.json'
        policy = load_policy(DEVICE / 'acceptance-policy.json', catalog)
        profiles = load_profiles(DEVICE / 'execution-profiles.json', catalog)
        plan = compile_plan(policy, catalog, profiles, 'mock', ['snapshot-output-parity'],
                            set(), False, set(), 'none')
        self.assertFalse(plan['ready'])
        self.assertEqual(['fixture:scene'], plan['missingInputs'])
        self.assertEqual(['launch-smoke', 'snapshot-output-parity'], plan['suites'][0]['modules'])
        self.assertTrue({'snapshot.open', 'snapshot.capture', 'snapshot.files', 'snapshot.close'}
                        <= set(plan['suites'][0]['capabilities']))


if __name__ == '__main__':
    unittest.main()
