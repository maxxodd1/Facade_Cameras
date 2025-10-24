# Facade_Cameras - Blender Addon

**Version:** 6.8.0
**Author:** Maxim Efanov
**Compatibility:** Blender 4.5.0 and newer
**Purpose:** Automated camera creation and rendering of building facades for architectural albums

[Russian README](README.md) | [English README](README_EN.md)

---

## 📋 Description

Facade_Cameras is a professional Blender addon designed for architects and designers. It automatically creates orthographic cameras based on selected building polygons, calculates optimal framing parameters, and performs batch rendering of facades with proper file naming and cardinal direction detection.

---

## 🚀 Key Features

### ✅ Automatic Camera Creation
- Creates orthographic cameras from selected mesh polygons
- Automatic camera distance calculation based on object dimensions
- Precise clipping planes calculation
- Optimal resolution based on facade size and aspect ratio

### 🧭 Cardinal Direction Detection
- Automatic facade orientation detection (8 directions)
- **Primary:** North, South, East, West
- **Intermediate:** NE, SE, SW, NW
- Accounts for building rotation in 3D space
- Average direction calculation from polygon normals

### 📂 Smart File Naming
Format: `MeshName_FacadeNumber-Direction_YYYYMMDD_VersionNumber.png`

**Examples:**
```
Building_001-South_20251024_1.png
Building_002-East_20251024_1.png
Tower_003-NE_20251024_2.png (version 2)
```

### 🎨 Professional Rendering
- **Viewport rendering** in SOLID mode with textures
- **Automatic outline disabling** for clean images
- **Wireframe adjustment** (0.5 coefficient) for technical drawings
- **Vulkan-compatible mode** for older GPUs (via Workbench)
- **Multiple render methods** with automatic fallback

### 🗂️ Object Management
- **Camera organization** in collections by objects (`CAMS_ObjectName`)
- **Dynamic show/hide** objects during rendering
- **Object isolation** - render only the relevant object for each camera
- **Object-based management** - render cameras for specific objects

### 🔧 Versioning and Safety
- **Automatic versioning** - files won't be overwritten
- **Compatibility** - migration of legacy cameras without direction support
- **Debug logs** - detailed console messages for diagnostics

---

## 📦 Installation

1. **Download** the `Facade_Cameras_v6.8.0.zip` file
2. **Open Blender** → `Edit` → `Preferences` → `Add-ons`
3. **Click** `Install...` and select the addon file
4. **Enable** the addon in the list
5. **Find the panel** in `3D View` → press `N` → tab `"Быстрые фасады"` (Quick Facades)

---

## 🎓 Quick Start Guide

### Step 1: Prepare the Model

```
1. Import or create a 3D building model
2. Ensure the building is oriented correctly:
   • +Y points North (↑)
   • +X points East (→)
   • -Y points South (↓)
   • -X points West (←)
3. Apply transforms: Ctrl+A → All Transforms
```

**Important:** Correct orientation ensures accurate cardinal direction detection!

### Step 2: Create Cameras

```
1. Select the building object in 3D viewport
2. Enter Edit Mode (Tab)
3. Select facade polygons:
   • Single selection: click on polygon
   • Multiple selection: Shift + click
   • Loop selection: Alt + click (for connected polygons)
4. In "Quick Facades" panel:
   • Choose preset (default recommended)
   • Check "Auto-distance" (✓)
   • Check "Auto-clipping" (✓)
   • Set max resolution (2000-8192 px)
   • Click "Create Cameras"
```

**Result:** Orthographic cameras created in collection `CAMS_ObjectName`

### Step 3: Rendering Setup

```
1. Save .blend file (Ctrl+S) - REQUIRED!
2. Configure output path (optional):
   • Empty path → automatic: //renders/ObjectName/
   • Or specify your own path
3. Choose rendering options:
   • "Ignore resolution percentage" (✓) - for exact size
```

### Step 4: Rendering

Choose one of the options:

| Button | Description | When to Use |
|--------|-------------|-------------|
| **All Cameras** | Render all cameras of all objects | Full project render |
| **Selected** | Only selected cameras | Test render |
| **Object Cameras** | Cameras of active object | One building render |
| **Render (Vulkan)** | Vulkan-compatible mode | Old GPUs or OpenGL errors |

**Progress:** Displayed at the bottom of Blender window

---

## 📁 Output File Structure

### Example Structure:
```
project_folder/
├── my_building.blend
└── renders/
    ├── Building1/
    │   ├── Building1_001-North_20251024_1.png
    │   ├── Building1_002-East_20251024_1.png
    │   ├── Building1_003-South_20251024_1.png
    │   ├── Building1_003-South_20251024_2.png  (updated version)
    │   ├── Building1_004-West_20251024_1.png
    │   └── Building1_005-NE_20251024_1.png
    └── Building2/
        ├── Building2_001-North_20251024_1.png
        └── Building2_002-SW_20251024_1.png
```

