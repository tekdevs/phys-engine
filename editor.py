import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import json
import os
import time
import random
import subprocess
from engine import Vector3, SimpleLighting, make_tex, Platform, Ceiling, Pillar, Skybox, ray_aabb_intersection
from PIL import Image, ImageDraw, ImageFont

PANEL_BG = (0.08, 0.08, 0.08)
PANEL_DARK = (0.04, 0.04, 0.04)
PANEL_BORDER = (0.13, 0.13, 0.13)
HEADER_BG = (0.06, 0.06, 0.06)
ACCENT = (0.9, 0.9, 0.92)
ACCENT_HOVER = (1.0, 1.0, 1.0)
TEXT_COLOR = (0.85, 0.85, 0.85)
TEXT_DIM = (0.4, 0.4, 0.4)
TEXT_BRIGHT = (1.0, 1.0, 1.0)
GRID_COLOR = (0.15, 0.15, 0.15)
GIZMO_X = (1, 0.25, 0.25)
GIZMO_Y = (0.25, 1, 0.25)
GIZMO_Z = (0.25, 0.45, 1)
GIZMO_HOVER = (1, 1, 0.3)
SELECTION_COLOR = (1, 1, 0.3)
MAT_PINK = (0.86, 0.08, 0.24)
MAT_GRAY = (0.45, 0.45, 0.45)

FONT_SZ_SM = 13
FONT_SZ_MD = 14
FONT_SZ_LG = 15

def lerp(a, b, t):
    return a + (b - a) * t

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

texture_cache = {}
def get_text_tex(text, font_size=12, color=(255, 255, 255, 255)):
    key = (text, font_size, color)
    if key in texture_cache:
        return texture_cache[key]
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    dummy = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0] + 4
    th = bbox[3] - bbox[1] + 4
    img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((2, 2), text, font=font, fill=color)
    data = img.tobytes("raw", "RGBA", 0, -1)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    result = (tex, img.width, img.height)
    texture_cache[key] = result
    return result

class EditorCamera:
    def __init__(self):
        self.pos = Vector3(0, 6, 20)
        self.yaw = 30
        self.pitch = -20
        self.speed = 12
        self.mouse_sensitivity = 0.25

    def get_forward(self):
        return Vector3(
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            -math.sin(math.radians(self.pitch)),
            -math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        ).normalize()

    def get_right(self):
        return Vector3(math.cos(math.radians(self.yaw)), 0, math.sin(math.radians(self.yaw))).normalize()

    def look_at(self):
        f = self.get_forward()
        target = self.pos + f
        gluLookAt(self.pos.x, self.pos.y, self.pos.z, target.x, target.y, target.z, 0, 1, 0)

    def update(self, keys, delta_time, right_drag=False, mouse_delta=None, scroll=0, arrow_delta=None):
        if right_drag and mouse_delta:
            self.yaw += mouse_delta[0] * self.mouse_sensitivity
            self.pitch += mouse_delta[1] * self.mouse_sensitivity
            self.pitch = max(-89, min(89, self.pitch))
        if arrow_delta:
            self.yaw += arrow_delta[0] * 60 * delta_time
            self.pitch += arrow_delta[1] * 60 * delta_time
            self.pitch = max(-89, min(89, self.pitch))
        f = self.get_forward()
        ff = Vector3(f.x, 0, f.z).normalize()
        r = self.get_right()
        spd = self.speed * delta_time
        m = Vector3(0, 0, 0)
        if keys.get(glfw.KEY_W): m = m + ff * spd
        if keys.get(glfw.KEY_S): m = m - ff * spd
        if keys.get(glfw.KEY_A): m = m - r * spd
        if keys.get(glfw.KEY_D): m = m + r * spd
        if keys.get(glfw.KEY_Q): m.y -= spd
        if keys.get(glfw.KEY_E): m.y += spd
        self.pos = self.pos + m
        fwd = self.get_forward()
        self.pos = self.pos + fwd * scroll * 3.0

class SceneNode:
    def __init__(self, name="Node", pos=None):
        self.name = name
        self.pos = pos if pos else Vector3()
        self.rot = Vector3()
        self.scale = Vector3(1, 1, 1)
        self.parent = None
        self.children = []
        self.selected = False
        self.visible = True
        self.expanded = True
        self.color = (0.8, 0.8, 0.8)

    def get_world_pos(self):
        if self.parent:
            return self.parent.get_world_pos() + self.pos
        return self.pos

    def get_type_name(self):
        return "Node"

    def get_properties(self):
        return {"pos": self.pos}

    def apply_properties(self, props):
        if "pos" in props:
            self.pos = props["pos"]

    def render_scene(self): pass
    def render_selected(self): pass
    def get_bounds(self):
        p = self.get_world_pos()
        return (p, p)

    def to_dict(self):
        return {"type": self.get_type_name(), "name": self.name,
                "pos": [self.pos.x, self.pos.y, self.pos.z]}

    def from_dict(self, d):
        self.name = d.get("name", self.name)
        p = d.get("pos", [0, 0, 0])
        self.pos = Vector3(p[0], p[1], p[2])

