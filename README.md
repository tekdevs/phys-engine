

## **About**
Phys Engine is a 3D game engine & editor written completely from scratch in Python, utilising low level libraries in order to create complex and optimised games intuitively.

I personally decided to create the engine in Python as I felt as that there were not enough game development opportunities with the Python language, especially 3D, and the ones that do exist are heavily restricted or not free.

***
***Early in-editor screenshot***
<img width="1437" height="1032" alt="image" src="https://github.com/user-attachments/assets/ff25448f-3135-45ce-b712-8ed74fc83a88" />

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
| subprocess | Launching game process from editor |
| copy | Deep copying nodes for duplicate/paste |
| sys | Script path and argv for game launch |

## Limitations
- 3D Only (No 2D development)
- Single-Player only (May add multiplayer later down the road)
- No Real-Time global illumination and realistic lightmaps (Semi-simple graphical output only)

## How it works
To put it simply, the editor and engine work together to build the master `game.py` file which contains all the code responsible for running the game logic. `engine.py` contains the dependencies and `editor.py` is the visual editor to actually **"build"** the game. 
