


## **About**
Phys Engine is a 3D game engine & editor written completely in Python. The project utilises a variety libraries in order to create complex and optimised games intuitively. Phys Engine also includes a highly-developed editor in which presents numerous tools to ease the development process.

<img width="512" height="512" alt="icon" src="https://github.com/user-attachments/assets/4e907a29-6f91-4be9-8f10-c302a22af126" />

***
***Early in-editor screenshot***

<img width="1437" height="1034" alt="image" src="https://github.com/user-attachments/assets/4d60e916-8a31-46fe-a2d4-90afe536539f" />

## Features
- 3D Physics & Graphics Engine
- Advanced Editor and Built-In IDE
- Unity-Like scriptable components
- Intuitive hierarchy and inspector to manage components
- Advanced object gizmos
- Collision detection and matrix
- Sprite & Animation systems
- Project management systems
- Dynamic lighting & Skybox settings
- Custom render texture pipelines
- & many more...


## Dependencies

| Package | Install | Usage |
|---------|---------|-------|
| glfw | `pip install glfw` | Window creation, input handling (keyboard, mouse, scroll), OpenGL context |
| PyOpenGL | `pip install PyOpenGL` | 3D rendering (GL) and camera projection (GLU) |
| Pillow | `pip install Pillow` | Image/texture loading, font rendering for editor UI |
| imgui | `pip install imgui[glfw]` | Dear ImGui bindings for editor UI panels, inspector, hierarchy, dialogs |
| numpy | `pip install numpy` | Mesh normal calculations, array operations for vertex data |
| trimesh | `pip install trimesh` | 3D model loading (.fbx, .obj, .gltf, .glb) |

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
| re | Regex for string parsing in scene operations and project management |
| random | Randomization in scene operations and engine init |
| shutil | File copy/move operations in editor and asset panel |
| importlib.util | Dynamic script loading for game components |
| types | Runtime module type creation for script components |
| tkinter | Native file browse dialogs (filedialog) |

## Limitations
- 3D Only (No 2D development)
- Single-Player only (May add multiplayer later down the road)
- No Real-Time global illumination and realistic lightmaps (Semi-realistic graphical output only)

## How it works
To put it simply, the editor and engine work together to build the master `game.py` file which contains all the code responsible for running the game logic. `engine.py` contains the dependencies and `editor.py` is the visual editor to actually **"build"** the game. 

<img width="2175" height="1781" alt="Blank diagram" src="https://github.com/user-attachments/assets/d61a1252-6823-4ee9-b531-60c323bc335d" />
