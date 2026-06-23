from engine import (Engine, Platform, Ceiling, Pillar, Vector3, GameObjectBase,
                    Skybox, Notifications, load_sprite, ray_sphere_intersection,
                    os, glfw, random, math, Image)
from OpenGL.GL import *
from OpenGL.GLU import *
import sys

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
    def load_editor_scene(self, path):
        import json
        with open(path, "r") as f:
            data = json.load(f)
        self.objects = []
        for d in data:
            t = d.get("type", "")
            p = d.get("pos", [0, 0, 0])
            pos = Vector3(p[0], p[1], p[2])
            if t == "Pillar":
                obj = Pillar(pos, height=d.get("height", 4.0), width=d.get("width", 1.5), depth=d.get("depth", 1.5))
                mat = d.get("material", "pink")
                obj.tex_id = self.tex_pillar if mat == "pink" else (self.tex_floor if mat == "gray" else 0)
                self.objects.append(obj)
            elif t == "Platform":
                obj = Platform(size=d.get("size", 150), grid_size=10)
                mat = d.get("material", "gray")
                obj.tex_id = self.tex_floor if mat == "gray" else (self.tex_pillar if mat == "pink" else 0)
                self.terrain = obj
            elif t == "Enemy":
                self.objects.append(Enemy(pos))
            elif t == "PlayerSpawn":
                self.camera.pos = pos

    def on_init(self):
        random.seed(42)
        self.skybox = Skybox(top_color=(0.08, 0.08, 0.25), horizon_color=(0.2, 0.15, 0.4),
                             ground_color=(0.02, 0.0, 0.03))
        self.lighting.ambient_color = (0.3, 0.25, 0.35)
        self.lighting.diffuse_color = (0.7, 0.7, 0.8)
        self.lighting.specular_color = (0.4, 0.4, 0.5)
        self.lighting.light_direction = Vector3(1, 1.5, 0.5).normalize()
        self.ceiling = None
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            self.load_editor_scene(sys.argv[1])
        else:
            self.terrain = Platform(size=150, grid_size=10, tex_id=self.tex_floor)
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
        self.show_notification("Game Started - Find and destroy the enemies!", 3.0, 0.6, 0.8, 1.0)
        dir_path = os.path.dirname(os.path.abspath(__file__))
        self.idle_frames = []
        for filename in ["Idle1.png", "Idle2.png"]:
            path = os.path.join(dir_path, filename)
            if os.path.exists(path):
                tex, w, h = load_sprite(path)
                self.idle_frames.append((tex, w, h))
        if not self.idle_frames:
            fallback_path = os.path.join(dir_path, "Idle.png")
            if os.path.exists(fallback_path):
                tex, w, h = load_sprite(fallback_path)
                self.idle_frames.append((tex, w, h))
        self.shoot_frame = None
        for filename in ["Shoot.png", "GunShoot.png", "MuzzleFlash.png"]:
            path = os.path.join(dir_path, filename)
            if os.path.exists(path):
                self.shoot_frame = load_sprite(path)
                break
        self.flip_frame = None
        path = os.path.join(dir_path, "FlipOff.png")
        if os.path.exists(path):
            self.flip_frame = load_sprite(path)
        self.grapple_frame = None
        path = os.path.join(dir_path, "Grapple.png")
        if os.path.exists(path):
            self.grapple_frame = load_sprite(path)
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
        self.impacts = []
        self.init_scene()

    def on_update(self, delta_time):
        for obj in self.objects:
            if isinstance(obj, Enemy) and obj.active:
                obj.update(delta_time, self.camera.pos)
        self.tracers = [t for t in self.tracers if t["timer"] > 0]
        for t in self.tracers:
            t["timer"] -= delta_time
        self.impacts = [i for i in self.impacts if i["timer"] > 0]
        for i in self.impacts:
            i["timer"] -= delta_time
            for p in i["particles"]:
                p["pos"] = p["pos"] + p["vel"] * delta_time
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
            
            # Raycast from camera center to find where we're aiming
            hit_pos = self.scene_raycast(self.camera.pos, forward)
            cam_hit = self.camera.pos + forward * 200.0
            if hit_pos is not None:
                cam_hit = hit_pos

            # Check enemy hit (closer takes priority)
            for obj in self.objects:
                if isinstance(obj, Enemy) and obj.active:
                    dist = ray_sphere_intersection(self.camera.pos, forward, obj.pos, 0.8)
                    if dist is not None:
                        enemy_hit = self.camera.pos + forward * dist
                        if (enemy_hit - self.camera.pos).length() < (cam_hit - self.camera.pos).length():
                            cam_hit = enemy_hit
                            obj.active = False
                            self.show_notification("Enemy destroyed! +100", 1.5, 1.0, 0.6, 0.2)

            # Tracer from hand to camera-aim point
            self.tracers.append({
                "start": start_pos,
                "end": cam_hit,
                "speed": 60,
                "timer": 2,
            })

            # Impact burst at hit point
            particles = []
            for _ in range(6):
                angle1 = random.uniform(0, math.pi * 2)
                angle2 = random.uniform(0, math.pi * 2)
                speed = random.uniform(2, 5)
                vel = Vector3(math.cos(angle1) * math.sin(angle2) * speed,
                              math.cos(angle2) * speed,
                              math.sin(angle1) * math.sin(angle2) * speed)
                particles.append({"pos": cam_hit, "vel": vel})
            self.impacts.append({"particles": particles, "timer": 0.4})

    def on_key(self, key, scancode, action, mods):
        if key == glfw.KEY_F and action == glfw.PRESS:
            if not self.shooting and not self.grappling and self.flip_cooldown_timer <= 0:
                self.flipping = True
                self.flip_timer = 1.0
                self.flip_cooldown_timer = 15.0
        
        # Grapple functionality shifted from right click to the Q key
        if key == glfw.KEY_Q:
            if action == glfw.PRESS:
                hit = self.scene_raycast(self.camera.pos, self.camera.get_forward())
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
        if not self.tracers and not self.impacts:
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
            elapsed = 2.0 - t["timer"]
            total_dist = (t["end"] - t["start"]).length()
            travel_time = total_dist / t["speed"] if total_dist > 0 else 0
            progress = min(1.0, elapsed / travel_time) if travel_time > 0 else 1.0
            pos = t["start"] + (t["end"] - t["start"]) * progress
            glTranslatef(pos.x, pos.y, pos.z)
            gluSphere(quad, 0.12, 8, 8)
            glPopMatrix()
        for i in self.impacts:
            frac = i["timer"] / 0.4
            for p in i["particles"]:
                alpha = max(0.0, min(1.0, frac))
                glColor4f(1.0, 0.9, 0.3, alpha)
                glPushMatrix()
                glTranslatef(p["pos"].x, p["pos"].y, p["pos"].z)
                gluSphere(quad, 0.08, 6, 6)
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
