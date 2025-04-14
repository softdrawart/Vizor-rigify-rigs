import bpy
from bpy.types import PoseBone

from rigify.base_rig import BaseRig, stage
from rigify.utils.bones import set_bone_widget_transform
from rigify.utils.naming import make_derived_name
from rigify.utils.widgets import layout_widget_dropdown, create_registered_widget
from rigify.utils.widgets_basic import create_pivot_widget
from rigify.utils.switch_parent import SwitchParentBuilder

class Rig(BaseRig):
    '''Controll bone with ability to Parent Switch between controllers from all rigs.
       Usefull for Props that need to be dynamically re-Parented.'''
    
    bones: BaseRig.ToplevelBones[
        str,
        'Rig.CtrlBones',
        'Rig.MchBones',
        str
    ]

    class CtrlBones(BaseRig.CtrlBones):
        master: str
        pivot: str

    class MchBones(BaseRig.MchBones):
        pass

    make_controller: bool
    make_deformer: bool
    parent_bones_names: list[str]

    def find_org_bones(self, bone: PoseBone):
        return bone.name
    
    def initialize(self):
        self.make_controller = self.params.make_controller
        self.make_deformer = self.params.make_deformer
        self.parent_bones_names = self.build_list()
    #forms a list of bone names from parameter
    def build_list(self):
        string = self.params.parents
        if isinstance(string, str):
            parents = [item.strip() for item in string.split(',')]
            return parents
        return []

    #generate CTRL bones and Switch Parent
    def generate_bones(self):
        #create controller bone
        if self.make_controller:
            org = self.bones.org
            ctrl = self.bones.ctrl.master = self.copy_bone(org, make_derived_name(org, 'ctrl'), parent=True)
            if self.params.make_pivot:
                self.bones.ctrl.pivot = self.copy_bone(org, make_derived_name(org, 'ctrl', '_pivot'))
            pbuild = SwitchParentBuilder(self.generator)
            if len(self.parent_bones_names) > 0:
                pbuild.build_child(self,ctrl,extra_parents=self.parent_bones_names, select_parent='root', exclude_self=True) #root is selected by default parent
            if self.params.inject:
                parent_rig = self.rigify_parent
                pbuild.register_parent(self, org, name=ctrl, exclude_self=True, inject_into=parent_rig)
        #create deformer bone
        if self.make_deformer:
            org = self.bones.org
            self.bones.deform = self.copy_bone(org, make_derived_name(org, 'def'))


    #parent ORG bone to CTRL
    def parent_bones(self):
        if self.make_controller:
            if self.params.make_pivot:
                self.set_bone_parent(self.bones.org, self.bones.ctrl.pivot)
                self.set_bone_parent(self.bones.ctrl.pivot, self.bones.ctrl.master)
            else:
                self.set_bone_parent(self.bones.org, self.bones.ctrl.master)
    #copy parameters from ORG bones if present
    def configure_bones(self):
        if self.make_controller:
            ctrl = self.bones.ctrl.master
            org = self.bones.org
            self.copy_bone_properties(org, ctrl)
    #add Copy Tranform constraint of ORG bone to DEF bone
    def rig_bones(self):
        if self.make_deformer:
            org = self.bones.org
            deform = self.bones.deform
            self.make_constraint(deform,'COPY_TRANSFORMS', org)
        if self.make_controller and self.params.make_pivot:
                self.make_constraint(self.bones.org,'COPY_LOCATION', 
                                     self.bones.ctrl.pivot, space='LOCAL',
                                     invert_xyz=(True,) * 3)
    #generate widget based on the selection from parameter
    def generate_widgets(self):
        if self.make_controller:
            if self.params.widget_selection != '':
                widget = self.params.widget_selection
                create_registered_widget(self.obj, self.bones.ctrl.master, widget)
            if self.params.make_pivot:
                create_pivot_widget(self.obj, self.bones.ctrl.pivot)
                set_bone_widget_transform(self.obj, self.bones.ctrl.master, self.bones.org)
    


    @classmethod
    def add_parameters(cls, params):
        params.make_controller = bpy.props.BoolProperty("Controller", default=False, description="Create Controller Bone")
        params.make_pivot = bpy.props.BoolProperty("Pivot", default=False, description="Create Pivot")
        params.make_deformer = bpy.props.BoolProperty("Deformer", default=False, description="Create Deformer Bone")
        params.widget_selection = bpy.props.StringProperty("Widget", description="Widget of controller bone", default='cube')
        params.parents = bpy.props.StringProperty("Parents", default="torso, ORG-spine, ORG-spine.003, ORG-spine.006, ORG-shoulder.L, ORG-hand.L", description="Parents for switching separated by , ")
        params.inject = bpy.props.BoolProperty("Inject", description="Inject this rig into Parent Rig", default=False)
    @classmethod
    def parameters_ui(cls, layout, params):
        row = layout.row()
        row.prop(params,'make_controller', text="Make Controller")

        if params.make_controller:
            layout_widget_dropdown(layout, params, 'widget_selection', text="Widget")
            layout.prop(params,'make_pivot', text="Make Pivot")
            layout.prop(params, 'parents', text="Parents")
            layout.prop(params, 'inject', text="Inject into parent")
        row = layout.row()
        row.prop(params,'make_deformer', text="Make Deformer")
