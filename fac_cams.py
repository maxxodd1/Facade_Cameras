bl_info = {
    "name": "Быстрые фасады",
    "author": "Максим Ефанов",
    "version": (6, 6, 1),
    "blender": (4, 5, 0),
    "location": "3D View > N-панель > Быстрые фасады",
    "description": "Создаёт камеры по полигонам для рендера фасадов с автоматическим расчётом расстояния, clipping planes и созданием папок, рендером выделенных камер, рендером камер объекта и управлением по объектам. Добавлены специальные рендер-настройки и пользовательские пресеты.",
    "warning": "Перед рендером сохраните файл .blend.",
    "doc_url": "https://github.com/maxxodd1/Facade_Cameras",
    "category": "Объект",
}

import bpy
import bmesh
from mathutils import Vector, Matrix
import os
import time
import datetime
import math

CAM_COLLECTION_PREFIX = "CAMS_"
CAM_RES_X_PROP = "sde_resolution_x"
CAM_RES_Y_PROP = "sde_resolution_y"
CAM_DIRECTION_PROP = "sde_facade_direction"  # Сохраняет сторону света фасада

# Константы для математических расчетов
VERTICAL_THRESHOLD = 0.001  # Порог для определения вертикальных поверхностей (крыши/полы)
ANGLE_45_DEGREES = 0.707    # cos(45°) для определения направления нормали вверх/вниз
FRAME_PADDING = 1.05        # 5% отступ вокруг объекта в кадре
MIN_FILE_SIZE = 1000        # Минимальный размер файла для считания рендера успешным (байты)
MIN_CLIPPING_RANGE = 1.0    # Минимальный диапазон между clip_start и clip_end (метры)
DEFAULT_CLIPPING_START = 0.1    # Значение clipping start по умолчанию
DEFAULT_CLIPPING_END = 1000.0   # Значение clipping end по умолчанию


# Функция автоматического создания имени папки
def get_auto_output_path(obj_name):
    """Создать автоматический путь для рендера на основе имени объекта"""
    clean_name = bpy.path.clean_name(obj_name)
    return f"//renders/{clean_name}/"


# Функция определения стороны света по направлению нормали
def get_cardinal_direction(face_normal_world):
    """Определить сторону света по мировой нормали грани"""
    
    # Нормализуем нормаль и берем только X и Y компоненты (игнорируем Z - высоту)
    # В Blender: +Y - север, -Y - юг, +X - восток, -X - запад
    x = face_normal_world.x
    y = face_normal_world.y
    
    # Проверяем на случай вертикальных поверхностей (крыши, полы)
    if abs(x) < VERTICAL_THRESHOLD and abs(y) < VERTICAL_THRESHOLD:
        print(f"[DIRECTION DEBUG] Вертикальная поверхность обнаружена (Z={face_normal_world.z:.3f})")
        return "Верт"  # Вертикальная поверхность (крыша/пол)
    
    # Рассчитываем угол относительно севера (положительная ось Y)
    angle = math.atan2(x, y)  # atan2(east, north)
    angle_degrees = math.degrees(angle)
    
    # Нормализуем угол к диапазону 0-360°
    if angle_degrees < 0:
        angle_degrees += 360
        
    print(f"[DIRECTION DEBUG] Нормаль: ({x:.3f}, {y:.3f}, {face_normal_world.z:.3f}) -> Угол: {angle_degrees:.1f}°")
    
    # Определяем сторону света по углу
    # Север: 337.5° - 22.5° (0°)
    # Северо-восток: 22.5° - 67.5°
    # Восток: 67.5° - 112.5°
    # Юго-восток: 112.5° - 157.5°
    # Юг: 157.5° - 202.5°
    # Юго-запад: 202.5° - 247.5°
    # Запад: 247.5° - 292.5°
    # Северо-запад: 292.5° - 337.5°
    
    direction = ""
    if angle_degrees <= 22.5 or angle_degrees > 337.5:
        direction = "Север"
    elif angle_degrees <= 67.5:
        direction = "СВ"  # Северо-восток
    elif angle_degrees <= 112.5:
        direction = "Восток"
    elif angle_degrees <= 157.5:
        direction = "ЮВ"  # Юго-восток
    elif angle_degrees <= 202.5:
        direction = "Юг"
    elif angle_degrees <= 247.5:
        direction = "ЮЗ"  # Юго-запад
    elif angle_degrees <= 292.5:
        direction = "Запад"
    else:  # 292.5° - 337.5°
        direction = "СЗ"  # Северо-запад
        
    print(f"[DIRECTION DEBUG] -> Определено направление: {direction}")
    return direction


# Функция создания имени файла с версионностью
def get_versioned_filename(base_dir, obj_name, face_index, direction):
    """Создать имя файла с версионностью"""
    
    # Форматируем дату
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Базовое имя файла
    base_name = f"{obj_name}_{face_index}-{direction}_{current_date}"
    
    # Ищем максимальный номер версии
    version = 1
    if os.path.exists(base_dir):
        try:
            existing_files = os.listdir(base_dir)
            print(f"[VERSIONING DEBUG] Проверяем папку: {base_dir}")
            print(f"[VERSIONING DEBUG] Найдено файлов: {len(existing_files)}")
            
            for filename in existing_files:
                if filename.startswith(base_name) and filename.endswith('.png'):
                    print(f"[VERSIONING DEBUG] Найден похожий файл: {filename}")
                    # Извлекаем номер версии из имени файла
                    try:
                        # Формат: basename_version.png
                        version_part = filename[len(base_name):].replace('.png', '')
                        if version_part.startswith('_'):
                            current_version = int(version_part[1:])
                            version = max(version, current_version + 1)
                            print(f"[VERSIONING DEBUG] Обновлена версия до: {version}")
                    except (ValueError, IndexError):
                        continue
        except OSError as e:
            print(f"[VERSIONING ERROR] Ошибка чтения папки: {e}")
    
    final_filename = f"{base_name}_{version}.png"
    print(f"[VERSIONING DEBUG] Финальное имя файла: {final_filename}")
    return final_filename


# Функция для расчёта оптимальных clipping planes
def calculate_clipping_planes(obj, camera_location, camera_direction):
    """Рассчитать оптимальные clipping planes на основе габаритов объекта и позиции камеры"""
    try:
        # Получаем мировые координаты всех вершин объекта
        world_matrix = obj.matrix_world
        mesh = obj.data

        # Создаём временный bmesh для получения вершин
        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Получаем все вершины в мировых координатах
        world_vertices = [world_matrix @ v.co for v in bm.verts]
        bm.free()

        if not world_vertices:
            return DEFAULT_CLIPPING_START, DEFAULT_CLIPPING_END

        # Проецируем все вершины на направление камеры
        camera_dir_normalized = camera_direction.normalized()

        # Вычисляем расстояния от камеры до всех вершин вдоль направления камеры
        distances = []
        for vertex in world_vertices:
            # Вектор от камеры к вершине
            to_vertex = vertex - camera_location
            # Проекция на направление камеры (отрицательное значение = позади камеры)
            distance = to_vertex.dot(camera_dir_normalized)
            distances.append(distance)

        if not distances:
            return DEFAULT_CLIPPING_START, DEFAULT_CLIPPING_END

        min_distance = min(distances)
        max_distance = max(distances)

        # Рассчитываем более точные clipping planes на основе габаритов меша
        
        # Clip start: минимальное расстояние минус небольшой буфер (но не меньше 0.001)
        if min_distance > 0:
            # Если объект перед камерой
            clip_start = max(0.001, min_distance * 0.9 - 1.0)
        else:
            # Если объект позади камеры или пересекает плоскость камеры
            clip_start = 0.001
        
        # Clip end: максимальное расстояние с разумным буфером
        if max_distance > 0:
            # Добавляем буфер 20% от максимального расстояния, но минимум 2 метра
            buffer = max(2.0, abs(max_distance) * 0.2)
            clip_end = max_distance + buffer
        else:
            # Если весь объект позади камеры - устанавливаем разумное значение
            clip_end = max(10.0, abs(min_distance) + 5.0)

        # Проверяем минимальный диапазон между start и end
        if clip_end - clip_start < MIN_CLIPPING_RANGE:
            clip_end = clip_start + 10.0  # Минимальный диапазон 10 метров вместо 1000

        return clip_start, clip_end

    except (AttributeError, ValueError, TypeError) as e:
        print(f"Ошибка при расчёте clipping planes: {e}")
        return DEFAULT_CLIPPING_START, DEFAULT_CLIPPING_END
    except Exception as e:
        print(f"Неожиданная ошибка при расчёте clipping planes: {e}")
        return DEFAULT_CLIPPING_START, DEFAULT_CLIPPING_END


