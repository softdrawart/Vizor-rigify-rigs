# SPDX-FileCopyrightText: 2010-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from rigify.base_rig import BaseRig

from rigify.utils.naming import make_derived_name
from rigify.utils.widgets import layout_widget_dropdown, create_registered_widget
from rigify.utils.widgets_basic import create_limb_widget, create_cube_widget
from rigify.utils.bones import put_bone, flip_bone, set_bone_widget_transform


class Rig(BaseRig):
    """ A scapular rig is mainly for quadrupit rigs with one org bone directed the oposite way and damped to target bone.
    """
    class CtrlBones(BaseRig.CtrlBones):
        fk: str
        ik: str
        target: str
    class MchBones(BaseRig.MchBones):
        direction: str #reversed ORG bone looking at target
        #target: str
    bones: BaseRig.ToplevelBones[
        str,
        'Rig.CtrlBones',
        'Rig.MchBones',
        str
    ]

    org_name: str
    rig_parent_bone: str

    def find_org_bones(self, pose_bone) -> str:
        return pose_bone.name

    def initialize(self):
        pass

    def generate_bones(self):
        bones = self.bones
        # CTRL
        bones.ctrl.fk = self.copy_bone(bones.org, make_derived_name(bones.org, 'ctrl', '_fk'), parent=True)
        bones.ctrl.ik = self.copy_bone(bones.org, make_derived_name(bones.org, 'ctrl',), parent=True)
        put_bone(self.obj, bones.ctrl.ik, self.get_bone(bones.org).tail, scale=0.3)
        bones.ctrl.target = self.copy_bone(bones.org, make_derived_name(bones.org, 'ctrl',), parent=True, scale=0.3)
        #MCH
        bones.mch.direction = direction_mch = self.copy_bone(bones.org, make_derived_name(bones.org, 'mch', '_direction'), parent=True)
        flip_bone(self.obj, direction_mch)
        #bones.mch.target = self.copy_bone(bones.org, make_derived_name(bones.org, 'mch', '_target'), parent=True, scale=0.1)
        # DEF
        bones.deform = self.copy_bone(bones.org, make_derived_name(bones.org, 'def'), bbone=True)

    def parent_bones(self):
        bones = self.bones
        self.rig_parent_bone = self.get_bone_parent(bones.org)
        #DEF
        self.set_bone_parent(bones.deform, make_derived_name(self.rig_parent_bone, 'def'))
        #CTRL
        self.set_bone_parent(bones.ctrl.ik, bones.ctrl.fk)
        self.set_bone_parent(bones.ctrl.target, bones.ctrl.fk)
        self.set_bone_parent(bones.ctrl.fk, self.rig_parent_bone)
        #ORG
        self.set_bone_parent(bones.org, bones.mch.direction)

    def configure_bones(self):
        bones = self.bones
        self.copy_bone_properties(bones.org, bones.ctrl.fk)

    def rig_bones(self):
        bones = self.bones
        # DEF
        self.make_constraint(bones.deform, 'COPY_TRANSFORMS', bones.org)
        # MCH
        self.make_constraint(bones.mch.direction, 'COPY_LOCATION', bones.ctrl.ik)
        self.make_constraint(bones.mch.direction, 'DAMPED_TRACK', bones.ctrl.target)

    def generate_widgets(self):
        bones = self.bones
        # Create FK widget
        create_limb_widget(self.obj, bones.ctrl.fk)
        # Create IK
        obj = create_cube_widget(self.obj, bones.ctrl.ik)
        set_bone_widget_transform(self.obj, bones.ctrl.ik, bones.mch.direction)
        # target widget
        obj = create_cube_widget(self.obj, bones.ctrl.target)
        

    @classmethod
    def add_parameters(cls, params):
        pass

    @classmethod
    def parameters_ui(cls, layout, params):
        pass

