import trimesh
import numpy as np
import os

base_path = 'frontend/public/models/base_mannequin.obj'
out_dir = 'frontend/public/models/'

print("Loading base mesh...")
mesh = trimesh.load(base_path, force='mesh')
verts = mesh.vertices.copy()

def deform(verts, y_min, y_max, scale_x, scale_z):
    new_verts = verts.copy()
    center_y = (y_min + y_max) / 2.0
    spread = (y_max - y_min) / 2.0
    
    for i, v in enumerate(new_verts):
        y = v[1]
        if y_min <= y <= y_max:
            dist = abs(y - center_y) / spread
            weight = 0.5 * (1 + np.cos(dist * np.pi))
            
            sx = 1.0 + (scale_x - 1.0) * weight
            sz = 1.0 + (scale_z - 1.0) * weight
            
            new_verts[i][0] *= sx
            new_verts[i][2] *= sz
            
    return new_verts

body_types = {
    'hourglass_body.obj': [
        (130, 150, 1.05, 1.05), # Vai cân đối
        (90, 120, 0.85, 0.85),  # Eo siêu nhỏ
        (70, 95, 1.15, 1.15)    # Hông nở
    ],
    'pear_body.obj': [
        (130, 150, 0.9, 0.9),  # Vai nhỏ
        (90, 120, 0.95, 0.95),
        (70, 95, 1.3, 1.25)    # Hông rất nở
    ],
    'apple_body.obj': [
        (130, 150, 1.0, 1.0),
        (90, 120, 1.25, 1.25), # Vòng 2 lớn
        (70, 95, 0.9, 0.9)     # Hông nhỏ
    ],
    'rectangle_body.obj': [
        (130, 150, 1.0, 1.0),
        (90, 120, 1.05, 1.05), # Eo ít thắt
        (70, 95, 1.0, 1.0)
    ],
    'inverted_triangle_body.obj': [
        (130, 150, 1.25, 1.15),# Vai ngang rộng
        (90, 120, 0.95, 0.95),
        (70, 95, 0.85, 0.85)   # Hông hẹp
    ]
}

for name, deformations in body_types.items():
    deformed_verts = verts.copy()
    for (y_min, y_max, sx, sz) in deformations:
        deformed_verts = deform(deformed_verts, y_min, y_max, sx, sz)
    
    new_mesh = mesh.copy()
    new_mesh.vertices = deformed_verts
    new_mesh.export(os.path.join(out_dir, name))
    print(f"Exported {name}")
