import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import json
import os
import time
import random
import subprocess
from PIL import Image, ImageDraw, ImageFont
PANEL_BG = (0.08, 0.08, 0.08)
PANEL_DARK = (0.04, 0.04, 0.04)
PANEL_BORDER = (0.13, 0.13, 0.13)
HEADER_BG = (0.06, 0.06, 0.06)
ACCENT = (0.9, 0.9, 0.92)
ACCENT_HOVER = (1.0, 1.0, 1.0)
TEXT_COLOR = (0.95, 0.95, 0.95)
TEXT_DIM = (0.55, 0.55, 0.55)
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
class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.x = x; self.y = y; self.z = z
    def __add__(self, o):
        return Vector3(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o):
        return Vector3(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, s):
        return Vector3(self.x*s, self.y*s, self.z*s)
    def __rmul__(self, s):
        return Vector3(self.x*s, self.y*s, self.z*s)
    def __neg__(self):
        return Vector3(-self.x, -self.y, -self.z)
    def __repr__(self):
        return f"Vector3({self.x},{self.y},{self.z})"
    def length(self):
        return math.sqrt(self.x*self.x+self.y*self.y+self.z*self.z)
    def normalize(self):
        l = self.length()
        return Vector3(self.x/l, self.y/l, self.z/l) if l else Vector3()
    def dot(self, o):
        return self.x*o.x+self.y*o.y+self.z*o.z

class SimpleLighting:
    def __init__(self):
        self.ambient_color = (0.2, 0.2, 0.3)
        self.diffuse_color = (0.7, 0.7, 0.8)
        self.specular_color = (0.3, 0.3, 0.4)
        self.light_direction = Vector3(1, 1, 1).normalize()
    def enable(self):
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_AMBIENT, (*self.ambient_color, 1.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (*self.diffuse_color, 1.0))
        glLightfv(GL_LIGHT0, GL_SPECULAR, (*self.specular_color, 1.0))
        glLightfv(GL_LIGHT0, GL_POSITION, (self.light_direction.x, self.light_direction.y, self.light_direction.z, 0.0))

def make_tex(c1, c2, size=64):
    from PIL import Image
    img = Image.new('RGB', (size, size))
    for y in range(size):
        for x in range(size):
            col = c1 if (x//8 + y//8) % 2 == 0 else c2
            img.putpixel((x, y), col)
    data = img.tobytes("raw", "RGB", 0, -1)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, data)
    return tex

def ray_aabb_intersection(origin, direction, aabb_min, aabb_max):
    ox, oy, oz = origin.x, origin.y, origin.z
    dx, dy, dz = direction.x, direction.y, direction.z
    tmin = (aabb_min[0] - ox) / dx if abs(dx) > 1e-8 else -1e9
    tmax = (aabb_max[0] - ox) / dx if abs(dx) > 1e-8 else 1e9
    if tmin > tmax: tmin, tmax = tmax, tmin
    tymin = (aabb_min[1] - oy) / dy if abs(dy) > 1e-8 else -1e9
    tymax = (aabb_max[1] - oy) / dy if abs(dy) > 1e-8 else 1e9
    if tymin > tymax: tymin, tymax = tymax, tymin
    if (tmin > tymax) or (tymin > tmax): return None
    if tymin > tmin: tmin = tymin
    if tymax < tmax: tmax = tymax
    tzmin = (aabb_min[2] - oz) / dz if abs(dz) > 1e-8 else -1e9
    tzmax = (aabb_max[2] - oz) / dz if abs(dz) > 1e-8 else 1e9
    if tzmin > tzmax: tzmin, tzmax = tzmax, tzmin
    if (tmin > tzmax) or (tzmin > tmax): return None
    if tzmin > tmin: tmin = tzmin
    if tzmax < tmax: tmax = tzmax
    return tmin if tmin > 0 else (tmax if tmax > 0 else None)

class Pillar:
    def __init__(self, pos, height=1.0, width=1.0, depth=1.0, tex_id=0):
        self.pos = pos; self.height = height; self.width = width; self.depth = depth; self.tex_id = tex_id
        self.rot = Vector3()
    def draw(self):
        glPushMatrix()
        glTranslatef(self.pos.x, self.pos.y, self.pos.z)
        if self.rot.x or self.rot.y or self.rot.z:
            glRotatef(self.rot.x, 1, 0, 0)
            glRotatef(self.rot.y, 0, 1, 0)
            glRotatef(self.rot.z, 0, 0, 1)
        if self.tex_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
        else:
            glDisable(GL_TEXTURE_2D)
        glDisable(GL_CULL_FACE)
        w, h, d = self.width/2, self.height/2, self.depth/2
        glBegin(GL_QUADS)
        glNormal3f(0,0,1)
        glTexCoord2f(0,0); glVertex3f(-w,-h, d)
        glTexCoord2f(1,0); glVertex3f( w,-h, d)
        glTexCoord2f(1,1); glVertex3f( w, h, d)
        glTexCoord2f(0,1); glVertex3f(-w, h, d)
        glNormal3f(0,0,-1)
        glTexCoord2f(0,0); glVertex3f( w,-h,-d)
        glTexCoord2f(1,0); glVertex3f(-w,-h,-d)
        glTexCoord2f(1,1); glVertex3f(-w, h,-d)
        glTexCoord2f(0,1); glVertex3f( w, h,-d)
        glNormal3f(-1,0,0)
        glTexCoord2f(0,0); glVertex3f(-w,-h,-d)
        glTexCoord2f(1,0); glVertex3f(-w,-h, d)
        glTexCoord2f(1,1); glVertex3f(-w, h, d)
        glTexCoord2f(0,1); glVertex3f(-w, h,-d)
        glNormal3f(1,0,0)
        glTexCoord2f(0,0); glVertex3f( w,-h, d)
        glTexCoord2f(1,0); glVertex3f( w,-h,-d)
        glTexCoord2f(1,1); glVertex3f( w, h,-d)
        glTexCoord2f(0,1); glVertex3f( w, h, d)
        glNormal3f(0,1,0)
        glTexCoord2f(0,0); glVertex3f(-w, h,-d)
        glTexCoord2f(1,0); glVertex3f(-w, h, d)
        glTexCoord2f(1,1); glVertex3f( w, h, d)
        glTexCoord2f(0,1); glVertex3f( w, h,-d)
        glNormal3f(0,-1,0)
        glTexCoord2f(0,0); glVertex3f(-w,-h, d)
        glTexCoord2f(1,0); glVertex3f( w,-h, d)
        glTexCoord2f(1,1); glVertex3f( w,-h,-d)
        glTexCoord2f(0,1); glVertex3f(-w,-h,-d)
        glEnd()
        glEnable(GL_CULL_FACE)
        glDisable(GL_TEXTURE_2D)
        glPopMatrix()

class Platform:
    def __init__(self, size=150, grid_size=10, tex_id=0):
        self.size = size; self.grid_size = grid_size; self.tex_id = tex_id
        self.pos = Vector3(0, -0.1, 0)
    def draw(self):
        glPushMatrix()
        if self.tex_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
        else:
            glDisable(GL_TEXTURE_2D)
        hs = self.size/2; step = self.size/self.grid_size
        glBegin(GL_QUADS)
        glNormal3f(0,1,0)
        for iz in range(self.grid_size):
            for ix in range(self.grid_size):
                x0 = -hs + ix*step; z0 = -hs + iz*step
                glTexCoord2f(0,0); glVertex3f(x0, -0.1, z0+step)
                glTexCoord2f(1,0); glVertex3f(x0+step, -0.1, z0+step)
                glTexCoord2f(1,1); glVertex3f(x0+step, -0.1, z0)
                glTexCoord2f(0,1); glVertex3f(x0, -0.1, z0)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glPopMatrix()

