import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import json
import os
import time
import random
import subprocess
from engine import (Vector3, SimpleLighting, make_tex, Platform, Ceiling, Pillar, Skybox, ray_aabb_intersection,
                    _euler_to_axes, ray_obb_intersection,
                    EditorCamera, SceneNode, PillarNode, PlatformNode, PlayerSpawnNode, EnemyNode, Gizmo)
from PIL import Image, ImageDraw, ImageFont

PANEL_BG = (0.08, 0.08, 0.08)
PANEL_DARK = (0.04, 0.04, 0.04)
PANEL_BORDER = (0.13, 0.13, 0.13)
HEADER_BG = (0.06, 0.06, 0.06)
ACCENT = (0.9, 0.9, 0.92)
ACCENT_HOVER = (1.0, 1.0, 1.0)
TEXT_COLOR = (0.95, 0.95, 0.95)
TEXT_DIM = (0.7, 0.7, 0.7)
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
        self.project_name = ""
        self.project_dir = ""
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self._node_counter = 0
        self._clipboard = None
        self._hierarchy_scroll = 0
        self._hierarchy_scroll_drag = False
        self._sb_hovered = False
        self._sb_grab_offset = 0.0
        self._sb_x = 0
        self._sb_y = 0
        self._sb_h = 0
        self._sb_w = 0
        self._snap_enabled = False
        self._snap_size = 0.5
        self._dialog_active = False
        self._dialog_title = ""
        self._dialog_buffer = ""
        self._dialog_cursor = 0
        self._dialog_callback = None
        self._dialog_items = None
        self._dialog_scroll = 0
        self._key_repeat_timer = 0.0
        self._key_repeat_delay = 0.4
        self._key_repeat_rate = 0.04
        self._key_repeat_active = False
        self._init_glfw()
        self._init_gl()
        self.gizmo = Gizmo()
        self._resolve_materials()
        self.project_name = "Untitled"
        glfw.set_window_title(self.window, "Engine Editor - Untitled")
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
        if self._dialog_active and self._dialog_items is None:
            ch = chr(char)
            if ch.isprintable():
                self._dialog_buffer = self._dialog_buffer[:self._dialog_cursor] + ch + self._dialog_buffer[self._dialog_cursor:]
                self._dialog_cursor += 1
            return
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
        if self._dialog_active and self._dialog_items is not None:
            self._dialog_scroll = max(0, self._dialog_scroll - y * 22)
            return
        if self.mouse_x < 260 and self.mouse_y > 40 and self.mouse_y < self.height - 24:
            self._hierarchy_scroll -= y * 22
            max_scroll = max(0, (len(self.nodes) - 18) * 22)
            self._hierarchy_scroll = max(0, min(self._hierarchy_scroll, max_scroll))
        else:
            self.camera.update({}, self.delta_time, scroll=y)

    def _key_callback(self, window, key, scancode, action, mods):
        if self._dialog_active:
            if action == glfw.PRESS or action == glfw.REPEAT:
                if self._dialog_items is not None:
                    if key == glfw.KEY_UP:
                        idx = int(self._dialog_buffer) if self._dialog_buffer.isdigit() else 0
                        self._dialog_buffer = str(max(0, idx - 1))
                    elif key == glfw.KEY_DOWN:
                        idx = int(self._dialog_buffer) if self._dialog_buffer.isdigit() else 0
                        self._dialog_buffer = str(min(len(self._dialog_items) - 1, idx + 1))
                    elif key == glfw.KEY_ENTER or key == glfw.KEY_KP_ENTER:
                        idx = int(self._dialog_buffer) if self._dialog_buffer.isdigit() else 0
                        if 0 <= idx < len(self._dialog_items) and self._dialog_callback:
                            self._dialog_callback(self._dialog_items[idx])
                        self._close_dialog()
                    elif key == glfw.KEY_ESCAPE:
                        self._close_dialog()
                else:
                    if key == glfw.KEY_ENTER or key == glfw.KEY_KP_ENTER:
                        if self._dialog_callback:
                            self._dialog_callback(self._dialog_buffer.strip())
                        self._close_dialog()
                    elif key == glfw.KEY_ESCAPE:
                        self._close_dialog()
                    elif key == glfw.KEY_BACKSPACE:
                        if self._dialog_cursor > 0:
                            self._dialog_buffer = self._dialog_buffer[:self._dialog_cursor-1] + self._dialog_buffer[self._dialog_cursor:]
                            self._dialog_cursor -= 1
                    elif key == glfw.KEY_DELETE:
                        if self._dialog_cursor < len(self._dialog_buffer):
                            self._dialog_buffer = self._dialog_buffer[:self._dialog_cursor] + self._dialog_buffer[self._dialog_cursor+1:]
                    elif key == glfw.KEY_LEFT:
                        self._dialog_cursor = max(0, self._dialog_cursor - 1)
                    elif key == glfw.KEY_RIGHT:
                        self._dialog_cursor = min(len(self._dialog_buffer), self._dialog_cursor + 1)
                    elif key == glfw.KEY_HOME:
                        self._dialog_cursor = 0
                    elif key == glfw.KEY_END:
                        self._dialog_cursor = len(self._dialog_buffer)
            return
        if self._editing_field is not None:
            if action == glfw.PRESS or action == glfw.REPEAT:
                ctrl = mods & glfw.MOD_CONTROL
                if ctrl:
                    if key == glfw.KEY_S:
                        self._finish_editing()
                        self._save_dialog()
                        return
                    elif key == glfw.KEY_Z:
                        self._cancel_editing()
                        self._undo()
                        return
                    elif key == glfw.KEY_Y:
                        self._cancel_editing()
                        self._redo()
                        return
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
            return
        if self._hierarchy_scroll_drag:
            return
        if action == glfw.PRESS:
            ctrl = mods & glfw.MOD_CONTROL
            if key == glfw.KEY_DELETE or key == glfw.KEY_BACKSPACE:
                self._delete_selected()
            elif ctrl:
                if key == glfw.KEY_S:
                    self._save_dialog()
                elif key == glfw.KEY_O:
                    self._load_dialog()
                elif key == glfw.KEY_N:
                    self._new_scene()
                elif key == glfw.KEY_Z:
                    self._undo()
                elif key == glfw.KEY_Y:
                    self._redo()
                elif key == glfw.KEY_D:
                    self._duplicate_selected()
                elif key == glfw.KEY_C:
                    self._copy_selected()
                elif key == glfw.KEY_V:
                    self._paste_clipboard()
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
            elif key == glfw.KEY_N:
                self._snap_enabled = not self._snap_enabled
                self._set_message(f"Snap {'ON' if self._snap_enabled else 'OFF'} ({self._snap_size})")
            elif key == glfw.KEY_LEFT_BRACKET:
                sizes = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
                idx = sizes.index(self._snap_size) if self._snap_size in sizes else 2
                self._snap_size = sizes[max(0, idx - 1)]
                self._set_message(f"Snap size: {self._snap_size}")
            elif key == glfw.KEY_RIGHT_BRACKET:
                sizes = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
                idx = sizes.index(self._snap_size) if self._snap_size in sizes else 2
                self._snap_size = sizes[min(len(sizes) - 1, idx + 1)]
                self._set_message(f"Snap size: {self._snap_size}")

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

    def _duplicate_selected(self):
        if not self.selected_node:
            return
        self._snapshot()
        import copy
        new_node = copy.copy(self.selected_node)
        new_node.name = self.selected_node.name + " Copy"
        fwd = self.camera.get_forward()
        new_node.pos = self.selected_node.pos + Vector3(fwd.x * 2, 0, fwd.z * 2)
        new_node.selected = False
        self.nodes.append(new_node)
        for n in self.selected_nodes:
            n.selected = False
        self.selected_nodes.clear()
        new_node.selected = True
        self.selected_nodes.add(new_node)
        self.selected_node = new_node
        self._node_counter += 1

    def _copy_selected(self):
        if self.selected_node:
            import copy
            self._clipboard = copy.copy(self.selected_node)

    def _paste_clipboard(self):
        if not self._clipboard:
            return
        self._snapshot()
        import copy
        new_node = copy.copy(self._clipboard)
        new_node.name = self._clipboard.name + " Paste"
        fwd = self.camera.get_forward()
        new_node.pos = self._clipboard.pos + Vector3(fwd.x * 2, 0, fwd.z * 2)
        new_node.selected = False
        self.nodes.append(new_node)
        for n in self.selected_nodes:
            n.selected = False
        self.selected_nodes.clear()
        new_node.selected = True
        self.selected_nodes.add(new_node)
        self.selected_node = new_node
        self._node_counter += 1

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
            rot = node.rot if hasattr(node, 'rot') else Vector3()
            if rot.x == 0 and rot.y == 0 and rot.z == 0:
                d = ray_aabb_intersection(origin, direction,
                    (aabb_min.x, aabb_min.y, aabb_min.z),
                    (aabb_max.x, aabb_max.y, aabb_max.z))
            else:
                cx = (aabb_min.x + aabb_max.x) / 2
                cy = (aabb_min.y + aabb_max.y) / 2
                cz = (aabb_min.z + aabb_max.z) / 2
                hw = (aabb_max.x - aabb_min.x) / 2
                hh = (aabb_max.y - aabb_min.y) / 2
                hd = (aabb_max.z - aabb_min.z) / 2
                axes = _euler_to_axes(rot.x, rot.y, rot.z)
                d = ray_obb_intersection(origin, direction, Vector3(cx, cy, cz), (hw, hh, hd), axes)
            if d is not None and 0 < d < best_dist:
                best_dist = d
                best_node = node
        return best_node, best_dist

    def _handle_left_click(self):
        mx, my = self.mouse_x, self.mouse_y
        if self._dialog_active:
            self._handle_dialog_click(mx, my)
            return
        if self._hierarchy_scroll_drag:
            return
        if self._editing_field is not None:
            if not (mx > self.width - 280 and my > 40 and my < self.height - 24):
                self._finish_editing()
                return
        ph = 40
        if my < ph:
            self._handle_toolbar_click(mx, my)
            return
        if mx < 250 and my > ph and my < self.height - 24:
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
            rot = self.selected_node.rot
            hit = self.gizmo.hit_test(origin, direction, self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)) * 1.3, rot=rot)
            if hit is not None:
                self._snapshot()
                self.gizmo.start_drag(origin, direction, self.selected_node.get_world_pos(), hit, rot=rot)
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
        cx = self.width // 2
        if cx - 20 <= mx <= cx + 20 and 7 <= my <= 33:
            self._play_game()
        elif 8 <= mx <= 58 and 7 <= my <= 33:
            self._new_project_dialog()
        elif 62 <= mx <= 117 and 7 <= my <= 33:
            self._save_dialog()
        elif 121 <= mx <= 176 and 7 <= my <= 33:
            self._load_dialog()

    def _handle_add_menu_click(self, mx, mouse_y):
        x, y = 0, 40
        pw = 260
        menu_y = y + 40
        items = ["Cube", "PlayerSpawn", "Enemy"]
        for i, item in enumerate(items):
            iy = menu_y + 4 + i * 26
            if x + 10 <= mx <= x + pw - 10 and iy <= mouse_y <= iy + 24:
                real_type = "Pillar" if item == "Cube" else item
                self._add_node(real_type)
                self.show_add_menu = False
                return
        self.show_add_menu = False

    def _add_node(self, type_name):
        self._snapshot()
        fwd = self.camera.get_forward()
        pos = self.camera.pos + fwd * 10
        cls = self.NODE_TYPES.get(type_name)
        if not cls: return
        self._node_counter += 1
        node = cls(pos)
        if type_name == "Pillar":
            node.name = f"Cube {self._node_counter}"
        elif type_name == "Platform":
            node.name = f"Platform {self._node_counter}"
        elif type_name == "Enemy":
            node.name = f"Enemy {self._node_counter}"
        elif type_name == "PlayerSpawn":
            node.name = "PlayerSpawn"
        if hasattr(node, "height"):
            node.pos.y = node.height / 2
        else:
            node.pos.y = 1.5
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
        x = self.width - 280
        pw = 280
        cy = 70
        line_h = 22
        fx = x + 55
        fw = pw - 61
        if fx <= mx <= fx + fw and cy + 1 <= my <= cy + line_h - 1:
            self._snapshot()
            self._editing_field = ("name", None, node)
            self._edit_buffer = node.name
            self._edit_cursor = len(self._edit_buffer)
            self._edit_cursor_timer = 0.0
            return
        cy += line_h + 3
        props = node.get_properties()
        for key, val in props.items():
            if key == "pos" and isinstance(val, Vector3):
                pos = val
                for i, (label, axis) in enumerate([("X", 0), ("Y", 1), ("Z", 2)]):
                    fx = x + 90 + i * 62
                    fw = 60
                    if fx <= mx <= fx + fw and cy + 1 <= my <= cy + line_h - 1:
                        self._snapshot()
                        self._editing_field = ("pos", i, node)
                        val_str = f"{[pos.x, pos.y, pos.z][i]:.3f}".rstrip('0').rstrip('.')
                        if '.' not in val_str: val_str = f"{val_str}.0"
                        self._edit_buffer = val_str
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
                    val_str = f"{val:.3f}".rstrip('0').rstrip('.')
                    if '.' not in val_str: val_str = f"{val_str}.0"
                    self._edit_buffer = val_str
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
        pw = 260
        ph = self.height - 40 - 24
        content_top = 42
        content_h = ph - 42
        item_h = 22
        visible_count = int(content_h / item_h)
        total = len(self.nodes)
        max_scroll = max(0, (total - visible_count) * item_h)
        if total > visible_count and mx >= pw - 18 and content_top <= my <= content_top + content_h:
            bar_h = max(30, int(content_h * visible_count / total))
            bar_y = content_top + int((self._hierarchy_scroll / max(max_scroll, 1)) * (content_h - bar_h))
            self._sb_grab_offset = my - bar_y
            self._hierarchy_scroll_drag = True
            return
        if 8 <= my < 34 and 10 <= mx <= 250:
            self.show_add_menu = not self.show_add_menu
            return
        shift = glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
        ctrl = glfw.get_key(self.window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS
        mode = "range" if shift else ("toggle" if ctrl else "set")
        scroll_idx = int(self._hierarchy_scroll / item_h)
        for idx in range(scroll_idx, min(scroll_idx + visible_count + 1, total)):
            node = self.nodes[idx]
            y = content_top + (idx - scroll_idx) * item_h
            if y <= my < y + item_h:
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

    def _sanitize_name(self, name):
        import re
        s = re.sub(r'[^a-zA-Z0-9]', '', name.replace(' ', ''))
        return s[:40] if s else "Untitled"

    def _get_project_scene_path(self):
        if self.project_dir:
            return os.path.join(self.project_dir, "scene.json")
        return ""

    def _get_project_game_path(self):
        if self.project_dir:
            return os.path.join(self.project_dir, f"{self.project_name}_game.py")
        return ""

    def _create_project(self, name):
        sanitized = self._sanitize_name(name)
        proj_dir = os.path.join(self._base_dir, "projects", sanitized)
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(os.path.join(proj_dir, "assets"), exist_ok=True)
        game_path = os.path.join(proj_dir, f"{sanitized}_game.py")
        if not os.path.exists(game_path):
            template = open(os.path.join(self._base_dir, "testgame_game.py"), "r").read()
            with open(game_path, "w") as f:
                f.write(template)
        self.project_name = sanitized
        self.project_dir = proj_dir
        glfw.set_window_title(self.window, f"Engine Editor - {sanitized}")
        self._set_message(f"Project '{sanitized}' created")

    def _save_dialog(self):
        if not self.project_dir:
            self._new_project_dialog()
            return
        scene_path = self._get_project_scene_path()
        self.save_scene(scene_path)
        self._set_message(f"Saved to {self.project_name}")

    def _load_dialog(self):
        from tkinter import filedialog, Tk
        root = Tk()
        root.withdraw()
        root.configure(bg='#1a1a1a')
        proj_dir = filedialog.askdirectory(title="Select Project Folder")
        root.destroy()
        if proj_dir:
            name = os.path.basename(proj_dir)
            scene_file = os.path.join(proj_dir, "scene.json")
            if os.path.exists(scene_file):
                self.project_name = name
                self.project_dir = proj_dir
                glfw.set_window_title(self.window, f"Engine Editor - {name}")
                self.load_scene(scene_file)
                self._set_message(f"Loaded '{name}'")
            else:
                self._set_message("No scene.json found in folder")

    def _new_project_dialog(self):
        def on_name(name):
            if name:
                self._create_project(name)
                self._new_scene()
        self._open_dialog("New Project", callback=on_name)

    def _play_game(self):
        if not self.project_dir:
            self._set_message("Create or load a project first")
            return
        scene_path = self._get_project_scene_path()
        self.save_scene(scene_path, show_message=False)
        game_path = self._get_project_game_path()
        if os.path.exists(game_path):
            subprocess.Popen(["python", game_path, scene_path],
                             cwd=self._base_dir,
                             env={**os.environ, "PYTHONPATH": self._base_dir},
                             creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            self._set_message(f"Game file not found: {os.path.basename(game_path)}")

    def _new_scene(self):
        self.nodes = []
        self.selected_node = None
        self.selected_nodes.clear()
        self._set_message("New scene created")

    def _set_message(self, msg):
        self.message = msg
        self.message_timer = 3.0

    def _finish_editing(self):
        if self._editing_field is not None:
            key, axis, node = self._editing_field
            if key == "name":
                new_name = self._edit_buffer.strip()
                if new_name:
                    node.name = new_name
            else:
                try:
                    val = float(self._edit_buffer)
                    val = round(val, 3)
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

    def save_scene(self, path, show_message=True):
        data = [n.to_dict() for n in self.nodes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        if show_message:
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
            self.gizmo.draw(self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)) * 1.3, rot=self.selected_node.rot)

    def render_toolbar(self):
        h = 40
        self._draw_rect(0, 0, self.width, h, PANEL_DARK, PANEL_BORDER)
        btn_h = 26
        btn_y = 7

        # New Project, Save, Load on the LEFT
        self._draw_rect(8, btn_y, 50, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(14, btn_y + 5, "New", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(62, btn_y, 55, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(72, btn_y + 5, "Save", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(121, btn_y, 55, btn_h, PANEL_BG, PANEL_BORDER)
        self._draw_text(131, btn_y + 5, "Load", TEXT_COLOR, FONT_SZ_SM)

        # Project name
        if self.project_name:
            self._draw_text(185, btn_y + 5, f"| {self.project_name}", ACCENT, FONT_SZ_SM)

        # Play button centered
        pw = 40
        cx = self.width // 2
        px = cx - pw // 2
        self._draw_rect(px, btn_y, pw, btn_h, (0.15, 0.15, 0.15), PANEL_BORDER)
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.3, 0.85, 0.3)
        glBegin(GL_TRIANGLES)
        glVertex2f(cx - 5, btn_y + 5); glVertex2f(cx - 5, btn_y + btn_h - 5); glVertex2f(cx + 7, btn_y + btn_h // 2)
        glEnd()

        if self.message and self.message_timer > 0:
            tw = get_text_tex(self.message, FONT_SZ_SM, (255,255,255,255))[1]
            mx = (self.width - tw) // 2
            self._draw_text(mx, 48, self.message, TEXT_COLOR, FONT_SZ_SM)

    def render_hierarchy(self):
        x, y = 0, 40
        pw = 260
        ph = self.height - 40 - 24
        self._draw_rect(x, y, pw, ph, PANEL_BG, PANEL_BORDER)
        
        btn_bg = (0.2, 0.2, 0.25) if self.show_add_menu else (0.14, 0.14, 0.17)
        self._draw_rect(x + 10, y + 8, pw - 20, 26, btn_bg, PANEL_BORDER)
        self._draw_text(x + 85, y + 13, "+ Add Object", TEXT_BRIGHT, FONT_SZ_SM)
        
        content_top = y + 42
        content_h = ph - 42
        item_h = 22
        visible_count = int(content_h / item_h)
        total = len(self.nodes)
        max_scroll = max(0, (total - visible_count) * item_h)
        self._hierarchy_scroll = max(0, min(self._hierarchy_scroll, max_scroll))
        scroll_idx = int(self._hierarchy_scroll / item_h)

        glDisable(GL_SCISSOR_TEST)
        glEnable(GL_SCISSOR_TEST)
        glScissor(x, self.height - (content_top + content_h), pw - 18, content_h)

        cy = content_top
        for idx in range(scroll_idx, total):
            node = self.nodes[idx]
            if not node.visible: continue
            if cy + item_h > content_top + content_h + item_h:
                break
            bg = (0.18, 0.19, 0.24) if node.selected else PANEL_BG
            self._draw_rect(x + 2, cy, pw - 4, item_h, bg)
            display_name = "Cube" if node.get_type_name() == "Pillar" else node.get_type_name()
            self._draw_text(x + 10, cy + 3, f"{node.name} ({display_name})",
                          SELECTION_COLOR if node.selected else TEXT_COLOR, FONT_SZ_SM)
            cy += item_h

        glDisable(GL_SCISSOR_TEST)

        if total > visible_count:
            bar_h = max(30, int(content_h * visible_count / total))
            bar_y = content_top + int((self._hierarchy_scroll / max(max_scroll, 1)) * (content_h - bar_h))
            self._draw_rect(x + pw - 16, content_top, 14, content_h, (0.06, 0.06, 0.06))
            sb_hover = (not self._hierarchy_scroll_drag and self._sb_hovered) or self._hierarchy_scroll_drag
            bar_col = (0.45, 0.45, 0.55) if sb_hover else (0.3, 0.3, 0.35)
            self._draw_rect(x + pw - 15, bar_y, 12, bar_h, bar_col, PANEL_BORDER)
            self._sb_x = x + pw - 15
            self._sb_y = bar_y
            self._sb_h = bar_h
            self._sb_w = 12

        if self.show_add_menu:
            menu_y = y + 40
            self._draw_rect(x + 10, menu_y, pw - 20, 84, PANEL_DARK, PANEL_BORDER)
            add_items = ["Cube", "PlayerSpawn", "Enemy"]
            for i, item in enumerate(add_items):
                iy = menu_y + 4 + i * 26
                self._draw_rect(x + 12, iy, pw - 24, 24, (0.16, 0.16, 0.2))
                self._draw_text(x + 20, iy + 4, item, TEXT_COLOR, FONT_SZ_SM)

    def render_inspector(self):
        x = self.width - 280
        y = 40
        pw = 280
        ph = self.height - 40 - 24
        self._draw_rect(x, y, pw, ph, PANEL_BG, PANEL_BORDER)
        if not self.selected_node:
            self._draw_text(x + 10, y + 15, "No object selected", TEXT_COLOR, FONT_SZ_SM)
            return
        node = self.selected_node
        display_type = "Cube" if node.get_type_name() == "Pillar" else node.get_type_name()
        self._draw_text(x + 8, y + 10, f"{display_type}", TEXT_DIM, FONT_SZ_SM)
        cy = y + 30
        line_h = 22
        self._draw_rect(x, cy, pw, line_h, PANEL_BG)
        self._draw_text(x + 10, cy + 3, "Name", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(x + 55, cy + 1, pw - 61, line_h - 2, (0.18, 0.18, 0.22), (0.3, 0.3, 0.35))
        if self._editing_field and self._editing_field[0] == "name":
            self._draw_text(x + 61, cy + 3, self._edit_buffer, ACCENT, FONT_SZ_SM)
            self._draw_cursor(x + 61, cy + 3, self._edit_buffer, self._edit_cursor)
        else:
            self._draw_text(x + 61, cy + 3, node.name, TEXT_COLOR, FONT_SZ_SM)
        cy += line_h + 3
        props = node.get_properties()
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
                        self._draw_cursor(fx + 18, cy + 3, self._edit_buffer, self._edit_cursor)
                    else:
                        fv = f"{v:.3f}".rstrip('0').rstrip('.')
                        if '.' not in fv: fv = f"{fv}.0"
                        self._draw_text(fx + 18, cy + 3, fv, TEXT_COLOR, FONT_SZ_SM)
                cy += line_h + 3
            elif isinstance(val, (int, float)):
                self._draw_rect(x, cy, pw, line_h, PANEL_BG)
                self._draw_text(x + 10, cy + 3, key.capitalize(), TEXT_COLOR, FONT_SZ_SM)
                self._draw_rect(x + 110, cy + 1, pw - 116, line_h - 2, (0.18, 0.18, 0.22), (0.3, 0.3, 0.35))
                if self._editing_field and self._editing_field[0] == key:
                    self._draw_text(x + 116, cy + 3, self._edit_buffer, ACCENT, FONT_SZ_SM)
                    self._draw_cursor(x + 116, cy + 3, self._edit_buffer, self._edit_cursor)
                else:
                    fval = f"{val:.3f}".rstrip('0').rstrip('.')
                    if '.' not in fval: fval = f"{fval}.0"
                    self._draw_text(x + 116, cy + 3, fval, TEXT_COLOR, FONT_SZ_SM)
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
            else:
                cy += line_h + 3

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
        left = 8
        if self.project_name:
            self._draw_text(left, y + 4, f"Project: {self.project_name}", ACCENT, FONT_SZ_SM)
            left += len(self.project_name) * 8 + 80
        if self.selected_node:
            p = self.selected_node.get_world_pos()
            label = f"Selected: {self.selected_node.name} ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})"
            if len(self.selected_nodes) > 1:
                label += f"  [+{len(self.selected_nodes) - 1} more]"
            self._draw_text(left, y + 4, label, TEXT_COLOR, FONT_SZ_SM)
        else:
            self._draw_text(left, y + 4,
                "No selection  |  [W/S/A/D] Fly  [Shift] Sprint  [R]Rotate  [E]Move  [F]Scale",
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
            if self._editing_field is not None:
                del_held = glfw.get_key(self.window, glfw.KEY_DELETE) == glfw.PRESS
                bsp_held = glfw.get_key(self.window, glfw.KEY_BACKSPACE) == glfw.PRESS
                if del_held or bsp_held:
                    self._key_repeat_timer += self.delta_time
                    if self._key_repeat_timer >= (self._key_repeat_delay if not self._key_repeat_active else self._key_repeat_rate):
                        self._key_repeat_active = True
                        self._key_repeat_timer = 0.0
                        if del_held and self._edit_cursor < len(self._edit_buffer):
                            self._edit_buffer = self._edit_buffer[:self._edit_cursor] + self._edit_buffer[self._edit_cursor+1:]
                            self._edit_cursor_timer = 0.0
                        if bsp_held and self._edit_cursor > 0:
                            self._edit_buffer = self._edit_buffer[:self._edit_cursor-1] + self._edit_buffer[self._edit_cursor:]
                            self._edit_cursor -= 1
                            self._edit_cursor_timer = 0.0
                else:
                    self._key_repeat_active = False
                    self._key_repeat_timer = 0.0
                self.render()
                glfw.swap_buffers(self.window)
                continue
            ctrl = glfw.get_key(self.window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or glfw.get_key(self.window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS
            keys = {
                glfw.KEY_W: glfw.get_key(self.window, glfw.KEY_W) if not ctrl else 0,
                glfw.KEY_S: glfw.get_key(self.window, glfw.KEY_S) if not ctrl else 0,
                glfw.KEY_A: glfw.get_key(self.window, glfw.KEY_A) if not ctrl else 0,
                glfw.KEY_D: glfw.get_key(self.window, glfw.KEY_D) if not ctrl else 0,
                glfw.KEY_LEFT_SHIFT: glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT),
            }
            arrow_delta = None
            if not ctrl:
                ax = 0
                ay = 0
                if glfw.get_key(self.window, glfw.KEY_LEFT) == glfw.PRESS: ax -= 1
                if glfw.get_key(self.window, glfw.KEY_RIGHT) == glfw.PRESS: ax += 1
                if glfw.get_key(self.window, glfw.KEY_UP) == glfw.PRESS: ay -= 1
                if glfw.get_key(self.window, glfw.KEY_DOWN) == glfw.PRESS: ay += 1
                if ax != 0 or ay != 0:
                    arrow_delta = (ax, ay)
            mouse_delta = None
            if not self._dialog_active and not self._hierarchy_scroll_drag and (self.right_dragging or self.middle_dragging):
                dx = self.mouse_x - self.last_mouse[0]
                dy = self.mouse_y - self.last_mouse[1]
                mouse_delta = (dx, dy)
            if not self._dialog_active and not self._hierarchy_scroll_drag:
                self.camera.update(keys, self.delta_time, self.right_dragging, mouse_delta, arrow_delta=arrow_delta)
            if glfw.get_key(self.window, glfw.KEY_DELETE) == glfw.PRESS and self._editing_field is None and not self._hierarchy_scroll_drag:
                if self.selected_node:
                    self._delete_selected()
            if self.gizmo.drag_axis is not None and self.left_dragging and self.selected_node:
                origin, direction = self._screen_to_ray(self.mouse_x, self.mouse_y)
                if origin:
                    rot = self.selected_node.rot
                    delta = self.gizmo.update_drag(origin, direction,
                        self.selected_node.get_world_pos(), self.gizmo.drag_axis, rot=rot)
                    if self.gizmo.mode == "translate":
                        base_axes = [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)]
                        rotated = self.gizmo._rotate_axes([(a, None) for a in base_axes], rot)
                        axis_dir = rotated[self.gizmo.drag_axis][0]
                        self.selected_node.pos = self.selected_node.pos + axis_dir * delta
                        if self._snap_enabled:
                            s = self._snap_size
                            p = self.selected_node.pos
                            self.selected_node.pos = Vector3(
                                round(p.x / s) * s,
                                round(p.y / s) * s,
                                round(p.z / s) * s)
                            snapped = self.selected_node.get_world_pos()
                            t = (self.gizmo.drag_plane_point - snapped).dot(axis_dir)
                            self.gizmo.drag_plane_point = snapped + axis_dir * t
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
                    self.gizmo.hit_test(origin, direction, self.selected_node.get_world_pos(), max(0.5, min(3.0, gs)) * 1.3, rot=self.selected_node.rot)
            if self._editing_field is not None:
                self._edit_cursor_timer += self.delta_time
            if self._hierarchy_scroll_drag and self.left_dragging:
                pw = 260
                ph = self.height - 40 - 24
                content_top = 42
                content_h = ph - 42
                item_h = 22
                total = len(self.nodes)
                visible_count = int(content_h / item_h)
                max_scroll = max(0, (total - visible_count) * item_h)
                bar_h = max(30, int(content_h * visible_count / total))
                track_h = content_h - bar_h
                new_y = self.mouse_y - self._sb_grab_offset
                new_y = max(content_top, min(content_top + track_h, new_y))
                if track_h > 0:
                    self._hierarchy_scroll = (new_y - content_top) / track_h * max_scroll
                    self._hierarchy_scroll = max(0, min(max_scroll, self._hierarchy_scroll))
                glfw.set_cursor(self.window, glfw.create_standard_cursor(glfw.CURSOR_DISABLED))
            elif self._hierarchy_scroll_drag and not self.left_dragging:
                self._hierarchy_scroll_drag = False
                glfw.set_cursor(self.window, None)
            self._sb_hovered = False
            if not self._hierarchy_scroll_drag:
                mx2, my2 = glfw.get_cursor_pos(self.window)
                mx2, my2 = int(mx2), int(my2)
                pw = 260
                ph = self.height - 40 - 24
                content_top = 42
                content_h = ph - 42
                item_h = 22
                total = len(self.nodes)
                visible_count = int(content_h / item_h)
                if total > visible_count and pw - 15 <= mx2 <= pw - 3 and content_top <= my2 <= content_top + content_h:
                    self._sb_hovered = True
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
        if self._dialog_active:
            self.render_dialog()
        self._ortho_end()

    def _open_dialog(self, title, default="", callback=None, items=None):
        self._dialog_active = True
        self._dialog_title = title
        self._dialog_buffer = default
        self._dialog_cursor = len(default)
        self._dialog_callback = callback
        self._dialog_items = items
        self._dialog_scroll = 0

    def _close_dialog(self):
        self._dialog_active = False
        self._dialog_title = ""
        self._dialog_buffer = ""
        self._dialog_cursor = 0
        self._dialog_callback = None
        self._dialog_items = None

    def render_dialog(self):
        dw, dh = 400, 300
        dx = (self.width - dw) // 2
        dy = (self.height - dh) // 2
        self._draw_rect(dx, dy, dw, dh, (0.1, 0.1, 0.12), (0.3, 0.3, 0.35))
        self._draw_text(dx + 15, dy + 12, self._dialog_title, TEXT_COLOR, FONT_SZ_LG)
        if self._dialog_items is not None:
            item_h = 22
            list_y = dy + 40
            list_h = dh - 80
            glEnable(GL_SCISSOR_TEST)
            glScissor(dx + 10, self.height - (list_y + list_h), dw - 20, list_h)
            for i, item in enumerate(self._dialog_items):
                iy = list_y + i * item_h - self._dialog_scroll
                if iy < list_y - item_h or iy > list_y + list_h:
                    continue
                bg = (0.18, 0.19, 0.24) if self._dialog_buffer.isdigit() and i == int(self._dialog_buffer) else (0.12, 0.12, 0.15)
                self._draw_rect(dx + 10, iy, dw - 20, item_h, bg, (0.2, 0.2, 0.25))
                self._draw_text(dx + 18, iy + 3, item, TEXT_COLOR, FONT_SZ_SM)
            glDisable(GL_SCISSOR_TEST)
            bar_h = max(20, int(list_h * list_h / (len(self._dialog_items) * item_h)))
            bar_y = list_y + int(self._dialog_scroll / max(len(self._dialog_items) * item_h - list_h, 1) * (list_h - bar_h))
            self._draw_rect(dx + dw - 22, list_y, 10, list_h, (0.06, 0.06, 0.06))
            self._draw_rect(dx + dw - 21, bar_y, 8, bar_h, (0.3, 0.3, 0.35))
        else:
            iy = dy + 50
            self._draw_rect(dx + 15, iy, dw - 30, 26, (0.15, 0.15, 0.18), (0.35, 0.35, 0.4))
            self._draw_text(dx + 21, iy + 5, self._dialog_buffer, ACCENT, FONT_SZ_MD)
            if int(time.time() * 2) % 2 == 0:
                tw = get_text_tex(self._dialog_buffer[:self._dialog_cursor], FONT_SZ_MD, (255,255,255,255))[1]
                cx = dx + 21 + tw
                self._draw_rect(cx, iy + 4, 1.5, 18, (0.8, 0.8, 0.8))
        btn_y = dy + dh - 35
        btn_w = 60
        ok_x = dx + dw - 140
        cancel_x = dx + dw - 70
        self._draw_rect(ok_x, btn_y, btn_w, 26, (0.2, 0.2, 0.25), PANEL_BORDER)
        ok_tw = get_text_tex("OK", FONT_SZ_SM, (255,255,255,255))[1]
        self._draw_text(ok_x + (btn_w - ok_tw) // 2, btn_y + 5, "OK", TEXT_COLOR, FONT_SZ_SM)
        self._draw_rect(cancel_x, btn_y, btn_w, 26, (0.2, 0.2, 0.25), PANEL_BORDER)
        can_tw = get_text_tex("Cancel", FONT_SZ_SM, (255,255,255,255))[1]
        self._draw_text(cancel_x + (btn_w - can_tw) // 2, btn_y + 5, "Cancel", TEXT_COLOR, FONT_SZ_SM)

    def _handle_dialog_click(self, mx, my):
        dw, dh = 400, 300
        dx = (self.width - dw) // 2
        dy = (self.height - dh) // 2
        btn_y = dy + dh - 35
        btn_w = 60
        ok_x = dx + dw - 140
        cancel_x = dx + dw - 70
        if ok_x <= mx <= ok_x + btn_w and btn_y <= my <= btn_y + 26:
            if self._dialog_items is not None:
                idx = int(self._dialog_buffer)
                if 0 <= idx < len(self._dialog_items) and self._dialog_callback:
                    self._dialog_callback(self._dialog_items[idx])
            else:
                if self._dialog_callback:
                    self._dialog_callback(self._dialog_buffer.strip())
            self._close_dialog()
            return True
        if cancel_x <= mx <= cancel_x + btn_w and btn_y <= my <= btn_y + 26:
            self._close_dialog()
            return True
        if self._dialog_items is not None:
            item_h = 22
            list_y = dy + 40
            list_h = dh - 80
            for i in range(len(self._dialog_items)):
                iy = list_y + i * item_h - self._dialog_scroll
                if dx + 10 <= mx <= dx + dw - 20 and iy <= my <= iy + item_h:
                    self._dialog_buffer = str(i)
                    return True
        return True

def main():
    editor = Editor(1280, 720)
    editor.run()

if __name__ == "__main__":
    main()