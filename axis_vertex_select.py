bl_info = {
    "name": "Axis Vertex Select",
    "author": "r2detta",
    "version": (1, 2, 2),  # Version bumped to reflect new Snap to Middle feature
    "blender": (4, 3, 0),
    "location": "View3D > Tool Panel",
    "description": "Select vertices based on world axis and perform symmetry operations",
    "warning": "",
    "wiki_url": "",
    "category": "Mesh",
}

import bpy
import bmesh
import math
from mathutils import Vector

class AxisSelectProperties(bpy.types.PropertyGroup):
    x_pos: bpy.props.BoolProperty(name="X+", default=False)
    x_neg: bpy.props.BoolProperty(name="X-", default=False)
    y_pos: bpy.props.BoolProperty(name="Y+", default=False)
    y_neg: bpy.props.BoolProperty(name="Y-", default=False)
    z_pos: bpy.props.BoolProperty(name="Z+", default=False)
    z_neg: bpy.props.BoolProperty(name="Z-", default=False)
    
    use_x: bpy.props.BoolProperty(name="X", default=True)
    use_y: bpy.props.BoolProperty(name="Y", default=True)
    use_z: bpy.props.BoolProperty(name="Z", default=True)
    center_threshold: bpy.props.FloatProperty(
        name="Threshold (m)",
        description="Distance from center in meters",
        default=0.01,
        min=0.00001,
        soft_max=1.0,
        subtype='DISTANCE',
        unit='LENGTH'
    )
    
    sym_axis: bpy.props.EnumProperty(
        name="Symmetry Axis",
        items=[
            ('X', "X", "X Axis"),
            ('Y', "Y", "Y Axis"),
            ('Z', "Z", "Z Axis"),
        ],
        default='X',
        description="Axis for symmetry searching"
    )
    sym_threshold: bpy.props.FloatProperty(
        name="Search Threshold (m)",
        description="Distance to search for matching vertices",
        default=0.05,
        min=0.00001,
        soft_max=1.0,
        subtype='DISTANCE',
        unit='LENGTH'
    )


class OBJECT_OT_SelectAxisVertices(bpy.types.Operator):
    bl_idname = "object.select_axis_vertices"
    bl_label = "Select Vertices by Axis"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.axis_select_props
        obj = context.edit_object

        if not obj:
            self.report({'ERROR'}, "No object in edit mode!")
            return {'CANCELLED'}

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        if not any([props.x_pos, props.x_neg, props.y_pos, props.y_neg, props.z_pos, props.z_neg]):
            self.report({'WARNING'}, "No axis selected!")
            return {'CANCELLED'}

        for v in bm.verts:
            world_co = obj.matrix_world @ v.co
            select = True

            if props.x_pos and world_co.x <= 0:
                select = False
            if props.x_neg and world_co.x >= 0:
                select = False
            if props.y_pos and world_co.y <= 0:
                select = False
            if props.y_neg and world_co.y >= 0:
                select = False
            if props.z_pos and world_co.z <= 0:
                select = False
            if props.z_neg and world_co.z >= 0:
                select = False

            v.select = select

        bmesh.update_edit_mesh(mesh)
        return {'FINISHED'}

class OBJECT_OT_SelectCenterVertices(bpy.types.Operator):
    bl_idname = "object.select_center_vertices"
    bl_label = "Select Center Vertices"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.axis_select_props
        obj = context.edit_object

        if not obj:
            self.report({'ERROR'}, "No object in edit mode!")
            return {'CANCELLED'}

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        if not any([props.use_x, props.use_y, props.use_z]):
            self.report({'WARNING'}, "No axis selected for center threshold!")
            return {'CANCELLED'}

        threshold = props.center_threshold

        for v in bm.verts:
            world_co = obj.matrix_world @ v.co
            select = True

            if props.use_x and abs(world_co.x) > threshold:
                select = False
            if props.use_y and abs(world_co.y) > threshold:
                select = False
            if props.use_z and abs(world_co.z) > threshold:
                select = False

            v.select = select

        bmesh.update_edit_mesh(mesh)
        return {'FINISHED'}

