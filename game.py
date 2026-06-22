import os
import glfw
import random
from OpenGL.GL import *
from OpenGL.GLU import *
from PIL import Image
from engine import Engine, Platform, Ceiling, Pillar, Vector3, GameObjectBase
import math

class Enemy(GameObjectBase):
    def __init__(self, pos):
        super().__init__(pos, (1.0, 0.2, 0.2))
        self.speed = 3.5

    def update(self, delta_time, player_pos):
        to_player = player_pos - self.pos
        if to_player.length() > 0.1:
            self.pos = self.pos + to_player.normalize() * (self.speed * delta_time)

    def draw(self):
        glPushMatrix()
        glTranslatef(self.pos.x, self.pos.y, self.pos.z)
        glColor3f(self.color[0], self.color[1], self.color[2])
        quad = gluNewQuadric()
        gluSphere(quad, 0.8, 12, 12)
        gluDeleteQuadric(quad)
        glPopMatrix()

class Game(Engine):
    def on_init(self):
        random.seed(42)
        self.terrain = Platform(size=150, grid_size=10, tex_id=self.tex_floor)
        self.ceiling = None
        
        for _ in range(15):
            px = random.uniform(-45, 45)
            pz = random.uniform(-45, 45)
            ph = random.uniform(1.0, 5.0)
            pw = random.uniform(8.0, 16.0)
            pd = random.uniform(8.0, 16.0)
            self.objects.append(Pillar(Vector3(px, ph/2.0, pz), height=ph, width=pw, depth=pd, tex_id=self.tex_pillar))

        for _ in range(10):
            px = random.uniform(-60, 60)
            pz = random.uniform(-60, 60)
            if abs(px) < 12 and abs(pz) < 12:
                px += 25
            ph = random.uniform(12.0, 30.0)
            pw = random.uniform(4.0, 8.0)
            self.objects.append(Pillar(Vector3(px, ph/2.0, pz), height=ph, width=pw, depth=pw, tex_id=self.tex_pillar))

        for _ in range(8):
            ex = random.uniform(-40, 40)
            ez = random.uniform(-40, 40)
            if abs(ex) < 12 and abs(ez) < 12:
                ex += 20
            self.objects.append(Enemy(Vector3(ex, 1.5, ez)))

        self.camera.pos = Vector3(0, 1.5, 18)
        self.fog_enabled = True
        self.fog_color = (0.02, 0.0, 0.03, 1.0)
        self.fog_start = 10.0
        self.fog_end = 75.0
        dir_path = os.path.dirname(os.path.abspath(__file__))
        self.idle_frames = []
        for filename in ["Idle1.png", "Idle2.png"]:
            path = os.path.join(dir_path, filename)
            if os.path.exists(path):
                tex, w, h = self.load_sprite(path)
                self.idle_frames.append((tex, w, h))
        if not self.idle_frames:
            fallback_path = os.path.join(dir_path, "Idle.png")
            if os.path.exists(fallback_path):
                tex, w, h = self.load_sprite(fallback_path)
                self.idle_frames.append((tex, w, h))
        self.shoot_frame = None
        for filename in ["Shoot.png", "GunShoot.png", "MuzzleFlash.png"]:
            path = os.path.join(dir_path, filename)
            if os.path.exists(path):
                self.shoot_frame = self.load_sprite(path)
                break
        self.flip_frame = None
        path = os.path.join(dir_path, "FlipOff.png")
        if os.path.exists(path):
            self.flip_frame = self.load_sprite(path)
        self.grapple_frame = None
        path = os.path.join(dir_path, "Grapple.png")
        if os.path.exists(path):
            self.grapple_frame = self.load_sprite(path)
        self.current_frame_index = 0
        self.anim_timer = 0.0
        self.frame_duration = 1.0
        self.shooting = False
        self.shoot_timer = 0.0
        self.shoot_duration = 0.3
        self.flipping = False
        self.flip_timer = 0.0
        self.flip_cooldown_timer = 0.0
        self.grappling = False
        self.grapple_point = None
        self.grapple_vel = Vector3(0, 0, 0)
        self.grapple_hold_time = 0.0
        self.tracers = []
        self.init_scene()

    def load_sprite(self, path, threshold=240):
        img = Image.open(path).convert("RGBA")
        pixels = img.getdata()
        new_pixels = []
        for r, g, b, a in pixels:
            if r > threshold and g > threshold and b > threshold:
                new_pixels.append((r, g, b, 0))
            else:
                new_pixels.append((r, g, b, a))
        img.putdata(new_pixels)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        raw = img.tobytes("raw", "RGBA")
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw)
        return tex, img.width, img.height

    def raycast(self, start, direction):
        hit_dist = 999.0
        hit_pos = None
        if direction.y < 0:
            d = -start.y / direction.y
            if 0 < d < hit_dist:
                hit_dist = d
                hit_pos = start + direction * d
        from engine import Pillar
        for obj in self.objects:
            if not obj.active or not isinstance(obj, Pillar):
                continue
            half_w = obj.width / 2.0
            half_d = obj.depth / 2.0
            min_x, max_x = obj.pos.x - half_w, obj.pos.x + half_w
            min_y, max_y = obj.pos.y - obj.height / 2.0, obj.pos.y + obj.height / 2.0
            min_z, max_z = obj.pos.z - half_d, obj.pos.z + half_d
            t1 = (min_x - start.x) / (direction.x if direction.x != 0 else 1e-6)
            t2 = (max_x - start.x) / (direction.x if direction.x != 0 else 1e-6)
            t3 = (min_y - start.y) / (direction.y if direction.y != 0 else 1e-6)
            t4 = (max_y - start.y) / (direction.y if direction.y != 0 else 1e-6)
            t5 = (min_z - start.z) / (direction.z if direction.z != 0 else 1e-6)
            t6 = (max_z - start.z) / (direction.z if direction.z != 0 else 1e-6)
            tmin = max(min(t1, t2), min(t3, t4), min(t5, t6))
            tmax = min(max(t1, t2), max(t3, t4), max(t5, t6))
            if tmax >= 0 and tmin <= tmax:
                if 0 < tmin < hit_dist:
                    hit_dist = tmin
                    hit_pos = start + direction * tmin
        return hit_pos

    def on_update(self, delta_time):
        for obj in self.objects:
            if isinstance(obj, Enemy) and obj.active:
                obj.update(delta_time, self.camera.pos)
        self.tracers = [t for t in self.tracers if t["timer"] > 0]
        for t in self.tracers:
            t["timer"] -= delta_time
            t["pos"] = t["pos"] + t["dir"] * (t["speed"] * delta_time)
            for obj in self.objects:
                if isinstance(obj, Enemy) and obj.active:
                    if (t["pos"] - obj.pos).length() < 0.9:
                        obj.active = False
                        t["timer"] = 0.0
                        break
        if self.flip_cooldown_timer > 0:
            self.flip_cooldown_timer -= delta_time
        if self.shooting:
            self.shoot_timer -= delta_time
            if self.shoot_timer <= 0:
                self.shooting = False
        elif self.grappling and self.grapple_point:
            self.grapple_hold_time += delta_time
            to_pt = self.grapple_point - self.camera.pos
            dist = to_pt.length()
            stop_dist = 2.5
            if dist > stop_dist:
                direction = to_pt.normalize()
                # Ramping spring pull: base spring is 20, but grows the longer we hold
                spring_k = 20.0 + (self.grapple_hold_time * 25.0)
                damping = 4.5
                accel = direction * spring_k
                self.grapple_vel = self.grapple_vel + accel * delta_time
                self.grapple_vel = self.grapple_vel - self.grapple_vel * (damping * delta_time)
                # Clamp max speed (ramps up with hold time too)
                max_speed = 30.0 + (self.grapple_hold_time * 15.0)
                spd = self.grapple_vel.length()
                if spd > max_speed:
                    self.grapple_vel = self.grapple_vel.normalize() * max_speed
                # Compute new position
                new_pos = self.camera.pos + self.grapple_vel * delta_time
                # Floor clamp
                if new_pos.y < 1.5:
                    new_pos.y = 1.5
                    self.grapple_vel = Vector3(self.grapple_vel.x, 0, self.grapple_vel.z)
                # Check collision per-axis
                test_x = Vector3(new_pos.x, self.camera.pos.y, self.camera.pos.z)
                test_z = Vector3(self.camera.pos.x, self.camera.pos.y, new_pos.z)
                blocked = False
                if not self.camera.check_collision(test_x, self.objects):
                    self.camera.pos.x = new_pos.x
                else:
                    self.grapple_vel = Vector3(0, self.grapple_vel.y, self.grapple_vel.z)
                    blocked = True
                if not self.camera.check_collision(test_z, self.objects):
                    self.camera.pos.z = new_pos.z
                else:
                    self.grapple_vel = Vector3(self.grapple_vel.x, self.grapple_vel.y, 0)
                    blocked = True
                # Y axis
                self.camera.pos.y = new_pos.y
                self.camera.velocity.y = 0
                # If fully blocked, stop grapple and release with momentum
                if blocked and self.grapple_vel.length() < 1.0:
                    self.camera.momentum_x = self.grapple_vel.x
                    self.camera.momentum_z = self.grapple_vel.z
                    self.camera.velocity = Vector3(0, 0, 0)
                    self.grappling = False
                    self.grapple_point = None
                    self.grapple_vel = Vector3(0, 0, 0)
                    self.grapple_hold_time = 0.0
            else:
                # Arrived near target - transfer momentum!
                self.camera.momentum_x = self.grapple_vel.x * 0.8
                self.camera.momentum_z = self.grapple_vel.z * 0.8
                self.camera.velocity.y = max(self.grapple_vel.y * 0.5, 0.0)
                self.grappling = False
                self.grapple_point = None
                self.grapple_vel = Vector3(0, 0, 0)
                self.grapple_hold_time = 0.0
        elif self.flipping:
            self.flip_timer -= delta_time
            if self.flip_timer <= 0:
                self.flipping = False
        else:
            if len(self.idle_frames) > 1:
                self.anim_timer += delta_time
                if self.anim_timer >= self.frame_duration:
                    self.anim_timer = 0.0
                    self.current_frame_index = (self.current_frame_index + 1) % len(self.idle_frames)

    def on_mouse_button(self, button, action, mods):
        if button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS:
            self.shooting = True
            self.shoot_timer = self.shoot_duration
            self.flipping = False
            self.grappling = False
            self.grapple_point = None
            forward = self.camera.get_forward()
            right = self.camera.get_right()
            offset_left = 0.55
            offset_up = 0.5
            base_right = 1.5
            base_down = 1.2
            up = Vector3(
                right.y * forward.z - right.z * forward.y,
                right.z * forward.x - right.x * forward.z,
                right.x * forward.y - right.y * forward.x
            ).normalize()
            start_pos = self.camera.pos + (forward * 1.2) + (right * (base_right - offset_left)) - (up * (base_down - offset_up))
            # Spawn bullet logic directly from camera.pos to ensure close-up hits
            self.tracers.append({
                "pos": self.camera.pos,
                "draw_pos": start_pos, # For drawing from muzzle
                "dir": forward,
                "speed": 60,
                "length": 1,
                "timer": 2
            })
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            if action == glfw.PRESS:
                hit = self.raycast(self.camera.pos, self.camera.get_forward())
                if hit is not None:
                    self.grappling = True
                    self.grapple_point = hit
                    self.grapple_vel = Vector3(0, 0, 0)
                    self.grapple_hold_time = 0.0
                    self.flipping = False
            elif action == glfw.RELEASE:
                if self.grappling:
                    # Transfer residual velocity into momentum on manual release
                    self.camera.momentum_x = self.grapple_vel.x * 0.85
                    self.camera.momentum_z = self.grapple_vel.z * 0.85
                    # Give a little vertical boost if moving up
                    if self.grapple_vel.y > 0:
                        self.camera.velocity.y = self.grapple_vel.y * 0.6
                self.grappling = False
                self.grapple_point = None
                self.grapple_vel = Vector3(0, 0, 0)
                self.grapple_hold_time = 0.0

    def on_key(self, key, scancode, action, mods):
        if key == glfw.KEY_F and action == glfw.PRESS:
            if not self.shooting and not self.grappling and self.flip_cooldown_timer <= 0:
                self.flipping = True
                self.flip_timer = 1.0
                self.flip_cooldown_timer = 15.0

    def on_draw_3d(self):
        if self.grappling and self.grapple_point:
            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glColor4f(1.0, 1.0, 1.0, 1.0)
            glLineWidth(2.0)
            forward = self.camera.get_forward()
            right = self.camera.get_right()
            offset_left = 0.55
            offset_up = 0.5
            base_right = 1.5
            base_down = 1.2
            up = Vector3(
                right.y * forward.z - right.z * forward.y,
                right.z * forward.x - right.x * forward.z,
                right.x * forward.y - right.y * forward.x
            ).normalize()
            start_pos = self.camera.pos + (forward * 1.2) + (right * (base_right - offset_left)) - (up * (base_down - offset_up))
            glBegin(GL_LINES)
            glVertex3f(start_pos.x, start_pos.y, start_pos.z)
            glVertex3f(self.grapple_point.x, self.grapple_point.y, self.grapple_point.z)
            glEnd()
            glLineWidth(1.0)
            glEnable(GL_LIGHTING)
        if not self.tracers:
            return
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        quad = gluNewQuadric()
        for t in self.tracers:
            alpha = max(0.0, min(1.0, t["timer"] / 0.15))
            glColor4f(1.0, 0.9, 0.3, alpha)
            glPushMatrix()
            # Draw visual tracer from the hand/gun muzzle start pos (or current tracer position offset)
            current_draw_pos = t["draw_pos"] + t["dir"] * (t["speed"] * (2.0 - t["timer"]))
            glTranslatef(current_draw_pos.x, current_draw_pos.y, current_draw_pos.z)
            gluSphere(quad, 0.12, 8, 8)
            glPopMatrix()
        gluDeleteQuadric(quad)
        glEnable(GL_LIGHTING)

    def on_draw_hud(self):
        if self.shooting and self.shoot_frame:
            tex, w, h = self.shoot_frame
        elif self.grappling and self.grapple_frame:
            tex, w, h = self.grapple_frame
        elif self.flipping and self.flip_frame:
            tex, w, h = self.flip_frame
        elif self.idle_frames:
            tex, w, h = self.idle_frames[self.current_frame_index]
        else:
            return
        if not tex:
            return
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, 0, self.height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex)
        glColor4f(1, 1, 1, 1)
        scale = self.height * 0.6375 / h
        sw = w * scale
        sh = h * scale
        x = self.width - sw
        y = 0
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, y)
        glTexCoord2f(1, 0); glVertex2f(x + sw, y)
        glTexCoord2f(1, 1); glVertex2f(x + sw, y + sh)
        glTexCoord2f(0, 1); glVertex2f(x, y + sh)
        glEnd()
        glDisable(GL_TEXTURE_2D)

        # Draw small circle in middle
        cx = self.width / 2.0
        cy = self.height / 2.0
        glColor4f(1.0, 1.0, 1.0, 0.8)
        glBegin(GL_LINE_LOOP)
        num_segments = 12
        r = 4.0
        for idx in range(num_segments):
            theta = 2.0 * math.pi * float(idx) / float(num_segments)
            tx = r * math.cos(theta)
            ty = r * math.sin(theta)
            glVertex2f(cx + tx, cy + ty)
        glEnd()
        
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

def main():
    g = Game(width=1000, height=800, fov=90, fps_limit=144, retro_mode=True)
    g.run()

if __name__ == "__main__":
    main()
