import bpy
from bpy.types import PoseBone
from rigify.utils.rig import is_rig_base_bone, connected_children_names
from rigify.utils.bones import put_bone
from rigify.base_rig import BaseRig, stage, RigComponent
from rigify.utils.naming import make_derived_name
from rigify.utils.misc import map_list
from itertools import count

import mathutils
from mathutils import Vector

class Rig(BaseRig):
    ''' This rig will collect metarig children bones of a feather rig bone and sort them by distance from the main
        org feather bone. So put main Feather rig bone to the right of the child bones. 
    '''
    create_stretch_mch: bool
    rig_parent_bone: str

    class CtrlBones(BaseRig.CtrlBones):
        first: str
        last: str

    class MchBones(BaseRig.MchBones):
        stretch: str
        damp_targets: list[str]
        damp_owners: list[str]
    
    bones: BaseRig.ToplevelBones[
        list[str],
        'Rig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]

    def find_org_bones(self, bone: PoseBone) -> list[str]:
        children = [b.name for b in bone.children] #get names of the children bones
        base_head = bone.bone.head
        children.sort()
        children.sort(key=lambda b: (self.get_bone(b).head - base_head).length)
        return children
    
    def initialize(self):
        feather_count = len(self.bones.org)
        if feather_count < 2:
            self.raise_error("input of a rig type feather must not less than 2 bones")
        if feather_count == 2:
            self.create_stretch_mch = False
        else:
            self.create_stretch_mch = True
        self.rig_parent_bone = self.get_bone_parent(self.bones.org[0])
    #CTRLS first & last
    @stage.generate_bones
    def make_ctrl_bones(self):
        org = self.bones.org
        
        if self.create_stretch_mch:

            org_length = sum(self.get_bone(b).length for b in connected_children_names(self.obj, org[0])) + self.get_bone(org[0]).length
            self.bones.ctrl.first = self.copy_bone(org[0], make_derived_name(org[0], 'ctrl', '_first'),length=org_length*1.1)
            
            org_length = sum(self.get_bone(b).length for b in connected_children_names(self.obj, org[-1])) + self.get_bone(org[-1]).length
            self.bones.ctrl.last = self.copy_bone(org[-1], make_derived_name(org[-1], 'ctrl', '_last'),length=org_length*1.1)
    @stage.parent_bones
    def parent_ctrl_bones(self):
        if self.create_stretch_mch:
            self.set_bone_parent(self.bones.ctrl.first, self.rig_parent_bone)
            self.set_bone_parent(self.bones.ctrl.last, self.rig_parent_bone)
    #MCH stretch bone
    @stage.generate_bones
    def make_mch_stretch_bone(self):
        if self.create_stretch_mch:
            self.bones.mch.stretch = stretch = self.copy_bone(self.base_bone, make_derived_name(self.base_bone, 'mch', '_stretch'))
            strech_eb = self.get_bone(stretch)
            first_eb = self.get_bone(self.bones.ctrl.first)
            last_eb = self.get_bone(self.bones.ctrl.last)
            strech_eb.head = first_eb.tail
            strech_eb.tail = last_eb.tail
    @stage.parent_bones
    def parent_mch_stretch_bone(self):
        if self.create_stretch_mch:
            self.set_bone_parent(self.bones.mch.stretch, self.bones.ctrl.first)
    @stage.rig_bones
    def rig_mch_stretch_bone(self):
        if self.create_stretch_mch:
            self.make_constraint(self.bones.mch.stretch, 'STRETCH_TO', self.bones.ctrl.last, head_tail=1.0)
    #MCH target bones
    @stage.generate_bones
    def make_target_bones(self):
        if self.create_stretch_mch:
            self.bones.mch.damp_targets = map_list(self.make_target_bone, count(0), self.bones.org[1:-1])

    def make_target_bone(self, i: int, bone: str):
        tgt_bone = self.copy_bone(bone, make_derived_name(bone, 'mch', '_target'))
        new_pos = self.find_closest_projected_intersection(bone, self.bones.mch.stretch) #tgt bone will be placed at interseciton of feather bone and stretch bone
        if new_pos is None:
            self.raise_error(f"Cant find closest projection intersection for {bone}")
        put_bone(self.obj, tgt_bone, new_pos)
        return tgt_bone
    
    def find_closest_projected_intersection(self, bone2_name, bone1_name, projection_plane='XY'):
        """Finds the intersection of an extended line of bone2 projected towards bone1 (2d plane)"""
        obj = self.obj
        bone1 = self.get_bone(bone1_name)
        bone2 = self.get_bone(bone2_name)
        
        mat = obj.matrix_world
        b1_head, b1_tail = mat @ bone1.head, mat @ bone1.tail
        b2_head, b2_tail = mat @ bone2.head, mat @ bone2.tail

        # Select projection plane
        if projection_plane == 'XY':
            b1_p1, b1_p2 = b1_head.xy, b1_tail.xy
            b2_p1, b2_p2 = b2_head.xy, b2_tail.xy
            z_coord = (b1_head.z + b1_tail.z + b2_head.z + b2_tail.z) / 4
        elif projection_plane == 'XZ':
            b1_p1, b1_p2 = b1_head.xz, b1_tail.xz
            b2_p1, b2_p2 = b2_head.xz, b2_tail.xz
            z_coord = (b1_head.y + b1_tail.y + b2_head.y + b2_tail.y) / 4
        elif projection_plane == 'YZ':
            b1_p1, b1_p2 = b1_head.yz, b1_tail.yz
            b2_p1, b2_p2 = b2_head.yz, b2_tail.yz
            z_coord = (b1_head.x + b1_tail.x + b2_head.x + b2_tail.x) / 4
        else:
            raise ValueError("Invalid projection plane. Use 'XY', 'XZ', or 'YZ'.")

        # Extend bone2 into an infinite line by treating it as a segment going to infinity
        def extend_point(p1, p2, factor=1000):
            """Extend a segment infinitely by moving points outward."""
            direction = (p2 - p1).normalized()
            return p1 - direction * factor, p2 + direction * factor

        extended_b2_p1, extended_b2_p2 = extend_point(b2_p1, b2_p2)

        # Find intersection of the extended line with bone1
        intersection = mathutils.geometry.intersect_line_line_2d(b1_p1, b1_p2, extended_b2_p1, extended_b2_p2)

        if intersection:
            # Convert 2D point back to 3D
            if projection_plane == 'XY':
                intersection_3d = mathutils.Vector((intersection.x, intersection.y, z_coord))
            elif projection_plane == 'XZ':
                intersection_3d = mathutils.Vector((intersection.x, z_coord, intersection.y))
            elif projection_plane == 'YZ':
                intersection_3d = mathutils.Vector((z_coord, intersection.x, intersection.y))

            # Ensure the intersection is on the finite bone1 segment
            closest_point, factor = mathutils.geometry.intersect_point_line(intersection_3d, b1_head, b1_tail)
            
            if 0.0 <= factor <= 1.0:
                return closest_point  # Valid intersection inside main_bone segment
            else:
                return b1_head if factor < 0 else b1_tail  # Use the closest bone1 endpoint

        return None  # No valid intersection
    @stage.parent_bones
    def parent_target_bones(self):
        if self.create_stretch_mch:
            stretch = self.bones.mch.stretch
            for tgt in self.bones.mch.damp_targets:
                self.set_bone_parent(tgt, stretch)

    #MCH damped bones
    @stage.generate_bones
    def make_damped_bones(self):
        if self.create_stretch_mch:
            self.bones.mch.damp_owners = map_list(self.make_damped_bone, count(0), self.bones.org[1:-1])
    def make_damped_bone(self, i: int, bone: str):
        damp_bone = self.copy_bone(bone, make_derived_name(bone, 'mch'), parent=True)
        return damp_bone
    @stage.rig_bones
    def rig_damped_bones(self):
        if self.create_stretch_mch:
            for owner, target in zip(self.bones.mch.damp_owners, self.bones.mch.damp_targets):
                self.make_constraint(owner, 'DAMPED_TRACK', target)