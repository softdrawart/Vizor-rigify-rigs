import bpy
from bpy.types import PoseBone
from rigify.base_rig import stage, BaseRig, RigComponent
from rigify.utils.bones import TypedBoneDict

class Rig(BaseRig):
    cluster_control = None
    class CtrlBones(BaseRig.CtrlBones):
        eye: str
        top_eyelash: str
        bot_eyelash: str
    class OrgBones(TypedBoneDict):
        eye: str
        top_eyelash: str
        bot_eyelash: str
    class DeformBones(TypedBoneDict):
        eye: str
        top_eyelash: str
        bot_eyelash: str
    class MchBones(BaseRig.MchBones):
        eye: str
        top_eyelash: str
        bot_eyelash: str
    bones: BaseRig.ToplevelBones [
        'Rig.OrgBones',
        'Rig.CtrlBones',
        'Rig.MchBones',
        'Rig.DeformBones'
    ]
    def find_org_bones(self, bone: PoseBone) -> str:
        #find which org bone is higher which lower
        eye = bone.name
        top = bone.name
        bot = bone.name
        self.OrgBones(
            eye = bone.name,
            top_eyelash = bone.name,
            bot_eyelash = bone.name,
        )
        return bone.name
    def initialize(self):
        if not self.cluster_control:
            self.create_cluster_control()
    def create_cluster_control(self):
        return EyeClusterControl(self)
    
class EyeClusterControl(RigComponent):
    owner: Rig
    rig_list: list[Rig]
    rig_count: int

    main_bone: str #moving both eyes

    def __init__(self, owner: Rig):
        super().__init__(owner)
        self.find_cluster_rigs()

    def find_cluster_rigs(self):
        owner = self.owner
        owner.cluster_control = self
        self.rig_list = [owner]

        parent_rig = owner.rigify_parent
        if parent_rig:
            for rig in parent_rig.rigify_children:
                if isinstance(rig,Rig) and rig != owner:
                    rig.cluster_control = self
                    self.rig_list.append(rig)
        else:
            self.raise_error("Parent rig is required for this rig type to function properly")
        
        self.rig_count = len(self.rig_list)
    
    #UTILITY
    def generate_bones(self):
        self.main_bone = self.new_bone('sabaka')


