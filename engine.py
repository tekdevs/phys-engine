import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import time
from PIL import Image, ImageDraw, ImageFont
import threading
from queue import Queue

def make_tex(c1, c2, size=4):
    t = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, t)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    b = bytearray()
    for y in range(size):
        for x in range(size):
            b.extend(c1 if (x + y) % 2 == 0 else c2)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, bytes(b))
    return t

class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def length(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        l = self.length()
        return Vector3(self.x/l, self.y/l, self.z/l) if l > 0 else Vector3(0, 0, 0)

    def dot(self, other):
        return self.x*other.x + self.y*other.y + self.z*other.z

    def distance_to(self, other):
        return (self - other).length()

class AdvancedLighting:
    def __init__(self):
        self.light_direction = Vector3(1, 1, 1).normalize()
        self.ambient_color = (0.2, 0.2, 0.25)
        self.diffuse_color = (0.6, 0.6, 0.65)
        self.specular_color = (0.8, 0.8, 0.8)
        self.time_elapsed = 0

    def enable(self):
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        light_pos = (self.light_direction.x * 100, self.light_direction.y * 100, self.light_direction.z * 100, 0)
        glLight(GL_LIGHT0, GL_POSITION, light_pos)
        glLight(GL_LIGHT0, GL_AMBIENT, (*self.ambient_color, 1.0))
        glLight(GL_LIGHT0, GL_DIFFUSE, (*self.diffuse_color, 1.0))
        glLight(GL_LIGHT0, GL_SPECULAR, (*self.specular_color, 1.0))
        glMaterial(GL_FRONT_AND_BACK, GL_SPECULAR, (0.5, 0.5, 0.5, 1.0))
        glMaterial(GL_FRONT_AND_BACK, GL_SHININESS, 16)
        glEnable(GL_NORMALIZE)

    def update(self, delta_time):
        self.time_elapsed += delta_time
        angle = (self.time_elapsed * 0.1) % (2 * math.pi)
        self.light_direction = Vector3(math.cos(angle), 0.7 + 0.3 * math.sin(angle), math.sin(angle)).normalize()

    def disable(self):
        glDisable(GL_LIGHTING)
        glDisable(GL_LIGHT0)

class SimpleLighting:
    def __init__(self):
        self.light_direction = Vector3(1, 1, 1).normalize()
        self.ambient_color = (0.4, 0.4, 0.4)
        self.diffuse_color = (0.8, 0.8, 0.8)

    def enable(self):
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        light_pos = (self.light_direction.x * 100, self.light_direction.y * 100, self.light_direction.z * 100, 0)
        glLight(GL_LIGHT0, GL_POSITION, light_pos)
        glLight(GL_LIGHT0, GL_AMBIENT, (*self.ambient_color, 1.0))
        glLight(GL_LIGHT0, GL_DIFFUSE, (*self.diffuse_color, 1.0))
        glLight(GL_LIGHT0, GL_SPECULAR, (0.8, 0.8, 0.8, 1.0))
        glEnable(GL_NORMALIZE)

    def disable(self):
        glDisable(GL_LIGHTING)
        glDisable(GL_LIGHT0)

    def update(self, delta_time):
        pass

class Platform:
    def __init__(self, size=200, grid_size=10, tex_id=0):
        self.size = size
        self.grid_size = grid_size
        self.tex_id = tex_id
        self.display_list = None
        self._build()

    def _build(self):
        self.display_list = glGenLists(1)
        glNewList(self.display_list, GL_COMPILE)
        half = self.size // 2
        glBegin(GL_QUADS)
        glNormal3f(0, 1, 0)
        for x in range(-half, half, self.grid_size):
            for z in range(-half, half, self.grid_size):
                u0, v0 = x / 4.0, z / 4.0
                u1, v1 = (x + self.grid_size) / 4.0, (z + self.grid_size) / 4.0
                glTexCoord2f(u0, v0); glVertex3f(x, 0, z)
                glTexCoord2f(u1, v0); glVertex3f(x + self.grid_size, 0, z)
                glTexCoord2f(u1, v1); glVertex3f(x + self.grid_size, 0, z + self.grid_size)
                glTexCoord2f(u0, v1); glVertex3f(x, 0, z + self.grid_size)
        glEnd()
        glEndList()

    def draw(self):
        if self.display_list:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
            glCallList(self.display_list)
            glDisable(GL_TEXTURE_2D)

class Ceiling:
    def __init__(self, size=200, height=8.0, grid_size=10, tex_id=0):
        self.size = size
        self.height = height
        self.grid_size = grid_size
        self.tex_id = tex_id
        self.display_list = None
        self._build()

    def _build(self):
        self.display_list = glGenLists(1)
        glNewList(self.display_list, GL_COMPILE)
        half = self.size // 2
        glBegin(GL_QUADS)
        glNormal3f(0, -1, 0)
        for x in range(-half, half, self.grid_size):
            for z in range(-half, half, self.grid_size):
                u0, v0 = x / 4.0, z / 4.0
                u1, v1 = (x + self.grid_size) / 4.0, (z + self.grid_size) / 4.0
                glTexCoord2f(u0, v0); glVertex3f(x, self.height, z)
                glTexCoord2f(u1, v0); glVertex3f(x + self.grid_size, self.height, z)
                glTexCoord2f(u1, v1); glVertex3f(x + self.grid_size, self.height, z + self.grid_size)
                glTexCoord2f(u0, v1); glVertex3f(x, self.height, z + self.grid_size)
        glEnd()
        glEndList()

    def draw(self):
        if self.display_list:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.tex_id)
            glCallList(self.display_list)
            glDisable(GL_TEXTURE_2D)

