import bpy
import mathutils
from bpy.types import PoseBone
from itertools import count

from rigify.base_rig import BaseRig, stage, RigComponent
from rigify.utils.misc import ArmatureObject, map_list
from rigify.utils.rig import is_rig_base_bone, connected_children_names
from rigify.utils.bones import put_bone
from rigify.utils.naming import make_derived_name
from math import pi
from mathutils import Vector


#Important to have rigify type set to one of the bones of the siblings
#Base_bone will be first

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
    #This is a Feather Rig. A set of sibling bones that are looking at stretched bone influenced by two controll bones.

    cluster_controls = None
    rig_parent_bone: str
    org_bones: dict[str, list[str]] = {} #collection of org bones with its connected children
    ctrl_bones: list[list[str]] = [] #collection of org bones with its connected children

    class CtrlBones(BaseRig.CtrlBones):
        first: str #ctrl located at the head of the rig parent bone
        last: str

    class MchBones(BaseRig.CtrlBones):
        stretch: str
        damp_targets: list[str]
        damp_owners: list[str]
        first_parent: str
        last_parent: str

    bones: BaseRig.ToplevelBones[
        list[str],
        'Rig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]
            
    def create_cluster_control(self):
        return FeathersClusterControls(self)


    def find_org_bones(self, bone: PoseBone) -> list[str]:
        base_head = bone.bone.head
        siblings = bone_siblings(self.obj, bone.name)

        # Sort list by name and distance
        siblings.sort()
        siblings.sort(key=lambda b: (self.get_bone(b).bone.head - base_head).length)
        #collect all connected org bones of the wing
        for b in siblings:
            self.org_bones[b] = connected_children_names(self.obj, b.name)

        return [bone.name] + siblings
    
    def initialize(self):
        if len(self.bones.org) < 2:
            self.raise_error("Input to rig type must be two or more siblings")
        self.rig_parent_bone = self.get_bone_parent(self.base_bone)
        self.first_org = self.bones.org[0]
        self.last_org = self.bones.org[-1]
        #collect feather rigs and add sub_object to them so it can create rig from this cluster instance
        if self.cluster_controls is None:
            self.create_cluster_control()

    #Chain of fk bones
    @stage.generate_bones
    def make_fk_bones(self):
        for org_bone in self.bones.org:
            self.ctrl_bones.append(map_list(self.make_fk_bone(), count(0), [org_bone] + self.org_bones[org_bone]))
    def make_fk_bone(self, i: int, bone: str):
        if i == 0:
            self.copy_bone(bone, make_derived_name(bone, 'ctrl'), parent=True)
        else:
            self.copy_bone(bone, make_derived_name(bone, 'ctrl'))
    @stage.generate_bones
    def create_fk_mch_bones(self):
        map_list(self.create_fk_mch_bone(), count(0), self.bones.org)
    def create_fk_mch_bone(self, i: int, bone: str):
        self.copy_bone(bone, make_derived_name(bone, 'mch'), parent=True)
    @stage.parent_bones
    def parent_fk_bones(self):
        for i, fk_chain in enumerate(self.ctrl_bones):
            self.parent_bone_chain(fk_chain, use_connect=True)
            self.set_bone_parent(fk_chain[0], self.bones.mch.damp_owners[i])

        
    # Master and secondary controlls
    @stage.generate_bones
    def make_main_controls(self):
        self.bones.ctrl.first = self.copy_bone(self.first_org, make_derived_name(self.first_org, 'ctrl', '_first'), parent=True)
        self.bones.ctrl.last = self.copy_bone(self.last_org, make_derived_name(self.last_org, 'ctrl', '_last'), parent=True)
    
    @stage.rig_bones
    def rig_main_org_bones(self):
        self.make_constraint(self.first_org, 'COPY_TRANSFORMS', self.bones.ctrl.first)
        self.make_constraint(self.last_org, 'COPY_TRANSFORMS', self.bones.ctrl.last)
    #Stretch bone for target bones
    @stage.generate_bones
    def make_stretch_bone(self):
        #self.first_org = self.bones.org[0]
        #self.last_org = self.bones.org[-1]

        self.bones.mch.stretch = self.copy_bone(self.first_org, make_derived_name(self.first_org, 'mch', '_stretch'), parent=True)
        stretch_bone = self.get_bone(self.bones.mch.stretch)

        first_tail = self.get_bone(self.first_org).tail
        last_tail = self.get_bone(self.last_org).tail

        stretch_bone.head = first_tail
        stretch_bone.tail = last_tail
        stretch_bone.roll = 0
    @stage.rig_bones
    def rig_stretch_bone(self):
        self.make_constraint(self.bones.mch.stretch, 'COPY_LOCATION', self.bones.ctrl.first, head_tail=1.0)
        self.make_constraint(self.bones.mch.stretch, 'STRETCH_TO', self.bones.ctrl.last, head_tail=1.0, volume='NO_VOLUME')
    #target bones
    @stage.generate_bones
    def make_target_bones(self):
        self.bones.mch.damp_targets = map_list(self.make_target_bone, count(0), self.bones.org[1:-1])

    def make_target_bone(self, i: int, bone: str):
        tgt_bone = self.copy_bone(bone, make_derived_name(bone, 'mch', '_target'))
        new_pos = self.find_closest_projected_intersection(bone, self.bones.mch.stretch) #tgt bone will be placed at interseciton of feather bone and stretch bone
        if new_pos is None:
            self.raise_error(f"Cant find closest projection intersection for {bone}")
        put_bone(self.obj, tgt_bone, new_pos)
        return tgt_bone
    
    def find_closest_projected_intersection(self, bone2_name, bone1_name, projection_plane='XY'):
        """Finds the intersection of an extended line of bone2 with bone1, 
        projecting them onto a 2D plane."""
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
    def parent_tgt_bones(self):
        main = self.bones.mch.stretch
        tgt_bones = self.bones.mch.damp_targets
        for tgt in tgt_bones:
            self.set_bone_parent(tgt, main)
    @stage.rig_bones
    def rig_tgt_bones(self):
        owners = self.bones.mch.damp_owners #damped bones
        targets = self.bones.mch.damp_targets
        map_list(self.rig_tgt_bone(), count(0), owners, targets)
    def rig_tgt_bone(self, i: int, owner: str, target: str):
        return self.make_constraint(owner, 'DAMPED_TRACK', target)
    
class FeathersClusterControls(RigComponent):
    owner: Rig
    org_rig_list: dict[str, Rig] = {} #org parent of the rig basebone
    rig_count: int
    main_bone: str

    def __init__(self, owner: Rig):
        super().__init__(owner)
        self.find_cluster_rigs()
        self.sort_cluster_rigs()

    def _rec_parent_to_child_hierarchy(self, bones: list[str], last: str) -> list[str]:
        # Base case: If we have no parent in the list, we stop the recursion
        sorted_hierarchy = [last]  # Start with the last bone

        last_eb = self.get_bone(last)
        parent = last_eb.parent

        # If the parent is in the bones list, recursively add the parent
        if parent and parent.name in bones:
            sorted_hierarchy.extend(self._rec_parent_to_child_hierarchy(bones, parent.name))

        return sorted_hierarchy

    def sort(self, bones: list[str]) -> list[str]:
        sorted_list = []
        child = None

        # Find the last bone that has no children in the list
        for b in bones:
            eb = self.get_bone(b)
            # Check if the bone has no children in the bones list
            if len([ch.name for ch in eb.children if ch.name in bones]) == 0:
                child = b
                break

        # If no valid child is found, return an empty list (or handle accordingly)
        if not child:
            return []

        # Get the hierarchy starting from the last bone (leaf) upwards
        sorted_list = self._rec_parent_to_child_hierarchy(bones, child)

        return sorted_list

    def sort_cluster_rigs(self):
        sorted_org_rig_list: dict[str, Rig] = {}
        
        # Get the list of bone names from the dict keys
        bones = list(self.org_rig_list.keys())
        
        # Sort the bones using your sort function
        sorted_bones = self.sort(bones)
        
        # Rebuild the dict in sorted order
        for b in sorted_bones:
            sorted_org_rig_list[b] = self.org_rig_list[b]
        
        # Replace the original dict with the sorted one
        self.org_rig_list = sorted_org_rig_list
        
    def find_cluster_rigs(self):
        owner = self.owner
        owner.cluster_controls = self
        
        self.org_rig_list[owner.rig_parent_bone] = owner

        parent_rig = owner.rigify_parent
        if parent_rig:
            for rig in parent_rig.rigify_children:
                if isinstance(rig, Rig) and rig != owner:
                    rig.cluster_controls = self #sub-object instance
                    self.org_rig_list[rig.rigify_parent] = rig
        else:
            self.raise_error("Parent rig is required for this rig type to function properly")
        
        self.rig_count = len(self.org_rig_list)

    def generate_bones(self):
        self.get_mid_vector()
        self.generate_mid_bones()
    #UTILITY
    def get_mid_vector(self, head: Vector, joint: Vector, tail: Vector) -> Vector:
        """Compute the bisector direction for a mid-joint bone."""
        vec1 = (head - joint).normalized()
        vec2 = (tail - joint).normalized()

        if vec1.length == 0 or vec2.length == 0:
            return Vector((0, 0, 1))  # Fallback to default up vector if degenerate

        return (vec1 + vec2).normalized()
    def generate_mid_bones(self):
        """Create middle bone and auxiliary bone."""
        # create mid and aux bones for each org bone
        # for first bone of the org_rig_list we need to check for parent of org bone
        # if none set secondary bones to none otherwise create a mch bone and save set its name in the secondary bones list

        for i, parent_bone, rig in enumerate(self.org_rig_list):
            if i == 0:
                #add two mch for first and last bone of the rig
                rig.bones.mch.first_master = self.copy_bone(rig.first_org, make_derived_name(rig.first_org, 'mch', 'master_first'), parent=True)
                rig.bones.mch.first_follow = self.copy_bone(rig.first_org, make_derived_name(rig.first_org, 'mch', 'follow_first'), parent=True)

                rig.bones.mch.last_master = self.copy_bone(rig.last_org, make_derived_name(rig.last_org, 'mch', 'master_last'), parent=True)
                rig.bones.mch.last_follow = self.copy_bone(rig.last_org, make_derived_name(rig.last_org, 'mch', 'follow_last'), parent=True)
            else:
                #if parent bone of the rig has parent add mch
                if self.get_bone(parent_bone).parent:
                    rig.bones.mch.last_master = self.copy_bone(rig.last_org, make_derived_name(rig.last_org, 'mch', 'master_last'), parent=True)
                    rig.bones.mch.last_follow  = self.copy_bone(rig.last_org, make_derived_name(rig.last_org, 'mch', 'follow_last'), parent=True)


        mid_eb = bones.new(MID_BONE_NAME)
        aux_eb = bones.new(AUX_BONE_NAME)

        # Get reference bones
        bone1_eb = _bones.get_bone(obj, bone1)
        bone2_eb = _bones.get_bone(obj, bone2)

        if not bone1_eb or not bone2_eb:
            raise ValueError("Bone1 or Bone2 not found in the armature.")

        # Get positions
        head = bone1_eb.head
        joint = bone1_eb.tail  # Common joint
        tail = bone2_eb.tail

        # Compute bisector vector
        mid_vector = get_mid_vector(head, joint, tail)

        # Set bone positions
        mid_length = min(bone1_eb.length, bone2_eb.length) * 0.5
        mid_eb.head = joint
        mid_eb.tail = joint + mid_vector * mid_length

        aux_eb.head = mid_eb.head
        aux_eb.tail = mid_eb.tail
        aux_eb.length = aux_eb.length / 2

        # Set roll
        mid_eb.roll = (bone1_eb.roll + bone2_eb.roll) / 2
        aux_eb.roll = mid_eb.roll


    def parent_bones():
        """Set up parenting for the middle and auxiliary bones."""
        #parent aux bone org parent bone and mid bone to org bone 
        mid_eb = _bones.get_bone(obj, MID_BONE_NAME)
        aux_eb = _bones.get_bone(obj, AUX_BONE_NAME)
        bone1_eb = _bones.get_bone(obj, bone1)
        bone2_eb = _bones.get_bone(obj, bone2)

        if mid_eb and aux_eb and bone1_eb and bone2_eb:
            mid_eb.parent = bone1_eb
            aux_eb.parent = bone2_eb
        else:
            raise ValueError("One or more bones could not be found for parenting.")


    def rig_bones():
        """Add Copy Transforms constraint to aux bone."""
        # Add Copy Transforms constraint to mid bone to copy from aux bone
        copy_transforms = self.make_constraint(aux_pb, 'COPY_TRANSFORMS', MID_BONE_NAME, influence = 0.5)
        copy_transforms.target = obj
        copy_transforms.subtarget = MID_BONE_NAME
        copy_transforms.influence = 0.5

        bpy.ops.object.mode_set(mode='EDIT')  # Switch back to edit mode
    def prent_claster_bones(self):
        #parent first and last bone of the cluster rig to MCH mid and aux bones
        pass