class PillarNode(SceneNode):
    def __init__(self, pos=None):
        super().__init__("Pillar", pos)
        self.width = 1.5
        self.height = 4.0
        self.depth = 1.5
        self.color = (0.7, 0.7, 0.8)
        self.material = "pink"
        self.tex_id = 0

    def get_type_name(self):
        return "Pillar"

    def get_properties(self):
        return {"pos": self.pos, "width": self.width, "height": self.height, "depth": self.depth, "material": self.material}

    def apply_properties(self, props):
        if "pos" in props: self.pos = props["pos"]
        if "width" in props: self.width = props["width"]
        if "height" in props: self.height = props["height"]
        if "depth" in props: self.depth = props["depth"]
        if "material" in props: self.material = props["material"]

    def get_bounds(self):
        p = self.get_world_pos()
        hw, hh, hd = self.width/2, self.height/2, self.depth/2
        return (Vector3(p.x-hw, p.y-hh, p.z-hd), Vector3(p.x+hw, p.y+hh, p.z+hd))

    def render_scene(self):
        if not self.visible: return
        p = self.get_world_pos()
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        glColor3f(*self.color)
        if self.tex_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
        w, h, d = self.width/2, self.height/2, self.depth/2
        glBegin(GL_QUADS)
        box_faces = [
            ((0,0,1), [(-w,-h,d),(w,-h,d),(w,h,d),(-w,h,d)]),
            ((0,0,-1), [(-w,-h,-d),(w,-h,-d),(w,h,-d),(-w,h,-d)]),
            ((-1,0,0), [(-w,-h,-d),(-w,-h,d),(-w,h,d),(-w,h,-d)]),
            ((1,0,0), [(w,-h,-d),(w,-h,d),(w,h,d),(w,h,-d)]),
            ((0,1,0), [(-w,h,-d),(-w,h,d),(w,h,d),(w,h,-d)]),
            ((0,-1,0), [(-w,-h,-d),(-w,-h,d),(w,-h,d),(w,-h,-d)]),
        ]
        for (nx, ny, nz), verts in box_faces:
            glNormal3f(nx, ny, nz)
            if abs(nz) == 1:
                for v in verts:
                    glTexCoord2f((v[0]+w)/(2*w), (v[1]+h)/(2*h))
                    glVertex3f(v[0], v[1], v[2])
            elif abs(nx) == 1:
                for v in verts:
                    glTexCoord2f((v[2]+d)/(2*d), (v[1]+h)/(2*h))
                    glVertex3f(v[0], v[1], v[2])
            else:
                for v in verts:
                    glTexCoord2f((v[0]+w)/(2*w), (v[2]+d)/(2*d))
                    glVertex3f(v[0], v[1], v[2])
        glEnd()
        if self.tex_id:
            glDisable(GL_TEXTURE_2D)
        glPopMatrix()

    def render_selected(self):
        p = self.get_world_pos()
        ofs = 0.04
        w, h, d = self.width/2 + ofs, self.height/2 + ofs, self.depth/2 + ofs
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        glBegin(GL_LINE_LOOP)
        for v in [(-w,-h,-d),(w,-h,-d),(w,-h,d),(-w,-h,d)]: glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        glBegin(GL_LINE_LOOP)
        for v in [(-w,h,-d),(w,h,-d),(w,h,d),(-w,h,d)]: glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        for v1, v2 in [((-w,-h,-d),(-w,h,-d)),((w,-h,-d),(w,h,-d)),((w,-h,d),(w,h,d)),((-w,-h,d),(-w,h,d))]:
            glBegin(GL_LINES)
            glVertex3f(p.x+v1[0], p.y+v1[1], p.z+v1[2])
            glVertex3f(p.x+v2[0], p.y+v2[1], p.z+v2[2])
            glEnd()
        glLineWidth(1)
        glEnable(GL_LIGHTING)

    def to_dict(self):
        d = super().to_dict()
        d.update({"width": self.width, "height": self.height, "depth": self.depth, "material": self.material})
        return d

    def from_dict(self, d):
        super().from_dict(d)
        self.width = d.get("width", 1.5)
        self.height = d.get("height", 4.0)
        self.depth = d.get("depth", 1.5)
        self.material = d.get("material", "pink")

class PlatformNode(SceneNode):
    def __init__(self, pos=None):
        super().__init__("Platform", pos if pos else Vector3(0, -0.1, 0))
        self.size = 150
        self.color = (0.5, 0.5, 0.55)
        self.material = "gray"
        self.tex_id = 0

    def get_type_name(self):
        return "Platform"

    def get_properties(self):
        return {"pos": self.pos, "size": self.size, "material": self.material}

    def get_bounds(self):
        p = self.get_world_pos()
        s = self.size / 2
        return (Vector3(p.x-s, p.y-0.1, p.z-s), Vector3(p.x+s, p.y+0.1, p.z+s))

    def render_scene(self):
        if not self.visible: return
        p = self.get_world_pos()
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        glColor3f(*self.color)
        if self.tex_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
        half = self.size / 2
        glBegin(GL_QUADS)
        glNormal3f(0, 1, 0)
        glTexCoord2f(0, 0); glVertex3f(-half, 0, -half)
        glTexCoord2f(1, 0); glVertex3f(half, 0, -half)
        glTexCoord2f(1, 1); glVertex3f(half, 0, half)
        glTexCoord2f(0, 1); glVertex3f(-half, 0, half)
        glEnd()
        if self.tex_id:
            glDisable(GL_TEXTURE_2D)
        glPopMatrix()

    def render_selected(self):
        p = self.get_world_pos()
        half = self.size / 2
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        glBegin(GL_LINE_LOOP)
        for v in [(-half,0,-half),(half,0,-half),(half,0,half),(-half,0,half)]:
            glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        glLineWidth(1)
        glEnable(GL_LIGHTING)

    def to_dict(self):
        d = super().to_dict()
        d["size"] = self.size
        d["material"] = self.material
        return d

    def from_dict(self, d):
        super().from_dict(d)
        self.size = d.get("size", 150)
        self.material = d.get("material", "gray")


class PlayerSpawnNode(SceneNode):
    def __init__(self, pos=None):
        super().__init__("PlayerSpawn", pos if pos else Vector3(0, 1.5, 0))
        self.color = (0.2, 0.8, 1.0)
        self.material = "none"
        self.tex_id = 0

    def get_type_name(self):
        return "PlayerSpawn"

    def get_bounds(self):
        p = self.get_world_pos()
        return (Vector3(p.x-0.5, p.y-1.5, p.z-0.5), Vector3(p.x+0.5, p.y+0.5, p.z+0.5))

    def get_properties(self):
        return {"pos": self.pos, "material": self.material}

    def render_scene(self):
        if not self.visible: return
        p = self.get_world_pos()
        glDisable(GL_LIGHTING)
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        quad = gluNewQuadric()
        glColor3f(*self.color)
        gluCylinder(quad, 0.3, 0.3, 1.5, 12, 1)
        glTranslatef(0, 1.5, 0)
        gluSphere(quad, 0.3, 12, 12)
        glColor3f(1, 1, 1)
        glBegin(GL_LINES)
        glVertex3f(0, 0.3, 0); glVertex3f(0, 1.0, 0)
        glEnd()
        glBegin(GL_TRIANGLES)
        glVertex3f(0, 1.2, 0); glVertex3f(-0.15, 0.8, 0); glVertex3f(0.15, 0.8, 0)
        glEnd()
        gluDeleteQuadric(quad)
        glPopMatrix()
        glEnable(GL_LIGHTING)

    def render_selected(self):
        p = self.get_world_pos()
        ofs = 0.04
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        glBegin(GL_LINE_LOOP)
        for v in [(-0.5-ofs,-1.5-ofs,-0.5-ofs),(0.5+ofs,-1.5-ofs,-0.5-ofs),(0.5+ofs,0.5+ofs,-0.5-ofs),(-0.5-ofs,0.5+ofs,-0.5-ofs)]:
            glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        glBegin(GL_LINE_LOOP)
        for v in [(-0.5-ofs,-1.5-ofs,0.5+ofs),(0.5+ofs,-1.5-ofs,0.5+ofs),(0.5+ofs,0.5+ofs,0.5+ofs),(-0.5-ofs,0.5+ofs,0.5+ofs)]:
            glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        glLineWidth(1)
        glEnable(GL_LIGHTING)

