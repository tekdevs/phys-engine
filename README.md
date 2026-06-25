


## **About**
Phys Engine is a 3D game engine & editor written completely from scratch in Python, utilising low level libraries in order to create complex and optimised games intuitively.

I personally decided to create the engine in Python as I felt as that there were not enough game development opportunities with the Python language, especially 3D, and the ones that do exist are heavily restricted or not open-source.

## Features
- 3D Physics & Graphics Engine
- Built-In Editor and IDE
- Unity-Like scriptable components
- Intuitive hierarchy and inspector to manage components
- Advanced object gizmos
- Collision detection and matrix
- Sprite & Animation systems
- Project management systems
- Dynamic lighting & Skybox settings
- Custom render texture pipelines
- & Many more...

## Dependencies

| Package | Install | Usage |
|---------|---------|-------|
| glfw | `pip install glfw` | Window creation, input handling (keyboard, mouse, scroll), OpenGL context |
| PyOpenGL | `pip install PyOpenGL` | 3D rendering (GL) and camera projection (GLU) |
| Pillow | `pip install Pillow` | Image/texture loading, font rendering for editor UI |

## Standard Library

| Module | Usage |
|--------|-------|
| math | Trig for geometry, vector math, radians/degrees |
| json | Save/load scene files |
| os | File paths, project directory scanning |
| time | Delta time, FPS counting |
| random | Scene randomization |
| subprocess | Launching game process from editor |
| copy | Deep copying nodes for duplicate/paste |
| sys | Script path and argv for game launch |

## Limitations
- 3D Only (No 2D development)
- Single-Player only (May add multiplayer later down the road)
- No Real-Time global illumination and realistic lightmaps (Semi-simple graphical output only)

## How It Works

The engine runs a standard game loop: input → update → render → swap buffers. `engine.py` provides the base `Engine` class with rendering (OpenGL fixed-function), collision detection, camera, and scene management. `editor.py` is a visual IDE with a hierarchy panel, inspector, gizmo transforms, and file management, it saves scenes as JSON.

Game scripts inherit from `Engine` and override `on_init()`, `on_update()`, and `on_draw()`. When you hit Play, the engine loads your scene JSON, creates all the scene objects, sets the camera to the PlayerSpawn position, and hands control to your script. Your game file (`<project>_game.py`) is auto-detected and launched in a separate process.

All objects share the same `SceneNode` base with position, rotation, scale, and visibility. The gizmo system uses ray casting to let you visually translate, rotate, and scale objects. Snap grid snaps translations to configurable increments. Scenes serialize to JSON and are backward-compatible across versions.

To put it simply, `engine.py` distributes as a building block instruction set to the editor and generated game file. You are able to edit components and directly edit objects with the built-in IDE, although since you are operating in the workspace the engine sits it, the game files are isolated to avoid mixing of code.
