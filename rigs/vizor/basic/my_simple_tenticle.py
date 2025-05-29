# SPDX-FileCopyrightText: 2014-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from itertools import count
from typing import Optional

from rigify.utils.bones import align_chain_x_axis, align_bone_orientation
from rigify.utils.widgets_basic import create_circle_widget
from rigify.utils.widgets import layout_widget_dropdown, create_registered_widget
from rigify.utils.layers import ControlLayersOption
from rigify.utils.naming import make_derived_name, strip_org
from rigify.utils.misc import map_list
from rigify.rigs.basic.raw_copy import RelinkConstraintsMixin

from rigify.base_rig import stage

from rigify.rigs.chain_rigs import TweakChainRig


class Rig(TweakChainRig, RelinkConstraintsMixin):
    copy_rotation_axes: tuple[bool, bool, bool]
    automate: bool
    separate_rotation: bool
    prop_bone: str
    min_chain_length = 1
    create_tweaks: bool
    create_ctrl: bool

    class MchBones(TweakChainRig.MchBones):
        rot: str

    bones: TweakChainRig.ToplevelBones[
        list[str],
        'TweakChainRig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]

    def initialize(self):
        super().initialize()

        self.copy_rotation_axes = self.params.copy_rotation_axes
        self.separate_rotation = self.params.separate_rotation
        self.create_tweaks = self.params.create_tweaks
        self.create_ctrl = self.params.create_ctrl
        if True not in self.copy_rotation_axes:
            self.automate = False
        else:
            self.automate = True

    # Prepare
    def prepare_bones(self):
        if self.params.roll_alignment == "automatic":
            align_chain_x_axis(self.obj, self.bones.org)
    
    ##############################
    # Control chain

    @stage.generate_bones
    def make_control_chain(self):
        if self.create_ctrl:
            super().make_control_chain()
    
    @stage.configure_bones
    def configure_control_chain(self):
        if self.create_ctrl:
            super().configure_control_chain()
    
    @stage.generate_widgets
    def make_control_widgets(self):
        if self.create_ctrl:
            super().make_control_widgets()

    def make_control_widget(self, i: int, ctrl: str):
        #create_circle_widget(self.obj, ctrl, radius=0.3, head_tail=0.5)
        if self.create_ctrl:
            create_registered_widget(self.obj, ctrl, self.params.fk_widget, radius=0.3, head_tail=0.5)
    ##############################
    # Tweak chain

    @stage.generate_bones
    def make_tweak_chain(self):
        if self.create_tweaks:
            super().make_tweak_chain()

    @stage.parent_bones
    def parent_tweak_chain(self):
        if self.create_tweaks:
            super().parent_tweak_chain()

    @stage.generate_widgets
    def make_tweak_widgets(self):
        if self.create_tweaks:
            super().make_tweak_widgets()

    ##############################
    # ORG chain

    # Parent
    @stage.parent_bones
    def parent_control_chain(self):
        # use_connect=False for backward compatibility
        if self.create_ctrl:
            self.parent_bone_chain(self.bones.ctrl.fk, use_connect=False)
        elif self.separate_rotation:
            self.set_bone_parent(self.bones.org[0], self.bones.mch.rot)

    # Configure
    @stage.configure_bones
    def configure_tweak_chain(self):
        if self.create_tweaks:
            super().configure_tweak_chain()

            ControlLayersOption.TWEAK.assign(self.params, self.obj, self.bones.ctrl.tweak)

    def configure_tweak_bone(self, i, tweak):
        if self.create_tweaks:
            super().configure_tweak_bone(i, tweak)

            # Backward compatibility
            self.get_bone(tweak).rotation_mode = 'QUATERNION'

    # Rig
    @stage.rig_bones
    def rig_control_chain(self):
        if self.create_ctrl:
            if self.automate:
                ctrls = self.bones.ctrl.fk
                for args in zip(count(0), ctrls, [None, *ctrls]):
                    self.rig_control_bone(*args)

    def rig_control_bone(self, _i: int, ctrl: str, prev_ctrl: Optional[str]):
        if prev_ctrl:
            self.make_constraint(
                ctrl, 'COPY_ROTATION', prev_ctrl,
                use_xyz=self.copy_rotation_axes,
                space='LOCAL', mix_mode='BEFORE',
            )


    ####################################################
    # Rotation follow

    @stage.generate_bones
    def generate_rot_mch(self):
        if self.separate_rotation:
            org = self.bones.org[0]
            self.bones.mch.rot = self.copy_bone(org, make_derived_name('ROT-' + strip_org(org), 'mch'), parent=True, scale=0.25)
    
    @stage.parent_bones
    def parent_mch_control_bones(self):
        if self.separate_rotation and self.create_ctrl:
            self.set_bone_parent(self.bones.ctrl.fk[0], self.bones.mch.rot)

    @stage.parent_bones
    def align_mch_follow_bone(self):
        if self.separate_rotation:
            align_bone_orientation(self.obj, self.bones.mch.rot, 'root')

    @stage.configure_bones
    def configure_mch_follow_bones(self):
        if self.separate_rotation and self.create_ctrl:
            controls = self.bones.ctrl.fk
            panel = self.script.panel_with_selected_check(self, controls)
            self.make_property(self.bones.ctrl.fk[0], 'root_follow', default=0.0)
            panel.custom_prop(self.bones.ctrl.fk[0], 'root_follow', text='root_follow', slider=True)

#    @stage.rig_bones
#    def rig_mch_follow_bones(self):

    def rig_bones(self):
        if self.separate_rotation:
            con = self.make_constraint(self.bones.mch.rot, 'COPY_ROTATION', 'root')

            if self.create_ctrl:
                self.make_driver(con, 'influence',
                            variables=[(self.bones.ctrl.fk[0], 'root_follow')], polynomial=[1, -1])
            
    ##############################
    #ORG bones RIG
    @stage.rig_bones
    def rig_org_chain(self):
        if self.separate_rotation:
            org = self.bones.org[0]
            #if relink constraint
            self.relink_bone_constraints(org)
            self.relink_move_constraints(org, self.bones.mch.rot, prefix='')

        if self.create_tweaks:
            super().rig_org_chain()
        elif self.create_ctrl:
            ctrls = self.bones.ctrl.fk
            for args in zip(count(0), self.bones.org, ctrls):
                self.rig_org_bone(*args)
    def rig_org_bone(self, i: int, org: str, ctrl: str):
        self.make_constraint(org, 'COPY_TRANSFORMS', ctrl)

    @classmethod
    def add_parameters(cls, params):
        """ Add the parameters of this rig type to the
            RigifyParameters PropertyGroup
        """
        params.copy_rotation_axes = bpy.props.BoolVectorProperty(
            size=3,
            description="Automation axes",
            default=tuple([i == 0 for i in range(0, 3)])
        )

        # Setting up extra tweak layers
        ControlLayersOption.TWEAK.add_parameters(params)

        items = [('automatic', 'Automatic', ''), ('manual', 'Manual', '')]
        params.roll_alignment = bpy.props.EnumProperty(items=items, name="Bone roll alignment", default='automatic')

        params.separate_rotation = bpy.props.BoolProperty(
            name='separate rotation',
            description='Add MCH to copy Rotation from Root bone',
            default=False
        )
        params.create_tweaks = bpy.props.BoolProperty(
            name='create tweaks',
            description='create tweak bones',
            default=False
        )
        params.create_ctrl = bpy.props.BoolProperty(
            name='create fk',
            description='create fk bones',
            default=True
        )
        
        params.fk_widget = bpy.props.StringProperty(
            name='widget fk select',
            description='select fk widget',
            default='circle'
        )

        cls.add_relink_constraints_params(params)

    @classmethod
    def parameters_ui(cls, layout, params):
        """ Create the ui for the rig parameters.
        """

        r = layout.row()
        r.prop(params, "roll_alignment")

        row = layout.row(align=True)
        for i, axis in enumerate(['x', 'y', 'z']):
            row.prop(params, "copy_rotation_axes", index=i, toggle=True, text=axis)

        row = layout.row()
        row.prop(params, 'separate_rotation')
        if params.separate_rotation:
            cls.add_relink_constraints_ui(layout, params)
            if params.relink_constraints:
                col = layout.column()
                col.label(text="All Constraints are moved to MCH bone", icon='INFO')
        

        layout.prop(params, 'create_ctrl')
        if params.create_ctrl:
            layout_widget_dropdown(layout, params, 'fk_widget')

            #option to create tweaks
            layout.prop(params, 'create_tweaks')
            if params.create_tweaks:
                ControlLayersOption.TWEAK.parameters_ui(layout, params)
        

        
        
        


def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Bone')
    bone.head[:] = 0.0000, 0.0000, 0.0000
    bone.tail[:] = 0.0000, 0.0000, 0.3333
    bone.roll = 0.0000
    bone.use_connect = False
    bones['Bone'] = bone.name

    bone = arm.edit_bones.new('Bone.002')
    bone.head[:] = 0.0000, 0.0000, 0.3333
    bone.tail[:] = 0.0000, 0.0000, 0.6667
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Bone']]
    bones['Bone.002'] = bone.name

    bone = arm.edit_bones.new('Bone.001')
    bone.head[:] = 0.0000, 0.0000, 0.6667
    bone.tail[:] = 0.0000, 0.0000, 1.0000
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Bone.002']]
    bones['Bone.001'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Bone']]
    pbone.rigify_type = 'limbs.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['Bone.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone
        if bcoll := arm.collections.active:
            bcoll.assign(bone)

    return bones