class EnemyNode(SceneNode):
    def __init__(self, pos=None):
        super().__init__("Enemy", pos if pos else Vector3(0, 1.5, 0))
        self.color = (1.0, 0.2, 0.15)
        self.radius = 0.8
        self.material = "none"
        self.tex_id = 0

    def get_type_name(self):
        return "Enemy"

    def get_bounds(self):
        p = self.get_world_pos()
        r = self.radius
        return (Vector3(p.x-r, p.y-r, p.z-r), Vector3(p.x+r, p.y+r, p.z+r))

    def get_properties(self):
        return {"pos": self.pos, "radius": self.radius, "material": self.material}

    def render_scene(self):
        if not self.visible: return
        p = self.get_world_pos()
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        glColor3f(*self.color)
        quad = gluNewQuadric()
        gluSphere(quad, self.radius, 16, 16)
        gluDeleteQuadric(quad)
        glPopMatrix()

    def render_selected(self):
        p = self.get_world_pos()
        ofs = 0.04
        r = self.radius + ofs
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        glBegin(GL_LINE_LOOP)
        for v in [(-r,-r,-r),(r,-r,-r),(r,r,-r),(-r,r,-r)]:
            glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        glBegin(GL_LINE_LOOP)
        for v in [(-r,-r,r),(r,-r,r),(r,r,r),(-r,r,r)]:
            glVertex3f(p.x+v[0], p.y+v[1], p.z+v[2])
        glEnd()
        glLineWidth(1)
        glEnable(GL_LIGHTING)

    def to_dict(self):
        d = super().to_dict()
        d["radius"] = self.radius
        d["material"] = self.material
        return d

    def from_dict(self, d):
        super().from_dict(d)
        self.radius = d.get("radius", 0.8)
        self.material = d.get("material", "none")

class Gizmo:
    def __init__(self):
        self.axis_len = 2.0
        self.axis_thickness = 0.06
        self.cone_radius = 0.12
        self.cone_height = 0.3
        self.hover_axis = None
        self.drag_axis = None
        self.drag_plane_point = None
        self.drag_offset = Vector3()
        self.mode = "translate"
        self.handle_dl = None
        self.scale_handle_dl = None
        self._build_handle()
        self._build_scale_handle()

    def _build_scale_handle(self):
        self.scale_handle_dl = glGenLists(1)
        glNewList(self.scale_handle_dl, GL_COMPILE)
        quad = gluNewQuadric()
        gluCylinder(quad, self.axis_thickness, self.axis_thickness, self.axis_len - 0.3, 12, 1)
        glTranslatef(0, 0, self.axis_len - 0.3)
        s = 0.1
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, -s); glVertex3f(s, -s, -s)
        glVertex3f(s, s, -s); glVertex3f(-s, s, -s)
        glEnd()
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, s); glVertex3f(s, -s, s)
        glVertex3f(s, s, s); glVertex3f(-s, s, s)
        glEnd()
        for dx, dy, dz in [(-s,-s,-s,-s,-s,s),(s,-s,-s,s,-s,s),(s,s,-s,s,s,s),(-s,s,-s,-s,s,s)]:
            glBegin(GL_LINES)
            glVertex3f(dx,dy,dz); glVertex3f(dx,dy,dz)
            glEnd()
        gluDeleteQuadric(quad)
        glEndList()

    def _build_handle(self):
        self.handle_dl = glGenLists(1)
        glNewList(self.handle_dl, GL_COMPILE)
        quad = gluNewQuadric()
        gluCylinder(quad, self.axis_thickness, self.axis_thickness, self.axis_len - self.cone_height, 12, 1)
        glTranslatef(0, 0, self.axis_len - self.cone_height)
        gluCylinder(quad, self.cone_radius, 0.001, self.cone_height, 12, 1)
        gluDeleteQuadric(quad)
        glEndList()

    def ray_axis_distance(self, ray_origin, ray_dir, axis_origin, axis_dir):
        w0 = ray_origin - axis_origin
        a = ray_dir.dot(ray_dir)
        b = ray_dir.dot(axis_dir)
        c = axis_dir.dot(axis_dir)
        d = ray_dir.dot(w0)
        e = axis_dir.dot(w0)
        denom = a * c - b * b
        if abs(denom) < 1e-8:
            return (w0 - w0.dot(axis_dir) * axis_dir).length(), 0, 0
        t_ray = (b * e - c * d) / denom
        t_axis = (a * e - b * d) / denom
        closest_ray = ray_origin + ray_dir * t_ray
        closest_axis = axis_origin + axis_dir * t_axis
        dist = (closest_ray - closest_axis).length()
        return dist, t_ray, t_axis

    def hit_test(self, ray_origin, ray_dir, node_pos, scale=1.0):
        self.hover_axis = None
        best_dist = 0.3 * scale
        best_axis = None
        axes = [(Vector3(1, 0, 0), GIZMO_X), (Vector3(0, 1, 0), GIZMO_Y), (Vector3(0, 0, 1), GIZMO_Z)]
        for i, (ax_dir, col) in enumerate(axes):
            dist, tr, ta = self.ray_axis_distance(ray_origin, ray_dir, node_pos, ax_dir)
            if 0 <= ta <= self.axis_len and tr > 0 and dist < best_dist:
                best_dist = dist
                best_axis = i
        if best_axis is not None:
            self.hover_axis = best_axis
            return best_axis
        return None

    def start_drag(self, ray_origin, ray_dir, node_pos, axis_idx):
        self.drag_axis = axis_idx
        axes = [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)]
        ax_dir = axes[axis_idx]
        _, _, t_ax = self.ray_axis_distance(ray_origin, ray_dir, node_pos, ax_dir)
        self.drag_plane_point = node_pos + ax_dir * t_ax

    def update_drag(self, ray_origin, ray_dir, node_pos, axis_idx):
        axes = [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)]
        ax_dir = axes[axis_idx]
        _, _, t_ax = self.ray_axis_distance(ray_origin, ray_dir, node_pos, ax_dir)
        new_point = node_pos + ax_dir * t_ax
        delta = (new_point - self.drag_plane_point).dot(ax_dir)
        self.drag_plane_point = new_point
        return delta

    def end_drag(self):
        self.drag_axis = None

    def draw(self, pos, scale=1.0):
        if self.drag_axis is not None and self.drag_axis < 0:
            return
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        axes = [
            (Vector3(1, 0, 0), GIZMO_X),
            (Vector3(0, 1, 0), GIZMO_Y),
            (Vector3(0, 0, 1), GIZMO_Z),
        ]
        for i, (ax_dir, col) in enumerate(axes):
            if self.hover_axis == i or self.drag_axis == i:
                glColor3f(*GIZMO_HOVER)
            else:
                glColor3f(*col)
            glPushMatrix()
            glTranslatef(pos.x, pos.y, pos.z)
            if ax_dir.x: glRotatef(90, 0, 1, 0)
            elif ax_dir.y: glRotatef(-90, 1, 0, 0)
            glScalef(scale, scale, scale)
            dl = self.handle_dl if self.mode == "translate" else self.scale_handle_dl
            glCallList(dl)
            glPopMatrix()
        glEnable(GL_DEPTH_TEST)

