# CAMERA DIRECTION DEBUG GUIDE

**Date:** October 24, 2025
**Issue:** Some cameras creating in opposite direction from polygon normal
**Status:** INVESTIGATING - Debug mode enabled

---

## Problem Report

User reports: "some cameras creating in the opposite direction of the polygon normal"
- Polygon normals ARE correctly oriented (confirmed by user)
- Issue is with camera placement/orientation logic

---

## Understanding Blender Camera Coordinate System

### Camera Local Axes:
```
+X = Right
+Y = Up
+Z = Backward (away from viewing direction)
-Z = Forward (VIEWING DIRECTION) ←←← IMPORTANT!
```

### What Should Happen:

For a building facade with normal pointing OUTWARD (away from building):

```
Building Wall (normal points AWAY from building →)
              |
    ←←← Camera looks TOWARD building
              |
        Camera Position
```

**Expected behavior:**
1. `face_normal_world` = normal of polygon (points AWAY from surface)
2. Camera position = `face_center + face_normal * distance` (camera AWAY from surface)
3. Camera looks = OPPOSITE to normal (TOWARD surface)
4. Camera local -Z should align OPPOSITE to `face_normal_world`

---

## Current Code Logic

### Line 998: Rotation Calculation
```python
rotation = face_normal_world.to_track_quat('Z', 'Y')
```

**What this does:**
- `to_track_quat('Z', 'Y')` = "Align my local +Z axis with the vector, keep +Y up"
- Camera local +Z aligns with `face_normal_world` (points AWAY from surface)
- Camera local -Z points OPPOSITE to `face_normal_world` (points TOWARD surface) ✓

**This should be CORRECT!**

### Line 1020: Position Calculation
```python
initial_location = face_center + face_normal_world * final_distance
```

**What this does:**
- Places camera in direction of normal (AWAY from surface) ✓
- Camera position = center + normal * distance
-For wall facing North: camera is NORTH of wall ✓

**This should also be CORRECT!**

---

## Debug Output Added

The code now outputs extensive debug information to the console:

### Per-Polygon Debug Info:
```
[CAMERA DEBUG] ===== Полигон N =====
[CAMERA DEBUG] Исходная нормаль: (x, y, z)
[CAMERA DEBUG] Центр полигона: (x, y, z)
[CAMERA DEBUG] Пол обнаружен (Z < 0), нормаль инвертирована  ← IF floor detected
[CAMERA DEBUG] Новая нормаль: (x, y, z)  ← IF floor detected
[CAMERA DEBUG] Направление взгляда камеры: (x, y, z)
[CAMERA DEBUG] Ожидаемое направление (против нормали): (x, y, z)
[CAMERA DEBUG] Направления совпадают: True/False  ← Should be True!
[CAMERA DEBUG] Auto distance: value
[CAMERA DEBUG] Начальная позиция камеры: (x, y, z)
[CAMERA DEBUG] Финальная позиция камеры (с offset): (x, y, z)
[CAMERA DEBUG] Offset: (x, y, z)
```

### Per-Camera Creation:
```
[CAMERA CREATE] ObjectName_face_NNN
  Позиция: (x, y, z)
  Rotation Euler (deg): (x, y, z)
  Направление фасада: North/South/East/West/etc
```

---

## Testing Instructions

### Step 1: Enable Console (Windows)
```
Window → Toggle System Console
```

### Step 2: Create Test Object
```
1. Add a Cube (Shift+A → Mesh → Cube)
2. Enter Edit Mode (Tab)
3. Enable Face Orientation overlay:
   Overlays (top right) → Face Orientation ON
   - Blue faces = normals point outward ✓
   - Red faces = normals point inward ✗
4. If faces are red: Alt+N → Recalculate Outside
```

### Step 3: Test Each Face
```
For each face of the cube:
1. Select the face (in Edit Mode)
2. Note the normal direction (arrow pointing away from face)
3. Create camera using addon: "Создать камеры"
4. Check console output
5. Exit Edit Mode (Tab)
6. Select the created camera
7. Press Numpad 0 to view through camera
8. Verify camera is LOOKING AT the face (you should see the face)
```

### Step 4: Analyze Debug Output

**For a North-facing wall (+Y normal):**
```
[CAMERA DEBUG] Исходная нормаль: (0.000, 1.000, 0.000)  ← Points North
[CAMERA DEBUG] Направление взгляда камеры: (0.000, -1.000, 0.000)  ← Should point South!
[CAMERA DEBUG] Направления совпадают: True  ← Should be True!
```

