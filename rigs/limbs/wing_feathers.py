import bpy
from bpy.types import PoseBone
from itertools import count

from rigify.base_rig import BaseRig, stage
from rigify.utils.misc import ArmatureObject, map_list
from rigify.utils.rig import is_rig_base_bone, connected_children_names
from rigify.utils.naming import make_derived_name

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
    '''This is a Feather Rig. A set of sibling bones that are looking stretch bone influenced by two controll bones.
       Plugin for this type of rig is used to add another set of intermediary bones to controll a bunch of siblings.
    '''
    class CtrlBones(BaseRig.CtrlBones):
        first: str
        last: str

    class MchBones(BaseRig.CtrlBones):
        stretch: str
        damp_targets: list[str]

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
        if len(self.bones.org) < 2:
            self.raise_error("Input to rig type must be two or more siblings")
        self.first_org = self.bones.org[0]
        self.last_org = self.bones.org[-1]

    # Master and secondary controlls
    @stage.generate_bones
    def make_main_controls(self):
        #self.first_org = self.bones.org[0]
        #self.last_org = self.bones.org[-1]

        self.bones.ctrl.first = self.copy_bone(self.first_org, make_derived_name(self.first_org, 'ctrl', '_first'), parent=True)
        self.bones.ctrl.last = self.copy_bone(self.last_org, make_derived_name(self.last_org, 'ctrl', '_last'), parent=True)
    
    @stage.rig_bones
    def rig_main_org_bones(self):
        #self.first_org = self.bones.org[0]
        #self.last_org = self.bones.org[-1]

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
        self.bones.deform = map_list(self.make_target_bone, count(0), self.bones.org[1:-1])
    def make_target_bone(self, i: int, bone: str):
        self.copy_bone(bone, make_derived_name(bone, 'mch', '_target'))