class Ceiling:
    def __init__(self, size=150, tex_id=0):
        self.size = size; self.tex_id = tex_id; self.pos = Vector3(0, 14, 0)
    def draw(self):
        glPushMatrix()
        if self.tex_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
        else:
            glDisable(GL_TEXTURE_2D)
        hs = self.size/2
        glBegin(GL_QUADS)
        glNormal3f(0,-1,0)
        glTexCoord2f(0,0); glVertex3f(-hs, 14, -hs)
        glTexCoord2f(10,0); glVertex3f(hs, 14, -hs)
        glTexCoord2f(10,10); glVertex3f(hs, 14, hs)
        glTexCoord2f(0,10); glVertex3f(-hs, 14, hs)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glPopMatrix()

class Skybox:
    def __init__(self, top_color=(0.1,0.1,0.3), horizon_color=(0.3,0.3,0.6), ground_color=(0.05,0.05,0.1)):
        self.top_color = top_color; self.horizon_color = horizon_color; self.ground_color = ground_color
    def draw(self, camera_pos):
        glPushMatrix()
        glTranslatef(camera_pos.x, camera_pos.y, camera_pos.z)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        r = 400
        glBegin(GL_QUADS)
        # top
        glColor3f(*self.top_color)
        glVertex3f(-r, r,-r); glVertex3f( r, r,-r); glVertex3f( r, r, r); glVertex3f(-r, r, r)
        # bottom
        glColor3f(*self.ground_color)
        glVertex3f(-r,-r, r); glVertex3f( r,-r, r); glVertex3f( r,-r,-r); glVertex3f(-r,-r,-r)
        # +X side
        glColor3f(*self.horizon_color); glVertex3f( r,-r,-r)
        glColor3f(*self.top_color);     glVertex3f( r, r,-r)
        glColor3f(*self.top_color);     glVertex3f( r, r, r)
        glColor3f(*self.horizon_color); glVertex3f( r,-r, r)
        # -X side
        glColor3f(*self.horizon_color); glVertex3f(-r,-r, r)
        glColor3f(*self.top_color);     glVertex3f(-r, r, r)
        glColor3f(*self.top_color);     glVertex3f(-r, r,-r)
        glColor3f(*self.horizon_color); glVertex3f(-r,-r,-r)
        # +Z side
        glColor3f(*self.horizon_color); glVertex3f( r,-r, r)
        glColor3f(*self.top_color);     glVertex3f( r, r, r)
        glColor3f(*self.top_color);     glVertex3f(-r, r, r)
        glColor3f(*self.horizon_color); glVertex3f(-r,-r, r)
        # -Z side
        glColor3f(*self.horizon_color); glVertex3f(-r,-r,-r)
        glColor3f(*self.top_color);     glVertex3f(-r, r,-r)
        glColor3f(*self.top_color);     glVertex3f( r, r,-r)
        glColor3f(*self.horizon_color); glVertex3f( r,-r,-r)
        glEnd()
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()

class EditorCamera:
    def __init__(self):
        self.pos = Vector3(0, 6, 20)
        self.yaw = 30
        self.pitch = -20
        self.speed = 12
        self.mouse_sensitivity = 0.25
        self._sprint = 1.0
        self._move_time = 0.0
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
        r = self.get_right()
        moving = any(keys.get(k) for k in (glfw.KEY_W, glfw.KEY_S, glfw.KEY_A, glfw.KEY_D))
        if moving:
            self._move_time += delta_time
        else:
            self._move_time = 0.0
        sprint = 2.5 if keys.get(glfw.KEY_LEFT_SHIFT) else 1.0
        ramp = 1.0 + self._move_time * 0.5
        spd = self.speed * sprint * ramp * delta_time
        m = Vector3(0, 0, 0)
        if keys.get(glfw.KEY_W): m = m + f * spd
        if keys.get(glfw.KEY_S): m = m - f * spd
        if keys.get(glfw.KEY_A): m = m - r * spd
        if keys.get(glfw.KEY_D): m = m + r * spd
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
                "pos": [self.pos.x, self.pos.y, self.pos.z],
                "rot": [self.rot.x, self.rot.y, self.rot.z]}
    def from_dict(self, d):
        self.name = d.get("name", self.name)
        p = d.get("pos", [0, 0, 0])
        self.pos = Vector3(p[0], p[1], p[2])
        r = d.get("rot", [0, 0, 0])
        self.rot = Vector3(r[0], r[1], r[2])

def _draw_box_outline(p, w, h, d, offset=0.04):
    """Draw wireframe box outline around a box at position p with half-extents w,h,d"""
    ow, oh, od = w + offset, h + offset, d + offset
    corners = [
        (-ow, -oh, -od), (ow, -oh, -od), (ow, oh, -od), (-ow, oh, -od),
        (-ow, -oh,  od), (ow, -oh,  od), (ow, oh,  od), (-ow, oh,  od),
    ]
    edges = [
        (0,1),(1,2),(2,3),(3,0),
        (4,5),(5,6),(6,7),(7,4),
        (0,4),(1,5),(2,6),(3,7),
    ]
    glBegin(GL_LINES)
    for a, b in edges:
        ca, cb = corners[a], corners[b]
        glVertex3f(p.x+ca[0], p.y+ca[1], p.z+ca[2])
        glVertex3f(p.x+cb[0], p.y+cb[1], p.z+cb[2])
    glEnd()

def _draw_sphere_outline(p, r, offset=0.04):
    """Draw 3 circles around a sphere"""
    r2 = r + offset
    segs = 32
    for plane in range(3):
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2 * math.pi * i / segs
            c, s = math.cos(a) * r2, math.sin(a) * r2
            if plane == 0:
                glVertex3f(p.x + c, p.y + s, p.z)
            elif plane == 1:
                glVertex3f(p.x + c, p.y, p.z + s)
            else:
                glVertex3f(p.x, p.y + c, p.z + s)
        glEnd()

