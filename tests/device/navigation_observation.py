"""Bounded normal Go To inputs and independent probe-derived navigation state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
from urllib.parse import parse_qs, urlsplit

OPERATIONS = {'places.open', 'places.close', 'places.goto', 'places.back', 'places.forward'}
FIXTURE_MARKERS = ['OVERTE_E2E_COLLISION_WALL', 'OVERTE_E2E_EAST', 'OVERTE_E2E_FLOOR',
                   'OVERTE_E2E_NORTH', 'OVERTE_E2E_ORIGIN']
VIEWPOINTS = {'A': '/0,0,4/0,0,0,1', 'B': '/2,0,4/0,0,0,1', 'C': '/-2,0,4/0,0,0,1'}
POSITIONS = {'A': {'x': 0, 'y': 0, 'z': 4}, 'B': {'x': 2, 'y': 0, 'z': 4},
             'C': {'x': -2, 'y': 0, 'z': 4}}


def owned_scene(value, *, viewpoint_required=False):
    if (not isinstance(value, str) or len(value) > 2048
            or any(ord(character) < 33 or ord(character) == 127 for character in value)):
        raise ValueError('Go To requires a bounded controlled scene URL')
    parsed = urlsplit(value)
    try:
        parsed.port
        query = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        raise ValueError('Controlled scene URL port or query is invalid') from None
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None or parsed.fragment
            or not parsed.path.endswith('/scene.json')
            or set(query) - {'location'} or 'location' in query and
                (len(query['location']) != 1 or query['location'][0] not in VIEWPOINTS.values())
            or viewpoint_required and 'location' not in query):
        raise ValueError('Go To may use only the controlled scene and its three fixed viewpoints')
    return parsed


def viewpoint_urls(scene_url):
    parsed = owned_scene(scene_url)
    base = parsed._replace(query='', fragment='').geturl()
    # Preserve literal separators. The normal cross-platform AddressManager
    # supports this form; percent-encoded separators are an Android-only fix.
    return {label: base + '?location=' + path for label, path in VIEWPOINTS.items()}


def same_viewpoint(observed, expected):
    try:
        actual = owned_scene(observed, viewpoint_required=True)
        wanted = owned_scene(expected, viewpoint_required=True)
    except ValueError:
        return False
    def identity(url):
        return (url.scheme, url.hostname, url.port or (443 if url.scheme == 'https' else 80),
                url.path, parse_qs(url.query))
    return identity(actual) == identity(wanted)


def action_arguments(operation, value):
    fields = {'url'} if operation == 'places.goto' else set()
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Normal Go To action fields are unsupported or missing')
    if fields:
        owned_scene(value['url'], viewpoint_required=True)
    return value


def project_probe(value):
    """Use actual fields from the existing fully validated native probe v2.

    The module calls OverteSession.snapshot first. Projection limits retained
    evidence and gives host counterfactuals a precise native-read seam.
    """
    try:
        return {'sampleSequence': value['sampleSequence'], 'sampleEpochMs': value['sampleEpochMs'],
            'foreground': value['application']['foreground'], 'domain': value['domain'],
            'sceneUrl': value['scene']['url'], 'fixtureMarkers': value['scene']['fixtureMarkers'],
            'fixtureMarkerCount': value['scene']['fixtureMarkerCount'],
            'feetPosition': value['avatar']['feetPosition'], 'velocity': value['avatar']['velocity'],
            'inAir': value['avatar']['inAir'], 'flying': value['avatar']['flying'],
            'render': value['render']}
    except (KeyError, TypeError):
        raise ValueError('Native navigation probe is incomplete') from None


class FreshNavigation:
    def __init__(self):
        self.previous = None

    def accept(self, value):
        fields = {'sampleSequence', 'sampleEpochMs', 'foreground', 'domain', 'sceneUrl',
                  'fixtureMarkers', 'fixtureMarkerCount', 'feetPosition', 'velocity',
                  'inAir', 'flying', 'render'}
        if (not isinstance(value, dict) or set(value) != fields
                or type(value['sampleSequence']) is not int or value['sampleSequence'] < 1
                or type(value['sampleEpochMs']) is not int or value['sampleEpochMs'] < 1
                or any(type(value[field]) is not bool for field in ('foreground', 'inAir', 'flying'))
                or not isinstance(value['sceneUrl'], str)
                or not isinstance(value['fixtureMarkers'], list)
                or not all(isinstance(item, str) for item in value['fixtureMarkers'])
                or type(value['fixtureMarkerCount']) is not int):
            raise ValueError('Native navigation observation is malformed')
        domain, render = value['domain'], value['render']
        if (not isinstance(domain, dict) or not {'connected', 'protocol', 'serverless'} <= set(domain)
                or type(domain['connected']) is not bool or type(domain['serverless']) is not bool
                or not isinstance(domain['protocol'], str)
                or not isinstance(render, dict) or set(render) != {'frameCount', 'lastFrameEpochMs'}
                or any(type(render[key]) is not int or render[key] < 0 for key in render)):
            raise ValueError('Native navigation domain or renderer observation is malformed')
        for field in ('feetPosition', 'velocity'):
            vector = value[field]
            if (not isinstance(vector, dict) or set(vector) != {'x', 'y', 'z'}
                    or any(type(item) not in (int, float) or not math.isfinite(item)
                           for item in vector.values())):
                raise ValueError('Native navigation avatar state is malformed')
        previous = self.previous
        if previous is not None and value['sampleSequence'] <= previous['sampleSequence']:
            raise ValueError('Native navigation probe sample was replayed or restarted')
        if previous is not None and render['frameCount'] < previous['render']['frameCount']:
            raise ValueError('Native navigation renderer frame history restarted')
        frame_advanced = render['frameCount'] > (previous['render']['frameCount'] if previous else 0)
        self.previous = value
        return value, frame_advanced


def arrived(value, expected_url, label):
    domain, render = value['domain'], value['render']
    return (value['foreground'] is True and domain['connected'] is False
        and domain['serverless'] is True and domain['protocol'] in {'http', 'https'}
        and same_viewpoint(value['sceneUrl'], expected_url)
        and value['fixtureMarkerCount'] == len(FIXTURE_MARKERS)
        and value['fixtureMarkers'] == FIXTURE_MARKERS
        and value['inAir'] is False and value['flying'] is False
        and math.dist([value['feetPosition'][key] for key in ('x', 'y', 'z')],
                      [POSITIONS[label][key] for key in ('x', 'y', 'z')]) <= 0.75
        and math.sqrt(sum(item * item for item in value['velocity'].values())) <= 0.15
        and render['lastFrameEpochMs'] > 0
        and abs(value['sampleEpochMs'] - render['lastFrameEpochMs']) <= 2000)
