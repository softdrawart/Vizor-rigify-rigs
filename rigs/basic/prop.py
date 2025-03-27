import bpy
from bpy.types import PoseBone

from rigify.base_rig import BaseRig, stage
from rigify.utils.naming import make_derived_name
from rigify.utils.widgets import layout_widget_dropdown, create_registered_widget
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
            ctrl = self.bones.ctrl = self.copy_bone(org, make_derived_name(org, 'ctrl'))
            pbuild = SwitchParentBuilder(self.generator)
            if len(self.parent_bones_names) > 0:
                pbuild.build_child(self,ctrl,extra_parents=self.parent_bones_names, select_parent='root', exclude_self=True)
        #create deformer bone
        if self.make_deformer:
            org = self.bones.org
            self.bones.deform = self.copy_bone(org, make_derived_name(org, 'def'))


    #parent ORG bone to CTRL
    def parent_bones(self):
        if self.make_controller:
            org = self.bones.org
            ctrl = self.bones.ctrl
            self.set_bone_parent(org, ctrl)
    #copy parameters from ORG bones if present
    def configure_bones(self):
        if self.make_controller:
            ctrl = self.bones.ctrl
            org = self.bones.org
            self.copy_bone_properties(org, ctrl)
    #add Copy Tranform constraint of ORG bone to DEF bone
    def rig_bones(self):
        if self.make_deformer:
            org = self.bones.org
            deform = self.bones.deform
            self.make_constraint(deform,'COPY_TRANSFORMS', org)
    #generate widget based on the selection from parameter
    def generate_widgets(self):
        if self.make_controller:
            ctrl = self.bones.ctrl
            widget = self.params.widget_selection
            create_registered_widget(self.obj, ctrl, widget)
    


    @classmethod
    def add_parameters(cls, params):
        params.make_controller = bpy.props.BoolProperty("Controller", default=False, description="Create Controller Bone")
        params.make_deformer = bpy.props.BoolProperty("Deformer", default=False, description="Create Deformer Bone")
        params.widget_selection = bpy.props.StringProperty("Widget", description="Widget of controller bone")
        params.parents = bpy.props.StringProperty("Parents", default="torso, ORG-hand.L, ORG-hand.R", description="Parents for switching separated by , ")
    
    @classmethod
    def parameters_ui(cls, layout, params):
        row = layout.row()
        row.prop(params,'make_controller')

        if params.make_controller:
            layout_widget_dropdown(layout, params, 'widget_selection')
            layout.prop(params, 'parents')
        row = layout.row()
        row.prop(params,'make_deformer')
