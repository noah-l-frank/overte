"""Original UI property admission; toolkit/GPU/device boundaries are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_composition import validate,admit,covers
from self_tests.test_pico_graphics_source import Boundary


def composition():
    return dict(compositionVersion=1,complete=True,
        screen=dict(id='cccccccc-cccc-4ccc-8ccc-cccccccccccc',parentId='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',type='Web',hostType='local',visible=True,alpha=1.,useBackground=True,pulseAlphaMode=0),
        root=dict(id='f'*32,**{'class':'TabletRoot_QMLTYPE_21'},objectName='tabletRoot',color=[.1,.1,.1,1.],radius=0.,
            width=480.,height=706.,quad=[[0,0],[480,0],[480,706],[0,706]]),viewport=[480,706],
        ancestors=[dict(visible=True,opacity=1.,layerEnabled=False,maskPresent=False,clip=None)])


def subject():return dict(source=dict(framework=dict(tablet=dict(screen='cccccccc-cccc-4ccc-8ccc-cccccccccccc',frame='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'),keyboard=dict(raised=False),entities=[dict(id='cccccccc-cccc-4ccc-8ccc-cccccccccccc',present=True,type='Web',parentId='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'),dict(id='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',present=True,type='Model')])))


def boundary():
    value=Boundary();value.edit=lambda packet:packet.update(graphicsObservationVersion=2,composition=composition());return value


class PicoGraphicsCompositionTests(unittest.TestCase):
    def test_original_properties_remain_separate_from_an_opaque_visibility_prerequisite(self):
        value=boundary().source().capture();self.assertEqual(composition(),value['composition'])
        self.assertEqual(composition(),admit(value,subject()))
        self.assertNotIn('worldVisible',value['composition'])

    def test_unknown_and_translucent_screen_root_layers_masks_and_clips_cannot_be_admitted(self):
        edits=[lambda v:v.update(complete=False),lambda v:v['screen'].update(alpha=.8),lambda v:v['screen'].update(visible=False),
            lambda v:v['screen'].update(useBackground=False),lambda v:v['screen'].update(pulseAlphaMode=1),
            lambda v:v['screen'].update(parentId='a'*32),lambda v:v['root']['color'].__setitem__(3,.9),
            lambda v:v['root'].update(radius=1),lambda v:v['ancestors'][0].update(visible=False),
            lambda v:v['ancestors'][0].update(opacity=.9),lambda v:v['ancestors'][0].update(layerEnabled=True),
            lambda v:v['ancestors'][0].update(maskPresent=True),
            lambda v:v['ancestors'][0].update(clip=[[1,0],[480,0],[480,706],[1,706]])]
        for edit in edits:
            packet=boundary().source().capture();edit(packet['composition'])
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):admit(packet,subject())
        packet=boundary().source().capture();packet['composition']=dict(compositionVersion=1,complete=False)
        with self.assertRaises(NativeUIError):admit(packet,subject())
        packet['tabletShown']=False;self.assertFalse(admit(packet,subject())['complete'])

    def test_rotated_quad_bounding_box_and_nonconvex_or_degenerate_background_are_not_full_cover(self):
        for shape in ([[240,-200],[800,353],[240,906],[-300,353]],[[0,0],[480,706],[480,0],[0,706]],[[0,0]]*4):
            with self.subTest(shape=shape),self.assertRaises(NativeUIError):covers(shape,[480,706])
        covers([[-10,-10],[490,-10],[490,716],[-10,716]],[480,706])

    def test_v1_reader_remains_explicit_but_cannot_replace_v2_after_acquisition_or_restore(self):
        source=Boundary().source();self.assertEqual(1,source.capture()['graphicsObservationVersion'])
        with self.assertRaises(NativeUIError):admit(source.capture(),subject())
        model=boundary();reader=model.source();original=reader.capture();model.edit=None
        with self.assertRaises(NativeUIError):reader.capture()
        reader=model.source();reader.restore_inventory(original)
        with self.assertRaises(NativeUIError):reader.capture()

    def test_missing_extra_nonfinite_or_wrongly_typed_original_composition_is_rejected(self):
        edits=[lambda v:v.pop('composition'),lambda v:v['composition'].update(opaque=True),
            lambda v:v['composition']['root']['color'].__setitem__(0,float('nan')),
            lambda v:v['composition']['ancestors'][0].update(opacity=True),
            lambda v:v['composition']['screen'].update(alpha=True),lambda v:v['composition']['root'].update(**{'class':'QQuickRectangle'}),
            lambda v:v['composition'].update(ancestors=[]),lambda v:v['composition'].update(compositionVersion=True)]
        for edit in edits:
            model=boundary();base=model.edit
            model.edit=lambda packet,edit=edit:(base(packet),edit(packet))
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):model.source().capture()


if __name__=='__main__':unittest.main()
