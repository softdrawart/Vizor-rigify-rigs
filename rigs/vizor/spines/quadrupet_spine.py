# SPDX-FileCopyrightText: 2019-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.types import PoseBone
import math
from typing import Optional

from itertools import count, repeat
from mathutils import Matrix

from rigify.utils.layers import ControlLayersOption
from rigify.utils.rig import connected_children_names
from rigify.utils.naming import strip_org, make_mechanism_name, make_derived_name
from rigify.utils.bones import (put_bone, align_bone_to_axis, align_bone_orientation, TypedBoneDict)

from rigify.utils.widgets import adjust_widget_transform_mesh
from rigify.utils.widgets_basic import create_circle_widget, create_cube_widget, create_bone_widget

from rigify.utils.misc import map_list
from rigify.utils.switch_parent import SwitchParentBuilder

from rigify.base_rig import stage, BaseRig


class Rig(BaseRig):
    """
    Simplified Spine rig for quadrupets of 3 bones!
    """
    chain_length = 3
    bbone_segments = 8

    length: float          # Total length of the chain bones

    rig_parent_bone: str  # Bone to be used as parent of the whole rig
    

    def initialize(self):
        if len(self.bones.org) != self.chain_length:
            self.raise_error(
                "Input to rig type must be a chain of {} bones.", self.chain_length)
        super().initialize()
        self.length = sum([self.get_bone(b).length for b in self.bones.org])
    
    def find_org_bones(self, bone: PoseBone):
        return [bone.name] + connected_children_names(self.obj, bone.name)
    
    def parent_bones(self):
        self.rig_parent_bone = self.get_bone_parent(self.bones.org[0])
    ####################################################
    # BONES

    class CtrlBones(BaseRig.CtrlBones):
        master: str                    # Master control
        chest: list[str]
        hips: list[str]

    class MchBones(BaseRig.MchBones):
        pivot: str                     # Central pivot between sub-chains

    bones: BaseRig.ToplevelBones[
        list[str],
        'Rig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]

    ####################################################
    # Master control bone

    @stage.generate_bones
    def make_master_control(self):
        self.bones.ctrl.master = name = self.make_master_control_bone(self.bones.org)
        self.build_parent_switch(name)

    def make_master_control_bone(self, orgs: list[str]):
        name = self.copy_bone(orgs[0], 'torso')
        put_bone(self.obj, name, self.get_bone(orgs[0]).head)
        align_bone_to_axis(self.obj, name, 'y', length=self.length * 0.6)
        return name

    def build_parent_switch(self, master_name: str):
        pbuilder = SwitchParentBuilder(self.generator)

        org_parent = self.get_bone_parent(self.bones.org[0])
        parents = [org_parent] if org_parent else []

        pbuilder.register_parent(self, self.bones.ctrl.master, name='Torso', tags={'torso', 'child'})

        pbuilder.build_child(
            self, master_name, exclude_self=True,
            extra_parents=parents, select_parent=org_parent,
            prop_id='torso_parent', prop_name='Torso Parent',
            controls=lambda: self.bones.flatten('ctrl'),
        )

        self.register_parent_bones(pbuilder)

    def register_parent_bones(self, pbuilder: SwitchParentBuilder):
        pbuilder.register_parent(self, self.bones.org[0], name='Hips', exclude_self=True, tags={'hips'})
        pbuilder.register_parent(self, self.bones.org[-1], name='Chest', exclude_self=True, tags={'chest'})

    @stage.generate_widgets
    def make_master_control_widget(self):
        master = self.bones.ctrl.master
        create_cube_widget(self.obj, master, radius=0.5)


    ####################################################
    # FK control bones

    @stage.generate_bones
    def make_control_chain(self):
        orgs = self.bones.org
        self.bones.ctrl.hips = map_list(self.make_control_bone, count(0), orgs[:1], repeat(True))
        self.bones.ctrl.chest = map_list(self.make_control_bone, count(0), orgs[1:], repeat(False))

    def make_control_bone(self, i: int, org: str, is_hip: bool):
        name = self.copy_bone(org, make_derived_name(org, 'ctrl'), parent=False)
        if is_hip:
            put_bone(self.obj, name, self.get_bone(name).tail)
        return name

    @stage.parent_bones
    def parent_control_chain(self):
        fk = self.bones.ctrl
        master = self.bones.ctrl.master
        self.parent_bone_chain([master] + fk.chest)
        self.set_bone_parent(fk.hips[0], master)

    @stage.configure_bones
    def configure_control_chain(self):
        fk = self.bones.ctrl.hips + self.bones.ctrl.chest
        for ctrl, org in zip(fk, self.bones.org):
            self.copy_bone_properties(org, ctrl)

    @stage.generate_widgets
    def make_control_widgets(self):
        fk = self.bones.ctrl
        for ctrl in fk.hips:
            self.make_control_widget(ctrl, True)
        for ctrl in fk.chest:
            self.make_control_widget(ctrl, False)

    def make_control_widget(self, ctrl: str, is_hip: bool):
        obj = create_circle_widget(self.obj, ctrl, radius=1.0, head_tail=0.5)
        if is_hip:
            adjust_widget_transform_mesh(obj, Matrix.Diagonal((1, -1, 1, 1)), local=True)

    ####################################################
    # MCH bones associated with main controls

    @stage.generate_bones
    def make_mch_control_bones(self):
        orgs = self.bones.org
        mch = self.bones.mch
        mch.pivot = self.copy_bone(orgs[1], make_derived_name(orgs[1], 'mch'), scale=0.5)
        ed_org = self.get_bone(orgs[1])
        mid_pos = (ed_org.head + ed_org.tail)/2
        put_bone(self.obj, mch.pivot, mid_pos)

    @stage.parent_bones
    def parent_mch_control_bones(self):
        mch = self.bones.mch
        org = self.bones.org
        self.set_bone_parent(org[1], mch.pivot)

    @stage.rig_bones
    def rig_mch_control_bones(self):
        mch = self.bones.mch
        fk = self.bones.ctrl
        self.make_constraint(mch.pivot, 'COPY_TRANSFORMS', fk.chest[1])
        self.make_constraint(mch.pivot, 'COPY_TRANSFORMS', fk.hips[0], influence=0.5)
        self.make_constraint(mch.pivot, 'DAMPED_TRACK', fk.chest[1])

    ####################################################
    # ORG bones
    @stage.parent_bones
    def parent_org_chain(self):
        fk = self.bones.ctrl
        for org, parent in zip(self.bones.org, fk.hips[:1] + [self.bones.mch.pivot] + fk.chest[-1:]):
            self.set_bone_parent(org, parent)

    ####################################################
    # Deform bones

    @stage.generate_bones
    def make_deform_chain(self):
        self.bones.deform = map_list(self.make_deform_bone, count(0), self.bones.org)

    def make_deform_bone(self, i: int, org: str):
        name = self.copy_bone(org, make_derived_name(org, 'def'), parent=True, bbone=True)
        if self.bbone_segments:
            self.get_bone(name).bbone_segments = self.bbone_segments
        return name

    @stage.parent_bones
    def parent_deform_chain(self):
        self.parent_bone_chain(self.bones.deform, use_connect=False)

    @stage.rig_bones
    def rig_deform_chain(self):
        for deform, org in zip(self.bones.deform, self.bones.org):
            self.make_constraint(deform, 'COPY_TRANSFORMS', org)

    @stage.configure_bones
    def configure_bbone_chain(self):
        self.get_bone(self.bones.deform[0]).bone.bbone_easein = 0.0
        

    ####################################################
    # SETTINGS

    @classmethod
    def add_parameters(cls, params):
        pass
    @classmethod
    def parameters_ui(cls, layout, params):
        pass