class PillarNode(SceneNode):
    def __init__(self, pos=None):
        super().__init__("Pillar", pos)
        self.width = 1.0
        self.height = 1.0
        self.depth = 1.0
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
        if self.rot.x or self.rot.y or self.rot.z:
            glRotatef(self.rot.x, 1, 0, 0)
            glRotatef(self.rot.y, 0, 1, 0)
            glRotatef(self.rot.z, 0, 0, 1)
        glColor3f(*self.color)
        if self.tex_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
        else:
            glDisable(GL_TEXTURE_2D)
        glDisable(GL_CULL_FACE)
        w, h, d = self.width/2, self.height/2, self.depth/2
        glBegin(GL_QUADS)
        glNormal3f(0,0,1)
        glTexCoord2f(0,0); glVertex3f(-w,-h, d)
        glTexCoord2f(1,0); glVertex3f( w,-h, d)
        glTexCoord2f(1,1); glVertex3f( w, h, d)
        glTexCoord2f(0,1); glVertex3f(-w, h, d)
        glNormal3f(0,0,-1)
        glTexCoord2f(0,0); glVertex3f( w,-h,-d)
        glTexCoord2f(1,0); glVertex3f(-w,-h,-d)
        glTexCoord2f(1,1); glVertex3f(-w, h,-d)
        glTexCoord2f(0,1); glVertex3f( w, h,-d)
        glNormal3f(-1,0,0)
        glTexCoord2f(0,0); glVertex3f(-w,-h,-d)
        glTexCoord2f(1,0); glVertex3f(-w,-h, d)
        glTexCoord2f(1,1); glVertex3f(-w, h, d)
        glTexCoord2f(0,1); glVertex3f(-w, h,-d)
        glNormal3f(1,0,0)
        glTexCoord2f(0,0); glVertex3f( w,-h, d)
        glTexCoord2f(1,0); glVertex3f( w,-h,-d)
        glTexCoord2f(1,1); glVertex3f( w, h,-d)
        glTexCoord2f(0,1); glVertex3f( w, h, d)
        glNormal3f(0,1,0)
        glTexCoord2f(0,0); glVertex3f(-w, h,-d)
        glTexCoord2f(1,0); glVertex3f(-w, h, d)
        glTexCoord2f(1,1); glVertex3f( w, h, d)
        glTexCoord2f(0,1); glVertex3f( w, h,-d)
        glNormal3f(0,-1,0)
        glTexCoord2f(0,0); glVertex3f(-w,-h, d)
        glTexCoord2f(1,0); glVertex3f( w,-h, d)
        glTexCoord2f(1,1); glVertex3f( w,-h,-d)
        glTexCoord2f(0,1); glVertex3f(-w,-h,-d)
        glEnd()
        glEnable(GL_CULL_FACE)
        glDisable(GL_TEXTURE_2D)
        glPopMatrix()
    def render_selected(self):
        p = self.get_world_pos()
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        # Account for rotation
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        if self.rot.x or self.rot.y or self.rot.z:
            glRotatef(self.rot.x, 1, 0, 0)
            glRotatef(self.rot.y, 0, 1, 0)
            glRotatef(self.rot.z, 0, 0, 1)
        ofs = 0.04
        w, h, d = self.width/2 + ofs, self.height/2 + ofs, self.depth/2 + ofs
        corners = [
            (-w,-h,-d),(w,-h,-d),(w,h,-d),(-w,h,-d),
            (-w,-h, d),(w,-h, d),(w,h, d),(-w,h, d),
        ]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        glBegin(GL_LINES)
        for a, b in edges:
            glVertex3f(*corners[a])
            glVertex3f(*corners[b])
        glEnd()
        glPopMatrix()
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
        else:
            glDisable(GL_TEXTURE_2D)
        half = self.size / 2
        glBegin(GL_QUADS)
        glNormal3f(0, 1, 0)
        glTexCoord2f(0, 0); glVertex3f(-half, 0, half)
        glTexCoord2f(1, 0); glVertex3f(half, 0, half)
        glTexCoord2f(1, 1); glVertex3f(half, 0, -half)
        glTexCoord2f(0, 1); glVertex3f(-half, 0, -half)
        glEnd()
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
        self.speed = 12.0
        self.health = 100.0
        self.jump_force = 8.0
        self.grapple_speed = 60.0
    def get_type_name(self):
        return "PlayerSpawn"
    def get_bounds(self):
        p = self.get_world_pos()
        return (Vector3(p.x-0.5, p.y-1.5, p.z-0.5), Vector3(p.x+0.5, p.y+0.5, p.z+0.5))
    def get_properties(self):
        return {"pos": self.pos, "speed": self.speed, "health": self.health,
                "jump_force": self.jump_force, "grapple_speed": self.grapple_speed}
    def render_scene(self):
        if not self.visible: return
        p = self.get_world_pos()
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_LIGHTING)
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        # Draw as flat-shaded capsule silhouette (lines only, no materials)
        glColor3f(*self.color)
        # Body cylinder lines
        segs = 12
        r = 0.3
        body_h = 1.5
        # Top circle
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2*math.pi*i/segs
            glVertex3f(math.cos(a)*r, body_h, math.sin(a)*r)
        glEnd()
        # Bottom circle
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2*math.pi*i/segs
            glVertex3f(math.cos(a)*r, 0, math.sin(a)*r)
        glEnd()
        # Vertical lines
        glBegin(GL_LINES)
        for i in range(4):
            a = 2*math.pi*i/4
            glVertex3f(math.cos(a)*r, 0, math.sin(a)*r)
            glVertex3f(math.cos(a)*r, body_h, math.sin(a)*r)
        glEnd()
        # Arrow up
        glColor3f(1, 1, 1)
        glBegin(GL_LINES)
        glVertex3f(0, body_h, 0); glVertex3f(0, body_h + 0.7, 0)
        glEnd()
        glBegin(GL_TRIANGLES)
        glVertex3f(0, body_h + 1.0, 0)
        glVertex3f(-0.15, body_h + 0.6, 0)
        glVertex3f(0.15, body_h + 0.6, 0)
        glEnd()
        glPopMatrix()
        glEnable(GL_LIGHTING)
    def render_selected(self):
        p = self.get_world_pos()
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        _draw_box_outline(p, 0.5, 1.0, 0.5, 0.08)
        glLineWidth(1)
        glEnable(GL_LIGHTING)
    def to_dict(self):
        d = super().to_dict()
        d["speed"] = self.speed
        d["health"] = self.health
        d["jump_force"] = self.jump_force
        d["grapple_speed"] = self.grapple_speed
        return d
    def from_dict(self, d):
        super().from_dict(d)
        self.speed = d.get("speed", 12.0)
        self.health = d.get("health", 100.0)
        self.jump_force = d.get("jump_force", 8.0)
        self.grapple_speed = d.get("grapple_speed", 60.0)
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
        return {"pos": self.pos, "radius": self.radius}
    def render_scene(self):
        if not self.visible: return
        p = self.get_world_pos()
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_LIGHTING)
        glPushMatrix()
        glTranslatef(p.x, p.y, p.z)
        glColor3f(*self.color)
        # Draw as 3 flat circles (wireframe sphere)
        segs = 24
        for plane in range(3):
            glBegin(GL_LINE_LOOP)
            for i in range(segs):
                a = 2*math.pi*i/segs
                c, s = math.cos(a)*self.radius, math.sin(a)*self.radius
                if plane == 0: glVertex3f(c, s, 0)
                elif plane == 1: glVertex3f(c, 0, s)
                else: glVertex3f(0, c, s)
            glEnd()
        glPopMatrix()
        glEnable(GL_LIGHTING)
    def render_selected(self):
        p = self.get_world_pos()
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glColor3f(*SELECTION_COLOR)
        _draw_sphere_outline(p, self.radius, 0.06)
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
        self.rotate_handle_dl = None
        self._build_handle()
        self._build_scale_handle()
        self._build_rotate_handle()
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
        for x1, y1, z1, x2, y2, z2 in [(-s,-s,-s,-s,-s,s),(s,-s,-s,s,-s,s),(s,s,-s,s,s,s),(-s,s,-s,-s,s,s)]:
            glBegin(GL_LINES)
            glVertex3f(x1, y1, z1); glVertex3f(x2, y2, z2)
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
    def _build_rotate_handle(self):
        self.rotate_handle_dl = glGenLists(1)
        glNewList(self.rotate_handle_dl, GL_COMPILE)
        glLineWidth(2)
        r = self.axis_len * 0.85
        glBegin(GL_LINE_LOOP)
        segs = 40
        for i in range(segs):
            a = 2 * math.pi * i / segs
            glVertex3f(math.cos(a) * r, math.sin(a) * r, 0)
        glEnd()
        glLineWidth(1)
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
    def _ring_plane_hit(self, ray_origin, ray_dir, node_pos, ax_dir):
        denom = ray_dir.dot(ax_dir)
        if abs(denom) < 1e-8:
            return None
        t = (node_pos - ray_origin).dot(ax_dir) / denom
        if t <= 0:
            return None
        return ray_origin + ray_dir * t
    def hit_test(self, ray_origin, ray_dir, node_pos, scale=1.0, rot=None):
        self.hover_axis = None
        best_dist = 1e9
        best_axis = None
        base_axes = [(Vector3(1, 0, 0), GIZMO_X), (Vector3(0, 1, 0), GIZMO_Y), (Vector3(0, 0, 1), GIZMO_Z)]
        axes = self._rotate_axes(base_axes, rot)
        if self.mode == "rotate":
            ring_r = self.axis_len * 0.85 * scale
            threshold = 0.3 * scale
            for i, (ax_dir, col) in enumerate(axes):
                hit = self._ring_plane_hit(ray_origin, ray_dir, node_pos, ax_dir)
                if hit is not None:
                    r = (hit - node_pos).length()
                    ring_dist = abs(r - ring_r)
                    if ring_dist < threshold and ring_dist < best_dist:
                        best_dist = ring_dist
                        best_axis = i
        else:
            for i, (ax_dir, col) in enumerate(axes):
                dist, tr, ta = self.ray_axis_distance(ray_origin, ray_dir, node_pos, ax_dir)
                if 0 <= ta <= self.axis_len * scale and tr > 0 and dist < 0.3 * scale:
                    best_dist = dist
                    best_axis = i
        if best_axis is not None:
            self.hover_axis = best_axis
            return best_axis
        return None
    def start_drag(self, ray_origin, ray_dir, node_pos, axis_idx, rot=None):
        self.drag_axis = axis_idx
        base_axes = [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)]
        rotated = self._rotate_axes([(a, None) for a in base_axes], rot)
        ax_dir = rotated[axis_idx][0]
        if self.mode == "rotate":
            hit = self._ring_plane_hit(ray_origin, ray_dir, node_pos, ax_dir)
            self.drag_plane_point = hit if hit is not None else node_pos
        else:
            _, _, t_ax = self.ray_axis_distance(ray_origin, ray_dir, node_pos, ax_dir)
            self.drag_plane_point = node_pos + ax_dir * t_ax
    def update_drag(self, ray_origin, ray_dir, node_pos, axis_idx, rot=None):
        base_axes = [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)]
        rotated = self._rotate_axes([(a, None) for a in base_axes], rot)
        ax_dir = rotated[axis_idx][0]
        if self.mode == "rotate":
            new_point = self._ring_plane_hit(ray_origin, ray_dir, node_pos, ax_dir)
            if new_point is None:
                return 0
            old_vec = self.drag_plane_point - node_pos
            new_vec = new_point - node_pos
            cross_x = old_vec.y * new_vec.z - old_vec.z * new_vec.y
            cross_y = old_vec.z * new_vec.x - old_vec.x * new_vec.z
            cross_z = old_vec.x * new_vec.y - old_vec.y * new_vec.x
            sign = 1 if cross_x * ax_dir.x + cross_y * ax_dir.y + cross_z * ax_dir.z > 0 else -1
            old_len = old_vec.length()
            new_len = new_vec.length()
            if old_len > 0.001 and new_len > 0.001:
                cos_a = old_vec.dot(new_vec) / (old_len * new_len)
                cos_a = max(-1, min(1, cos_a))
                angle = math.degrees(math.acos(cos_a) * sign)
            else:
                angle = 0
            self.drag_plane_point = new_point
            return angle
        else:
            _, _, t_ax = self.ray_axis_distance(ray_origin, ray_dir, node_pos, ax_dir)
            new_point = node_pos + ax_dir * t_ax
            delta = (new_point - self.drag_plane_point).dot(ax_dir)
            self.drag_plane_point = new_point
            return delta
    def end_drag(self):
        self.drag_axis = None
    def _rotate_axes(self, axes, rot):
        if rot is None:
            return axes
        rx, ry, rz = math.radians(rot.x), math.radians(rot.y), math.radians(rot.z)
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        def rotate_vec(v):
            x = v.x * (cy*cz) + v.y * (sx*sy*cz - cx*sz) + v.z * (cx*sy*cz + sx*sz)
            y = v.x * (cy*sz) + v.y * (sx*sy*sz + cx*cz) + v.z * (cx*sy*sz - sx*cz)
            z = v.x * (-sy) + v.y * (sx*cy) + v.z * (cx*cy)
            return Vector3(x, y, z)
        return [(rotate_vec(d), c) for d, c in axes]
    def draw(self, pos, scale=1.0, rot=None):
        if self.drag_axis is not None and self.drag_axis < 0:
            return
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glPushMatrix()
        glTranslatef(pos.x, pos.y, pos.z)
        if rot is not None:
            glRotatef(rot.z, 0, 0, 1)
            glRotatef(rot.y, 0, 1, 0)
            glRotatef(rot.x, 1, 0, 0)
        base_axes = [
            (Vector3(1, 0, 0), GIZMO_X),
            (Vector3(0, 1, 0), GIZMO_Y),
            (Vector3(0, 0, 1), GIZMO_Z),
        ]
        for i, (ax_dir, col) in enumerate(base_axes):
            if self.hover_axis == i or self.drag_axis == i:
                glColor3f(*GIZMO_HOVER)
            else:
                glColor3f(*col)
            glPushMatrix()
            if ax_dir.x: glRotatef(90, 0, 1, 0)
            elif ax_dir.y: glRotatef(-90, 1, 0, 0)
            glScalef(scale, scale, scale)
            if self.mode == "translate":
                dl = self.handle_dl
            elif self.mode == "scale":
                dl = self.scale_handle_dl
            else:
                dl = self.rotate_handle_dl
            glCallList(dl)
            glPopMatrix()
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)
class Editor:
    NODE_TYPES = {
        "Pillar": PillarNode,
        "Enemy": EnemyNode,
        "PlayerSpawn": PlayerSpawnNode,
        "Platform": PlatformNode,
    }
    def __init__(self, width=1280, height=720):
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
        self._edit_cursor = 0
        self._edit_cursor_timer = 0.0
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
            if ch.isprintable():
                self._edit_buffer = self._edit_buffer[:self._edit_cursor] + ch + self._edit_buffer[self._edit_cursor:]
                self._edit_cursor += 1
                self._edit_cursor_timer = 0.0
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
            if (key == glfw.KEY_DELETE or key == glfw.KEY_BACKSPACE) and self._editing_field is None:
                self._delete_selected()
            elif key == glfw.KEY_E:
                self.gizmo.mode = "translate"
            elif key == glfw.KEY_R:
                self.gizmo.mode = "rotate"
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
                    if self._edit_cursor > 0:
                        self._edit_buffer = self._edit_buffer[:self._edit_cursor-1] + self._edit_buffer[self._edit_cursor:]
                        self._edit_cursor -= 1
                        self._edit_cursor_timer = 0.0
                elif key == glfw.KEY_DELETE:
                    if self._edit_cursor < len(self._edit_buffer):
                        self._edit_buffer = self._edit_buffer[:self._edit_cursor] + self._edit_buffer[self._edit_cursor+1:]
                        self._edit_cursor_timer = 0.0
                elif key == glfw.KEY_LEFT:
                    if self._edit_cursor > 0:
                        self._edit_cursor -= 1
                        self._edit_cursor_timer = 0.0
                elif key == glfw.KEY_RIGHT:
                    if self._edit_cursor < len(self._edit_buffer):
                        self._edit_cursor += 1
                        self._edit_cursor_timer = 0.0
                elif key == glfw.KEY_HOME:
                    self._edit_cursor = 0
                    self._edit_cursor_timer = 0.0
                elif key == glfw.KEY_END:
                    self._edit_cursor = len(self._edit_buffer)
                    self._edit_cursor_timer = 0.0
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
        gluPerspective(90, aspect, 0.1, 500.0)
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
        if self._editing_field is not None:
            if not (mx > self.width - 280 and my > 40 and my < self.height - 24):
                self._finish_editing()
                return
        ph = 40
        if my < ph:
            self._handle_toolbar_click(mx, my)
            return
        if mx < 260 and my > ph and my < self.height - 24:
            if self.show_add_menu:
                self._handle_add_menu_click(mx, my)
                return
            self._handle_hierarchy_click(mx, my - ph)
            return
        if mx > self.width - 280 and my > 40 and my < self.height - 24:
            self._handle_inspector_click(mx, my)
            return
        self.show_add_menu = False
        origin, direction = self._screen_to_ray(mx, my)
        if origin is None: return
        if self.selected_node:
            gs = (self.selected_node.get_world_pos() - self.camera.pos).length() * 0.06
            hit = self.gizmo.hit_test(origin, direction, self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)) * 1.3)
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
        # Save/Load/New on the LEFT
        if 8 <= mx <= 63 and 7 <= my <= 33:
            self._save_dialog()
        elif 68 <= mx <= 123 and 7 <= my <= 33:
            self._load_dialog()
        elif 128 <= mx <= 173 and 7 <= my <= 33:
            self._new_scene()
        # Play button centered
        cx = self.width // 2
        if cx - 20 <= mx <= cx + 20 and 7 <= my <= 33:
            self._play_game()
    def _handle_add_menu_click(self, mx, mouse_y):
        x, y = 0, 40
        pw = 260
        ph = self.height - 40 - 24
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
        cy = 118
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
                        self._edit_cursor = len(self._edit_buffer)
                        self._edit_cursor_timer = 0.0
                        return
                cy += line_h + 3
            elif isinstance(val, (int, float)):
                vx = x + 110
                vw = 146
                if vx <= mx <= vx + vw and cy + 1 <= my <= cy + line_h - 1:
                    self._snapshot()
                    self._editing_field = (key, None, node)
                    self._edit_buffer = str(val)
                    self._edit_cursor = len(self._edit_buffer)
                    self._edit_cursor_timer = 0.0
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
        # + button in header
        if 0 <= my < 42 and 230 <= mx <= 256:
            self.show_add_menu = not self.show_add_menu
            return
        shift = glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
        ctrl = glfw.get_key(self.window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS
        mode = "range" if shift else ("toggle" if ctrl else "set")
        header_off = 42
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
        self._editing_field = None
        self._edit_buffer = ""
        self._edit_cursor = 0
        self._edit_cursor_timer = 0.0
    def _cancel_editing(self):
        self._editing_field = None
        self._edit_buffer = ""
        self._edit_cursor = 0
        self._edit_cursor_timer = 0.0
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
        gluPerspective(90, aspect, 0.1, 500.0)
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
            self.gizmo.draw(self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)) * 1.3)
    def render_toolbar(self):
        h = 40
        self._draw_rect(0, 0, self.width, h, PANEL_DARK, PANEL_BORDER)
        btn_h = 26
        btn_y = 7
        # Save / Load / New on the LEFT
        self._draw_rect(8, btn_y, 55, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(18, btn_y + 6, "Save", TEXT_BRIGHT, FONT_SZ_SM)
        self._draw_rect(68, btn_y, 55, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(78, btn_y + 6, "Load", TEXT_BRIGHT, FONT_SZ_SM)
        self._draw_rect(128, btn_y, 45, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(136, btn_y + 6, "New", TEXT_BRIGHT, FONT_SZ_SM)
        # Play button centered
        pw = 40
        cx = self.width // 2
        px = cx - pw // 2
        self._draw_rect(px, btn_y, pw, btn_h, (0.15, 0.15, 0.15), PANEL_BORDER)
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.3, 0.85, 0.3)
        glBegin(GL_TRIANGLES)
        glVertex2f(cx - 5, btn_y + 5)
        glVertex2f(cx - 5, btn_y + btn_h - 5)
        glVertex2f(cx + 7, btn_y + btn_h // 2)
        glEnd()
        if self.message and self.message_timer > 0:
            self._draw_text(self.width // 2 - 80, btn_y + 6, self.message, TEXT_COLOR, FONT_SZ_SM)
    def render_hierarchy(self):
        x, y = 0, 40
        pw = 260
        ph = self.height - 40 - 24
        self._draw_rect(x, y, pw, ph, PANEL_BG, PANEL_BORDER)
        self._draw_rect(x, y, pw, 42, HEADER_BG)
        self._draw_text(x + 10, y + 13, "HIERARCHY", TEXT_BRIGHT, FONT_SZ_MD)
        # + button fully inside panel
        plus_x = x + pw - 30
        self._draw_rect(plus_x, y + 8, 22, 26, (0.2, 0.2, 0.25), PANEL_BORDER)
        self._draw_text(plus_x + 6, y + 11, "+", TEXT_BRIGHT, FONT_SZ_LG)
        cy = y + 46
        for node in self.nodes:
            if not node.visible: continue
            bg = (0.22, 0.24, 0.30) if node.selected else PANEL_BG
            self._draw_rect(x + 2, cy, pw - 4, 20, bg)
            col = SELECTION_COLOR if node.selected else TEXT_BRIGHT
            self._draw_text(x + 12, cy + 3, f"{node.name} ({node.get_type_name()})", col, FONT_SZ_SM)
            cy += 22
            if cy > y + ph: break
        if self.show_add_menu:
            my = y + ph - 130
            if my < 60: my = 60
            self._draw_rect(x + 6, my, 140, 110, PANEL_DARK, PANEL_BORDER)
            add_items = ["Pillar", "PlayerSpawn", "Enemy", "Platform"]
            for i, item in enumerate(add_items):
                iy = my + 4 + i * 26
                self._draw_rect(x + 8, iy, 136, 24, (0.18, 0.18, 0.22))
                self._draw_text(x + 16, iy + 5, item, TEXT_BRIGHT, FONT_SZ_SM)
    def render_inspector(self):
        x = self.width - 280
        y = 40
        pw = 280
        ph = self.height - 40 - 24
        self._draw_rect(x, y, pw, ph, PANEL_BG, PANEL_BORDER)
        self._draw_rect(x, y, pw, 42, HEADER_BG)
        self._draw_text(x + 10, y + 13, "INSPECTOR", TEXT_BRIGHT, FONT_SZ_MD)
        if not self.selected_node:
            self._draw_text(x + 12, y + 52, "No object selected", TEXT_DIM, FONT_SZ_SM)
            return
        node = self.selected_node
        self._draw_text(x + 10, y + 46, f"{node.name}", ACCENT, FONT_SZ_LG)
        self._draw_text(x + 10, y + 64, f"{node.get_type_name()}", TEXT_DIM, FONT_SZ_SM)
        props = node.get_properties()
        cy = y + 86
        line_h = 22
        for key, val in props.items():
            if key == "pos" and isinstance(val, Vector3):
                self._draw_rect(x, cy, pw, line_h, (0.10, 0.10, 0.12))
                self._draw_text(x + 10, cy + 4, "Position", TEXT_BRIGHT, FONT_SZ_SM)
                pos = val
                for i, (label, axis) in enumerate([("X", 0), ("Y", 1), ("Z", 2)]):
                    fx = x + 92 + i * 60
                    fw = 58
                    colors = [GIZMO_X, GIZMO_Y, GIZMO_Z]
                    self._draw_rect(fx, cy + 2, fw, line_h - 4, (0.16, 0.16, 0.20), (0.28, 0.28, 0.34))
                    self._draw_text(fx + 3, cy + 4, label, colors[i], FONT_SZ_SM)
                    v = [pos.x, pos.y, pos.z][i]
                    if self._editing_field and self._editing_field[0] == "pos" and self._editing_field[1] == i:
                        self._draw_text(fx + 16, cy + 4, self._edit_buffer, ACCENT, FONT_SZ_SM)
                        self._draw_cursor(fx + 16, cy + 4, self._edit_buffer, self._edit_cursor)
                    else:
                        self._draw_text(fx + 16, cy + 4, f"{v:.2f}", TEXT_BRIGHT, FONT_SZ_SM)
                cy += line_h + 4
            elif isinstance(val, (int, float)):
                self._draw_rect(x, cy, pw, line_h, (0.10, 0.10, 0.12))
                self._draw_text(x + 10, cy + 4, key.capitalize(), TEXT_BRIGHT, FONT_SZ_SM)
                self._draw_rect(x + 110, cy + 2, pw - 116, line_h - 4, (0.16, 0.16, 0.20), (0.28, 0.28, 0.34))
                if self._editing_field and self._editing_field[0] == key:
                    self._draw_text(x + 116, cy + 4, self._edit_buffer, ACCENT, FONT_SZ_SM)
                    self._draw_cursor(x + 116, cy + 4, self._edit_buffer, self._edit_cursor)
                else:
                    self._draw_text(x + 116, cy + 4, f"{val:.2f}", TEXT_BRIGHT, FONT_SZ_SM)
                cy += line_h + 4
            elif key == "material" and isinstance(val, str):
                self._draw_rect(x, cy, pw, line_h, (0.10, 0.10, 0.12))
                self._draw_text(x + 10, cy + 4, "Material", TEXT_BRIGHT, FONT_SZ_SM)
                sw = 28
                mats = [("pink", MAT_PINK), ("gray", MAT_GRAY)]
                for mi, (mname, mcol) in enumerate(mats):
                    sx = x + 100 + mi * (sw + 6)
                    border = (1, 1, 1) if node.material == mname else (0.3, 0.3, 0.3)
                    self._draw_rect(sx, cy + 2, sw, line_h - 4, mcol, border)
                cy += line_h + 4
            else:
                cy += line_h + 4
    def _draw_cursor(self, tx, ty, text, cursor_pos, h=16):
        if self._editing_field is None:
            return
        if int(self._edit_cursor_timer * 2) % 2 == 0:
            prefix = text[:cursor_pos]
            pw = get_text_tex(prefix, FONT_SZ_SM, (255,255,255,255))[1]
            cx = tx + pw
            glDisable(GL_TEXTURE_2D)
            glColor3f(0.9, 0.9, 0.9)
            glBegin(GL_LINES)
            glVertex2f(cx, ty); glVertex2f(cx, ty + h)
            glEnd()
    def render_status_bar(self):
        y = self.height - 24
        self._draw_rect(0, y, self.width, 24, PANEL_DARK, PANEL_BORDER)
        if self.selected_node:
            p = self.selected_node.get_world_pos()
            label = f"Selected: {self.selected_node.name} ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})"
            if len(self.selected_nodes) > 1:
                label += f"  [+{len(self.selected_nodes) - 1} more]"
            self._draw_text(8, y + 4, label, TEXT_BRIGHT, FONT_SZ_SM)
        else:
            self._draw_text(8, y + 4,
                "[Arrow] Look  [W/S/A/D] Fly  [E]Move [R]Rotate [F]Scale  [G]Focus  [Del] Delete  [Ctrl+Z] Undo  [Ctrl+Y] Redo",
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
                    elif self.gizmo.mode == "rotate":
                        if self.gizmo.drag_axis == 0:
                            self.selected_node.rot.x += delta
                        elif self.gizmo.drag_axis == 1:
                            self.selected_node.rot.y += delta
                        else:
                            self.selected_node.rot.z += delta
            elif not self.left_dragging and not self.right_dragging and self.selected_node:
                origin, direction = self._screen_to_ray(self.mouse_x, self.mouse_y)
                if origin:
                    gs = (self.selected_node.get_world_pos() - self.camera.pos).length() * 0.06
                    self.gizmo.hit_test(origin, direction, self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)) * 1.3)
            if self._editing_field is not None:
                self._edit_cursor_timer += self.delta_time
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
    editor = Editor(1280, 720)
    editor.run()
if __name__ == "__main__":
    main()

class GameObjectBase:
    def __init__(self, pos, color=(1,1,1)):
        self.pos = pos
        self.color = color
        self.active = True

class Notifications:
    pass

def load_sprite(path):
    try:
        img = Image.open(path).convert("RGBA")
        data = img.tobytes("raw", "RGBA", 0, -1)
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        return tex, img.width, img.height
    except Exception as e:
        print(f"Failed to load sprite {path}: {e}")
        return 0, 0, 0

def ray_sphere_intersection(origin, direction, sphere_pos, sphere_radius):
    oc = origin - sphere_pos
    b = oc.dot(direction)
    c = oc.dot(oc) - sphere_radius * sphere_radius
    if b > 0 and c > 0:
        return None
    discriminant = b * b - c
    if discriminant < 0:
        return None
    t = -b - math.sqrt(discriminant)
    if t < 0:
        t = -b + math.sqrt(discriminant)
    return t if t >= 0 else None


def _euler_to_axes(rx, ry, rz):
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    ax = Vector3(cy*cz, sx*sy*cz + cx*sz, -cx*sy*cz + sx*sz)
    ay = Vector3(-cy*sz, -sx*sy*sz + cx*cz, cx*sy*sz + sx*cz)
    az = Vector3(sy, -sx*cy, cx*cy)
    return ax, ay, az


def _obb_overlap(pos_a, ext_a, axes_a, pos_b, ext_b, axes_b):
    axes_a = list(axes_a); axes_b = list(axes_b)
    for axis in axes_a + axes_b:
        if axis.length() < 1e-8:
            continue
        proj_a = ext_a[0] * abs(axes_a[0].dot(axis)) + ext_a[1] * abs(axes_a[1].dot(axis)) + ext_a[2] * abs(axes_a[2].dot(axis))
        proj_b = ext_b[0] * abs(axes_b[0].dot(axis)) + ext_b[1] * abs(axes_b[1].dot(axis)) + ext_b[2] * abs(axes_b[2].dot(axis))
        d = abs((pos_b - pos_a).dot(axis))
        if d > proj_a + proj_b + 1e-6:
            return False
    for a in axes_a:
        for b in axes_b:
            axis = Vector3(a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x)
            if axis.length() < 1e-8:
                continue
            proj_a = ext_a[0] * abs(axes_a[0].dot(axis)) + ext_a[1] * abs(axes_a[1].dot(axis)) + ext_a[2] * abs(axes_a[2].dot(axis))
            proj_b = ext_b[0] * abs(axes_b[0].dot(axis)) + ext_b[1] * abs(axes_b[1].dot(axis)) + ext_b[2] * abs(axes_b[2].dot(axis))
            d = abs((pos_b - pos_a).dot(axis))
            if d > proj_a + proj_b + 1e-6:
                return False
    return True


def _obb_penetration(pos_a, ext_a, axes_a, pos_b, ext_b, axes_b):
    best_axis = None
    best_depth = 1e9
    all_axes = list(axes_a) + list(axes_b)
    for a in axes_a:
        for b in axes_b:
            c = Vector3(a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x)
            if c.length() > 1e-8:
                all_axes.append(c)
    for axis in all_axes:
        if axis.length() < 1e-8:
            continue
        n = axis.normalize()
        proj_a = ext_a[0] * abs(axes_a[0].dot(n)) + ext_a[1] * abs(axes_a[1].dot(n)) + ext_a[2] * abs(axes_a[2].dot(n))
        proj_b = ext_b[0] * abs(axes_b[0].dot(n)) + ext_b[1] * abs(axes_b[1].dot(n)) + ext_b[2] * abs(axes_b[2].dot(n))
        d = abs((pos_b - pos_a).dot(n))
        overlap = proj_a + proj_b - d
        if overlap <= 0:
            return None, 0
        if overlap < best_depth:
            best_depth = overlap
            best_axis = n
    if best_axis is None:
        return None, 0
    if (pos_b - pos_a).dot(best_axis) > 0:
        best_axis = Vector3(-best_axis.x, -best_axis.y, -best_axis.z)
    return best_axis, best_depth


def ray_obb_intersection(origin, direction, box_pos, box_ext, box_axes):
    diff = origin - box_pos
    t_min = -1e9
    t_max = 1e9
    for i in range(3):
        ax = box_axes[i]
        e = diff.dot(ax)
        f = direction.dot(ax)
        if abs(f) > 1e-8:
            t1 = (-box_ext[i] - e) / f
            t2 = (box_ext[i] - e) / f
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max + 1e-6:
                return None
        else:
            if e < -box_ext[i] or e > box_ext[i]:
                return None
    if t_max < 0:
        return None
    return t_min if t_min >= 0 else t_max

class PlayerCamera:
    def __init__(self):
        self.pos = Vector3(0, 1.5, 0)
        self.velocity = Vector3(0, 0, 0)
        self.yaw = 0
        self.pitch = 0
        self.momentum_x = 0.0
        self.momentum_z = 0.0
        self.speed = 8.0
        self.mouse_sensitivity = 0.15
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
    def check_collision(self, next_pos, objects):
        p_ext = (0.4, 1.5, 0.4)
        p_axes = [Vector3(1,0,0), Vector3(0,1,0), Vector3(0,0,1)]
        for obj in objects:
            if hasattr(obj, 'width') and hasattr(obj, 'height') and hasattr(obj, 'depth'):
                w, h, d = obj.width/2, obj.height/2, obj.depth/2
                rot = getattr(obj, 'rot', Vector3())
                if rot.x == 0 and rot.y == 0 and rot.z == 0:
                    o_min = (obj.pos.x - w, obj.pos.y - h, obj.pos.z - d)
                    o_max = (obj.pos.x + w, obj.pos.y + h, obj.pos.z + d)
                    if (next_pos.x - p_ext[0] < o_max[0] and next_pos.x + p_ext[0] > o_min[0] and
                        next_pos.y - p_ext[1] < o_max[1] and next_pos.y + p_ext[1] > o_min[1] and
                        next_pos.z - p_ext[2] < o_max[2] and next_pos.z + p_ext[2] > o_min[2]):
                        return True
                else:
                    o_axes = _euler_to_axes(rot.x, rot.y, rot.z)
                    if _obb_overlap(next_pos, p_ext, p_axes, obj.pos, (w, h, d), o_axes):
                        return True
        return False

    def resolve_collision(self, old_pos, desired, objects):
        result = Vector3(desired.x, desired.y, desired.z)
        p_ext = (0.4, 1.5, 0.4)
        p_axes = [Vector3(1,0,0), Vector3(0,1,0), Vector3(0,0,1)]
        grounded = False
        for _ in range(4):
            pushed = False
            for obj in objects:
                if not (hasattr(obj, 'width') and hasattr(obj, 'height') and hasattr(obj, 'depth')):
                    continue
                w, h, d = obj.width/2, obj.height/2, obj.depth/2
                rot = getattr(obj, 'rot', Vector3())
                if rot.x == 0 and rot.y == 0 and rot.z == 0:
                    o_min = Vector3(obj.pos.x - w, obj.pos.y - h, obj.pos.z - d)
                    o_max = Vector3(obj.pos.x + w, obj.pos.y + h, obj.pos.z + d)
                    overlap_x = min(result.x + p_ext[0] - o_min.x, o_max.x - (result.x - p_ext[0]))
                    overlap_y = min(result.y + p_ext[1] - o_min.y, o_max.y - (result.y - p_ext[1]))
                    overlap_z = min(result.z + p_ext[2] - o_min.z, o_max.z - (result.z - p_ext[2]))
                    if overlap_x <= 0 or overlap_y <= 0 or overlap_z <= 0:
                        continue
                    if overlap_x < overlap_y and overlap_x < overlap_z:
                        if result.x < obj.pos.x:
                            result.x = o_min.x - p_ext[0]
                        else:
                            result.x = o_max.x + p_ext[0]
                    elif overlap_y < overlap_z:
                        if result.y < obj.pos.y:
                            result.y = o_min.y - p_ext[1]
                        else:
                            result.y = o_max.y + p_ext[1]
                            grounded = True
                    else:
                        if result.z < obj.pos.z:
                            result.z = o_min.z - p_ext[2]
                        else:
                            result.z = o_max.z + p_ext[2]
                    pushed = True
                else:
                    ax, ay, az = _euler_to_axes(rot.x, rot.y, rot.z)
                    diff = result - obj.pos
                    local = [diff.dot(ax), diff.dot(ay), diff.dot(az)]
                    best_axis = None
                    best_overlap = 1e9
                    for test_n, test_ext in [(ax, w), (ay, h), (az, d)]:
                        obj_proj = test_ext
                        ply_proj = p_ext[0] * abs(p_axes[0].dot(test_n)) + p_ext[1] * abs(p_axes[1].dot(test_n)) + p_ext[2] * abs(p_axes[2].dot(test_n))
                        center_dist = abs(diff.dot(test_n))
                        overlap = obj_proj + ply_proj - center_dist
                        if overlap <= 0:
                            best_axis = None
                            break
                        if overlap < best_overlap:
                            best_overlap = overlap
                            sign = 1.0 if diff.dot(test_n) > 0 else -1.0
                            best_axis = test_n * sign
                    if best_axis is not None and best_overlap > 0:
                        for test_n, test_ext in [(Vector3(1,0,0), p_ext[0]), (Vector3(0,1,0), p_ext[1]), (Vector3(0,0,1), p_ext[2])]:
                            obj_proj = abs(ax.dot(test_n)) * w + abs(ay.dot(test_n)) * h + abs(az.dot(test_n)) * d
                            ply_proj = test_ext
                            center_dist = abs(diff.dot(test_n))
                            overlap = obj_proj + ply_proj - center_dist
                            if overlap <= 0:
                                best_axis = None
                                break
                            if overlap < best_overlap:
                                best_overlap = overlap
                                sign = 1.0 if diff.dot(test_n) > 0 else -1.0
                                best_axis = test_n * sign
                    if best_axis is not None and best_overlap > 0:
                        result = result + best_axis * best_overlap
                        if best_axis.y > 0.5:
                            grounded = True
                        pushed = True
            if not pushed:
                break
        return result, grounded

class Engine:
    def __init__(self, width=1000, height=800, fov=90, fps_limit=144, retro_mode=True):
        self.width = width
        self.height = height
        self.fov = fov
        self.fps_limit = fps_limit
        self.retro_mode = retro_mode
        self.running = True
        self.delta_time = 0.0
        self.last_time = time.time()
        self.objects = []
        self.terrain = None
        self.skybox = None
        self.lighting = SimpleLighting()
        self.camera = PlayerCamera()
        self.notifications = []
        self.tex_floor = 0
        self.tex_pillar = 0
        
        if not glfw.init():
            raise RuntimeError("Failed to init GLFW")
            
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)
        self.window = glfw.create_window(self.width, self.height, "Game", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Failed to create window")
            
        glfw.make_context_current(self.window)
        glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        
        glfw.set_window_size_callback(self.window, self._resize_callback)
        glfw.set_key_callback(self.window, self._key_callback)
        glfw.set_mouse_button_callback(self.window, self._mouse_button_callback)
        glfw.set_cursor_pos_callback(self.window, self._cursor_pos_callback)
        
        # Initialize textures
        self.tex_floor = make_tex((65, 60, 70), (35, 30, 40))
        self.tex_pillar = make_tex((220, 0, 220), (35, 0, 55))
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        
        self.retro_fbo = 0
        self.retro_tex = 0
        self.retro_depth = 0
        self.retro_w = 480
        self.retro_h = 320
        if self.retro_mode:
            self._init_retro_fbo()
        
        self.last_mouse_x, self.last_mouse_y = glfw.get_cursor_pos(self.window)

    def _init_retro_fbo(self):
        self.retro_fbo = glGenFramebuffers(1)
        self.retro_tex = glGenTextures(1)
        self.retro_depth = glGenRenderbuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.retro_fbo)
        glBindTexture(GL_TEXTURE_2D, self.retro_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.retro_w, self.retro_h, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.retro_tex, 0)
        glBindRenderbuffer(GL_RENDERBUFFER, self.retro_depth)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.retro_w, self.retro_h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.retro_depth)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def _resize_callback(self, window, w, h):
        self.width = w
        self.height = h

    def _key_callback(self, window, key, scancode, action, mods):
        if hasattr(self, 'on_key'):
            self.on_key(key, scancode, action, mods)
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            self.running = False

    def _mouse_button_callback(self, window, button, action, mods):
        if hasattr(self, 'on_mouse_button'):
            self.on_mouse_button(button, action, mods)

    def _cursor_pos_callback(self, window, x, y):
        dx = x - self.last_mouse_x
        dy = y - self.last_mouse_y
        self.last_mouse_x = x
        self.last_mouse_y = y
        self.camera.yaw += dx * self.camera.mouse_sensitivity
        self.camera.pitch += dy * self.camera.mouse_sensitivity
        self.camera.pitch = max(-89.0, min(89.0, self.camera.pitch))

    def show_notification(self, text, duration=3.0, r=1.0, g=1.0, b=1.0):
        self.notifications.append({
            "text": text,
            "timer": duration,
            "color": (r, g, b)
        })

    def init_scene(self):
        pass

    def scene_raycast(self, origin, direction):
        best_t = 1e9
        hit_pos = None
        for obj in self.objects:
            if hasattr(obj, 'width') and hasattr(obj, 'height') and hasattr(obj, 'depth'):
                w, h, d = obj.width/2, obj.height/2, obj.depth/2
                rot = getattr(obj, 'rot', Vector3())
                if rot.x == 0 and rot.y == 0 and rot.z == 0:
                    t = ray_aabb_intersection(origin, direction, (obj.pos.x - w, obj.pos.y - h, obj.pos.z - d), (obj.pos.x + w, obj.pos.y + h, obj.pos.z + d))
                else:
                    axes = _euler_to_axes(rot.x, rot.y, rot.z)
                    t = ray_obb_intersection(origin, direction, obj.pos, (w, h, d), axes)
                if t is not None and 0 < t < best_t:
                    best_t = t
                    hit_pos = origin + direction * t
        if abs(direction.y) > 1e-6:
            t = (0.0 - origin.y) / direction.y
            if 0 < t < best_t:
                pt = origin + direction * t
                if self.terrain:
                    hs = self.terrain.size / 2
                    if -hs <= pt.x <= hs and -hs <= pt.z <= hs:
                        best_t = t
                        hit_pos = pt
                else:
                    best_t = t
                    hit_pos = pt
        return hit_pos

    def run(self):
        if hasattr(self, 'on_init'):
            self.on_init()
        while self.running and not glfw.window_should_close(self.window):
            t = time.time()
            self.delta_time = min(t - self.last_time, 0.1)
            self.last_time = t
            
            glfw.poll_events()
            
            # Default keyboard movement when not grappling
            if not getattr(self, 'grappling', False):
                self.camera.momentum_x -= self.camera.momentum_x * (5.0 * self.delta_time)
                self.camera.momentum_z -= self.camera.momentum_z * (5.0 * self.delta_time)
                
                f = self.camera.get_forward()
                ff = Vector3(f.x, 0, f.z).normalize()
                r = self.camera.get_right()
                
                move_dir = Vector3()
                if glfw.get_key(self.window, glfw.KEY_W) == glfw.PRESS: move_dir = move_dir + ff
                if glfw.get_key(self.window, glfw.KEY_S) == glfw.PRESS: move_dir = move_dir - ff
                if glfw.get_key(self.window, glfw.KEY_A) == glfw.PRESS: move_dir = move_dir - r
                if glfw.get_key(self.window, glfw.KEY_D) == glfw.PRESS: move_dir = move_dir + r
                
                if move_dir.length() > 0.1:
                    move_dir = move_dir.normalize()
                
                sprint = 2.0 if glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS else 1.0
                vx = move_dir.x * self.camera.speed * sprint + self.camera.momentum_x
                vz = move_dir.z * self.camera.speed * sprint + self.camera.momentum_z
                
                self.camera.velocity.y -= 25.0 * self.delta_time
                vy = self.camera.velocity.y

                desired = self.camera.pos + Vector3(vx * self.delta_time, vy * self.delta_time, vz * self.delta_time)
                if desired.y < 1.5:
                    desired.y = 1.5
                    self.camera.velocity.y = 0.0
                    if glfw.get_key(self.window, glfw.KEY_SPACE) == glfw.PRESS:
                        self.camera.velocity.y = getattr(self, 'player_jump', 9.0)

                resolved, grounded = self.camera.resolve_collision(self.camera.pos, desired, self.objects)
                self.camera.pos = resolved
                if grounded and self.camera.velocity.y < 0:
                    self.camera.velocity.y = 0
                    if glfw.get_key(self.window, glfw.KEY_SPACE) == glfw.PRESS:
                        self.camera.velocity.y = getattr(self, 'player_jump', 9.0)
            
            if hasattr(self, 'on_update'):
                self.on_update(self.delta_time)
                
            self.render()
            glfw.swap_buffers(self.window)
        glfw.terminate()

    def render(self):
        if self.retro_mode and self.retro_fbo:
            glBindFramebuffer(GL_FRAMEBUFFER, self.retro_fbo)
            glViewport(0, 0, self.retro_w, self.retro_h)
        else:
            glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.width / self.height if self.height > 0 else 1
        gluPerspective(self.fov, aspect, 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)
        glClearColor(0.02, 0.0, 0.03, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        self.camera.look_at()
        
        if self.skybox:
            self.skybox.draw(self.camera.pos)
            
        self.lighting.enable()
        
        if getattr(self, 'fog_enabled', False):
            glEnable(GL_FOG)
            glFogi(GL_FOG_MODE, GL_LINEAR)
            
            glFogfv(GL_FOG_COLOR, getattr(self, 'fog_color', (0.02, 0.0, 0.03, 1.0)))
            glFogf(GL_FOG_START, getattr(self, 'fog_start', 10.0))
            glFogf(GL_FOG_END, getattr(self, 'fog_end', 75.0))
            
        if self.terrain:
            self.terrain.draw()
            
        for obj in self.objects:
            if getattr(obj, 'active', True):
                obj.draw()
                
        if hasattr(self, 'on_draw_3d'):
            self.on_draw_3d()
            
        glDisable(GL_FOG)
        
        if self.retro_mode and self.retro_fbo:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glViewport(0, 0, self.width, self.height)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_LIGHTING)
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.retro_tex)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glOrtho(0, 1, 0, 1, -1, 1)
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            glColor3f(1, 1, 1)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex2f(0, 0)
            glTexCoord2f(1, 0); glVertex2f(1, 0)
            glTexCoord2f(1, 1); glVertex2f(1, 1)
            glTexCoord2f(0, 1); glVertex2f(0, 1)
            glEnd()
            glPopMatrix()
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_TEXTURE_2D)
        
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        
        if hasattr(self, 'on_draw_hud'):
            self.on_draw_hud()
            
        self.notifications = [n for n in self.notifications if n["timer"] > 0]
        cy = self.height - 50
        for n in self.notifications:
            n["timer"] -= self.delta_time
            tc = (int(n["color"][0]*255), int(n["color"][1]*255), int(n["color"][2]*255), 255)
            tex, tw, th = get_text_tex(n["text"], 16, tc)
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glBindTexture(GL_TEXTURE_2D, tex)
            glColor3f(1, 1, 1)
            tx = (self.width - tw) // 2
            glBegin(GL_QUADS)
            glTexCoord2f(0, 1); glVertex2f(tx, cy)
            glTexCoord2f(1, 1); glVertex2f(tx + tw, cy)
            glTexCoord2f(1, 0); glVertex2f(tx + tw, cy + th)
            glTexCoord2f(0, 0); glVertex2f(tx, cy + th)
            glEnd()
            glDisable(GL_BLEND)
            glDisable(GL_TEXTURE_2D)
            cy -= (th + 10)
            
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)