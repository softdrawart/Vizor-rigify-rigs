import bpy

from rigify.rigs.spines.basic_spine import Rig as basic_spine
from rigify.rigs.spines.spine_rigs import BaseSpineRig

class Rig(basic_spine, BaseSpineRig):
    def get_master_control_pos(self, orgs: list[str]):
        return BaseSpineRig.get_master_control_pos(self, orgs)