class GameObjectBase:
    def __init__(self, pos, color=(1, 1, 1)):
        self.pos = pos
        self.color = color
        self.active = True
        self.visible = True
        self.lod_level = 0
        self.distance_from_camera = 0

    def update_culling_state(self, camera_pos, forward, fov_angle, view_distance):
        self.distance_from_camera = camera_pos.distance_to(self.pos)
        if self.distance_from_camera > view_distance:
            self.visible = False
            return
        if self.distance_from_camera <= self.get_radius() + 3.0:
            self.visible = True
            return
        to_object = self.pos - camera_pos
        dot_product = to_object.dot(forward)
        if dot_product < -self.get_radius():
            self.visible = False
            return
        to_object_len = to_object.length()
        cos_theta = dot_product / to_object_len
        theta = math.degrees(math.acos(max(-1.0, min(1.0, cos_theta))))
        angular_size = math.degrees(math.asin(min(1.0, self.get_radius() / to_object_len)))
        self.visible = theta < (fov_angle / 2.0 + angular_size + 15.0)

    def update_lod(self):
        if self.distance_from_camera < 80:
            self.lod_level = 0
        elif self.distance_from_camera < 160:
            self.lod_level = 1
        else:
            self.lod_level = 2

    def get_radius(self):
        return 1.0

    def draw(self):
        pass