### File Name Breakdown:

| Part | Example | Description |
|------|---------|-------------|
| **Object name** | `Building1` | Object name in Blender |
| **Facade number** | `001` | Sequential polygon/facade number (with leading zeros) |
| **Cardinal direction** | `North` | Automatically determined direction |
| **Date** | `20251024` | Render creation date (YYYYMMDD) |
| **Version** | `1` | Auto-increment version number |

### Cardinal Directions in Names:

| Direction | Label | Angle (degrees) |
|-----------|-------|-----------------|
| North | `North` | 337.5° - 22.5° |
| Northeast | `NE` | 22.5° - 67.5° |
| East | `East` | 67.5° - 112.5° |
| Southeast | `SE` | 112.5° - 157.5° |
| South | `South` | 157.5° - 202.5° |
| Southwest | `SW` | 202.5° - 247.5° |
| West | `West` | 247.5° - 292.5° |
| Northwest | `NW` | 292.5° - 337.5° |
| Vertical | `Vert` | Roof/floor (Z-oriented) |

---

## 🐛 Troubleshooting

### Problem: Gray/empty images without objects

**Causes and solutions:**
1. **Object is hidden:**
   - Check eye icon in Outliner
   - Check camera icon (hide_render) in Outliner

2. **Cameras created for wrong object:**
   - Ensure you selected polygons of correct object
   - Delete cameras and create again

3. **File not saved:**
   - Save .blend file before rendering
   - Addon will show a warning

4. **Clipping planes cut object:**
   - Enable "Auto-clipping"
   - Or adjust manually: select camera → Properties → Camera Data → Clip Start/End

### Problem: Cameras too close/far

**Solutions:**
1. **Enable "Auto-distance"** in creation settings
2. **Check object scale:**
   - In Object Mode: Ctrl+A → Apply → Scale
   - Scale should be 1.0 for correct calculations
3. **Adjust distance manually:**
   - Disable "Auto-distance"
   - Set desired value (usually 20-100 m)

### Problem: Incorrect cardinal directions

**Solutions:**
1. **Rotate object:**
   - In Object Mode: R → Z → 90 (rotate 90° around Z)
   - North should point in +Y direction

2. **Check polygon normals:**
   - In Edit Mode: Alt+N → Recalculate Outside
   - Enable Face Orientation: Overlays → Face Orientation
   - Blue = correct side, red = flipped

---

## 📝 Version History

### Version 6.8.0 (current)
- ✅ Fixed critical bug: cameras were created in wrong direction
- ✅ Problem with tilted surfaces solved - added horizontality check
- ✅ Disabled excessive debug logging - clean console
- ✅ Kept only critical error messages

### Version 6.7.0
- ✅ Code refactoring - eliminated ~800 lines of duplication
- ✅ Viewport optimization - improved performance
- ✅ Path validation - protection from path traversal attacks
- ✅ Camera parameter validation - prevents incorrect values
- ✅ Improved code maintainability - unified render function
- ✅ File size reduced by 16% (from 1,995 to 1,734 lines)

### Version 6.6.1
- ✅ Fixed critical bugs (division by zero, context.screen)
- ✅ Added constants instead of magic numbers
- ✅ Improved error handling and UTF-8 encoding
- ✅ Created detailed documentation and CHANGELOG

### Version 6.6.0
- ✅ Automatic cardinal direction detection (8 directions)
- ✅ File versioning - protection from overwriting
- ✅ Dynamic object visibility management
- ✅ Multiple render methods with fallback
- ✅ Vulkan-compatible mode
- ✅ Improved debugging with detailed logs
- ✅ Legacy camera migration

---

## 🆘 Support

### If you encounter problems:

1. **Check the "Troubleshooting" section** above
2. **Ensure correct action sequence**
3. **Check Blender console** for errors:
   - Windows: `Window → Toggle System Console`
   - Linux/Mac: Run Blender from terminal
4. **Collect information for report:**
   - Blender version
   - Addon version
   - Problem description
   - Console messages
   - Steps to reproduce
5. **Create Issue on GitHub** with detailed description

### Useful Resources:
- Blender API Documentation: https://docs.blender.org/api/
- Blender Stack Exchange: https://blender.stackexchange.com/
- Blender Forum: https://blenderartists.org/

---

## 👨‍💻 Author

**Developer:** Maxim Efanov
**Purpose:** Professional architectural visualization
**Version:** 6.8.0
**Date:** October 2025

---

## 📄 License

This addon is distributed freely for use in commercial and non-commercial projects.

**Terms of use:**
- Free use in personal and commercial projects
- Code modification is permitted
- Distribution is permitted with author attribution
- Author is not responsible for potential issues

---

**Happy facade rendering! 🏢📐**
