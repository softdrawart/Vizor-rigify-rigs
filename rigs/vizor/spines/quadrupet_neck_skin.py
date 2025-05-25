import bpy
from rigify.base_rig import BaseRig, stage
from rigify.rigs.spines.super_head import Rig as HeadRig
from math import radians

from bpy.types import PoseBone
from rigify.utils.misc import map_list, ArmatureObject
from rigify.utils.rig import is_rig_base_bone, connected_children_names
from rigify.utils.bones import is_same_position, put_bone, flip_bone, align_bone_orientation
from rigify.utils.naming import make_derived_name
from rigify.utils.widgets_basic import create_sphere_widget

from itertools import count

def bone_siblings(obj: ArmatureObject, bone: str) -> list[str]:
    """ Returns a list of the siblings of the given bone.
        This requires that the bones has a parent.
    """
    parent = obj.data.bones[bone].parent
    connected_siblings = connected_children_names(obj, parent.name)

    if parent is None:
        return []

    bones = []

    for b in parent.children:
        if b.name != bone and not is_rig_base_bone(obj, b.name) and b.name not in connected_siblings:
            bones += [b.name]

    return bones

class Rig(BaseRig):
    """ A "chain_skin" rig.  A set of sibling bones that move based on the parent chain rig.
        This is a control and deformation rig.
    """
    class MchBones(BaseRig.MchBones):
        tip: list[str]
        main: list[str]
        mid: str
        direction: str

    class CtrlBones(BaseRig.CtrlBones):
        tip: list[str]

    bones: BaseRig.ToplevelBones[
        list[str],
        'Rig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]

    def find_org_bones(self, bone: PoseBone) -> list[str]:
        base_head = bone.bone.head
        siblings = bone_siblings(self.obj, bone.name)

        # Sort list by name and distance
        siblings.sort()
        siblings.sort(key=lambda b: (self.get_bone(b).bone.head - base_head).length)

        return [bone.name] + siblings
        
    def initialize(self):
        org = self.bones.org
        if not isinstance(self.rigify_parent, HeadRig):
            self.raise_error('Parent rig of the {} must be Super Head Rig Type', org[0])
        parent_org = self.rigify_parent.bones.org
        required_bone_amount = 3 #len(parent_org) later change for dinamic rig
        if len(org) != required_bone_amount:
            self.raise_error('Amount of bones for {} must {}', org[0], required_bone_amount)
        for org, parent_org in zip(org, parent_org):
            if not is_same_position(self.obj, org, parent_org):
                self.raise_error('Bone {} and {} should be in the same position', org, parent_org)
    def prepare_bones(self):
        #set second bone to midle position
        ed1 = self.get_bone(self.bones.org[0]).tail
        ed2 = self.get_bone(self.bones.org[2]).tail
        mid_pos = (ed1 + ed2)/2
        self.get_bone(self.bones.org[1]).tail = mid_pos
        #parent org bones temporary
        parent_org = self.rigify_parent.bones.org
        for org, parent_org in zip(self.bones.org, parent_org):
            self.set_bone_parent(org, parent_org)

    def parent_bones(self):
        self.rig_parent_bone = parent = self.get_bone_parent(self.bones.org[0])
        self.rig_parent_parent_bone = self.get_bone_parent(parent) #either none or other rig parent bone
        #parent org bones temporary
        parent_org = self.rigify_parent.bones.deform
        for org, parent_org in zip(self.bones.org, parent_org):
            self.set_bone_parent(org, parent_org)
        
    ##############################
    # Tip bones MCH and CTRL
    @stage.generate_bones
    def make_tip_controls(self):
        self.bones.ctrl.tip = map_list(self.make_tip_contorol, self.bones.org)
    def make_tip_contorol(self, org:str):
        #copy and place at tail
        bone = self.copy_bone(org, make_derived_name(org, 'ctrl', '_tip'), scale=0.2)
        pos = self.get_bone(org).tail
        put_bone(self.obj, bone, pos)
        return bone
    @stage.generate_bones
    def make_tip_mchs(self):
        self.bones.mch.tip = map_list(self.make_tip_mch, self.bones.ctrl.tip, self.rigify_parent.bones.org)
        mid_ctrl = self.bones.ctrl.tip[1]
        self.bones.mch.mid = self.copy_bone(mid_ctrl, make_derived_name(mid_ctrl, 'mch', '_mid'), parent=True, scale=.5)
    def make_tip_mch(self, ctrl:str, align_bone:str):
        #copy and place at tail
        bone = self.copy_bone(ctrl, make_derived_name(ctrl, 'mch'), scale=1.2)
        align_bone_orientation(self.obj, bone, align_bone)
        return bone
    @stage.parent_bones
    def parent_tip_controlers(self):
        for i, ctrl, mch in zip(count(0), self.bones.ctrl.tip, self.bones.mch.tip):
            self.set_bone_parent(ctrl, mch)
    @stage.parent_bones
    def parent_tip_mch(self):
        mch = self.bones.mch.tip
        parent = self.rigify_parent.bones.ctrl
        self.set_bone_parent(mch[0], self.rig_parent_parent_bone)
        self.set_bone_parent(mch[-2], parent.neck)
        self.set_bone_parent(mch[-1], parent.head)
    @stage.rig_bones
    def rig_tip_mch_bones(self):
        mch = self.bones.mch.tip
        mid = self.bones.mch.mid
        ctrl = self.bones.ctrl.tip
        parent_org = self.rigify_parent.bones.org
        co = self.make_constraint(mch[0], 'TRANSFORM', parent_org[0], space='LOCAL', map_from='ROTATION', map_to='LOCATION')
        co.from_max_x_rot = radians(150)
        co.to_max_y = -.35
        co.to_max_z = -.09
        co.map_to_y_from = 'X'
        co.map_to_z_from = 'X'

        co = self.make_constraint(mch[2], 'TRANSFORM', parent_org[2], space='LOCAL', map_from='ROTATION', map_to='LOCATION')
        co.from_min_x_rot = radians(-100)
        co.from_max_x_rot = radians(100)
        co.to_min_y = -.2
        co.to_max_y = .2
        co.map_to_y_from = 'X'

        self.make_constraint(mid, 'COPY_LOCATION', ctrl[0], space='WORLD', influence=1.0)
        self.make_constraint(mid, 'COPY_LOCATION', ctrl[2], space='WORLD', influence=0.5)
    @stage.generate_widgets
    def make_tip_widgets(self):
        for tip in self.bones.ctrl.tip:
            create_sphere_widget(self.obj, tip)
    ##############################
    # Main MCHs
    @stage.generate_bones
    def make_mch_bones(self):
        self.bones.mch.main = map_list(self.make_mch_bone, self.bones.org)
    def make_mch_bone(self, org:str):
        #duplicate and flip org bones
        bone = self.copy_bone(org, make_derived_name(org, 'mch'))
        flip_bone(self.obj, bone)
        return bone
    @stage.parent_bones
    def parent_mch_bones(self):
        for child, parent in zip(self.bones.mch.main, self.rigify_parent.bones.deform):
            self.set_bone_parent(child, parent)
    @stage.rig_bones
    def rig_mch_bones(self):
        for mch, tip_ctrl, parent_org in zip(self.bones.mch.main, self.bones.ctrl.tip, self.rigify_parent.bones.org):
            self.make_constraint(mch, 'COPY_LOCATION', tip_ctrl)
            self.make_constraint(mch, 'DAMPED_TRACK', parent_org)
    ##############################
    # Direction mid MCH
    @stage.generate_bones
    def make_mid_direction_mch(self):
        mid_bone = self.bones.org[1]
        self.bones.mch.direction = self.copy_bone(mid_bone, make_derived_name(mid_bone, 'mch', '_direction'))
    def parent_mid_direction_mch(self):
        self.set_bone_parent(self.bones.mch.direction, self.bones.org[1])
    @stage.rig_bones
    def rig_mid_direction_mch(self):
        direction = self.bones.mch.direction
        self.make_constraint(direction, 'COPY_LOCATION', self.rigify_parent.bones.org[1])
        self.make_constraint(direction, 'DAMPED_TRACK',  self.bones.mch.mid)

        self.make_constraint(self.bones.mch.tip[1], 'COPY_LOCATION', direction, head_tail=1)
    ##############################
    # DEF bones
    @stage.generate_bones
    def make_def_bones(self):
        self.bones.deform = map_list(lambda b: self.copy_bone(b, make_derived_name(b, 'def'), parent=True), self.bones.org)
    @stage.rig_bones
    def rig_def_bones(self):
        for b, b2 in zip(self.bones.deform, self.bones.org):
            self.make_constraint(b, 'COPY_LOCATION', b2)
            self.make_constraint(b, 'COPY_ROTATION', b2)
    @stage.parent_bones
    def parent_def_bones(self):
        children = self.bones.deform
        parents = self.rigify_parent.bones.deform
        for i, child, parent in zip(count(0), children, parents):
            if i == 0:
                parent = self.rigify_parent.rigify_parent.bones.org[-1]
                self.set_bone_parent(children[0], make_derived_name(parent,'def'))
            else:
                self.set_bone_parent(child, parent)
    ##############################
    # ORG bones
    @stage.parent_bones
    def parent_mch_bones(self):
        for child, parent in zip(self.bones.org, self.bones.mch.main):
            self.set_bone_parent(child, parent)


def create_sample(obj):  # noqa
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('neck')
    bone.head = -0.0000, 0.2287, 0.1410
    bone.tail = -0.0000, 0.1653, 0.1599
    bone.roll = 0.0000
    bone.use_connect = False
    bones['neck'] = bone.name
    bone = arm.edit_bones.new('neck.001')
    bone.head = -0.0000, 0.1653, 0.1599
    bone.tail = -0.0000, 0.1140, 0.1910
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['neck']]
    bones['neck.001'] = bone.name
    bone = arm.edit_bones.new('skin3')
    bone.head = -0.0000, 0.1140, 0.1910
    bone.tail = -0.0000, 0.0210, 0.0390
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['neck']]
    bones['skin3'] = bone.name
    bone = arm.edit_bones.new('skin2')
    bone.head = -0.0000, 0.1653, 0.1599
    bone.tail = -0.0000, 0.1016, 0.0158
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['neck']]
    bones['skin2'] = bone.name
    bone = arm.edit_bones.new('skin1')
    bone.head = -0.0000, 0.2287, 0.1410
    bone.tail = -0.0000, 0.1960, -0.0122
    bone.roll = -3.1416
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['neck']]
    bones['skin1'] = bone.name
    bone = arm.edit_bones.new('head')
    bone.head = -0.0000, 0.1140, 0.1910
    bone.tail = -0.0000, 0.0227, 0.3671
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['neck.001']]
    bones['head'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['neck']]
    pbone.rigify_type = 'game.spines.super_head'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.connect_chain = False
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.enable_scale = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['neck.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['skin3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['skin2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['skin1']]
    pbone.rigify_type = 'vizor.spines.chain_skin'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['head']]
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
        bone.bbone_x = bone.bbone_z = bone.length * 0.05
        arm.edit_bones.active = bone
        if bcoll := arm.collections.active:
            bcoll.assign(bone)

    return bones
