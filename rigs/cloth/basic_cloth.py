from rigify.rigs.chain_rigs import TweakChainRig
from rigify.base_rig import stage
from rigify.utils.bones import make_derived_name, align_bone_orientation

class Rig(TweakChainRig):
    min_chain_length = 1

    class MchBones (TweakChainRig.MchBones):
        follow: str

    bones: TweakChainRig.ToplevelBones[
        list[str],
        'TweakChainRig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]
    
    @stage.generate_bones
    def make_mch_follow_bone(self):
        org = self.bones.org[0]
        self.bones.mch.follow = self.copy_bone(org, make_derived_name(org, 'mch', '_parent'), scale=1 / 4)
        mch = self.bones.mch.follow
        align_bone_orientation(self.obj, mch, 'root')

    @stage.rig_bones
    def rig_mch_follow_bone(self):
        mch = self.bones.mch.follow

        con = self.make_constraint(mch, 'COPY_ROTATION', 'root')

        self.make_driver(con, 'influence', variables=[(self.bones.ctrl.fk[0], 'FK_limb_follow')])
    
    @stage.configure_bones
    def configure_mch_follow_bone(self):
        fk = self.bones.ctrl.fk[0]
        panel = self.script.panel_with_selected_check(self, [fk])
        
        self.make_property(fk, 'FK_limb_follow', default=0.0)
        panel.custom_prop(fk, 'FK_limb_follow', text='FK Limb Follow', slider=True)
    
    @stage.parent_bones
    def parent_fk_to_mch(self):
        fk = self.bones.ctrl.fk[0]
        mch = self.bones.mch.follow
        fk_parent = self.get_bone_parent(fk)
        self.set_bone_parent(fk, mch)
        self.set_bone_parent(mch, fk_parent)