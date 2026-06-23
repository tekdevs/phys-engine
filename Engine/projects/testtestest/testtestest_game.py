import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from engine import (Engine, Platform, Ceiling, Pillar, Vector3, GameObjectBase,
                    Skybox, Notifications, load_sprite, ray_sphere_intersection,
                    glfw, random, math, Image)
from OpenGL.GL import *
from OpenGL.GLU import *

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
                r = d.get("rot", [0, 0, 0])
                obj.rot = Vector3(r[0], r[1], r[2])
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
                self.player_speed = d.get("speed", 12.0)
                self.player_health = d.get("health", 100.0)
                self.player_jump = d.get("jump_force", 8.0)
                self.player_grapple = d.get("grapple_speed", 60.0)
                self.camera.speed = self.player_speed

    def on_init(self):
        random.seed(42)
        self.player_speed = 12.0
        self.player_health = 100.0
        self.player_jump = 8.0
        self.player_grapple = 60.0
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
        for obj in self.objects:
            if isinstance(obj, Enemy) and obj.active:
                diff = obj.pos - self.camera.pos
                dist = diff.length()
                min_dist = 0.8 + 0.5
                if dist < min_dist and dist > 0.001:
                    push_dir = diff.normalize()
                    push_amt = (min_dist - dist) * 0.5
                    obj.pos = obj.pos + push_dir * push_amt
                    self.camera.pos = self.camera.pos - push_dir * (push_amt * 0.3)
        self.tracers = [t for t in self.tracers if t["timer"] > 0]
        for t in self.tracers:
            t["timer"] -= delta_time
        self.impacts = [i for i in self.impacts if i["timer"] > 0]
        for i in self.impacts:
            i["timer"] -= delta_time
            if i.get("flash_timer", 0) > 0:
                i["flash_timer"] -= delta_time
            for p in i["particles"]:
                new_pos = p["pos"] + p["vel"] * delta_time
                hit_wall = False
                if new_pos.y < 0.1:
                    new_pos.y = 0.1
                    hit_wall = True
                for obj in self.objects:
                    if hasattr(obj, 'width') and hasattr(obj, 'height') and hasattr(obj, 'depth'):
                        w, h, d = obj.width/2, obj.height/2, obj.depth/2
                        if (obj.pos.x - w < new_pos.x < obj.pos.x + w and
                            obj.pos.y - h < new_pos.y < obj.pos.y + h and
                            obj.pos.z - d < new_pos.z < obj.pos.z + d):
                            hit_wall = True
                            break
                if hit_wall:
                    p["vel"] = Vector3(0, 0, 0)
                    new_pos = p["pos"]
                p["pos"] = new_pos
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
                spring_k = self.player_grapple + (self.grapple_hold_time * 40.0)
                damping = 3.0
                accel = direction * spring_k
                self.grapple_vel = self.grapple_vel + accel * delta_time
                self.grapple_vel = self.grapple_vel - self.grapple_vel * (damping * delta_time)
                max_speed = self.player_grapple + (self.grapple_hold_time * 20.0)
                spd = self.grapple_vel.length()
                if spd > max_speed:
                    self.grapple_vel = self.grapple_vel.normalize() * max_speed
                new_pos = self.camera.pos + self.grapple_vel * delta_time
                if new_pos.y < 1.5:
                    new_pos.y = 1.5
                    self.grapple_vel = Vector3(self.grapple_vel.x, 0, self.grapple_vel.z)
                test_x = Vector3(new_pos.x, self.camera.pos.y, self.camera.pos.z)
                test_y = Vector3(self.camera.pos.x, new_pos.y, self.camera.pos.z)
                test_z = Vector3(self.camera.pos.x, self.camera.pos.y, new_pos.z)
                blocked = False
                if not self.camera.check_collision(test_x, self.objects):
                    self.camera.pos.x = new_pos.x
                else:
                    self.grapple_vel = Vector3(0, self.grapple_vel.y, self.grapple_vel.z)
                    blocked = True
                if not self.camera.check_collision(test_y, self.objects):
                    self.camera.pos.y = new_pos.y
                else:
                    self.grapple_vel = Vector3(self.grapple_vel.x, 0, self.grapple_vel.z)
                    blocked = True
                if not self.camera.check_collision(test_z, self.objects):
                    self.camera.pos.z = new_pos.z
                else:
                    self.grapple_vel = Vector3(self.grapple_vel.x, self.grapple_vel.y, 0)
                    blocked = True
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
                "speed": 90,
                "timer": 2,
            })

            # Impact burst at hit point - more particles, debris chunks
            particles = []
            for _ in range(16):
                angle1 = random.uniform(0, math.pi * 2)
                angle2 = random.uniform(0, math.pi * 2)
                speed = random.uniform(3, 12)
                vel = Vector3(math.cos(angle1) * math.sin(angle2) * speed,
                              math.cos(angle2) * speed,
                              math.sin(angle1) * math.sin(angle2) * speed)
                particles.append({"pos": cam_hit, "vel": vel, "size": random.uniform(0.04, 0.15), "color": (1.0, random.uniform(0.6, 1.0), random.uniform(0.1, 0.4))})
            self.impacts.append({"particles": particles, "timer": 0.6, "flash_pos": cam_hit, "flash_timer": 0.15})

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
        if self.tracers or self.impacts:
            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            quad = gluNewQuadric()
            for t in self.tracers:
                total_dist = (t["end"] - t["start"]).length()
                travel_time = total_dist / t["speed"] if total_dist > 0 else 0
                elapsed = 2.0 - t["timer"]
                progress = min(1.0, elapsed / travel_time) if travel_time > 0 else 1.0
                if progress < 1.0:
                    alpha = 1.0
                    sz = 0.12
                    pos = t["start"] + (t["end"] - t["start"]) * progress
                else:
                    break_time = elapsed - travel_time
                    alpha = max(0.0, 1.0 - break_time * 20.0)
                    sz = max(0.01, 0.12 * (1.0 - break_time * 15.0))
                    pos = t["end"]
                if alpha <= 0:
                    continue
                glColor4f(1.0, 0.9, 0.3, alpha)
                glPushMatrix()
                glTranslatef(pos.x, pos.y, pos.z)
                gluSphere(quad, sz, 6, 6)
                glPopMatrix()
            for i in self.impacts:
                frac = i["timer"] / 0.6
                flash = i.get("flash_timer", 0)
                if flash > 0:
                    fp = i["flash_pos"]
                    glColor4f(1.0, 0.9, 0.5, flash / 0.15)
                    glPushMatrix()
                    glTranslatef(fp.x, fp.y, fp.z)
                    gluSphere(quad, 0.6 * (1.0 - frac), 8, 8)
                    glPopMatrix()
                for p in i["particles"]:
                    alpha = max(0.0, min(1.0, frac))
                    c = p.get("color", (1.0, 0.9, 0.3))
                    glColor4f(c[0], c[1], c[2], alpha)
                    glPushMatrix()
                    glTranslatef(p["pos"].x, p["pos"].y, p["pos"].z)
                    sz = p.get("size", 0.08)
                    gluSphere(quad, sz * (0.3 + 0.7 * frac), 4, 4)
                    glPopMatrix()
            gluDeleteQuadric(quad)
            glEnable(GL_LIGHTING)
        self._draw_hand_sprite()

    def _draw_hand_sprite(self):
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
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
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

    def on_draw_hud(self):
        cx = self.width / 2
        cy = self.height / 2
        r = 6
        segs = 24
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor4f(1, 1, 1, 0.8)
        glLineWidth(1.5)
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2 * math.pi * i / segs
            glVertex2f(cx + math.cos(a) * r, cy + math.sin(a) * r)
        glEnd()
        glLineWidth(1)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

def main():
    g = Game(width=1000, height=800, fov=90, fps_limit=144, retro_mode=True)
    g.retro_w = 400
    g.retro_h = 250
    if g.retro_fbo:
        glBindFramebuffer(GL_FRAMEBUFFER, g.retro_fbo)
        glBindTexture(GL_TEXTURE_2D, g.retro_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, g.retro_w, g.retro_h, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glBindRenderbuffer(GL_RENDERBUFFER, g.retro_depth)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, g.retro_w, g.retro_h)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    g.run()

if __name__ == "__main__":
    main()