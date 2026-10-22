#!/usr/bin/env python3
"""Exercise protected release transport without network or native builds."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/repository-checks'))
import pr_ci_android_assets as A


class Response(io.BytesIO):
    def __init__(self, data, url='https://release-assets.githubusercontent.com/github-production-release-asset/fixture'):
        super().__init__(data)
        self.url = url
    def geturl(self):
        return self.url


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = b'actual bounded bytes\x00\xff'
        self.descriptor = {'url': 'https://github.com/noah-l-frank/overte/releases/download/android-ci-v1/runtime.tar.gz',
            'bytes': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest()}
    def tearDown(self):
        self.temp.cleanup()
    def fetch(self, data=None, **kwargs):
        return A.fetch(self.descriptor, self.root,
            opener=lambda *_args, **_kwargs: Response(self.data if data is None else data, **kwargs))
    def test_download_checks_bytes_digest_and_uses_no_credentials(self):
        def opened(request, **options):
            self.assertNotIn('Authorization', dict(request.header_items()))
            self.assertEqual(options['timeout'], 60)
            return Response(self.data)
        path = A.fetch(self.descriptor, self.root, opener=opened)
        self.assertEqual(path.read_bytes(), self.data)
        self.assertEqual(path.name, self.descriptor['sha256'])
        self.assertEqual(list(self.root.glob('.android-download-*')), [])
    def test_exact_cache_hit_is_rehashed_without_a_network_request(self):
        path = self.fetch()
        with patch.object(A.urllib.request, 'urlopen', side_effect=AssertionError('no network')):
            self.assertEqual(A.fetch(self.descriptor, self.root, opener=A.urllib.request.urlopen), path)
        path.write_bytes(b'X' * len(self.data))
        self.assertEqual(self.fetch().read_bytes(), self.data)
    def test_short_long_and_same_length_wrong_downloads_are_not_published(self):
        for data in (self.data[:-1], self.data + b'x', b'X' * len(self.data)):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'byte'):
                self.fetch(data)
            self.assertEqual(list(self.root.iterdir()), [])
    def test_foreign_or_mutable_urls_and_unbounded_sizes_are_refused(self):
        for mutation in ({'url': self.descriptor['url'].replace('noah-l-frank', 'overte-org')},
                         {'url': self.descriptor['url'] + '?token=private'},
                         {'url': self.descriptor['url'].replace('https:', 'http:')},
                         {'url': 'https://github.com/noah-l-frank/overte/raw/main/runtime'},
                         {'bytes': True}, {'bytes': A.MAX_ASSET + 1}, {'sha256': 'f' * 63}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                A.asset(self.descriptor | mutation)
    def test_foreign_redirect_refused_before_reading_or_publishing(self):
        with self.assertRaisesRegex(ValueError, 'redirected'):
            self.fetch(url='https://other.example/runtime')
        self.assertEqual(list(self.root.iterdir()), [])
    def test_cache_symlink_cannot_substitute_other_bytes(self):
        target = self.root / 'elsewhere'; target.write_bytes(self.data)
        (self.root / self.descriptor['sha256']).symlink_to(target)
        restored = self.fetch()
        self.assertFalse(restored.is_symlink())
        self.assertEqual(restored.read_bytes(), self.data)
        self.assertEqual(target.read_bytes(), self.data)
    def test_concurrent_publisher_is_preserved(self):
        link = A.os.link
        def concurrent(source, destination):
            Path(destination).write_bytes(b'another completed asset')
            link(source, destination)
        with patch.object(A.os, 'link', side_effect=concurrent), self.assertRaises(FileExistsError):
            self.fetch()
        self.assertEqual((self.root / self.descriptor['sha256']).read_bytes(), b'another completed asset')
        self.assertEqual(list(self.root.glob('.android-download-*')), [])
    def test_pending_production_policy_cannot_prepare_or_claim_a_build(self):
        (self.root / '.github').mkdir()
        pending = {'schema': 1, 'kind': 'overte-android-native-runtime-v1',
                   'status': 'awaiting-local-qualification', 'assets': {}, 'products': {}}
        (self.root / A.POLICY).write_text(json.dumps(pending))
        value = A.policy(self.root, qualified=False)
        self.assertEqual(value['status'], 'awaiting-local-qualification')
        with self.assertRaisesRegex(ValueError, 'awaiting'):
            A.policy(self.root)
        with self.assertRaisesRegex(ValueError, 'unqualified'):
            A.prepare(value, self.root / 'output', self.root)
        self.assertFalse((self.root / 'output').exists())
    def test_unqualified_policy_cannot_smuggle_partial_authority(self):
        root = self.root; (root / '.github').mkdir()
        value = {'schema': 1, 'kind': 'overte-android-native-runtime-v1',
                 'status': 'awaiting-local-qualification', 'assets': {'image': self.descriptor}, 'products': {}}
        (root / A.POLICY).write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'partial authority'):
            A.policy(root, qualified=False)

    def test_actual_sealed_readonly_payloads_prepare_without_overwriting_a_destination(self):
        payload = self.root / 'payload'; (payload / 'sealed').mkdir(parents=True)
        (payload / 'sealed/data').write_bytes(b'fixture transport data')
        (payload / 'sealed/data').chmod(0o444); (payload / 'sealed').chmod(0o555)
        inventory = A.R.canonical(A.R.inventory(payload))
        archive = self.root / 'archive.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            stream.add(payload / 'sealed', arcname='sealed')
        bodies = {}
        def descriptor(name, body):
            url = 'https://github.com/noah-l-frank/overte/releases/download/android-ci-v1/' + name
            bodies[url] = body
            return {'url': url, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        assets = {name: {'archive': descriptor(name + '.tar.gz', archive.read_bytes()),
                         'inventory': descriptor(name + '.json', inventory)}
                  for name in A.KINDS if name != 'image'}
        assets['image'] = {'archive': descriptor('image.tar.gz', b'image transport fixture')}
        cache = self.root / 'cache'; cache.mkdir()
        destination = self.root / 'prepared'
        opener = lambda request, **_kwargs: Response(bodies[request.full_url])
        result = A.prepare({'status': 'qualified', 'assets': assets}, destination, cache, opener=opener)
        self.assertFalse(result['build_qualified'])
        for name in A.NATIVE_KINDS - {'image'}:
            self.assertEqual((destination / name / 'sealed/data').read_bytes(), b'fixture transport data')
            self.assertEqual((destination / name / 'sealed').stat().st_mode & 0o777, 0o555)
        self.assertFalse((destination / 'groovy').exists())
        with self.assertRaisesRegex(ValueError, 'new and canonical'):
            A.prepare({'status': 'qualified', 'assets': assets}, destination, cache, opener=opener)
        self.assertEqual(list(self.root.glob('.android-runtime-*')), [])
        A.remove_private_tree(destination)
        A.remove_private_tree(payload)


if __name__ == '__main__':
    unittest.main()