**If "Направления совпадают: False"** → BUG FOUND!

---

## Potential Issues to Check

### Issue 1: Floor Inversion Logic (Lines 983-986)
```python
if abs(z_component) > ANGLE_45_DEGREES and z_component < 0:
    face_normal_world = -face_normal_world
```

**When this triggers:**
- Polygon with normal pointing DOWN (z < -0.707)
- Example: Floor with normal = (0, 0, -1)

**What it does:**
- Inverts normal to (0, 0, 1) - points UP
- Camera will be placed ABOVE and look DOWN

**Potential problem:**
- If roof has normal pointing UP (0, 0, 1) - NO inversion
- If roof has normal pointing DOWN (0, 0, -1) - INVERTED to UP
- Both cases result in same: camera above looking down
- **This might be the issue!**

### Issue 2: to_track_quat Axis
Current: `face_normal_world.to_track_quat('Z', 'Y')`

**Alternative to test:**
```python
# Try this if 'Z' doesn't work:
rotation = face_normal_world.to_track_quat('-Z', 'Y')
```

This would align camera -Z WITH normal (looking AWAY from surface) ✗ WRONG

**Or:**
```python
# Or try inverting the normal:
rotation = (-face_normal_world).to_track_quat('Z', 'Y')
```

This would align camera +Z OPPOSITE to normal... might work?

---

## Test Cases

### Test Case 1: Cube - All 6 Faces
**Setup:**
- Default cube at origin
- Each face should have outward normal

**Expected Results:**
| Face | Normal | Camera Should Be | Camera Looks |
|------|--------|-----------------|--------------|
| Front (+Y) | (0, 1, 0) | North of cube | South (at cube) |
| Back (-Y) | (0, -1, 0) | South of cube | North (at cube) |
| Right (+X) | (1, 0, 0) | East of cube | West (at cube) |
| Left (-X) | (-1, 0, 0) | West of cube | East (at cube) |
| Top (+Z) | (0, 0, 1) | Above cube | Down (at cube) |
| Bottom (-Z) | (0, 0, -1) | Below cube → INVERTED → Above | Down (at cube) |

**Check in Debug Output:**
- All should show "Направления совпадают: True"
- Floor (bottom) should show "Пол обнаружен, нормаль инвертирована"

### Test Case 2: Building with 4 Walls
**Setup:**
- Create simple building shape
- 4 vertical walls (North, South, East, West facades)

**Expected:**
- All cameras positioned OUTSIDE building
- All cameras looking INWARD at building
- Direction labels should match actual directions

---

## How to Interpret Results

### ✅ CORRECT Behavior:
```
[CAMERA DEBUG] Направления совпадают: True
When viewing through camera (Numpad 0): You SEE the facade
```

### ❌ WRONG Behavior:
```
[CAMERA DEBUG] Направления совпадают: False
OR
When viewing through camera: You see AWAY from building (sky/background)
```

---

## Next Steps

### If All Tests Pass:
- Issue might be user-specific (incorrect normals despite user claim)
- Ask for specific test case / blend file

### If Specific Faces Fail:
- Note which faces fail (vertical? horizontal? specific directions?)
- Check if floor inversion logic is the culprit
- May need to adjust to_track_quat axis parameter

### If All Tests Fail:
- Fundamental issue with to_track_quat understanding
- Need to test alternative rotation methods
- Consider using Matrix-based rotation instead

---

## Quick Fix Attempts

If testing shows the camera is backwards, try these fixes in order:

### Fix Attempt 1: Use '-Z' track axis
```python
rotation = face_normal_world.to_track_quat('-Z', 'Y')
```

### Fix Attempt 2: Invert normal before track
```python
rotation = (-face_normal_world).to_track_quat('Z', 'Y')
```

### Fix Attempt 3: Remove floor inversion
```python
# Comment out lines 983-986
# if abs(z_component) > ANGLE_45_DEGREES and z_component < 0:
#     face_normal_world = -face_normal_world
```

### Fix Attempt 4: Rotate camera 180° around Y
```python
rotation = face_normal_world.to_track_quat('Z', 'Y')
extra_rotation = Quaternion((0, 1, 0), math.radians(180))  # 180° around Y
rotation = rotation @ extra_rotation
```

---

## Files Modified

- `fac_cams.py`: Added extensive debug output (lines 970-1007, 943-946)

---

**Status:** READY FOR TESTING

User should:
1. Enable console
2. Create test cube
3. Create cameras on all 6 faces
4. Report console output
5. Report which cameras are correct/incorrect when viewed through (Numpad 0)
