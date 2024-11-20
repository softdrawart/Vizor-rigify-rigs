import bpy
from rigify.base_rig import stage, BaseRig
import rigify.utils as utils

class Rig(BaseRig):

    def generate_bbone(self, name):
        #create bone
        bone_name = self.copy_bone(name, utils.naming.make_derived_name(name, 'def'))

        #set bbone stuff
        bone = self.get_bone(bone_name)
        bone.bbone_segments = self.params.example_bb_segs

        return bone_name

    def generate_control(self, name):
        #create bone
        bone_name = self.copy_bone(name, utils.naming.make_derived_name(name, 'ctrl'))

        #set orientation and size
        utils.bones.align_bone_to_axis(self.obj, bone_name, 'y', length=self.scale)
        return bone_name

    def generate_control_chain(self, names, include_head, include_tail):
        if include_head:
            chain_names = [self.generate_control(b) for b in names]
        else:
            chain_names = [self.generate_control(b) for b in names[1:]]
        if include_tail:
            chain_names.append(self.generate_control(names[-1]))
            utils.bones.put_bone(self.obj, chain_names[-1], self.get_bone(names[-1]).tail)
        return chain_names

    def initialize(self):
        self.scale = self.get_bone(self.base_bone).length * 0.25

    @stage.generate_bones
    def generate_chain_bones(self):
        base_chain = [self.base_bone] + utils.connected_children_names(self.obj, self.base_bone)
        self.bones.deform = [self.generate_bbone(b) for b in base_chain]
        self.bones.ctrl = self.generate_control_chain(base_chain, True, True)
        
    @stage.parent_bones
    def set_bone_relations(self):
        self.parent_bone_chain(self.bones.deform, use_connect=True, inherit_scale="NONE")
    
    @stage.configure_bones
    def set_layers(self):
        Rig.tweak.assign_rig(self, self.bones.ctrl) 

    @stage.rig_bones
    def add_constraints_and_drivers(self):
        prop_b = self.bones.ctrl[0]
        self.make_property(prop_b, 'stretch', default=1.0, min=0.0, max=1.0)

        panel = self.script.panel_with_selected_check(self, self.bones.ctrl)
        panel.custom_prop (prop_b, 'stretch', text='stretch', slider=True)

        for ctrl, deform in zip(self.bones.ctrl[1:], self.bones.deform):
            self.make_constraint(deform, "DAMPED_TRACK", ctrl)
            self.make_constraint(deform, "STRETCH_TO", ctrl, name=f'{deform}_stretch')
            self.make_driver(self.get_bone(deform).constraints[f'{deform}_stretch'], "influence", variables=[(prop_b, 'stretch')])
        '''
        for b, c1, c2 in zip(self.bones.deform, self.bones.ctrl, self.bones.ctrl[1:]):
            self.make_driver(self.get_bone(b), 'bbone_scalein[0]', variables=[utils.mechanism.driver_var_transform(self.obj, c1, type='SCALE_X', space='WORLD')])
            self.make_driver(self.get_bone(b), 'bbone_scalein[1]', variables=[utils.mechanism.driver_var_transform(self.obj, c1, type='SCALE_Y', space='WORLD')])
            self.make_driver(self.get_bone(b), 'bbone_scaleout[0]', variables=[utils.mechanism.driver_var_transform(self.obj, c2, type='SCALE_X', space='WORLD')])
            self.make_driver(self.get_bone(b), 'bbone_scaleout[1]', variables=[utils.mechanism.driver_var_transform(self.obj, c2, type='SCALE_Y', space='WORLD')])
        '''

    
    @stage.generate_widgets
    def generate_control_widgets(self):
        for ctrl in self.bones.ctrl: 
            utils.widgets_basic.create_cube_widget(self.obj, ctrl)
    
    @classmethod
    def add_parameters(self, params):
        """ Add the parameters of this rig type to the
            RigifyParameters PropertyGroup
        """
        
        params.example_bb_segs = bpy.props.IntProperty(
            name        = 'B-Bone Segments',
            default     = 3,
            min         = 1,
            description = 'Number of B-Bone segments'
        )
        
        Rig.tweak.add_parameters(params)

    @classmethod
    def parameters_ui(self, layout, params):
        """ Create the ui for the rig parameters."""

        layout.row().prop(params, 'example_bb_segs')
        Rig.tweak.parameters_ui(layout.row(), params)

Rig.tweak = utils.layers.ControlLayersOption('Tweak', description="Layers for the tweak controls to be on")