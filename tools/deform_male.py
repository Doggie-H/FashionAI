import trimesh
import numpy as np
import os

out_dir = 'frontend/public/models/'
base_male = 'frontend/public/models/base_male.obj'

print("Loading base male mesh...")
mesh = trimesh.load(base_male, force='mesh')
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
    'male_trapezoid.obj': [
        (145, 165, 1.05, 1.05), # Vai vừa
        (100, 130, 0.95, 0.95), # Eo gọn
        (80, 105, 0.95, 0.95)   # Hông gọn
    ],
    'male_inverted_triangle.obj': [
        (145, 165, 1.25, 1.15), # Vai siêu rộng (V-taper)
        (100, 130, 0.85, 0.85), # Eo nhỏ
        (80, 105, 0.9, 0.9)     # Hông nhỏ
    ],
    'male_rectangle.obj': [
        (145, 165, 1.0, 1.0),
        (100, 130, 1.05, 1.05), # Eo thẳng từ vai
        (80, 105, 1.05, 1.05)
    ],
    'male_triangle.obj': [
        (145, 165, 0.95, 0.95), # Vai nhỏ
        (100, 130, 1.1, 1.1),
        (80, 105, 1.2, 1.15)    # Hông/đùi to
    ],
    'male_oval.obj': [
        (145, 165, 1.0, 1.0),
        (100, 130, 1.35, 1.35), # Bụng to
        (80, 105, 1.15, 1.15)   # Hông/mông to
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