# ------------------------------------------------------------------------
# ГРУППА СВОЙСТВ ДЛЯ НАСТРОЕК
# ------------------------------------------------------------------------
class SDE_CameraProSettings(bpy.types.PropertyGroup):
    distance: bpy.props.FloatProperty(
        name="Расстояние",
        description="Расстояние от полигона до камеры (минимальное значение при автоматическом режиме)",
        default=50.0, min=0.01, unit='LENGTH'
    )
    auto_distance: bpy.props.BoolProperty(
        name="Автоматическое расстояние",
        description="Автоматически рассчитывать расстояние от крайней точки фасада с определением направления нормали",
        default=True
    )
    auto_clipping: bpy.props.BoolProperty(
        name="Автоматические clipping planes",
        description="Автоматически рассчитывать clipping planes на основе габаритов объекта",
        default=True
    )
    max_resolution: bpy.props.IntProperty(
        name="Максимальное разрешение",
        description="Разрешение для большей стороны кадра (базовое значение, процент рендера применяется отдельно)",
        default=2000, min=128, soft_max=8192
    )
    ignore_percentage: bpy.props.BoolProperty(
        name="Игнорировать процент рендера",
        description="Временно установить 100% процентов во время рендера для точного контроля размера изображения",
        default=True
    )
    output_path: bpy.props.StringProperty(
        name="Папка для рендера",
        description="Путь для сохранения отрендеренных изображений (автоматически создается по имени объекта)",
        subtype='DIR_PATH',
        default=""
    )
    preset: bpy.props.EnumProperty(
        name="Шаблон",
        description="Готовые шаблоны настроек для быстрой настройки",
        items=[('DEFAULT', "По умолчанию", "Стандартные настройки для большинства случаев"),
               ('HIGH_RES', "Высокое разрешение", "Высокое разрешение для детальных фасадов"),
               ('QUICK_PREVIEW', "Быстрый просмотр", "Низкое разрешение для быстрого предварительного просмотра")],
        default='DEFAULT',
        update=lambda self, context: self.update_preset(context)
    )

    def update_preset(self, context):
        if self.preset == 'HIGH_RES':
            self.max_resolution = 10000
            self.auto_distance = True
            self.auto_clipping = True
            self.ignore_percentage = True
            self.output_path = ""  # Использовать автоматический путь
        elif self.preset == 'QUICK_PREVIEW':
            self.max_resolution = 4000
            self.auto_distance = False
            self.auto_clipping = True
            self.ignore_percentage = False
            self.output_path = ""  # Использовать автоматический путь
        elif self.preset == 'DEFAULT':
            self.max_resolution = 2000
            self.auto_distance = True
            self.auto_clipping = True
            self.ignore_percentage = True
            self.output_path = ""


# ------------------------------------------------------------------------
# КЛАСС ДЛЯ ПОЛЬЗОВАТЕЛЬСКИХ ПРЕСЕТОВ
# ------------------------------------------------------------------------
class SDE_Preset(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Имя пресета", default="Новый пресет")
    distance: bpy.props.FloatProperty(default=50.0)
    auto_distance: bpy.props.BoolProperty(default=True)
    auto_clipping: bpy.props.BoolProperty(default=True)
    max_resolution: bpy.props.IntProperty(default=2000)
    ignore_percentage: bpy.props.BoolProperty(default=True)
    output_path: bpy.props.StringProperty(default="")


# ------------------------------------------------------------------------
# ПРЕФЕРЕНСЫ АДДОНА ДЛЯ ХРАНЕНИЯ ПРЕСЕТОВ
# ------------------------------------------------------------------------
class SDE_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    presets: bpy.props.CollectionProperty(type=SDE_Preset)
    selected_preset_index: bpy.props.IntProperty(default=0)


# ------------------------------------------------------------------------
# ОПЕРАТОР: ДОБАВИТЬ ПРЕСЕТ
# ------------------------------------------------------------------------
class SDE_OT_add_preset(bpy.types.Operator):
    bl_idname = "object.sde_add_preset"
    bl_label = "Добавить пресет"
    bl_description = "Сохранить текущие настройки как новый пресет"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.sde_cam_pro_settings
        prefs = context.preferences.addons[__name__].preferences
        new_preset = prefs.presets.add()
        new_preset.name = f"Пресет {len(prefs.presets)}"
        new_preset.distance = settings.distance
        new_preset.auto_distance = settings.auto_distance
        new_preset.auto_clipping = settings.auto_clipping
        new_preset.max_resolution = settings.max_resolution
        new_preset.ignore_percentage = settings.ignore_percentage
        new_preset.output_path = settings.output_path
        prefs.selected_preset_index = len(prefs.presets) - 1
        self.report({'INFO'}, f"Пресет «{new_preset.name}» добавлен")
        return {'FINISHED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: УДАЛИТЬ ПРЕСЕТ
# ------------------------------------------------------------------------
class SDE_OT_delete_preset(bpy.types.Operator):
    bl_idname = "object.sde_delete_preset"
    bl_label = "Удалить пресет"
    bl_description = "Удалить выбранный пресет"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__name__].preferences
        return len(prefs.presets) > 0

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        if 0 <= prefs.selected_preset_index < len(prefs.presets):
            preset_name = prefs.presets[prefs.selected_preset_index].name
            prefs.presets.remove(prefs.selected_preset_index)
            prefs.selected_preset_index = max(0, min(prefs.selected_preset_index, len(prefs.presets) - 1))
            self.report({'INFO'}, f"Пресет «{preset_name}» удалён")
        return {'FINISHED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: ЗАГРУЗИТЬ ПРЕСЕТ
# ------------------------------------------------------------------------
class SDE_OT_load_preset(bpy.types.Operator):
    bl_idname = "object.sde_load_preset"
    bl_label = "Загрузить пресет"
    bl_description = "Загрузить выбранный пресет в текущие настройки"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__name__].preferences
        return len(prefs.presets) > 0

    def execute(self, context):
        settings = context.scene.sde_cam_pro_settings
        prefs = context.preferences.addons[__name__].preferences
        if 0 <= prefs.selected_preset_index < len(prefs.presets):
            preset = prefs.presets[prefs.selected_preset_index]
            settings.distance = preset.distance
            settings.auto_distance = preset.auto_distance
            settings.auto_clipping = preset.auto_clipping
            settings.max_resolution = preset.max_resolution
            settings.ignore_percentage = preset.ignore_percentage
            settings.output_path = preset.output_path
            settings.preset = 'DEFAULT'  # Сбросить встроенный пресет
            self.report({'INFO'}, f"Пресет «{preset.name}» загружен")
        return {'FINISHED'}


# ------------------------------------------------------------------------
# UI LIST ДЛЯ ПРЕСЕТОВ
# ------------------------------------------------------------------------
class SDE_UL_preset_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name", text="", emboss=False)


# ------------------------------------------------------------------------
# ОПЕРАТОР: СОЗДАНИЕ КАМЕР
# ------------------------------------------------------------------------
class SDE_OT_create_cameras_from_faces(bpy.types.Operator):
    bl_idname = "object.sde_create_cameras_pro"
    bl_label = "Создать камеры"
    bl_description = "Создать камеры на основе выделенных полигонов с текущими настройками"
    bl_options = {'REGISTER', 'UNDO'}

    distance: bpy.props.FloatProperty()
    max_resolution: bpy.props.IntProperty()
    auto_distance: bpy.props.BoolProperty()
    auto_clipping: bpy.props.BoolProperty()

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        return obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Выберите объект типа Mesh")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [f for f in bm.faces if f.select]

        if not selected_faces:
            self.report({'WARNING'}, "Не выделен ни один полигон")
            return {'CANCELLED'}

        world_matrix = obj.matrix_world

        short_name = bpy.path.clean_name(obj.name)
        cam_collection_name = f"{CAM_COLLECTION_PREFIX}{short_name}"
        cam_collection = bpy.data.collections.get(cam_collection_name)
        if not cam_collection:
            cam_collection = bpy.data.collections.new(cam_collection_name)
            context.scene.collection.children.link(cam_collection)

        created_cameras = []
        for face in selected_faces:
            # Всегда используем весь объект для кадрирования
            verts_to_project = [world_matrix @ v.co for v in bm.verts]
            all_verts = bm.verts

            if not verts_to_project:
                continue

            cam_data_tuple = self.get_framing_data(face, world_matrix, verts_to_project, all_verts, obj)
            if not cam_data_tuple:
                continue

            final_cam_location, cam_rotation_quat, ortho_scale, res_x, res_y, clip_start, clip_end, facade_direction = cam_data_tuple

            cam_name = f"{short_name}_face_{face.index:03d}"
            camera_data = bpy.data.cameras.new(name=cam_name)
            camera_data.type = 'ORTHO'
            camera_data.ortho_scale = ortho_scale
            camera_data.clip_start = clip_start
            camera_data.clip_end = clip_end

            camera_obj = bpy.data.objects.new(name=cam_name, object_data=camera_data)
            camera_obj.location = final_cam_location
            if cam_rotation_quat is not None:
                camera_obj.rotation_euler = cam_rotation_quat.to_euler()
            else:
                print("Предупреждение: не удалось установить поворот камеры")

            camera_obj[CAM_RES_X_PROP] = res_x
            camera_obj[CAM_RES_Y_PROP] = res_y
            camera_obj[CAM_DIRECTION_PROP] = facade_direction
            
            print(f"[CAMERA CREATE] {cam_name} - направление: {facade_direction}")

            cam_collection.objects.link(camera_obj)
            created_cameras.append(camera_obj)

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"Создано камер: {len(created_cameras)} в коллекции «{cam_collection.name}»")
        return {'FINISHED'}

    def get_framing_data(self, face, world_matrix, vertices, all_verts, obj):
        try:
            # Проверяем наличие вершин
            if not all_verts or len(all_verts) == 0:
                print("Ошибка: объект не содержит вершин")
                return None

            face_normal_world = (world_matrix.to_3x3() @ face.normal).normalized()
            face_center = world_matrix @ face.calc_center_median()

            # Дополнительная проверка перед делением
            if len(all_verts) == 0:
                return None

            centroid = sum([world_matrix @ v.co for v in all_verts], Vector()) / len(all_verts)
            centroid_proj = (centroid - face_center).dot(face_normal_world)

            projs = [(world_matrix @ v.co - face_center).dot(face_normal_world) for v in all_verts]

            if centroid_proj > 0:
                face_normal_world = -face_normal_world
                projs = [-p for p in projs]
                centroid_proj = (centroid - face_center).dot(face_normal_world)

            z_dot = face_normal_world.dot(Vector((0, 0, 1)))
            if abs(z_dot) > ANGLE_45_DEGREES and z_dot < 0:
                face_normal_world = -face_normal_world
                projs = [-p for p in projs]

            rotation = (-face_normal_world).to_track_quat('-Z', 'Y')

            if self.auto_distance:
                min_proj = min(projs)
                buffer = max(10.0, -min_proj * 0.1)
                final_distance = max(self.distance, -min_proj + buffer)
            else:
                final_distance = self.distance

            initial_location = face_center + face_normal_world * final_distance

            view_matrix = (Matrix.Translation(initial_location) @ rotation.to_matrix().to_4x4()).inverted()
            projected_points = [view_matrix @ v for v in vertices]

            min_x = min(p.x for p in projected_points)
            max_x = max(p.x for p in projected_points)
            min_y = min(p.y for p in projected_points)
            max_y = max(p.y for p in projected_points)

            width = max_x - min_x
            height = max_y - min_y
            if width <= 0 or height <= 0:
                return None

            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2

            rotation_mat = rotation.to_matrix()
            offset = rotation_mat @ Vector((center_x, center_y, 0))
            final_location = initial_location + offset

            padding = FRAME_PADDING

            effective_max_res = self.max_resolution
            content_aspect = width / height if height != 0 else 1.0
            res_x, res_y = 1920, 1080
            if effective_max_res > 0:
                if content_aspect > 1.0:
                    res_x = int(effective_max_res)
                    res_y = int(effective_max_res / content_aspect) if content_aspect != 0 else 1
                else:
                    res_y = int(effective_max_res)
                    res_x = int(effective_max_res * content_aspect)

            res_x = max(res_x, 1)
            res_y = max(res_y, 1)

            final_scale = max(width, height) * padding

            # Рассчитываем clipping planes
            if self.auto_clipping:
                camera_direction = -face_normal_world  # Направление взгляда камеры
                clip_start, clip_end = calculate_clipping_planes(obj, final_location, camera_direction)
            else:
                # Значения по умолчанию
                clip_start = 0.001
                clip_end = max(100000.0, final_scale * 1000.0)

            # Определяем сторону света для фасада
            facade_direction = get_cardinal_direction(face_normal_world)

            return (final_location, rotation, final_scale, res_x, res_y, clip_start, clip_end, facade_direction)
        except Exception as e:
            print(f"Ошибка при обработке полигона: {e}")
            return None