class Camera:
    def __init__(self, pos=None):
        self.pos = pos if pos else Vector3(0, 1.5, 0)
        self.pitch = 0
        self.yaw = 0
        self.speed = 4.5
        self.mouse_sensitivity = 0.15
        self.velocity = Vector3(0, 0, 0)
        self.gravity = -9.8
        self.on_ground = True
        self.jump_power = 4.8
        self.can_jump = True
        self.jump_cooldown = 0.1
        self.jump_timer = 0
        self.radius = 0.4

    def get_forward(self):
        forward = Vector3(
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            -math.sin(math.radians(self.pitch)),
            -math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        )
        return forward.normalize()

    def get_right(self):
        return Vector3(math.cos(math.radians(self.yaw)), 0, math.sin(math.radians(self.yaw))).normalize()

    def look_at(self):
        forward = self.get_forward()
        target = self.pos + forward
        gluLookAt(self.pos.x, self.pos.y, self.pos.z, target.x, target.y, target.z, 0, 1, 0)

    def update(self, keys, mouse_delta, delta_time, sprint=False, collision_objects=None):
        if mouse_delta:
            self.yaw += mouse_delta[0] * self.mouse_sensitivity
            self.pitch += mouse_delta[1] * self.mouse_sensitivity
            self.pitch = max(-89, min(89, self.pitch))

        forward = self.get_forward()
        forward.y = 0
        forward = forward.normalize() if forward.length() > 0 else Vector3(0, 0, 0)
        right = self.get_right()

        speed_mult = 2.0 if sprint else 1.0
        move_dist = self.speed * delta_time * speed_mult

        move_vec = Vector3(0, 0, 0)
        if keys.get(glfw.KEY_W):
            move_vec = move_vec + forward * move_dist
        if keys.get(glfw.KEY_S):
            move_vec = move_vec + forward * -move_dist
        if keys.get(glfw.KEY_A):
            move_vec = move_vec + right * -move_dist
        if keys.get(glfw.KEY_D):
            move_vec = move_vec + right * move_dist

        if collision_objects:
            if move_vec.x != 0:
                test_pos_x = Vector3(self.pos.x + move_vec.x, self.pos.y, self.pos.z)
                if not self.check_collision(test_pos_x, collision_objects):
                    self.pos.x = test_pos_x.x
            if move_vec.z != 0:
                test_pos_z = Vector3(self.pos.x, self.pos.y, self.pos.z + move_vec.z)
                if not self.check_collision(test_pos_z, collision_objects):
                    self.pos.z = test_pos_z.z
        else:
            self.pos.x += move_vec.x
            self.pos.z += move_vec.z

        self.velocity.y += self.gravity * delta_time
        self.pos.y += self.velocity.y * delta_time

        if self.pos.y <= 1.5:
            self.pos.y = 1.5
            self.velocity.y = 0
            self.on_ground = True
            self.can_jump = True
            self.jump_timer = 0
        else:
            self.on_ground = False

        if keys.get(glfw.KEY_SPACE) and self.on_ground and self.can_jump:
            self.velocity.y = self.jump_power
            self.on_ground = False
            self.can_jump = False
            self.jump_timer = self.jump_cooldown

        if not self.can_jump:
            self.jump_timer -= delta_time
            if self.jump_timer <= 0:
                self.can_jump = True

    def check_collision(self, test_pos, collision_objects):
        player_bottom = test_pos.y - 1.5
        player_top = test_pos.y + 0.2
        pr = self.radius
        for obj in collision_objects:
            if hasattr(obj, 'pos') and hasattr(obj, 'width') and hasattr(obj, 'height'):
                obj_bottom = obj.pos.y - obj.height / 2
                obj_top = obj.pos.y + obj.height / 2
                if player_bottom < obj_top and player_top > obj_bottom:
                    depth = getattr(obj, 'depth', obj.width)
                    if (test_pos.x + pr > obj.pos.x - obj.width / 2 and
                        test_pos.x - pr < obj.pos.x + obj.width / 2 and
                        test_pos.z + pr > obj.pos.z - depth / 2 and
                        test_pos.z - pr < obj.pos.z + depth / 2):
                        return True
        return False