class OBJECT_OT_SnapToSymmetry(bpy.types.Operator):
    bl_idname = "object.snap_to_symmetry"
    bl_label = "Snap to Symmetry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.axis_select_props
        obj = context.edit_object

        if not obj:
            self.report({'ERROR'}, "No object in edit mode!")
            return {'CANCELLED'}

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        
        all_verts = [v for v in bm.verts]
        selected_verts = [v for v in bm.verts if v.select]
        
        if not selected_verts:
            self.report({'WARNING'}, "No vertices selected!")
            return {'CANCELLED'}
        
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[props.sym_axis]
        axis_name = props.sym_axis
        threshold = props.sym_threshold
        
        matched_count = 0
        unmatched_count = 0
        
        for sel_vert in selected_verts:
            sel_world_co = obj.matrix_world @ sel_vert.co
            
            # Karşı taraftaki ideal konum (mirrored position)
            mirrored_co = sel_world_co.copy()
            mirrored_co[axis_idx] *= -1
            
            closest_vert = None
            min_distance = float('inf')
            
            # Tüm vertexler arasında karşı tarafta olanlara bakalım
            for other_vert in all_verts:
                if other_vert == sel_vert or other_vert.select:
                    continue
                
                other_world_co = obj.matrix_world @ other_vert.co
                
                # Sadece karşı tarafta olan vertexleri kontrol edelim
                if (sel_world_co[axis_idx] * other_world_co[axis_idx]) >= 0:
                    continue
                
                # İdeal simetrik konuma olan mesafeyi hesaplayalım (tüm eksenleri dikkate alarak)
                total_distance = 0
                for i in range(3):
                    diff = abs(mirrored_co[i] - other_world_co[i])
                    # Tüm eksenlerdeki farklar threshold değerinden küçük olmalı
                    if diff > threshold:
                        total_distance = float('inf')  # Threshold'u geçen herhangi bir eksen olursa, bu vertex uygun değil
                        break
                    total_distance += diff * diff  # Euclidean mesafe hesabı için kare toplamı
                
                # Eğer tüm eksenler için fark threshold içindeyse, toplam mesafeyi kullan
                if total_distance < float('inf'):
                    distance = math.sqrt(total_distance)
                    if distance < min_distance:
                        min_distance = distance
                        closest_vert = other_vert
            
            if closest_vert:
                other_world_co = obj.matrix_world @ closest_vert.co
                              
                new_co = list(other_world_co)
                new_co[axis_idx] = -other_world_co[axis_idx]
                
                new_local_co = obj.matrix_world.inverted() @ Vector(new_co)
                sel_vert.co = new_local_co
                matched_count += 1
            else:
                unmatched_count += 1
        
        bmesh.update_edit_mesh(mesh)
        
        self.report({'INFO'}, f"Snapped {matched_count} vertices. {unmatched_count} vertices had no match within threshold.")
        return {'FINISHED'}


class OBJECT_OT_SnapToMiddle(bpy.types.Operator):
    bl_idname = "object.snap_to_middle"
    bl_label = "Snap to Middle"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.axis_select_props
        obj = context.edit_object

        if not obj:
            self.report({'ERROR'}, "No object in edit mode!")
            return {'CANCELLED'}

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        
        selected_verts = [v for v in bm.verts if v.select]
        
        if not selected_verts:
            self.report({'WARNING'}, "No vertices selected!")
            return {'CANCELLED'}
        
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[props.sym_axis]
        snapped_count = 0
        
        for vert in selected_verts:
            world_co = obj.matrix_world @ vert.co
            
            # Seçili eksende koordinatı 0'a ayarla
            new_world_co = world_co.copy()
            new_world_co[axis_idx] = 0.0
            
            # Dünya koordinatlarını yerel koordinatlara çevir
            new_local_co = obj.matrix_world.inverted() @ Vector(new_world_co)
            vert.co = new_local_co
            snapped_count += 1
        
        bmesh.update_edit_mesh(mesh)
        
        self.report({'INFO'}, f"Snapped {snapped_count} vertices to middle (axis {props.sym_axis}).")
        return {'FINISHED'}


class VIEW3D_PT_AxisSelect(bpy.types.Panel):
    bl_label = "Axis Vertex Select"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.axis_select_props

        # X Axis
        box = layout.box()
        row = box.row()
        row.label(text="X Axis")
        row.prop(props, "x_pos", toggle=True, text="+")
        row.prop(props, "x_neg", toggle=True, text="-")

        # Y Axis
        box = layout.box()
        row = box.row()
        row.label(text="Y Axis")
        row.prop(props, "y_pos", toggle=True, text="+")
        row.prop(props, "y_neg", toggle=True, text="-")

        # Z Axis
        box = layout.box()
        row = box.row()
        row.label(text="Z Axis")
        row.prop(props, "z_pos", toggle=True, text="+")
        row.prop(props, "z_neg", toggle=True, text="-")

        layout.operator("object.select_axis_vertices", text="Select Vertices")

        # Center Threshold Selection
        layout.separator()
        box = layout.box()
        box.label(text="Center Selection")
        
        row = box.row()
        row.label(text="Axes:")
        row.prop(props, "use_x", toggle=True)
        row.prop(props, "use_y", toggle=True)
        row.prop(props, "use_z", toggle=True)
        
        box.prop(props, "center_threshold")
        box.operator("object.select_center_vertices", text="Select Center Vertices")
        
        # Symmetry Snap
        layout.separator()
        box = layout.box()
        box.label(text="Symmetry Snap")
        
        box.prop(props, "sym_axis", text="Mirror Axis")
        box.prop(props, "sym_threshold")
        box.operator("object.snap_to_symmetry", text="Snap to Symmetry")
        box.operator("object.snap_to_middle", text="Snap to Middle")

def register():
    bpy.utils.register_class(AxisSelectProperties)
    bpy.utils.register_class(OBJECT_OT_SelectAxisVertices)
    bpy.utils.register_class(OBJECT_OT_SelectCenterVertices)
    bpy.utils.register_class(OBJECT_OT_SnapToSymmetry)
    bpy.utils.register_class(OBJECT_OT_SnapToMiddle)
    bpy.utils.register_class(VIEW3D_PT_AxisSelect)
    bpy.types.Scene.axis_select_props = bpy.props.PointerProperty(type=AxisSelectProperties)

def unregister():
    bpy.utils.unregister_class(AxisSelectProperties)
    bpy.utils.unregister_class(OBJECT_OT_SelectAxisVertices)
    bpy.utils.unregister_class(OBJECT_OT_SelectCenterVertices)
    bpy.utils.unregister_class(OBJECT_OT_SnapToSymmetry)
    bpy.utils.unregister_class(OBJECT_OT_SnapToMiddle)
    bpy.utils.unregister_class(VIEW3D_PT_AxisSelect)
    del bpy.types.Scene.axis_select_props

if __name__ == "__main__":
    register()