# ------------------------------------------------------------------------
# ОПЕРАТОР: РЕНДЕР ВЫДЕЛЕННЫХ КАМЕР
# ------------------------------------------------------------------------
class SDE_OT_render_selected_cameras(bpy.types.Operator):
    bl_idname = "object.sde_render_selected_cameras"
    bl_label = "Отрендерить выделенные камеры"
    bl_description = "Выполнить рендер только выделенных камер с изоляцией активного объекта"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # Более эффективная проверка - прерываем на первом найденном объекте
        if bpy.data.filepath == "":
            return False
        
        for obj in context.scene.objects:
            if obj.select_get() and obj.type == 'CAMERA' and CAM_RES_X_PROP in obj:
                return True
        return False

    def execute(self, context):
        settings = context.scene.sde_cam_pro_settings
        if bpy.data.filepath == "":
            self.report({'WARNING'}, "Перед рендером сохраните файл .blend")
            return {'CANCELLED'}

        # Получаем только выделенные камеры аддона
        selected_cameras = [obj for obj in context.scene.objects
                            if obj.select_get() and obj.type == 'CAMERA' and CAM_RES_X_PROP in obj]
                            
        # Обновляем старые камеры без информации о направлении
        for cam in selected_cameras:
            if CAM_DIRECTION_PROP not in cam:
                print(f"[MIGRATION] Обновляем камеру {cam.name} - добавляем информацию о направлении")
                cam[CAM_DIRECTION_PROP] = "Неизв"  # Для совместимости со старыми камерами

        if not selected_cameras:
            self.report({'WARNING'}, "Не выделено ни одной камеры, созданной аддоном")
            return {'CANCELLED'}

        # Используем тот же код рендера, но только для выделенных камер
        return self._render_cameras(context, settings, selected_cameras)

    def _render_cameras(self, context, settings, cameras_to_render):
        # Аналогичный код как в SDE_OT_render_all_cameras, но для конкретного списка камер
        # Сохранение исходных настроек
        original_camera = context.scene.camera
        original_res_x = context.scene.render.resolution_x
        original_res_y = context.scene.render.resolution_y
        original_percentage = context.scene.render.resolution_percentage
        original_filepath = context.scene.render.filepath
        original_format = context.scene.render.image_settings.file_format
        original_mode = context.mode

        # Добавленные сохранения для рендера
        scene = context.scene
        original_display_device = scene.display_settings.display_device
        original_view_transform = scene.view_settings.view_transform
        
        # Безопасный поиск 3D viewport для сохранения настроек outline
        original_show_object_outline = False
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    if hasattr(space, 'shading') and hasattr(space.shading, 'show_object_outline'):
                        original_show_object_outline = space.shading.show_object_outline
                        break

        view3d_area = None
        original_view_persp = None
        original_show_overlays = True
        original_shading_type = None
        original_shading_light = None
        original_shading_color = None
        original_wireframe_threshold = None
        original_show_wireframe = None

        if context.screen:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    view3d_area = area
                    space_data = area.spaces.active
                    original_view_persp = space_data.region_3d.view_perspective
                    original_show_overlays = space_data.overlay.show_overlays
                    original_shading_type = space_data.shading.type
                    original_shading_light = space_data.shading.light
                    original_shading_color = space_data.shading.color_type
                    # Сохраняем настройки wireframe
                    if hasattr(space_data.overlay, 'wireframe_threshold'):
                        original_wireframe_threshold = space_data.overlay.wireframe_threshold
                    if hasattr(space_data.overlay, 'show_wireframes'):
                        original_show_wireframe = space_data.overlay.show_wireframes
                    break

        wm = context.window_manager
        rendered_count = 0
        original_visibility_state = {}

        try:
            # Переходим в Object Mode
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            # Определяем объект для рендера - ищем меш, а не камеру
            target_object = context.active_object
            # Если активный объект - камера, ищем меш по имени камеры
            if target_object and target_object.type == 'CAMERA':
                cam_name = target_object.name
                print(f"[DEBUG] Активная камера: {cam_name}")
                
                # Способ 1: извлекаем имя объекта из имени камеры (формат: ObjectName_face_XXX)
                if '_face_' in cam_name:
                    object_name = cam_name.split('_face_')[0]
                    mesh_object = bpy.data.objects.get(object_name)
                    if mesh_object and mesh_object.type == 'MESH':
                        target_object = mesh_object
                        print(f"[DEBUG] Найден меш по имени камеры: {target_object.name}")
                
                # Способ 2: ищем через коллекции камер (если первый не сработал)
                if target_object.type == 'CAMERA':
                    for collection in bpy.data.collections:
                        if collection.name.startswith(CAM_COLLECTION_PREFIX) and target_object in collection.objects.values():
                            # Извлекаем имя объекта из имени коллекции
                            obj_name_from_collection = collection.name[len(CAM_COLLECTION_PREFIX):]
                            mesh_object = bpy.data.objects.get(obj_name_from_collection)
                            if mesh_object and mesh_object.type == 'MESH':
                                target_object = mesh_object
                                print(f"[DEBUG] Найден меш через коллекцию: {target_object.name}")
                                break
            
            print(f"[DEBUG] Целевой объект для рендера: {target_object.name if target_object else 'None'}")
            
            # Сохраняем исходное состояние видимости всех объектов для восстановления
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    original_visibility_state[obj.name] = (obj.hide_viewport, obj.hide_render)
            print("[DEBUG] Используем динамическое управление видимостью для каждой камеры")

            # Настройки рендера
            if settings.ignore_percentage:
                context.scene.render.resolution_percentage = 100

            # Специальные настройки для рендера
            scene.display_settings.display_device = 'sRGB'
            scene.view_settings.view_transform = 'Standard'
            
            # Безопасное отключение outline во всех 3D viewport
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        space = area.spaces.active
                        if hasattr(space, 'shading') and hasattr(space.shading, 'show_object_outline'):
                            space.shading.show_object_outline = False

            # Настройки viewport
            if view3d_area:
                space_data = view3d_area.spaces.active
                space_data.shading.type = 'SOLID'
                space_data.shading.light = 'FLAT'
                space_data.shading.color_type = 'TEXTURE'
                # Включаем overlays для wireframe
                space_data.overlay.show_overlays = True
                # Настраиваем wireframe
                if hasattr(space_data.overlay, 'show_wireframes'):
                    space_data.overlay.show_wireframes = True
                if hasattr(space_data.overlay, 'wireframe_threshold'):
                    space_data.overlay.wireframe_threshold = 0.5

            # Создаем папку для рендеров
            if settings.output_path:
                output_dir = bpy.path.abspath(settings.output_path)
            else:
                output_dir = bpy.path.abspath(get_auto_output_path(target_object.name if target_object else "renders"))

            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                self.report({'ERROR'}, f"Не удалось создать папку {output_dir}: {str(e)}. Используется временная папка")
                output_dir = os.path.join(bpy.app.tempdir, "renders")
                os.makedirs(output_dir, exist_ok=True)

            cameras_to_render.sort(key=lambda cam: cam.name)
            wm.progress_begin(0, len(cameras_to_render))

            # Цикл рендера
            for i, cam in enumerate(cameras_to_render):
                try:
                    print(f"[DEBUG] Рендер камеры: {cam.name}")

                    # Динамическое управление видимостью - показываем только объект этой камеры
                    current_cam_object = None
                    # Определяем объект для текущей камеры
                    cam_name_parts = cam.name.split('_face_')
                    if len(cam_name_parts) == 2:
                        current_obj_name = cam_name_parts[0]
                        current_cam_object = bpy.data.objects.get(current_obj_name)
                    
                    # Скрываем все объекты кроме нужного
                    if current_cam_object:
                        print(f"[DEBUG] Показываем только объект: {current_cam_object.name}")
                        for obj in context.scene.objects:
                            if obj.type == 'MESH':
                                if obj == current_cam_object:
                                    obj.hide_viewport = False
                                    obj.hide_render = False
                                else:
                                    obj.hide_viewport = True
                                    obj.hide_render = True
                    
                    # Принудительно обновляем сцену для отображения изменений
                    context.view_layer.update()

                    # Устанавливаем камеру
                    context.scene.camera = cam
                    # Безопасное получение разрешения с проверками
                    res_x = cam.get(CAM_RES_X_PROP, 1920)
                    res_y = cam.get(CAM_RES_Y_PROP, 1080)
                    context.scene.render.resolution_x = res_x
                    context.scene.render.resolution_y = res_y

                    print(f"[DEBUG] Разрешение: {res_x} x {res_y}")
                    print(f"[DEBUG] Clipping: {cam.data.clip_start} - {cam.data.clip_end}")
                    print(f"[DEBUG] Позиция камеры: {cam.location}")
                    print(f"[DEBUG] Ортографический масштаб: {cam.data.ortho_scale}")
                    
                    # Отладка видимости объектов
                    print(f"[DEBUG] Проверка видимости объектов:")
                    visible_meshes = []
                    for obj in context.scene.objects:
                        if obj.type == 'MESH':
                            is_visible = not obj.hide_viewport and not obj.hide_render
                            print(f"[DEBUG]   {obj.name}: viewport={not obj.hide_viewport}, render={not obj.hide_render}, видим={is_visible}")
                            if is_visible:
                                visible_meshes.append(obj.name)
                    print(f"[DEBUG] Видимых мешей: {len(visible_meshes)}: {visible_meshes}")
                    
                    # Проверка настроек камеры
                    print(f"[DEBUG] Камера настройки:")
                    print(f"[DEBUG]   Тип: {cam.data.type}")
                    print(f"[DEBUG]   Ортографический масштаб: {cam.data.ortho_scale}")
                    print(f"[DEBUG]   Направление: {cam.rotation_euler}")
                    print(f"[DEBUG]   Матрица: {cam.matrix_world}")

                    # Принудительно обновляем сцену
                    context.view_layer.update()
                    bpy.context.evaluated_depsgraph_get().update()

                    # Настройка viewport для рендера
                    if view3d_area:
                        space_data = view3d_area.spaces.active
                        space_data.region_3d.view_perspective = 'CAMERA'

                        # Принудительно обновляем viewport
                        for region in view3d_area.regions:
                            if region.type == 'WINDOW':
                                # Перерисовываем область
                                region.tag_redraw()

                        # Даём время на обновление
                        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

                    # Проверяем, что камера действительно активна
                    if context.scene.camera != cam:
                        print(
                            f"[ERROR] Камера не установилась! Ожидалась: {cam.name}, получена: {context.scene.camera.name if context.scene.camera else 'None'}")
                        continue

                    # Подготавливаем файл для сохранения с новым именованием
                    # Извлекаем информацию из камеры
                    facade_direction = cam.get(CAM_DIRECTION_PROP, "Неизв")
                    
                    # Извлекаем имя объекта и номер фасада из имени камеры
                    cam_name_parts = cam.name.split('_face_')
                    if len(cam_name_parts) == 2:
                        obj_name = cam_name_parts[0]
                        face_number = cam_name_parts[1]
                    else:
                        obj_name = cam.name
                        face_number = "001"
                    
                    # Создаем новое имя файла с версионностью
                    filename = get_versioned_filename(output_dir, obj_name, face_number, facade_direction)
                    filepath = os.path.join(output_dir, filename)
                    context.scene.render.filepath = filepath
                    context.scene.render.image_settings.file_format = 'PNG'
                    context.scene.render.image_settings.color_mode = 'RGBA'
                    context.scene.render.image_settings.color_depth = '8'

                    print(f"[DEBUG] Сохранение в: {filepath}")
                    print(f"[DEBUG] Имя файла: {filename}")
                    print(f"[DEBUG] Объект: {obj_name}, Фасад: {face_number}, Направление: {facade_direction}")

                    # Пробуем разные методы рендера
                    render_success = False

                    # Метод 1: Стандартный OpenGL рендер
                    try:
                        print("[DEBUG] Попытка 1: bpy.ops.render.opengl")
                        bpy.ops.render.opengl(write_still=True)

                        # Проверяем, создался ли файл
                        if os.path.exists(filepath):
                            try:
                                if os.path.getsize(filepath) > MIN_FILE_SIZE:  # Больше 1KB
                                    render_success = True
                                    print("[DEBUG] Успех методом 1")
                            except OSError as e:
                                print(f"[DEBUG] Не удалось проверить размер файла: {e}")
                    except Exception as e:
                        print(f"[DEBUG] Метод 1 неудачен: {e}")

                    # Метод 2: Если первый не сработал, пробуем viewport рендер
                    if not render_success:
                        try:
                            print("[DEBUG] Попытка 2: viewport рендер")

                            # Делаем снимок viewport напрямую
                            if view3d_area:
                                # Находим 3D viewport region
                                for region in view3d_area.regions:
                                    if region.type == 'WINDOW':
                                        # Устанавливаем контекст для области
                                        override = {
                                            'area': view3d_area,
                                            'region': region,
                                            'scene': context.scene,
                                            'camera': cam
                                        }

                                        with context.temp_override(**override):
                                            bpy.ops.render.opengl(write_still=True, view_context=True)

                                        if os.path.exists(filepath):
                                            try:
                                                if os.path.getsize(filepath) > MIN_FILE_SIZE:
                                                    render_success = True
                                                    print("[DEBUG] Успех методом 2")
                                            except OSError as e:
                                                print(f"[DEBUG] Не удалось проверить размер файла: {e}")
                                        break
                        except Exception as e:
                            print(f"[DEBUG] Метод 2 неудачен: {e}")

                    # Метод 3: Ручное сохранение изображения
                    if not render_success:
                        try:
                            print("[DEBUG] Попытка 3: ручное сохранение")

                            # Принудительно рендерим в память
                            bpy.ops.render.opengl(write_still=False)

                            # Получаем изображение из рендера
                            image = bpy.data.images.get('Render Result')
                            if image:
                                # Сохраняем вручную
                                image.save_render(filepath)
                                if os.path.exists(filepath):
                                    try:
                                        if os.path.getsize(filepath) > MIN_FILE_SIZE:
                                            render_success = True
                                            print("[DEBUG] Успех методом 3")
                                    except OSError as e:
                                        print(f"[DEBUG] Не удалось проверить размер файла: {e}")
                        except Exception as e:
                            print(f"[DEBUG] Метод 3 неудачен: {e}")

                    if render_success:
                        rendered_count += 1
                        print(f"[DEBUG] Камера {cam.name} успешно отрендерена")
                    else:
                        print(f"[ERROR] Не удалось отрендерить камеру {cam.name}")
                        # Создаём пустой файл для отладки
                        with open(filepath.replace('.png', '_ERROR.txt'), 'w', encoding='utf-8') as f:
                            f.write(f"Ошибка рендера камеры {cam.name}\n")
                            f.write(f"Разрешение: {cam.get(CAM_RES_X_PROP, 'N/A')} x {cam.get(CAM_RES_Y_PROP, 'N/A')}\n")
                            f.write(f"Позиция: {cam.location}\n")
                            f.write(f"Clipping: {cam.data.clip_start} - {cam.data.clip_end}\n")

                    wm.progress_update(i + 1)

                except Exception as e:
                    print(f"[ERROR] Критическая ошибка при рендере камеры {cam.name}: {e}")
                    # Продолжаем с следующей камерой
                    continue

        except Exception as e:
            self.report({'ERROR'}, f"Критическая ошибка при рендере: {e}")
        finally:
            # Восстановление настроек
            wm.progress_end()

            # Восстанавливаем видимость объектов
            for obj_name, original_visibility in original_visibility_state.items():
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    if isinstance(original_visibility, tuple):
                        obj.hide_viewport, obj.hide_render = original_visibility
                    else:
                        # Совместимость со старым форматом
                        obj.hide_viewport = original_visibility

            context.scene.camera = original_camera
            context.scene.render.resolution_x = original_res_x
            context.scene.render.resolution_y = original_res_y
            context.scene.render.resolution_percentage = original_percentage
            context.scene.render.filepath = original_filepath
            context.scene.render.image_settings.file_format = original_format

            # Восстанавливаем специальные настройки
            scene.display_settings.display_device = original_display_device
            scene.view_settings.view_transform = original_view_transform
            
            # Восстанавливаем outline во всех 3D viewport
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        space = area.spaces.active
                        if hasattr(space, 'shading') and hasattr(space.shading, 'show_object_outline'):
                            space.shading.show_object_outline = original_show_object_outline

            # Восстанавливаем режим
            if original_mode != 'OBJECT' and context.mode == 'OBJECT':
                try:
                    if original_mode and '_' in original_mode:
                        mode_name = original_mode.split('_')[-1]
                        if mode_name in ['EDIT', 'SCULPT', 'VERTEX_PAINT', 'WEIGHT_PAINT', 'TEXTURE_PAINT']:
                            bpy.ops.object.mode_set(mode=mode_name)
                except Exception as e:
                    print(f"Не удалось восстановить режим {original_mode}: {e}")

            # Восстанавливаем viewport
            if view3d_area:
                space_data = view3d_area.spaces.active
                if original_view_persp:
                    space_data.region_3d.view_perspective = original_view_persp
                space_data.overlay.show_overlays = original_show_overlays
                if original_shading_type:
                    space_data.shading.type = original_shading_type
                if original_shading_light:
                    space_data.shading.light = original_shading_light
                if original_shading_color:
                    space_data.shading.color_type = original_shading_color
                # Восстанавливаем wireframe настройки
                if original_wireframe_threshold is not None and hasattr(space_data.overlay, 'wireframe_threshold'):
                    space_data.overlay.wireframe_threshold = original_wireframe_threshold
                if original_show_wireframe is not None and hasattr(space_data.overlay, 'show_wireframes'):
                    space_data.overlay.show_wireframes = original_show_wireframe

        if rendered_count > 0:
            self.report({'INFO'}, f"Рендер завершён: {rendered_count} изображений сохранено в {output_dir}")
        else:
            self.report({'WARNING'}, "Ни одно изображение не было отрендерено")

        return {'FINISHED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: УДАЛЕНИЕ КАМЕР АКТИВНОГО ОБЪЕКТА
# ------------------------------------------------------------------------
class SDE_OT_delete_active_object_cameras(bpy.types.Operator):
    bl_idname = "object.sde_delete_active_object_cameras"
    bl_label = "Удалить камеры активного объекта"
    bl_description = "Удалить камеры и коллекцию только для активного объекта"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        obj_name = bpy.path.clean_name(context.active_object.name)
        target_collection_name = f"{CAM_COLLECTION_PREFIX}{obj_name}"
        return bpy.data.collections.get(target_collection_name) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            obj_name = bpy.path.clean_name(context.active_object.name)
            target_collection_name = f"{CAM_COLLECTION_PREFIX}{obj_name}"
            target_collection = bpy.data.collections.get(target_collection_name)

            if not target_collection:
                self.report({'WARNING'}, f"Коллекция камер для объекта «{context.active_object.name}» не найдена")
                return {'CANCELLED'}

            cameras_in_coll = [obj for obj in target_collection.objects if obj.type == 'CAMERA']
            deleted_cameras_count = len(cameras_in_coll)

            for cam in cameras_in_coll:
                bpy.data.objects.remove(cam, do_unlink=True)
            bpy.data.collections.remove(target_collection)

            self.report({'INFO'}, f"Удалено камер: {deleted_cameras_count} для объекта «{context.active_object.name}»")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при удалении камер: {e}")
            return {'CANCELLED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: РЕНДЕР КАМЕР АКТИВНОГО ОБЪЕКТА
# ------------------------------------------------------------------------
class SDE_OT_render_active_object_cameras(bpy.types.Operator):
    bl_idname = "object.sde_render_active_object_cameras"
    bl_label = "Отрендерить камеры объекта"
    bl_description = "Выполнить рендер камер только для активного объекта с изоляцией"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        obj_name = bpy.path.clean_name(context.active_object.name)
        target_collection_name = f"{CAM_COLLECTION_PREFIX}{obj_name}"
        return bpy.data.collections.get(target_collection_name) is not None and bpy.data.filepath != ""

    def execute(self, context):
        settings = context.scene.sde_cam_pro_settings
        if bpy.data.filepath == "":
            self.report({'WARNING'}, "Перед рендером сохраните файл .blend")
            return {'CANCELLED'}

        obj_name = bpy.path.clean_name(context.active_object.name)
        target_collection_name = f"{CAM_COLLECTION_PREFIX}{obj_name}"
        target_collection = bpy.data.collections.get(target_collection_name)

        if not target_collection:
            self.report({'WARNING'}, f"Коллекция камер для объекта «{context.active_object.name}» не найдена")
            return {'CANCELLED'}

        # Получаем камеры аддона из коллекции
        cameras_to_render = [obj for obj in target_collection.objects
                             if obj.type == 'CAMERA' and CAM_RES_X_PROP in obj]
                             
        # Обновляем старые камеры без информации о направлении
        for cam in cameras_to_render:
            if CAM_DIRECTION_PROP not in cam:
                print(f"[MIGRATION] Обновляем камеру {cam.name} - добавляем информацию о направлении")
                cam[CAM_DIRECTION_PROP] = "Неизв"  # Для совместимости со старыми камерами

        if not cameras_to_render:
            self.report({'WARNING'}, "Нет подходящих камер для рендера в коллекции объекта")
            return {'CANCELLED'}

        # Используем метод рендера из SDE_OT_render_selected_cameras
        return SDE_OT_render_selected_cameras._render_cameras(self, context, settings, cameras_to_render)


# ------------------------------------------------------------------------
# ОПЕРАТОР: ПРИМЕНИТЬ РАЗРЕШЕНИЕ КАМЕРЫ
# ------------------------------------------------------------------------
class SDE_OT_apply_camera_resolution(bpy.types.Operator):
    bl_idname = "object.sde_apply_camera_resolution"
    bl_label = "Применить разрешение"
    bl_description = "Установить разрешение рендера из активной камеры"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        cam = context.scene.camera
        return cam and CAM_RES_X_PROP in cam

    def execute(self, context):
        try:
            cam = context.scene.camera
            res_x = cam.get(CAM_RES_X_PROP, context.scene.render.resolution_x)
            res_y = cam.get(CAM_RES_Y_PROP, context.scene.render.resolution_y)

            context.scene.render.resolution_x = res_x
            context.scene.render.resolution_y = res_y
            self.report({'INFO'}, f"Разрешение установлено: {res_x} × {res_y}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при установке разрешения: {e}")
            return {'CANCELLED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: РЕНДЕР ИЗ ВСЕХ КАМЕР С ИЗОЛЯЦИЕЙ ОБЪЕКТА
# ------------------------------------------------------------------------
class SDE_OT_render_all_cameras(bpy.types.Operator):
    bl_idname = "object.sde_render_all_cameras"
    bl_label = "Отрендерить все камеры"
    bl_description = "Выполнить рендер всех камер с изоляцией активного объекта"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return any(
            coll.name.startswith(CAM_COLLECTION_PREFIX) for coll in bpy.data.collections) and bpy.data.filepath != ""

    def execute(self, context):
        settings = context.scene.sde_cam_pro_settings
        if bpy.data.filepath == "":
            self.report({'WARNING'}, "Перед рендером сохраните файл .blend")
            return {'CANCELLED'}

        # Сохранение исходных настроек
        original_camera = context.scene.camera
        original_res_x = context.scene.render.resolution_x
        original_res_y = context.scene.render.resolution_y
        original_percentage = context.scene.render.resolution_percentage
        original_filepath = context.scene.render.filepath
        original_format = context.scene.render.image_settings.file_format
        original_mode = context.mode

        # Добавленные сохранения для рендера
        scene = context.scene
        original_display_device = scene.display_settings.display_device
        original_view_transform = scene.view_settings.view_transform
        
        # Безопасный поиск 3D viewport для сохранения настроек outline
        original_show_object_outline = False
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    if hasattr(space, 'shading') and hasattr(space.shading, 'show_object_outline'):
                        original_show_object_outline = space.shading.show_object_outline
                        break

        view3d_area = None
        original_view_persp = None
        original_show_overlays = True
        original_shading_type = None
        original_shading_light = None
        original_shading_color = None
        original_wireframe_threshold = None
        original_show_wireframe = None

        if context.screen:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    view3d_area = area
                    space_data = area.spaces.active
                    original_view_persp = space_data.region_3d.view_perspective
                    original_show_overlays = space_data.overlay.show_overlays
                    original_shading_type = space_data.shading.type
                    original_shading_light = space_data.shading.light
                    original_shading_color = space_data.shading.color_type
                    # Сохраняем настройки wireframe
                    if hasattr(space_data.overlay, 'wireframe_threshold'):
                        original_wireframe_threshold = space_data.overlay.wireframe_threshold
                    if hasattr(space_data.overlay, 'show_wireframes'):
                        original_show_wireframe = space_data.overlay.show_wireframes
                    break

        wm = context.window_manager
        rendered_count = 0
        original_visibility_state = {}

        try:
            # Переходим в Object Mode
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            # Запоминаем исходное состояние видимости ВСЕХ объектов
            target_object = context.active_object
            for obj in context.scene.objects:
                original_visibility_state[obj.name] = obj.hide_viewport

            # Программно имитируем Local View: скрываем всё кроме target_object
            if target_object:
                for obj in context.scene.objects:
                    if obj != target_object:
                        obj.hide_viewport = True
                    else:
                        obj.hide_viewport = False

            # Настройки рендера
            if settings.ignore_percentage:
                context.scene.render.resolution_percentage = 100

            # Специальные настройки для рендера
            scene.display_settings.display_device = 'sRGB'
            scene.view_settings.view_transform = 'Standard'
            
            # Безопасное отключение outline во всех 3D viewport
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        space = area.spaces.active
                        if hasattr(space, 'shading') and hasattr(space.shading, 'show_object_outline'):
                            space.shading.show_object_outline = False

            # Настройки viewport
            if view3d_area:
                space_data = view3d_area.spaces.active
                space_data.shading.type = 'SOLID'
                space_data.shading.light = 'FLAT'
                space_data.shading.color_type = 'TEXTURE'
                # Включаем overlays для wireframe
                space_data.overlay.show_overlays = True
                # Настраиваем wireframe
                if hasattr(space_data.overlay, 'show_wireframes'):
                    space_data.overlay.show_wireframes = True
                if hasattr(space_data.overlay, 'wireframe_threshold'):
                    space_data.overlay.wireframe_threshold = 0.5

            # Создаем папку для рендеров
            if settings.output_path:
                output_dir = bpy.path.abspath(settings.output_path)
            else:
                output_dir = bpy.path.abspath(get_auto_output_path(target_object.name if target_object else "renders"))

            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                self.report({'ERROR'}, f"Не удалось создать папку {output_dir}: {str(e)}. Используется временная папка")
                output_dir = os.path.join(bpy.app.tempdir, "renders")
                os.makedirs(output_dir, exist_ok=True)

            # Собираем все камеры
            all_cameras = []
            collections = [c for c in bpy.data.collections if c.name.startswith(CAM_COLLECTION_PREFIX)]
            for coll in collections:
                all_cameras.extend([obj for obj in coll.objects if obj.type == 'CAMERA' and CAM_RES_X_PROP in obj])
            all_cameras.sort(key=lambda cam: cam.name)
            
            # Обновляем старые камеры без информации о направлении
            for cam in all_cameras:
                if CAM_DIRECTION_PROP not in cam:
                    print(f"[MIGRATION] Обновляем камеру {cam.name} - добавляем информацию о направлении")
                    cam[CAM_DIRECTION_PROP] = "Неизв"  # Для совместимости со старыми камерами

            if not all_cameras:
                self.report({'WARNING'}, "Нет подходящих камер для рендера")
                return {'CANCELLED'}

            wm.progress_begin(0, len(all_cameras))

            # Цикл рендера
            for i, cam in enumerate(all_cameras):
                try:
                    print(f"[DEBUG] Рендер камеры: {cam.name}")

                    # Устанавливаем камеру
                    context.scene.camera = cam
                    # Безопасное получение разрешения с проверками
                    res_x = cam.get(CAM_RES_X_PROP, 1920)
                    res_y = cam.get(CAM_RES_Y_PROP, 1080)
                    context.scene.render.resolution_x = res_x
                    context.scene.render.resolution_y = res_y

                    print(f"[DEBUG] Разрешение: {res_x} x {res_y}")
                    print(f"[DEBUG] Clipping: {cam.data.clip_start} - {cam.data.clip_end}")
                    print(f"[DEBUG] Позиция камеры: {cam.location}")
                    print(f"[DEBUG] Ортографический масштаб: {cam.data.ortho_scale}")
                    
                    # Отладка видимости объектов
                    print(f"[DEBUG] Проверка видимости объектов:")
                    visible_meshes = []
                    for obj in context.scene.objects:
                        if obj.type == 'MESH':
                            is_visible = not obj.hide_viewport and not obj.hide_render
                            print(f"[DEBUG]   {obj.name}: viewport={not obj.hide_viewport}, render={not obj.hide_render}, видим={is_visible}")
                            if is_visible:
                                visible_meshes.append(obj.name)
                    print(f"[DEBUG] Видимых мешей: {len(visible_meshes)}: {visible_meshes}")
                    
                    # Проверка настроек камеры
                    print(f"[DEBUG] Камера настройки:")
                    print(f"[DEBUG]   Тип: {cam.data.type}")
                    print(f"[DEBUG]   Ортографический масштаб: {cam.data.ortho_scale}")
                    print(f"[DEBUG]   Направление: {cam.rotation_euler}")
                    print(f"[DEBUG]   Матрица: {cam.matrix_world}")

                    # Принудительно обновляем сцену
                    context.view_layer.update()
                    bpy.context.evaluated_depsgraph_get().update()

                    # Настройка viewport для рендера
                    if view3d_area:
                        space_data = view3d_area.spaces.active
                        space_data.region_3d.view_perspective = 'CAMERA'

                        # Принудительно обновляем viewport
                        for region in view3d_area.regions:
                            if region.type == 'WINDOW':
                                # Перерисовываем область
                                region.tag_redraw()

                        # Даём время на обновление
                        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

                    # Проверяем, что камера действительно активна
                    if context.scene.camera != cam:
                        print(
                            f"[ERROR] Камера не установилась! Ожидалась: {cam.name}, получена: {context.scene.camera.name if context.scene.camera else 'None'}")
                        continue

                    # Подготавливаем файл для сохранения с новым именованием
                    # Извлекаем информацию из камеры
                    facade_direction = cam.get(CAM_DIRECTION_PROP, "Неизв")
                    
                    # Извлекаем имя объекта и номер фасада из имени камеры
                    cam_name_parts = cam.name.split('_face_')
                    if len(cam_name_parts) == 2:
                        obj_name = cam_name_parts[0]
                        face_number = cam_name_parts[1]
                    else:
                        obj_name = cam.name
                        face_number = "001"
                    
                    # Создаем новое имя файла с версионностью
                    filename = get_versioned_filename(output_dir, obj_name, face_number, facade_direction)
                    filepath = os.path.join(output_dir, filename)
                    context.scene.render.filepath = filepath
                    context.scene.render.image_settings.file_format = 'PNG'
                    context.scene.render.image_settings.color_mode = 'RGBA'
                    context.scene.render.image_settings.color_depth = '8'

                    print(f"[DEBUG] Сохранение в: {filepath}")
                    print(f"[DEBUG] Имя файла: {filename}")
                    print(f"[DEBUG] Объект: {obj_name}, Фасад: {face_number}, Направление: {facade_direction}")

                    # Пробуем разные методы рендера
                    render_success = False

                    # Метод 1: Стандартный OpenGL рендер
                    try:
                        print("[DEBUG] Попытка 1: bpy.ops.render.opengl")
                        bpy.ops.render.opengl(write_still=True)

                        # Проверяем, создался ли файл
                        if os.path.exists(filepath):
                            try:
                                if os.path.getsize(filepath) > MIN_FILE_SIZE:  # Больше 1KB
                                    render_success = True
                                    print("[DEBUG] Успех методом 1")
                            except OSError as e:
                                print(f"[DEBUG] Не удалось проверить размер файла: {e}")
                    except Exception as e:
                        print(f"[DEBUG] Метод 1 неудачен: {e}")

                    # Метод 2: Если первый не сработал, пробуем viewport рендер
                    if not render_success:
                        try:
                            print("[DEBUG] Попытка 2: viewport рендер")

                            # Делаем снимок viewport напрямую
                            if view3d_area:
                                # Находим 3D viewport region
                                for region in view3d_area.regions:
                                    if region.type == 'WINDOW':
                                        # Устанавливаем контекст для области
                                        override = {
                                            'area': view3d_area,
                                            'region': region,
                                            'scene': context.scene,
                                            'camera': cam
                                        }

                                        with context.temp_override(**override):
                                            bpy.ops.render.opengl(write_still=True, view_context=True)

                                        if os.path.exists(filepath):
                                            try:
                                                if os.path.getsize(filepath) > MIN_FILE_SIZE:
                                                    render_success = True
                                                    print("[DEBUG] Успех методом 2")
                                            except OSError as e:
                                                print(f"[DEBUG] Не удалось проверить размер файла: {e}")
                                        break
                        except Exception as e:
                            print(f"[DEBUG] Метод 2 неудачен: {e}")

                    # Метод 3: Ручное сохранение изображения
                    if not render_success:
                        try:
                            print("[DEBUG] Попытка 3: ручное сохранение")

                            # Принудительно рендерим в память
                            bpy.ops.render.opengl(write_still=False)

                            # Получаем изображение из рендера
                            image = bpy.data.images.get('Render Result')
                            if image:
                                # Сохраняем вручную
                                image.save_render(filepath)
                                if os.path.exists(filepath):
                                    try:
                                        if os.path.getsize(filepath) > MIN_FILE_SIZE:
                                            render_success = True
                                            print("[DEBUG] Успех методом 3")
                                    except OSError as e:
                                        print(f"[DEBUG] Не удалось проверить размер файла: {e}")
                        except Exception as e:
                            print(f"[DEBUG] Метод 3 неудачен: {e}")

                    if render_success:
                        rendered_count += 1
                        print(f"[DEBUG] Камера {cam.name} успешно отрендерена")
                    else:
                        print(f"[ERROR] Не удалось отрендерить камеру {cam.name}")
                        # Создаём пустой файл для отладки
                        with open(filepath.replace('.png', '_ERROR.txt'), 'w', encoding='utf-8') as f:
                            f.write(f"Ошибка рендера камеры {cam.name}\n")
                            f.write(f"Разрешение: {cam.get(CAM_RES_X_PROP, 'N/A')} x {cam.get(CAM_RES_Y_PROP, 'N/A')}\n")
                            f.write(f"Позиция: {cam.location}\n")
                            f.write(f"Clipping: {cam.data.clip_start} - {cam.data.clip_end}\n")

                    wm.progress_update(i + 1)

                except Exception as e:
                    print(f"[ERROR] Критическая ошибка при рендере камеры {cam.name}: {e}")
                    # Продолжаем с следующей камерой
                    continue

        except Exception as e:
            self.report({'ERROR'}, f"Критическая ошибка при рендере: {e}")
        finally:
            # Восстановление настроек
            wm.progress_end()

            # ВАЖНО: Восстанавливаем исходное состояние видимости всех объектов
            for obj_name, original_visibility in original_visibility_state.items():
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    obj.hide_viewport = original_visibility

            context.scene.camera = original_camera
            context.scene.render.resolution_x = original_res_x
            context.scene.render.resolution_y = original_res_y
            context.scene.render.resolution_percentage = original_percentage
            context.scene.render.filepath = original_filepath
            context.scene.render.image_settings.file_format = original_format

            # Восстанавливаем специальные настройки
            scene.display_settings.display_device = original_display_device
            scene.view_settings.view_transform = original_view_transform
            
            # Восстанавливаем outline во всех 3D viewport
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        space = area.spaces.active
                        if hasattr(space, 'shading') and hasattr(space.shading, 'show_object_outline'):
                            space.shading.show_object_outline = original_show_object_outline

            # Восстанавливаем режим
            if original_mode != 'OBJECT' and context.mode == 'OBJECT':
                try:
                    if original_mode and '_' in original_mode:
                        mode_name = original_mode.split('_')[-1]
                        if mode_name in ['EDIT', 'SCULPT', 'VERTEX_PAINT', 'WEIGHT_PAINT', 'TEXTURE_PAINT']:
                            bpy.ops.object.mode_set(mode=mode_name)
                except Exception as e:
                    print(f"Не удалось восстановить режим {original_mode}: {e}")

            # Восстанавливаем viewport (убрал код с local view)
            if view3d_area:
                space_data = view3d_area.spaces.active
                if original_view_persp:
                    space_data.region_3d.view_perspective = original_view_persp
                space_data.overlay.show_overlays = original_show_overlays
                if original_shading_type:
                    space_data.shading.type = original_shading_type
                if original_shading_light:
                    space_data.shading.light = original_shading_light
                if original_shading_color:
                    space_data.shading.color_type = original_shading_color
                # Восстанавливаем wireframe настройки
                if original_wireframe_threshold is not None and hasattr(space_data.overlay, 'wireframe_threshold'):
                    space_data.overlay.wireframe_threshold = original_wireframe_threshold
                if original_show_wireframe is not None and hasattr(space_data.overlay, 'show_wireframes'):
                    space_data.overlay.show_wireframes = original_show_wireframe

        if rendered_count > 0:
            self.report({'INFO'}, f"Рендер завершён: {rendered_count} изображений сохранено в {output_dir}")
        else:
            self.report({'WARNING'}, "Ни одно изображение не было отрендерено")

        return {'FINISHED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: АЛЬТЕРНАТИВНЫЙ РЕНДЕР ДЛЯ VULKAN
# ------------------------------------------------------------------------
class SDE_OT_render_vulkan_compatible(bpy.types.Operator):
    bl_idname = "object.sde_render_vulkan_compatible"
    bl_label = "Рендер (совместимый с Vulkan)"
    bl_description = "Альтернативный метод рендера, совместимый с Vulkan API"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # Более эффективная проверка - прерываем на первом найденном объекте
        if bpy.data.filepath == "":
            return False
        
        for obj in context.scene.objects:
            if obj.select_get() and obj.type == 'CAMERA' and CAM_RES_X_PROP in obj:
                return True
        return False

    def execute(self, context):
        settings = context.scene.sde_cam_pro_settings
        if bpy.data.filepath == "":
            self.report({'WARNING'}, "Перед рендером сохраните файл .blend")
            return {'CANCELLED'}

        # Получаем выделенные камеры аддона
        selected_cameras = [obj for obj in context.scene.objects
                            if obj.select_get() and obj.type == 'CAMERA' and CAM_RES_X_PROP in obj]
                            
        # Обновляем старые камеры без информации о направлении
        for cam in selected_cameras:
            if CAM_DIRECTION_PROP not in cam:
                print(f"[MIGRATION] Обновляем камеру {cam.name} - добавляем информацию о направлении")
                cam[CAM_DIRECTION_PROP] = "Неизв"  # Для совместимости со старыми камерами

        if not selected_cameras:
            self.report({'WARNING'}, "Не выделено ни одной камеры, созданной аддоном")
            return {'CANCELLED'}

        return self._vulkan_render(context, settings, selected_cameras)

    def _vulkan_render(self, context, settings, cameras_to_render):
        # Сохранение настроек
        original_camera = context.scene.camera
        original_res_x = context.scene.render.resolution_x
        original_res_y = context.scene.render.resolution_y
        original_percentage = context.scene.render.resolution_percentage
        original_filepath = context.scene.render.filepath
        original_format = context.scene.render.image_settings.file_format
        original_engine = context.scene.render.engine

        wm = context.window_manager
        rendered_count = 0
        original_visibility_state = {}

        try:
            # Переходим в Object Mode
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            # Определяем объект для рендера - ищем меш, а не камеру
            target_object = context.active_object
            # Если активный объект - камера, ищем меш по имени камеры
            if target_object and target_object.type == 'CAMERA':
                cam_name = target_object.name
                print(f"[DEBUG] Активная камера: {cam_name}")
                
                # Способ 1: извлекаем имя объекта из имени камеры (формат: ObjectName_face_XXX)
                if '_face_' in cam_name:
                    object_name = cam_name.split('_face_')[0]
                    mesh_object = bpy.data.objects.get(object_name)
                    if mesh_object and mesh_object.type == 'MESH':
                        target_object = mesh_object
                        print(f"[DEBUG] Найден меш по имени камеры: {target_object.name}")
                
                # Способ 2: ищем через коллекции камер (если первый не сработал)
                if target_object.type == 'CAMERA':
                    for collection in bpy.data.collections:
                        if collection.name.startswith(CAM_COLLECTION_PREFIX) and target_object in collection.objects.values():
                            # Извлекаем имя объекта из имени коллекции
                            obj_name_from_collection = collection.name[len(CAM_COLLECTION_PREFIX):]
                            mesh_object = bpy.data.objects.get(obj_name_from_collection)
                            if mesh_object and mesh_object.type == 'MESH':
                                target_object = mesh_object
                                print(f"[DEBUG] Найден меш через коллекцию: {target_object.name}")
                                break
            
            print(f"[DEBUG] Целевой объект для рендера: {target_object.name if target_object else 'None'}")
            
            # Сохраняем исходное состояние видимости всех объектов для восстановления
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    original_visibility_state[obj.name] = (obj.hide_viewport, obj.hide_render)
            print("[DEBUG] Используем динамическое управление видимостью для каждой камеры")

            # Настройки рендера
            if settings.ignore_percentage:
                context.scene.render.resolution_percentage = 100

            # Используем Workbench для Vulkan совместимости
            context.scene.render.engine = 'BLENDER_WORKBENCH'

            # Создаем папку для рендеров
            if settings.output_path:
                output_dir = bpy.path.abspath(settings.output_path)
            else:
                output_dir = bpy.path.abspath(get_auto_output_path(target_object.name if target_object else "renders"))

            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                self.report({'ERROR'}, f"Не удалось создать папку {output_dir}: {str(e)}. Используется временная папка")
                output_dir = os.path.join(bpy.app.tempdir, "renders")
                os.makedirs(output_dir, exist_ok=True)

            cameras_to_render.sort(key=lambda cam: cam.name)
            wm.progress_begin(0, len(cameras_to_render))

            # Цикл рендера с Workbench
            for i, cam in enumerate(cameras_to_render):
                try:
                    print(f"[VULKAN DEBUG] Рендер камеры: {cam.name}")

                    context.scene.camera = cam
                    # Безопасное получение разрешения с проверками
                    res_x = cam.get(CAM_RES_X_PROP, 1920)
                    res_y = cam.get(CAM_RES_Y_PROP, 1080)
                    context.scene.render.resolution_x = res_x
                    context.scene.render.resolution_y = res_y

                    # Создаем имя файла с vulkan суффиксом
                    facade_direction = cam.get(CAM_DIRECTION_PROP, "Неизв")
                    cam_name_parts = cam.name.split('_face_')
                    if len(cam_name_parts) == 2:
                        obj_name = cam_name_parts[0]
                        face_number = cam_name_parts[1]
                    else:
                        obj_name = cam.name
                        face_number = "001"
                    
                    # Для vulkan добавляем суффикс в направление
                    facade_direction_vulkan = f"{facade_direction}-V"
                    filename = get_versioned_filename(output_dir, obj_name, face_number, facade_direction_vulkan)
                    filepath = os.path.join(output_dir, filename)
                    context.scene.render.filepath = filepath
                    context.scene.render.image_settings.file_format = 'PNG'

                    print(f"[VULKAN DEBUG] Рендер через Workbench engine")
                    print(f"[VULKAN DEBUG] Имя файла: {filename}")
                    print(f"[VULKAN DEBUG] Объект: {obj_name}, Фасад: {face_number}, Направление: {facade_direction_vulkan}")

                    # Используем стандартный рендер вместо OpenGL
                    bpy.ops.render.render(write_still=True)

                    if os.path.exists(filepath) and os.path.getsize(filepath) > MIN_FILE_SIZE:
                        rendered_count += 1
                        print(f"[VULKAN DEBUG] Камера {cam.name} успешно отрендерена")
                    else:
                        print(f"[VULKAN ERROR] Не удалось отрендерить камеру {cam.name}")

                    wm.progress_update(i + 1)

                except Exception as e:
                    print(f"[VULKAN ERROR] Ошибка при рендере камеры {cam.name}: {e}")
                    continue

        except Exception as e:
            self.report({'ERROR'}, f"Критическая ошибка при Vulkan рендере: {e}")
        finally:
            # Восстановление настроек
            wm.progress_end()

            # Восстанавливаем видимость объектов
            for obj_name, original_visibility in original_visibility_state.items():
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    if isinstance(original_visibility, tuple):
                        obj.hide_viewport, obj.hide_render = original_visibility
                    else:
                        # Совместимость со старым форматом
                        obj.hide_viewport = original_visibility

            context.scene.camera = original_camera
            context.scene.render.resolution_x = original_res_x
            context.scene.render.resolution_y = original_res_y
            context.scene.render.resolution_percentage = original_percentage
            context.scene.render.filepath = original_filepath
            context.scene.render.image_settings.file_format = original_format
            context.scene.render.engine = original_engine

        if rendered_count > 0:
            self.report({'INFO'}, f"Vulkan рендер завершён: {rendered_count} изображений сохранено в {output_dir}")
        else:
            self.report({'WARNING'}, "Ни одно изображение не было отрендерено")

        return {'FINISHED'}


class SDE_OT_preview_camera(bpy.types.Operator):
    bl_idname = "object.sde_preview_camera"
    bl_label = "Просмотр камеры"
    bl_description = "Переключиться в режим просмотра через активную камеру"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None

    def execute(self, context):
        try:
            if context.screen:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.spaces.active.region_3d.view_perspective = 'CAMERA'
                        break
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при переключении в вид камеры: {e}")
            return {'CANCELLED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: АВТО-ДЕТЕКТ НАСТРОЕК
# ------------------------------------------------------------------------
class SDE_OT_auto_detect_settings(bpy.types.Operator):
    bl_idname = "object.sde_auto_detect_settings"
    bl_label = "Определить настройки"
    bl_description = "Автоматически определить оптимальные настройки на основе размеров сцены"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        try:
            settings = context.scene.sde_cam_pro_settings
            obj = context.active_object
            bbox = obj.bound_box
            bbox_size = max(max(v) - min(v) for v in zip(*bbox))

            suggested_distance = bbox_size * 1.5
            suggested_max_res = int(bbox_size * 10)
            suggested_max_res = max(128, min(suggested_max_res, 8192))

            settings.distance = suggested_distance
            settings.max_resolution = suggested_max_res
            settings.auto_distance = True
            settings.auto_clipping = True

            self.report({'INFO'},
                        f"Настройки определены: расстояние = {suggested_distance:.1f} м, максимальное разрешение = {suggested_max_res}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при определении настроек: {e}")
            return {'CANCELLED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: ПОМОЩЬ POPUP
# ------------------------------------------------------------------------
class SDE_OT_help_popup(bpy.types.Operator):
    bl_idname = "object.sde_help_popup"
    bl_label = "Справка по аддону"
    bl_description = "Показать подробную инструкцию по использованию аддона"
    bl_options = {'REGISTER'}

    def execute(self, context):
        def draw_popup(self, context):
            layout = self.layout
            layout.label(text="Быстрые фасады: инструкция", icon='INFO')
            layout.separator()

            col = layout.column(align=True)
            col.label(text="1. Откройте объект в режиме редактирования (Tab)")
            col.label(text="2. Выделите полигоны фасадов")
            col.label(text="3. Нажмите «Создать камеры»")
            col.label(text="4. Сохраните файл .blend")
            col.label(text="5. Нажмите «Отрендерить все камеры»")

            layout.separator()
            col = layout.column(align=True)
            col.label(text="Советы:", icon='LIGHT')
            col.label(text="• Папка создается автоматически по имени объекта")
            col.label(text="• Используйте «Определить настройки» для автонастройки")
            col.label(text="• Можно рендерить только выделенные камеры или камеры объекта")
            col.label(text="• Используйте пользовательские пресеты для сохранения настроек")
            col.label(text="• Автоматические clipping planes предотвращают артефакты")

        context.window_manager.popup_menu(draw_popup, title="Инструкция", icon='QUESTION')
        return {'FINISHED'}


# ------------------------------------------------------------------------
# ОПЕРАТОР: УДАЛЕНИЕ КАМЕР
# ------------------------------------------------------------------------
class SDE_OT_delete_all_addon_cameras(bpy.types.Operator):
    bl_idname = "object.sde_delete_all_cameras_pro"
    bl_label = "Удалить все камеры"
    bl_description = "Удалить все камеры и коллекции, созданные данным аддоном"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(coll.name.startswith(CAM_COLLECTION_PREFIX) for coll in bpy.data.collections)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            collections_to_delete = [c for c in bpy.data.collections if c.name.startswith(CAM_COLLECTION_PREFIX)]
            deleted_cameras_count = 0
            for coll in collections_to_delete:
                cameras_in_coll = [obj for obj in coll.objects if obj.type == 'CAMERA']
                deleted_cameras_count += len(cameras_in_coll)
                for cam in cameras_in_coll:
                    bpy.data.objects.remove(cam, do_unlink=True)
                bpy.data.collections.remove(coll)
            self.report({'INFO'}, f"Удалено камер: {deleted_cameras_count}, коллекций: {len(collections_to_delete)}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при удалении камер: {e}")
            return {'CANCELLED'}


# ------------------------------------------------------------------------
# UI ПАНЕЛЬ
# ------------------------------------------------------------------------
class SDE_PT_cameras_pro_panel(bpy.types.Panel):
    bl_label = "Быстрые фасады"
    bl_idname = "SDE_PT_cameras_pro_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Быстрые фасады"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.sde_cam_pro_settings
        prefs = context.preferences.addons[__name__].preferences

        # Блок настроек создания
        creation_box = layout.box()
        creation_box.label(text="Настройки создания", icon='CAMERA_DATA')
        creation_col = creation_box.column(align=True)
        creation_col.prop(settings, "preset", text="Шаблон")
        row = creation_col.row(align=True)
        row.active = not settings.auto_distance
        row.prop(settings, "distance", slider=True)
        creation_col.prop(settings, "auto_distance")
        creation_col.prop(settings, "auto_clipping")
        creation_col.prop(settings, "max_resolution")

        op_create = creation_col.operator(SDE_OT_create_cameras_from_faces.bl_idname, text="Создать камеры", icon='ADD')

        op_create.distance = settings.distance
        op_create.max_resolution = settings.max_resolution
        op_create.auto_distance = settings.auto_distance
        op_create.auto_clipping = settings.auto_clipping

        if not SDE_OT_create_cameras_from_faces.poll(context):
            creation_box.label(text="Доступно в режиме редактирования", icon='INFO')

        # Блок пользовательских пресетов
        preset_box = layout.box()
        preset_box.label(text="Пользовательские пресеты", icon='PRESET')
        preset_col = preset_box.column(align=True)
        preset_col.template_list("SDE_UL_preset_list", "presets", prefs, "presets", prefs, "selected_preset_index",
                                 rows=3)
        row = preset_col.row(align=True)
        row.operator(SDE_OT_add_preset.bl_idname, text="Добавить", icon='ADD')
        row.operator(SDE_OT_delete_preset.bl_idname, text="Удалить", icon='REMOVE')
        row.operator(SDE_OT_load_preset.bl_idname, text="Загрузить", icon='FILE_REFRESH')

        # Блок настроек рендера
        render_box = layout.box()
        render_box.label(text="Настройки рендера", icon='RENDER_STILL')
        render_col = render_box.column(align=True)
        render_col.prop(settings, "ignore_percentage")

        # Показываем автоматический путь если не задан
        if not settings.output_path and context.active_object:
            auto_path = get_auto_output_path(context.active_object.name)
            render_col.label(text=f"Автоматический путь: {auto_path}", icon='FOLDER_REDIRECT')
        render_col.prop(settings, "output_path")

        # Блок управления
        manage_box = layout.box()
        manage_box.label(text="Управление", icon='TOOL_SETTINGS')
        manage_col = manage_box.column(align=True)

        if scene.camera and CAM_RES_X_PROP in scene.camera:
            res_x = scene.camera[CAM_RES_X_PROP]
            res_y = scene.camera[CAM_RES_Y_PROP]
            manage_col.label(text=f"Активная камера: {scene.camera.name}", icon='CAMERA_DATA')
            manage_col.label(text=f"Разрешение: {res_x} × {res_y}", icon='IMAGE_PLANE')
            manage_col.label(text=f"Clipping: {scene.camera.data.clip_start:.3f} - {scene.camera.data.clip_end:.1f}",
                             icon='OUTLINER_DATA_CAMERA')
            manage_col.operator(SDE_OT_apply_camera_resolution.bl_idname, icon='CHECKMARK')
            manage_col.operator(SDE_OT_preview_camera.bl_idname, text="Просмотр камеры", icon='VIEW_CAMERA')

        # Кнопки рендера
        row = manage_col.row(align=True)
        row.operator(SDE_OT_render_all_cameras.bl_idname, text="Все камеры", icon='RENDER_STILL')

        # Проверяем есть ли выделенные камеры аддона
        selected_addon_cameras = [obj for obj in context.scene.objects
                                  if obj.select_get() and obj.type == 'CAMERA' and CAM_RES_X_PROP in obj]
        if selected_addon_cameras:
            row.operator(SDE_OT_render_selected_cameras.bl_idname, text="Выделенные", icon='RESTRICT_SELECT_OFF')

        # Добавляем кнопку Vulkan рендера
        if selected_addon_cameras:
            manage_col.operator(SDE_OT_render_vulkan_compatible.bl_idname, text="Рендер (Vulkan)",
                                icon='OUTLINER_OB_CAMERA')

        if SDE_OT_render_active_object_cameras.poll(context):
            manage_col.operator(SDE_OT_render_active_object_cameras.bl_idname, text="Камеры объекта",
                                icon='RENDER_STILL')

        # Кнопки удаления
        row = manage_col.row(align=True)
        row.operator(SDE_OT_delete_all_addon_cameras.bl_idname, text="Все", icon='TRASH')
        if SDE_OT_delete_active_object_cameras.poll(context):
            row.operator(SDE_OT_delete_active_object_cameras.bl_idname, text="Этого объекта", icon='X')

        # Блок инструментов и справки
        help_box = layout.box()
        help_box.label(text="Инструменты и справка", icon='QUESTION')
        help_col = help_box.column(align=True)
        help_col.operator(SDE_OT_auto_detect_settings.bl_idname, text="Определить настройки", icon='ZOOM_SELECTED')
        help_col.operator(SDE_OT_help_popup.bl_idname, text="Справка", icon='INFO')


# ------------------------------------------------------------------------
# РЕГИСТРАЦИЯ
# ------------------------------------------------------------------------
classes = (
    SDE_CameraProSettings,
    SDE_Preset,
    SDE_AddonPreferences,
    SDE_UL_preset_list,
    SDE_OT_add_preset,
    SDE_OT_delete_preset,
    SDE_OT_load_preset,
    SDE_OT_create_cameras_from_faces,
    SDE_OT_apply_camera_resolution,
    SDE_OT_preview_camera,
    SDE_OT_auto_detect_settings,
    SDE_OT_help_popup,
    SDE_OT_render_all_cameras,
    SDE_OT_render_selected_cameras,
    SDE_OT_render_vulkan_compatible,
    SDE_OT_render_active_object_cameras,
    SDE_OT_delete_all_addon_cameras,
    SDE_OT_delete_active_object_cameras,
    SDE_PT_cameras_pro_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sde_cam_pro_settings = bpy.props.PointerProperty(type=SDE_CameraProSettings)


def unregister():
    del bpy.types.Scene.sde_cam_pro_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()