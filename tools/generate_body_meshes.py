import os
import trimesh
import numpy as np

def create_body_mesh(chest_scale, waist_scale, hip_scale):
    # Tạo các phần cơ thể cơ bản (Abstract 3D Mannequin)
    chest = trimesh.creation.capsule(height=0.3, radius=0.2 * chest_scale)
    chest.apply_translation([0, 1.2, 0])
    
    waist = trimesh.creation.capsule(height=0.2, radius=0.18 * waist_scale)
    waist.apply_translation([0, 0.9, 0])
    
    hips = trimesh.creation.capsule(height=0.3, radius=0.22 * hip_scale)
    hips.apply_translation([0, 0.6, 0])
    
    # Gộp lại thành 1 mesh
    mesh = trimesh.util.concatenate([chest, waist, hips])
    
    # Tô màu mesh mặc định (màu xám dịu)
    mesh.visual.vertex_colors = [180, 180, 180, 255]
    return mesh

out_dir = os.path.join(os.path.dirname(__file__), "../data/models")
os.makedirs(out_dir, exist_ok=True)

# 1. Quả Lê (Pear): Hông to, vai nhỏ
mesh_pear = create_body_mesh(0.8, 0.9, 1.3)
mesh_pear.export(os.path.join(out_dir, "pear_body.obj"))

# 2. Quả Táo (Apple): Tròn trịa, bụng to
mesh_apple = create_body_mesh(1.1, 1.4, 1.0)
mesh_apple.export(os.path.join(out_dir, "apple_body.obj"))

# 3. Đồng Hồ Cát (Hourglass): Ngực nở, eo thon, hông to
mesh_hourglass = create_body_mesh(1.2, 0.7, 1.2)
mesh_hourglass.export(os.path.join(out_dir, "hourglass_body.obj"))

# 4. Chữ Nhật (Rectangle): Ít đường cong
mesh_rectangle = create_body_mesh(1.0, 1.0, 1.0)
mesh_rectangle.export(os.path.join(out_dir, "rectangle_body.obj"))

# 5. Tam giác ngược (Inverted Triangle): Vai rộng, hông hẹp
mesh_inverted = create_body_mesh(1.3, 0.9, 0.8)
mesh_inverted.export(os.path.join(out_dir, "inverted_triangle_body.obj"))

print(f"[*] Đã tạo thành công 5 mô hình 3D (.obj) tại {out_dir}")