class Editor:
    NODE_TYPES = {
        "Pillar": PillarNode,
        "Enemy": EnemyNode,
        "PlayerSpawn": PlayerSpawnNode,
        "Platform": PlatformNode,
    }

    def __init__(self, width=1400, height=900):
        self.width = width
        self.height = height
        self.nodes = []
        self.selected_node = None
        self.selected_nodes = set()
        self._select_anchor = None
        self.camera = EditorCamera()
        self.lighting = SimpleLighting()
        self.lighting.ambient_color = (0.35, 0.3, 0.4)
        self.lighting.diffuse_color = (0.8, 0.8, 0.9)
        self.lighting.light_direction = Vector3(1, 2, 1).normalize()
        self.gizmo = None
        self.skybox = None
        self.tex_floor = None
        self.tex_pillar = None
        self.running = True
        self.delta_time = 0
        self.last_time = time.time()
        self.mouse_x = 0
        self.mouse_y = 0
        self.right_dragging = False
        self.middle_dragging = False
        self.last_mouse = (0, 0)
        self.show_add_menu = False
        self.dragging_value = None
        self.left_dragging = False
        self.scene_file = ""
        self.show_save_dialog = False
        self.show_load_dialog = False
        self.message = ""
        self.message_timer = 0
        self.fps = 0
        self.fps_count = 0
        self.fps_time = 0
        self.expanded_nodes = set()
        self._editing_field = None
        self._edit_buffer = ""
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 50

        self._init_glfw()
        self._init_gl()
        self.gizmo = Gizmo()
        self._init_scene()
        self._resolve_materials()

    def _init_glfw(self):
        if not glfw.init():
            raise RuntimeError("Failed to init GLFW")
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)
        self.window = glfw.create_window(self.width, self.height, "Engine Editor", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Failed to create window")
        glfw.make_context_current(self.window)
        glfw.set_cursor_pos_callback(self.window, self._cursor_callback)
        glfw.set_mouse_button_callback(self.window, self._mouse_callback)
        glfw.set_scroll_callback(self.window, self._scroll_callback)
        glfw.set_key_callback(self.window, self._key_callback)
        glfw.set_window_size_callback(self.window, self._resize_callback)
        glfw.set_char_callback(self.window, self._char_callback)

    def _char_callback(self, window, char):
        if self._editing_field is not None:
            ch = chr(char)
            if ch == "-" and not self._edit_buffer.startswith("-"):
                self._edit_buffer = "-" + self._edit_buffer
            elif ch.isdigit() or ch == "." or ch == "-":
                self._edit_buffer += ch

    def _resize_callback(self, window, w, h):
        self.width = w
        self.height = h

    def _cursor_callback(self, window, x, y):
        self.mouse_x = x
        self.mouse_y = y

    def _mouse_callback(self, window, button, action, mods):
        if button == glfw.MOUSE_BUTTON_RIGHT:
            self.right_dragging = (action == glfw.PRESS)
        if button == glfw.MOUSE_BUTTON_MIDDLE:
            self.middle_dragging = (action == glfw.PRESS)
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.left_dragging = (action == glfw.PRESS)
            if action == glfw.PRESS:
                self._handle_left_click()
            else:
                self.gizmo.end_drag()
                self.dragging_value = None

    def _scroll_callback(self, window, x, y):
        self.camera.update({}, self.delta_time, scroll=y)

    def _key_callback(self, window, key, scancode, action, mods):
        if action == glfw.PRESS:
            if key == glfw.KEY_DELETE or key == glfw.KEY_BACKSPACE:
                self._delete_selected()
            elif key == glfw.KEY_E:
                self.gizmo.mode = "translate"
            elif key == glfw.KEY_F:
                self.gizmo.mode = "scale"
            elif key == glfw.KEY_G and self.selected_node:
                p = self.selected_node.get_world_pos()
                fwd = self.camera.get_forward()
                d = (p - self.camera.pos).length()
                self.camera.pos = p - fwd * max(d, 3)
            elif key == glfw.KEY_S and (mods & glfw.MOD_CONTROL):
                self._save_dialog()
            elif key == glfw.KEY_O and (mods & glfw.MOD_CONTROL):
                self._load_dialog()
            elif key == glfw.KEY_N and (mods & glfw.MOD_CONTROL):
                self._new_scene()
            elif key == glfw.KEY_Z and (mods & glfw.MOD_CONTROL):
                self._undo()
            elif key == glfw.KEY_Y and (mods & glfw.MOD_CONTROL):
                self._redo()
            if self._editing_field is not None:
                if key == glfw.KEY_ENTER or key == glfw.KEY_KP_ENTER:
                    self._finish_editing()
                elif key == glfw.KEY_ESCAPE:
                    self._cancel_editing()
                elif key == glfw.KEY_BACKSPACE:
                    self._edit_buffer = self._edit_buffer[:-1]
                elif key == glfw.KEY_MINUS:
                    self._edit_buffer += "-"
                elif key == glfw.KEY_PERIOD:
                    self._edit_buffer += "."

    def _init_gl(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        self.tex_floor = make_tex((65, 60, 70), (35, 30, 40))
        self.tex_pillar = make_tex((220, 0, 220), (35, 0, 55))
        self.material_tex = {
            "pink": self.tex_pillar,
            "gray": self.tex_floor,
            "none": 0,
        }

    def _resolve_materials(self):
        for node in self.nodes:
            if hasattr(node, 'material') and hasattr(node, 'tex_id'):
                node.tex_id = self.material_tex.get(node.material, 0)

    def _init_scene(self):
        pf = PlatformNode()
        pf.tex_id = self.tex_floor
        self.nodes.append(pf)
        ps = PlayerSpawnNode()
        self.nodes.append(ps)
        for _ in range(5):
            ex = random.uniform(-15, 15)
            ez = random.uniform(-15, 15)
            if abs(ex) < 4 and abs(ez) < 4:
                ex += 8 + random.uniform(0, 5)
            en = EnemyNode(Vector3(ex, 1.5, ez))
            self.nodes.append(en)
        for _ in range(6):
            px = random.uniform(-20, 20)
            pz = random.uniform(-20, 20)
            if abs(px) < 6 and abs(pz) < 6:
                px += 10
            ph = random.uniform(2.0, 6.0)
            pw = random.uniform(1.0, 3.0)
            pn = PillarNode(Vector3(px, ph/2, pz))
            pn.height = ph
            pn.width = pw
            pn.depth = pw
            pn.tex_id = self.tex_pillar
            self.nodes.append(pn)

    def _delete_selected(self):
        if self.selected_nodes:
            self._snapshot()
            for n in list(self.selected_nodes):
                if n in self.nodes:
                    self.nodes.remove(n)
            self.selected_nodes.clear()
            self.selected_node = None

    def _screen_to_ray(self, mx, my):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.width / self.height
        gluPerspective(60, aspect, 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.camera.look_at()
        viewport = glGetIntegerv(GL_VIEWPORT)
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        wy = viewport[3] - my
        try:
            near = gluUnProject(mx, wy, 0, modelview, projection, viewport)
            far = gluUnProject(mx, wy, 1, modelview, projection, viewport)
        except:
            return None, None
        origin = Vector3(near[0], near[1], near[2])
        fv = Vector3(far[0] - near[0], far[1] - near[1], far[2] - near[2])
        fl = fv.length()
        if fl < 1e-8: return None, None
        direction = fv * (1.0 / fl)
        return origin, direction

    def _raycast_scene(self, origin, direction):
        best_dist = 1e9
        best_node = None
        for node in self.nodes:
            if not node.visible:
                continue
            aabb_min, aabb_max = node.get_bounds()
            d = ray_aabb_intersection(origin, direction,
                (aabb_min.x, aabb_min.y, aabb_min.z),
                (aabb_max.x, aabb_max.y, aabb_max.z))
            if d is not None and 0 < d < best_dist:
                best_dist = d
                best_node = node
        return best_node, best_dist

    def _handle_left_click(self):
        mx, my = self.mouse_x, self.mouse_y
        ph = 34
        if my < ph:
            self._handle_toolbar_click(mx, my)
            return
        if mx < 250 and my > ph and my < self.height - 24:
            if self.show_add_menu:
                self._handle_add_menu_click(mx, my)
                return
            self._handle_hierarchy_click(mx, my - ph)
            return
        if mx > self.width - 280 and my > ph and my < self.height - 24:
            self._handle_inspector_click(mx, my)
            return
        self.show_add_menu = False
        origin, direction = self._screen_to_ray(mx, my)
        if origin is None: return
        if self.selected_node:
            gs = (self.selected_node.get_world_pos() - self.camera.pos).length() * 0.06
            hit = self.gizmo.hit_test(origin, direction, self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)))
            if hit is not None:
                self._snapshot()
                self.gizmo.start_drag(origin, direction, self.selected_node.get_world_pos(), hit)
                return
        node, dist = self._raycast_scene(origin, direction)
        shift = glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
        ctrl = glfw.get_key(self.window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS
        mode = "range" if shift else ("toggle" if ctrl else "set")
        if node:
            self._select_node(node, mode=mode)
        else:
            if mode == "set":
                self._select_node(None)

    def _handle_toolbar_click(self, mx, my):
        if 8 <= mx <= 58 and 5 <= my <= 29:
            self._play_game()
        elif 64 <= mx <= 112 and 5 <= my <= 29:
            self.show_add_menu = not self.show_add_menu
        elif 118 <= mx <= 170 and 5 <= my <= 29:
            self._save_dialog()
        elif 174 <= mx <= 226 and 5 <= my <= 29:
            self._load_dialog()
        elif 230 <= mx <= 256 and 5 <= my <= 29:
            self._new_scene()

    def _handle_add_menu_click(self, mx, mouse_y):
        x, y = 0, 32
        pw = 250
        ph = self.height - 32 - 24
        menu_y = y + ph - 130
        if menu_y < 60: menu_y = 60
        items = ["Pillar", "PlayerSpawn", "Enemy", "Platform"]
        for i, item in enumerate(items):
            iy = menu_y + 4 + i * 26
            if x + 8 <= mx <= x + 8 + 126 and iy <= mouse_y <= iy + 24:
                self._add_node(item)
                self.show_add_menu = False
                return
        self.show_add_menu = False

    def _add_node(self, type_name):
        self._snapshot()
        fwd = self.camera.get_forward()
        pos = self.camera.pos + fwd * 10
        pos.y = 1.5
        cls = self.NODE_TYPES.get(type_name)
        if not cls: return
        node = cls(pos)
        if type_name in ("Pillar",):
            if hasattr(node, 'tex_id'):
                node.tex_id = self.tex_pillar
        if type_name in ("Platform",):
            if hasattr(node, 'tex_id'):
                node.tex_id = self.tex_floor
        self.nodes.append(node)
        self._resolve_materials()
        self._select_node(node)

    def _apply_scale(self, node, axis, delta):
        if hasattr(node, "width"):
            dims = [node.width, node.height, node.depth]
            factor = 1.0 + delta / max(dims[axis], 0.01)
            dims[axis] = max(0.1, dims[axis] * factor)
            node.width, node.height, node.depth = dims[0], dims[1], dims[2]
        elif hasattr(node, "size"):
            factor = 1.0 + delta / max(node.size, 0.01)
            node.size = max(0.1, node.size * factor)
        elif hasattr(node, "radius"):
            factor = 1.0 + delta / max(node.radius, 0.01)
            node.radius = max(0.1, node.radius * factor)

    def _handle_inspector_click(self, mx, my):
        node = self.selected_node
        if not node:
            return
        props = node.get_properties()
        x = self.width - 280
        cy = 78
        line_h = 22
        for key, val in props.items():
            if key == "pos" and isinstance(val, Vector3):
                pos = val
                for i, (label, axis) in enumerate([("X", 0), ("Y", 1), ("Z", 2)]):
                    fx = x + 90 + i * 62
                    fw = 60
                    if fx <= mx <= fx + fw and cy + 1 <= my <= cy + line_h - 1:
                        self._snapshot()
                        self._editing_field = ("pos", i, node)
                        self._edit_buffer = str([pos.x, pos.y, pos.z][i])
                        return
                cy += line_h + 3
            elif isinstance(val, (int, float)):
                vx = x + 110
                vw = 146
                if vx <= mx <= vx + vw and cy + 1 <= my <= cy + line_h - 1:
                    self._snapshot()
                    self._editing_field = (key, None, node)
                    self._edit_buffer = str(val)
                    return
                cy += line_h + 3
            elif key == "material" and isinstance(val, str):
                sw = 28
                mats = ["pink", "gray"]
                for mi, mname in enumerate(mats):
                    sx = x + 100 + mi * (sw + 6)
                    if sx <= mx <= sx + sw and cy + 1 <= my <= cy + line_h - 1:
                        self._snapshot()
                        node.material = mname
                        self._resolve_materials()
                        return
                cy += line_h + 3
            else:
                cy += line_h + 3

    def _handle_hierarchy_click(self, mx, my):
        shift = glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
        ctrl = glfw.get_key(self.window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS
        mode = "range" if shift else ("toggle" if ctrl else "set")
        header_off = 38
        for i, node in enumerate(self.nodes):
            y = header_off + i * 22
            if y <= my < y + 22:
                self._select_node(node, mode=mode)
                return

    def _select_node(self, node, mode="set"):
        if mode == "toggle":
            if node:
                node.selected = not node.selected
                if node.selected:
                    self.selected_nodes.add(node)
                else:
                    self.selected_nodes.discard(node)
                if node.selected:
                    self.selected_node = node
                elif self.selected_nodes:
                    self.selected_node = next(iter(self.selected_nodes))
                else:
                    self.selected_node = None
        elif mode == "range" and node and self._select_anchor is not None:
            anchor_idx = -1
            click_idx = -1
            for i, n in enumerate(self.nodes):
                if n == self._select_anchor:
                    anchor_idx = i
                if n == node:
                    click_idx = i
            if anchor_idx != -1 and click_idx != -1:
                start = min(anchor_idx, click_idx)
                end = max(anchor_idx, click_idx)
                for n in self.nodes:
                    n.selected = False
                self.selected_nodes.clear()
                for i in range(start, end + 1):
                    n = self.nodes[i]
                    n.selected = True
                    self.selected_nodes.add(n)
                self.selected_node = node
        else:
            for n in self.nodes:
                n.selected = False
            self.selected_nodes.clear()
            if node:
                node.selected = True
                self.selected_nodes.add(node)
                self._select_anchor = node
            self.selected_node = node if node else (next(iter(self.selected_nodes)) if self.selected_nodes else None)

    def _save_dialog(self):
        from tkinter import filedialog, Tk
        root = Tk()
        root.withdraw()
        fp = filedialog.asksaveasfilename(defaultextension=".scene", filetypes=[("Scene", "*.scene")])
        root.destroy()
        if fp:
            self.save_scene(fp)

    def _load_dialog(self):
        from tkinter import filedialog, Tk
        root = Tk()
        root.withdraw()
        fp = filedialog.askopenfilename(filetypes=[("Scene", "*.scene")])
        root.destroy()
        if fp:
            self.load_scene(fp)

    def _play_game(self):
        self._set_message("Launching game...")
        temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_scene.scene")
        self.save_scene(temp_path)
        subprocess.Popen(["python", "game.py", temp_path], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _new_scene(self):
        self.nodes = []
        self.selected_node = None
        self.selected_nodes.clear()
        self._init_scene()
        self._set_message("New scene created")

    def _set_message(self, msg):
        self.message = msg
        self.message_timer = 3.0

    def _finish_editing(self):
        if self._editing_field is not None:
            key, axis, node = self._editing_field
            try:
                val = float(self._edit_buffer)
                if key == "pos" and axis is not None:
                    v = [node.pos.x, node.pos.y, node.pos.z]
                    v[axis] = val
                    node.pos = Vector3(v[0], v[1], v[2])
                elif isinstance(key, str) and hasattr(node, key):
                    setattr(node, key, val)
            except ValueError:
                pass
            if key == "material" and isinstance(key, str):
                self._resolve_materials()
        self._editing_field = None
        self._edit_buffer = ""

    def _cancel_editing(self):
        self._editing_field = None
        self._edit_buffer = ""

    def _snapshot(self):
        state = json.dumps([n.to_dict() for n in self.nodes])
        if self.undo_stack and self.undo_stack[-1] == state:
            return
        self.undo_stack.append(state)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

    def _load_state_from(self, state):
        data = json.loads(state)
        self.nodes = []
        self.selected_node = None
        self.selected_nodes.clear()
        for d in data:
            t = d.get("type", "Pillar")
            cls = self.NODE_TYPES.get(t)
            if cls:
                node = cls()
                node.from_dict(d)
                self.nodes.append(node)
        self._resolve_materials()

    def _undo(self):
        if not self.undo_stack:
            return
        current = json.dumps([n.to_dict() for n in self.nodes])
        self.redo_stack.append(current)
        state = self.undo_stack.pop()
        self._load_state_from(state)

    def _redo(self):
        if not self.redo_stack:
            return
        current = json.dumps([n.to_dict() for n in self.nodes])
        self.undo_stack.append(current)
        state = self.redo_stack.pop()
        self._load_state_from(state)

    def save_scene(self, path):
        data = [n.to_dict() for n in self.nodes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._set_message(f"Saved: {os.path.basename(path)}")

    def load_scene(self, path):
        with open(path, "r") as f:
            data = json.load(f)
        self.nodes = []
        self.selected_node = None
        for d in data:
            t = d.get("type", "Pillar")
            cls = self.NODE_TYPES.get(t)
            if cls:
                node = cls()
                node.from_dict(d)
                self.nodes.append(node)
        self._resolve_materials()
        self._set_message(f"Loaded: {os.path.basename(path)}")

    def _draw_rect(self, x, y, w, h, color, border_color=None):
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_LIGHTING)
        glBegin(GL_QUADS)
        glColor3f(*color)
        glVertex2f(x, y)
        glVertex2f(x + w, y)
        glVertex2f(x + w, y + h)
        glVertex2f(x, y + h)
        glEnd()
        if border_color:
            glColor3f(*border_color)
            glLineWidth(1)
            glBegin(GL_LINE_LOOP)
            glVertex2f(x, y)
            glVertex2f(x + w, y)
            glVertex2f(x + w, y + h)
            glVertex2f(x, y + h)
            glEnd()

    def _draw_text(self, x, y, text, color=(1, 1, 1), size=12):
        tc = (int(color[0]*255), int(color[1]*255), int(color[2]*255), 255)
        tex, tw, th = get_text_tex(text, size, tc)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBindTexture(GL_TEXTURE_2D, tex)
        glColor3f(1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex2f(x, y)
        glTexCoord2f(1, 1); glVertex2f(x + tw, y)
        glTexCoord2f(1, 0); glVertex2f(x + tw, y + th)
        glTexCoord2f(0, 0); glVertex2f(x, y + th)
        glEnd()
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)
        return tw, th

    def _ortho_mode(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)

    def _ortho_end(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def _render_grid(self):
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBegin(GL_LINES)
        n = 30
        spacing = 2.0
        for i in range(-n, n + 1):
            alpha = 0.3 if i % 5 == 0 else 0.1
            glColor4f(*GRID_COLOR, alpha)
            glVertex3f(i * spacing, 0, -n * spacing)
            glVertex3f(i * spacing, 0, n * spacing)
            glVertex3f(-n * spacing, 0, i * spacing)
            glVertex3f(n * spacing, 0, i * spacing)
        glEnd()
        glDisable(GL_BLEND)

    def render_scene(self):
        viewport_w = self.width
        viewport_h = self.height
        glViewport(0, 0, viewport_w, viewport_h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = viewport_w / viewport_h if viewport_h > 0 else 1
        gluPerspective(60, aspect, 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)
        glClearColor(0.08, 0.08, 0.1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        self.camera.look_at()
        if self.skybox:
            self.skybox.draw(self.camera.pos)
        self.lighting.enable()
        self._render_grid()
        for node in self.nodes:
            node.render_scene()
        for node in self.nodes:
            if node.selected:
                node.render_selected()
        if self.selected_node:
            gs = (self.selected_node.get_world_pos() - self.camera.pos).length() * 0.06
            self.gizmo.draw(self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)))

    def render_toolbar(self):
        h = 34
        self._draw_rect(0, 0, self.width, h, PANEL_DARK, PANEL_BORDER)
        btn_h = 24
        btn_y = 5
        self._draw_rect(8, btn_y, 50, btn_h, (0.15, 0.15, 0.15), PANEL_BORDER)
        self._draw_text(16, btn_y + 4, "Play", (0.3, 0.85, 0.3), FONT_SZ_MD)
        self._draw_rect(64, btn_y, 48, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(70, btn_y + 4, "+ Add", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(118, btn_y, 52, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(124, btn_y + 4, "Save", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(174, btn_y, 52, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(180, btn_y + 4, "Load", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(230, btn_y, 26, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(235, btn_y + 4, "N", TEXT_COLOR, FONT_SZ_SM)
        fps_text = f"FPS: {self.fps}"
        self._draw_text(self.width - 100, btn_y + 4, fps_text, TEXT_DIM, FONT_SZ_SM)
        if self.message and self.message_timer > 0:
            self._draw_text(self.width / 2 - 80, btn_y + 4, self.message, TEXT_COLOR, FONT_SZ_SM)

    def render_hierarchy(self):
        x, y = 0, 32
        pw = 250
        ph = self.height - 32 - 24
        self._draw_rect(x, y, pw, ph, PANEL_BG, PANEL_BORDER)
        self._draw_rect(x, y, pw, 34, HEADER_BG)
        self._draw_text(x + 8, y + 7, "HIERARCHY", TEXT_BRIGHT, FONT_SZ_MD)
        cy = y + 38
        for node in self.nodes:
            if not node.visible: continue
            bg = (0.18, 0.19, 0.24) if node.selected else PANEL_BG
            self._draw_rect(x + 2, cy, pw - 4, 22, bg)
            self._draw_text(x + 10, cy + 3, f"{node.name} ({node.get_type_name()})",
                          SELECTION_COLOR if node.selected else TEXT_COLOR, FONT_SZ_SM)
            cy += 22
            if cy > y + ph: break
        if self.show_add_menu:
            my = y + ph - 130
            if my < 60: my = 60
            self._draw_rect(x + 6, my, 130, 110, PANEL_DARK, PANEL_BORDER)
            add_items = ["Pillar", "PlayerSpawn", "Enemy", "Platform"]
            for i, item in enumerate(add_items):
                iy = my + 4 + i * 26
                self._draw_rect(x + 8, iy, 126, 24, (0.16, 0.16, 0.2))
                self._draw_text(x + 14, iy + 4, item, TEXT_COLOR, FONT_SZ_SM)

    def render_inspector(self):
        x = self.width - 280
        y = 32
        pw = 280
        ph = self.height - 32 - 24
        self._draw_rect(x, y, pw, ph, PANEL_BG, PANEL_BORDER)
        self._draw_rect(x, y, pw, 34, HEADER_BG)
        self._draw_text(x + 8, y + 7, "INSPECTOR", TEXT_BRIGHT, FONT_SZ_MD)
        if not self.selected_node:
            self._draw_text(x + 10, y + 40, "No object selected", TEXT_DIM, FONT_SZ_SM)
            return
        node = self.selected_node
        self._draw_text(x + 8, y + 38, f"{node.name}", ACCENT, FONT_SZ_LG)
        self._draw_text(x + 8, y + 56, f"{node.get_type_name()}", TEXT_DIM, FONT_SZ_SM)
        props = node.get_properties()
        cy = y + 78
        line_h = 22
        for key, val in props.items():
            if key == "pos" and isinstance(val, Vector3):
                self._draw_rect(x, cy, pw, line_h, PANEL_BG)
                self._draw_text(x + 10, cy + 3, "Position", TEXT_COLOR, FONT_SZ_SM)
                pos = val
                for i, (label, axis) in enumerate([("X", 0), ("Y", 1), ("Z", 2)]):
                    fx = x + 90 + i * 62
                    fw = 60
                    colors = [GIZMO_X, GIZMO_Y, GIZMO_Z]
                    self._draw_rect(fx, cy + 1, fw, line_h - 2, (0.18, 0.18, 0.22), (0.3, 0.3, 0.35))
                    self._draw_text(fx + 3, cy + 3, label, colors[i], FONT_SZ_SM)
                    v = [pos.x, pos.y, pos.z][i]
                    if self._editing_field and self._editing_field[0] == "pos" and self._editing_field[1] == i:
                        self._draw_text(fx + 18, cy + 3, self._edit_buffer, ACCENT, FONT_SZ_SM)
                    else:
                        self._draw_text(fx + 18, cy + 3, f"{v:.2f}", TEXT_COLOR, FONT_SZ_SM)
                cy += line_h + 3
            elif isinstance(val, (int, float)):
                self._draw_rect(x, cy, pw, line_h, PANEL_BG)
                self._draw_text(x + 10, cy + 3, key.capitalize(), TEXT_COLOR, FONT_SZ_SM)
                self._draw_rect(x + 110, cy + 1, pw - 116, line_h - 2, (0.18, 0.18, 0.22), (0.3, 0.3, 0.35))
                if self._editing_field and self._editing_field[0] == key:
                    self._draw_text(x + 116, cy + 3, self._edit_buffer, ACCENT, FONT_SZ_SM)
                else:
                    self._draw_text(x + 116, cy + 3, f"{val:.2f}", TEXT_COLOR, FONT_SZ_SM)
                cy += line_h + 3
            elif key == "material" and isinstance(val, str):
                self._draw_rect(x, cy, pw, line_h, PANEL_BG)
                self._draw_text(x + 10, cy + 3, "Material", TEXT_COLOR, FONT_SZ_SM)
                sw = 28
                mats = [("pink", MAT_PINK), ("gray", MAT_GRAY)]
                for mi, (mname, mcol) in enumerate(mats):
                    sx = x + 100 + mi * (sw + 6)
                    border = (1, 1, 1) if node.material == mname else (0.3, 0.3, 0.3)
                    self._draw_rect(sx, cy + 1, sw, line_h - 2, mcol, border)
                    if node.material == mname:
                        self._draw_text(sx + 8, cy + 3, "D", TEXT_BRIGHT, FONT_SZ_SM)
                cy += line_h + 3

    def render_status_bar(self):
        y = self.height - 24
        self._draw_rect(0, y, self.width, 24, PANEL_DARK, PANEL_BORDER)
        if self.selected_node:
            p = self.selected_node.get_world_pos()
            label = f"Selected: {self.selected_node.name} ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})"
            if len(self.selected_nodes) > 1:
                label += f"  [+{len(self.selected_nodes) - 1} more]"
            self._draw_text(8, y + 4, label, TEXT_COLOR, FONT_SZ_SM)
        else:
            self._draw_text(8, y + 4,
                f"No selection  |  Nodes: {len(self.nodes)}  |  [Arrow] Look  [W/S/A/D/Q/E] Fly  [F] Focus  [Del] Delete  [Ctrl+Z] Undo  [Ctrl+Y] Redo",
                TEXT_DIM, FONT_SZ_SM)

    def run(self):
        while self.running:
            t = time.time()
            self.delta_time = t - self.last_time
            self.last_time = t
            self.fps_count += 1
            if t - self.fps_time > 1:
                self.fps = self.fps_count
                self.fps_count = 0
                self.fps_time = t
            if self.message_timer > 0:
                self.message_timer -= self.delta_time
            glfw.poll_events()
            if glfw.window_should_close(self.window):
                self.running = False
            keys = {
                glfw.KEY_W: glfw.get_key(self.window, glfw.KEY_W),
                glfw.KEY_S: glfw.get_key(self.window, glfw.KEY_S),
                glfw.KEY_A: glfw.get_key(self.window, glfw.KEY_A),
                glfw.KEY_D: glfw.get_key(self.window, glfw.KEY_D),
                glfw.KEY_Q: glfw.get_key(self.window, glfw.KEY_Q),
                glfw.KEY_E: glfw.get_key(self.window, glfw.KEY_E),
            }
            arrow_delta = None
            ax = 0
            ay = 0
            if glfw.get_key(self.window, glfw.KEY_LEFT) == glfw.PRESS: ax -= 1
            if glfw.get_key(self.window, glfw.KEY_RIGHT) == glfw.PRESS: ax += 1
            if glfw.get_key(self.window, glfw.KEY_UP) == glfw.PRESS: ay -= 1
            if glfw.get_key(self.window, glfw.KEY_DOWN) == glfw.PRESS: ay += 1
            if ax != 0 or ay != 0:
                arrow_delta = (ax, ay)
            mouse_delta = None
            if self.right_dragging or self.middle_dragging:
                dx = self.mouse_x - self.last_mouse[0]
                dy = self.mouse_y - self.last_mouse[1]
                mouse_delta = (dx, dy)
            self.camera.update(keys, self.delta_time, self.right_dragging, mouse_delta, arrow_delta=arrow_delta)
            if self.gizmo.drag_axis is not None and self.left_dragging and self.selected_node:
                origin, direction = self._screen_to_ray(self.mouse_x, self.mouse_y)
                if origin:
                    delta = self.gizmo.update_drag(origin, direction,
                        self.selected_node.get_world_pos(), self.gizmo.drag_axis)
                    if self.gizmo.mode == "translate":
                        axes = [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)]
                        self.selected_node.pos = self.selected_node.pos + axes[self.gizmo.drag_axis] * delta
                    elif self.gizmo.mode == "scale":
                        self._apply_scale(self.selected_node, self.gizmo.drag_axis, delta)
            elif not self.left_dragging and not self.right_dragging and self.selected_node:
                origin, direction = self._screen_to_ray(self.mouse_x, self.mouse_y)
                if origin:
                    gs = (self.selected_node.get_world_pos() - self.camera.pos).length() * 0.06
                    self.gizmo.hit_test(origin, direction, self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)))
            self.last_mouse = (self.mouse_x, self.mouse_y)
            self.render()
            glfw.swap_buffers(self.window)

    def render(self):
        self.render_scene()
        self._ortho_mode()
        self.render_toolbar()
        self.render_hierarchy()
        self.render_inspector()
        self.render_status_bar()
        self._ortho_end()

def main():
    editor = Editor(1400, 900)
    editor.run()

if __name__ == "__main__":
    main()