class Pillar(GameObjectBase):
    def __init__(self, pos, height=8.0, width=1.5, depth=None, color=(1, 1, 1), tex_id=0):
        super().__init__(pos, color)
        self.height = height
        self.width = width
        self.depth = depth if depth is not None else width
        self.tex_id = tex_id

    def get_radius(self):
        return max(self.width, self.depth, self.height) * 0.7

    def draw(self):
        if not self.visible or not self.active:
            return
        glPushMatrix()
        glTranslatef(self.pos.x, self.pos.y, self.pos.z)
        glColor3f(self.color[0], self.color[1], self.color[2])
        w = self.width / 2
        h = self.height / 2
        d = self.depth / 2
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.tex_id)
        glBegin(GL_QUADS)
        glNormal3f(0, 0, 1)
        glTexCoord2f(0, 0); glVertex3f(-w, -h, d)
        glTexCoord2f(w, 0); glVertex3f(w, -h, d)
        glTexCoord2f(w, h); glVertex3f(w, h, d)
        glTexCoord2f(0, h); glVertex3f(-w, h, d)
        glNormal3f(0, 0, -1)
        glTexCoord2f(w, 0); glVertex3f(-w, -h, -d)
        glTexCoord2f(w, h); glVertex3f(-w, h, -d)
        glTexCoord2f(0, h); glVertex3f(w, h, -d)
        glTexCoord2f(0, 0); glVertex3f(w, -h, -d)
        glNormal3f(-1, 0, 0)
        glTexCoord2f(0, 0); glVertex3f(-w, -h, -d)
        glTexCoord2f(d, 0); glVertex3f(-w, -h, d)
        glTexCoord2f(d, h); glVertex3f(-w, h, d)
        glTexCoord2f(0, h); glVertex3f(-w, h, -d)
        glNormal3f(1, 0, 0)
        glTexCoord2f(d, 0); glVertex3f(w, -h, -d)
        glTexCoord2f(d, h); glVertex3f(w, h, -d)
        glTexCoord2f(0, h); glVertex3f(w, h, d)
        glTexCoord2f(0, 0); glVertex3f(w, -h, d)
        glNormal3f(0, 1, 0)
        glTexCoord2f(0, 0); glVertex3f(-w, h, -d)
        glTexCoord2f(w, 0); glVertex3f(-w, h, d)
        glTexCoord2f(w, d); glVertex3f(w, h, d)
        glTexCoord2f(0, d); glVertex3f(w, h, -d)
        glNormal3f(0, -1, 0)
        glTexCoord2f(0, 0); glVertex3f(-w, -h, -d)
        glTexCoord2f(w, 0); glVertex3f(w, -h, -d)
        glTexCoord2f(w, d); glVertex3f(w, -h, d)
        glTexCoord2f(0, d); glVertex3f(-w, -h, d)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glPopMatrix()

