import bpy
from typing import Optional
from rigify.rigs.skin.skin_rigs import BaseSkinChainRigWithRotationOption
from rigify.base_rig import stage
from rigify.utils.rig import connected_children_names
from rigify.utils.misc import map_list
from rigify.utils.naming import make_derived_name
from itertools import count, repeat
from rigify.rigs.skin.skin_nodes import ControlBoneNode, ControlNodeEnd

class Rig(BaseSkinChainRigWithRotationOption):
    class MchBones (BaseSkinChainRigWithRotationOption.MchBones):
        handles: list[str]

    bones: BaseSkinChainRigWithRotationOption.ToplevelBones[
        list[str],
        'Rig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]

    control_node_chain: Optional[list[ControlBoneNode | None]]
    control_nodes: list[ControlBoneNode]

    def find_org_bones(self, bone) -> list[str]:
        return [bone.name] + connected_children_names(self.obj, bone.name)

    @stage.initialize
    def init_control_nodes(self):
        orgs = self.bones.org

        self.control_nodes = nodes = [
            *map_list(self.make_control_node, count(0), orgs, repeat(False)),
            self.make_control_node(len(orgs), orgs[-1], True),
        ]

        self.control_node_chain = None
    
    def make_control_node(self, i: int, org: str, is_end: bool) -> ControlBoneNode:
        bone = self.get_bone(org)
        name = make_derived_name(org,'ctrl', '_end' if is_end else '')
        pos = bone.tail if is_end else bone.head

        if i == 0:
            chain_end = ControlNodeEnd.START
        elif is_end:
            chain_end = ControlNodeEnd.END
        else:
            chain_end = ControlNodeEnd.MIDDLE

        return ControlBoneNode(
            self, org, name, point=pos, index=i, chain_end=chain_end
        )

    def get_node_chain_with_mirror(self):
        """Get node chain with connected node extensions at the ends."""
        if self.control_node_chain is not None:
            return self.control_node_chain

        nodes = self.control_nodes
        prev_link, self.prev_node, self.prev_corner = self.get_connected_node(nodes[0])
        next_link, self.next_node, self.next_corner = self.get_connected_node(nodes[-1])

        self.control_node_chain = [self.prev_node, *nodes, self.next_node]

        # Optimize connect next by sharing last handle mch
        if next_link and next_link.index == 0:
            assert isinstance(next_link.rig, Rig)
            self.next_chain_rig = next_link.rig
        else:
            self.next_chain_rig = None

        return self.control_node_chain
    
    #@stage.generate_bones
    def make_mch_handle_bones(self):
        mch = self.bones.mch
        #chain = self.get_node_chain_with_mirror()
        chain = self.control_nodes

        mch.handles = map_list(self.make_mch_handle_bone, count(0),
                                   chain, chain[1:], chain[2:])
        
    def make_mch_handle_bone(self, _i: int,
                             prev_node: Optional[ControlBoneNode],
                             node: ControlBoneNode,
                             next_node: Optional[ControlBoneNode]):
        name = self.copy_bone(node.org, make_derived_name(node.name, 'mch', '_handle'))
        return name