class FPSCounter:
    def __init__(self):
        self.frame_count = 0
        self.fps = 0
        self.last_time = time.time()
        self.text_texture = None
        self.text_width = 0
        self.text_height = 0
        self.visible_objects = 0
        self.culled_objects = 0
        self.total_objects = 0
        self.render_distance = 100.0

    def update(self):
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time = current_time
            self._create_text_texture()

    def _create_text_texture(self):
        cull_ratio = 0 if self.total_objects == 0 else (self.culled_objects / self.total_objects) * 100
        text = f"FPS: {self.fps} | Visible: {self.visible_objects}/{self.total_objects} | Culled: {cull_ratio:.1f}% | Render Dist: {self.render_distance:.1f}m"
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
        dummy_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        img = Image.new('RGBA', (text_width + 4, text_height + 4), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((2, 2), text, font=font, fill=(255, 255, 255, 255))
        img_data = img.tobytes("raw", "RGBA", 0, -1)
        self.text_texture = img_data
        self.text_width = img.width
        self.text_height = img.height

    def get_texture_data(self):
        if self.text_texture is None:
            self._create_text_texture()
        return self.text_texture, self.text_width, self.text_height

class CullingThread(threading.Thread):
    def __init__(self, objects, camera_pos_queue, culling_queue):
        super().__init__(daemon=True)
        self.objects = objects
        self.camera_pos_queue = camera_pos_queue
        self.culling_queue = culling_queue
        self.running = True

    def run(self):
        while self.running:
            try:
                camera_data = self.camera_pos_queue.get(timeout=0.016)
                if camera_data is None:
                    break
                camera_pos, forward, fov, view_dist = camera_data
                for obj in self.objects:
                    if not obj.active:
                        obj.visible = False
                        continue
                    obj.update_culling_state(camera_pos, forward, fov, view_dist)
                    obj.update_lod()
                self.culling_queue.put(True)
            except:
                pass

    def stop(self):
        self.running = False
        self.camera_pos_queue.put(None)

class Engine:
    def __init__(self, width=1000, height=800, fov=90, fps_limit=144, retro_mode=True):
        self.width = width
        self.height = height
        self.fov = fov
        self.fps_limit = fps_limit
        self.retro_mode = retro_mode
        self.view_distance = 200.0
        self.culling_enabled = True
        self.lod_enabled = True
        self.use_threading = True
        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW")
        self.window = glfw.create_window(width, height, "Phys Engine | Runtime Testing", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Failed to create window")
        glfw.make_context_current(self.window)
        glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        self.tex_floor = make_tex((20, 20, 25), (5, 5, 8))
        self.tex_pillar = make_tex((220, 0, 220), (35, 0, 55))
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.01, 0.01, 0.015, 1)
        glEnable(GL_FOG)
        glFogf(GL_FOG_START, 5.0)
        glFogf(GL_FOG_END, 40.0)
        glFogi(GL_FOG_MODE, GL_LINEAR)
        glFogfv(GL_FOG_COLOR, (0.01, 0.01, 0.015, 1.0))
        glMatrixMode(GL_PROJECTION)
        gluPerspective(fov, (width / height), 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)
        self.camera = Camera(Vector3(0, 1.5, 18))
        self.terrain = None
        self.ceiling = None
        self.objects = []
        if self.retro_mode:
            self.lighting = SimpleLighting()
            self.lighting.disable()
        else:
            self.lighting = AdvancedLighting()
            self.lighting.enable()
        self.fps_counter = FPSCounter()
        self.fps_counter.render_distance = self.view_distance
        self.fps_counter._create_text_texture()
        self.camera_pos_queue = Queue(maxsize=1)
        self.culling_queue = Queue()
        self.culling_thread = None
        self.running = True
        self.delta_time = 0
        self.last_time = time.time()
        
        glfw.set_mouse_button_callback(self.window, self._mouse_button_callback)
        glfw.set_key_callback(self.window, self._key_callback)
        
        self.init_fbo()
        self.on_init()

    def init_fbo(self):
        self.pixel_scale = 3
        self.retro_w = self.width // self.pixel_scale
        self.retro_h = self.height // self.pixel_scale

        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        self.fbo_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.fbo_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.retro_w, self.retro_h, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.fbo_tex, 0)

        self.rbo = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.rbo)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.retro_w, self.retro_h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.rbo)

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print("Warning: Framebuffer is not complete!")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def draw_fbo_quad(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, 0, self.height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.fbo_tex)
        glColor3f(1, 1, 1)
        
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(1, 0); glVertex2f(self.width, 0)
        glTexCoord2f(1, 1); glVertex2f(self.width, self.height)
        glTexCoord2f(0, 1); glVertex2f(0, self.height)
        glEnd()
        
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)



    def _mouse_button_callback(self, window, button, action, mods):
        self.on_mouse_button(button, action, mods)

    def _key_callback(self, window, key, scancode, action, mods):
        self.on_key(key, scancode, action, mods)

    def on_init(self):
        pass

    def on_update(self, delta_time):
        pass

    def on_draw_hud(self):
        pass

    def on_draw_3d(self):
        pass

    def on_mouse_button(self, button, action, mods):
        pass

    def on_key(self, key, scancode, action, mods):
        pass

    def init_scene(self):
        self.fps_counter.total_objects = len(self.objects)
        if self.use_threading:
            self.culling_thread = CullingThread(self.objects, self.camera_pos_queue, self.culling_queue)
            self.culling_thread.start()

    def update_culling(self):
        if not self.use_threading:
            forward = self.camera.get_forward()
            for obj in self.objects:
                if not obj.active:
                    obj.visible = False
                    continue
                if self.culling_enabled:
                    obj.update_culling_state(self.camera.pos, forward, self.fov, self.view_distance)
                else:
                    obj.visible = True
                if self.lod_enabled:
                    obj.update_lod()
        if self.use_threading and self.culling_thread and self.culling_thread.is_alive():
            try:
                if self.camera_pos_queue.empty():
                    forward = self.camera.get_forward()
                    self.camera_pos_queue.put_nowait((self.camera.pos, forward, self.fov, self.view_distance))
            except:
                pass
        self.fps_counter.visible_objects = sum(1 for obj in self.objects if obj.visible)
        self.fps_counter.culled_objects = len(self.objects) - self.fps_counter.visible_objects

    def handle_events(self):
        if glfw.window_should_close(self.window):
            self.running = False
        glfw.poll_events()
        keys = {
            glfw.KEY_W: glfw.get_key(self.window, glfw.KEY_W),
            glfw.KEY_S: glfw.get_key(self.window, glfw.KEY_S),
            glfw.KEY_A: glfw.get_key(self.window, glfw.KEY_A),
            glfw.KEY_D: glfw.get_key(self.window, glfw.KEY_D),
            glfw.KEY_SPACE: glfw.get_key(self.window, glfw.KEY_SPACE),
            glfw.KEY_LEFT_CONTROL: glfw.get_key(self.window, glfw.KEY_LEFT_CONTROL),
        }
        sprint = glfw.get_key(self.window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS
        if glfw.get_key(self.window, glfw.KEY_R) == glfw.PRESS:
            self.retro_mode = not self.retro_mode
            if self.retro_mode:
                self.lighting.disable()
            else:
                self.lighting.enable()
        if glfw.get_key(self.window, glfw.KEY_ESCAPE) == glfw.PRESS:
            self.running = False
        if glfw.get_key(self.window, glfw.KEY_C) == glfw.PRESS:
            self.culling_enabled = not self.culling_enabled
        if glfw.get_key(self.window, glfw.KEY_L) == glfw.PRESS:
            self.lod_enabled = not self.lod_enabled
        mouse_x, mouse_y = glfw.get_cursor_pos(self.window)
        center_x, center_y = self.width / 2, self.height / 2
        mouse_delta = (mouse_x - center_x, mouse_y - center_y)
        glfw.set_cursor_pos(self.window, center_x, center_y)
        self.camera.update(keys, mouse_delta, self.delta_time, sprint, self.objects)

    def render(self):
        if self.retro_mode:
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
            glViewport(0, 0, self.retro_w, self.retro_h)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        self.camera.look_at()
        self.update_culling()
        self.lighting.enable()
        if self.terrain:
            self.terrain.draw()
        if self.ceiling:
            self.ceiling.draw()
        for obj in self.objects:
            if obj.active and obj.visible:
                obj.draw()

        self.on_draw_3d()
        self.on_draw_hud()

        if self.retro_mode:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glViewport(0, 0, self.width, self.height)
            self.draw_fbo_quad()

        self.render_fps_text()
        glfw.swap_buffers(self.window)

    def render_fps_text(self):
        text_data, text_w, text_h = self.fps_counter.get_texture_data()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, 0, self.height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glColor3f(1, 1, 1)
        glRasterPos2f(10, self.height - 30)
        glDrawPixels(text_w, text_h, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def run(self):
        try:
            while self.running:
                current_time = time.time()
                self.delta_time = current_time - self.last_time
                self.last_time = current_time
                self.lighting.update(self.delta_time)
                self.on_update(self.delta_time)
                self.handle_events()
                self.render()
                self.fps_counter.update()
                sleep_time = 1.0/self.fps_limit - self.delta_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            if self.use_threading and self.culling_thread:
                self.culling_thread.stop()
                self.culling_thread.join(timeout=1.0)
            glfw.terminate()
