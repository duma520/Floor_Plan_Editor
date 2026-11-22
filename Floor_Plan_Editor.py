#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房屋平面图绘制工具 v2.1
基于 PySide6 开发
本次更新:
1. 版本升级到2.1
2. 新增设置实时自动保存与持久化:网格显示/网格吸附/自动附着/窗口几何,下次启动自动恢复
3. 丰富右键菜单,增加更多常用操作(复制/粘贴/删除/全选/缩放/重置/导出图片/历史记录等)
4. 完善历史记录功能:保存时自动记录,可在历史记录对话框中查看、预览和加载
5. 历史记录保存在程序所在目录的history子目录下,最多保留20条
6. 自动保存功能确保下次启动恢复上次编辑状态
7. 优化菜单结构和交互体验
"""
import sys
import os
import json
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsLineItem, QGraphicsTextItem, QGraphicsPixmapItem,
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QListWidget,
    QListWidgetItem, QLabel, QDoubleSpinBox, QPushButton,
    QColorDialog, QFileDialog, QMessageBox, QDockWidget,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog,
    QAbstractItemView, QSplitter, QFrame, QLineEdit, QMenu
)
from PySide6.QtCore import (
    Qt, QPointF, QRectF, QSizeF, QSize, Signal, QObject, QMimeData,
    QByteArray, QDataStream, QIODevice, QTimer
)
from PySide6.QtGui import (
    QPen, QBrush, QColor, QPolygonF, QPainter, QPainterPath,
    QIcon, QFont, QCursor, QAction, QKeySequence,
    QDrag, QUndoStack, QUndoCommand, QTransform, QPixmap
)

# ============================================================
# 自动保存和历史记录相关函数
# ============================================================
def get_app_dir():
    """获取程序所在目录"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_history_dir():
    """获取历史记录目录"""
    history_path = os.path.join(get_app_dir(), 'history')
    if not os.path.exists(history_path):
        os.makedirs(history_path)
    return history_path

def get_autosave_path():
    """获取自动保存文件路径"""
    return os.path.join(get_app_dir(), 'autosave.json')

def get_settings_path():
    """获取设置文件路径(程序目录/exe目录)"""
    return os.path.join(get_app_dir(), 'floor_plan_editor_settings.json')

DEFAULT_SETTINGS = {
    'snap_to_grid': True,
    'show_grid': True,
    'auto_attach': True,
    'window_geometry': None,
    'window_maximized': False,
}

def load_settings():
    """加载设置,缺失键用默认值"""
    settings = dict(DEFAULT_SETTINGS)
    try:
        path = get_settings_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                settings.update(data)
    except Exception:
        pass
    return settings

def save_settings(settings):
    """保存设置(原子写入 tmp + os.replace,防止写坏)"""
    try:
        path = get_settings_path()
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass

# ============================================================
# 常量定义
# ============================================================
GRID_SIZE = 20
SNAP_TO_GRID = True
ITEM_Z_VALUE = {
    'grid': 0,
    'room': 10,
    'door': 20,
    'window': 20,
    'label': 30,
    'handle': 100,
}
ROOM_TYPES = {
    '客厅': {'color': '#E8F4FD', 'border': '#2196F3'},
    '主卧': {'color': '#FFF3E0', 'border': '#FF9800'},
    '次卧': {'color': '#FFF8E1', 'border': '#FFC107'},
    '厨房': {'color': '#E8F5E9', 'border': '#4CAF50'},
    '卫生间': {'color': '#E0F7FA', 'border': '#00BCD4'},
    '阳台': {'color': '#F3E5F5', 'border': '#9C27B0'},
    '餐厅': {'color': '#FBE9E7', 'border': '#FF5722'},
    '书房': {'color': '#ECEFF1', 'border': '#607D8B'},
    '走廊': {'color': '#FAFAFA', 'border': '#9E9E9E'},
    '自定义': {'color': '#EEEEEE', 'border': '#757575'},
}

def snap_to_grid(value):
    if not SNAP_TO_GRID:
        return value
    return round(value / GRID_SIZE) * GRID_SIZE

def snap_point_to_grid(point):
    if not SNAP_TO_GRID:
        return point
    return QPointF(
        round(point.x() / GRID_SIZE) * GRID_SIZE,
        round(point.y() / GRID_SIZE) * GRID_SIZE
    )

# ============================================================
# 顶点手柄图元
# ============================================================
class VertexHandle(QGraphicsRectItem):
    def __init__(self, index, parent=None):
        super().__init__(-5, -5, 10, 10, parent)
        self.index = index
        self.setBrush(QBrush(QColor('#2196F3')))
        self.setPen(QPen(Qt.white, 2))
        self.setZValue(ITEM_Z_VALUE['handle'])
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeAllCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.parentItem():
            snapped = snap_point_to_grid(value)
            self.parentItem().vertex_moved(self.index, snapped)
            return snapped
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if self.parentItem():
            self.parentItem().start_vertex_edit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.parentItem():
            self.parentItem().end_vertex_edit()
        super().mouseReleaseEvent(event)

# ============================================================
# 边手柄图元(用于四边拖拽调整大小)
# ============================================================
class EdgeHandle(QGraphicsRectItem):
    """房间四边的调整手柄,拖拽可沿垂直方向调整房间大小"""
    def __init__(self, edge_name, parent=None):
        # edge_name: 'top', 'bottom', 'left', 'right'
        super().__init__(-12, -12, 24, 24, parent)
        self.edge_name = edge_name
        self.setBrush(QBrush(QColor('#FF9800')))
        self.setPen(QPen(Qt.white, 2))
        self.setZValue(ITEM_Z_VALUE['handle'])
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        # 阻止事件向父项传播,确保拖拽手柄时不会移动整个房间
        self.setFlag(QGraphicsItem.ItemStopsClickFocusPropagation, True)
        # 根据边的位置设置光标形状
        if edge_name in ('top', 'bottom'):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.SizeHorCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.parentItem():
            parent = self.parentItem()
            if hasattr(parent, '_updating_handles') and parent._updating_handles:
                return value
            snapped = snap_point_to_grid(value)
            parent.edge_moved(self.edge_name, snapped)
            return snapped
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if self.parentItem():
            self.parentItem().start_edge_edit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.parentItem():
            self.parentItem().end_edge_edit()
        super().mouseReleaseEvent(event)

# ============================================================
# 房间图元
# ============================================================
class RoomItem(QGraphicsPolygonItem):
    def __init__(self, polygon=None, room_type='客厅', parent=None):
        if polygon is None:
            polygon = QPolygonF([
                QPointF(0, 0), QPointF(200, 0),
                QPointF(200, 150), QPointF(0, 150)
            ])
        super().__init__(polygon, parent)
        self.room_type = room_type
        self.room_name = room_type
        self.vertex_handles = []
        self.editing_vertices = False
        self.edge_handles = []
        self.editing_edges = False
        self.show_area = True
        style = ROOM_TYPES.get(room_type, ROOM_TYPES['自定义'])
        self.fill_color = QColor(style['color'])
        self.border_color = QColor(style['border'])
        self.update_style()
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(ITEM_Z_VALUE['room'])
        self.setAcceptHoverEvents(True)
        # 边缘拖拽调整大小状态
        self._resizing = False
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_rect = None
        self.label_item = QGraphicsTextItem(self)
        self.label_item.setDefaultTextColor(QColor('#333333'))
        self.label_item.setFont(QFont('微软雅黑', 10, QFont.Bold))
        self.update_label()

    def update_style(self):
        pen = QPen(self.border_color, 2)
        brush = QBrush(self.fill_color)
        self.setPen(pen)
        self.setBrush(brush)

    def update_label(self):
        area = self.calculate_area()
        text = f"{self.room_name}\n{area:.1f}㎡" if self.show_area else self.room_name
        self.label_item.setPlainText(text)
        bounds = self.polygon().boundingRect()
        text_rect = self.label_item.boundingRect()
        self.label_item.setPos(
            bounds.center().x() - text_rect.width() / 2,
            bounds.center().y() - text_rect.height() / 2
        )

    def calculate_area(self):
        poly = self.polygon()
        n = len(poly)
        if n < 3:
            return 0
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += poly[i].x() * poly[j].y()
            area -= poly[j].x() * poly[i].y()
        return abs(area) / 2 / 10000

    def get_width(self):
        """获取房间宽度(边界矩形宽度)"""
        return self.polygon().boundingRect().width()

    def get_height(self):
        """获取房间高度(边界矩形高度)"""
        return self.polygon().boundingRect().height()

    def set_size(self, width, height):
        """[新增]设置房间尺寸(保持左上角位置不变)"""
        poly = self.polygon()
        bounds = poly.boundingRect()
        left = bounds.left()
        top = bounds.top()
        # 重建为标准矩形(针对矩形房间)
        new_poly = QPolygonF([
            QPointF(left, top),
            QPointF(left + width, top),
            QPointF(left + width, top + height),
            QPointF(left, top + height)
        ])
        self.setPolygon(new_poly)
        self.update_label()
        # 刷新手柄
        if self.editing_vertices:
            self.show_vertex_handles(False)
            self.show_vertex_handles(True)
        if self.editing_edges:
            self.show_edge_handles(False)
            self.show_edge_handles(True)

    def set_room_type(self, room_type):
        self.room_type = room_type
        if room_type in ROOM_TYPES:
            style = ROOM_TYPES[room_type]
            self.fill_color = QColor(style['color'])
            self.border_color = QColor(style['border'])
            self.update_style()

    def set_room_name(self, name):
        self.room_name = name
        self.update_label()

    def set_colors(self, fill_color, border_color):
        self.fill_color = QColor(fill_color)
        self.border_color = QColor(border_color)
        self.update_style()

    def show_vertex_handles(self, show=True):
        if show and not self.editing_vertices:
            self.editing_vertices = True
            poly = self.polygon()
            for i in range(len(poly)):
                handle = VertexHandle(i, self)
                handle.setPos(poly[i])
                self.vertex_handles.append(handle)
        elif not show and self.editing_vertices:
            self.editing_vertices = False
            for handle in self.vertex_handles:
                if handle.scene():
                    handle.scene().removeItem(handle)
            self.vertex_handles.clear()

    def vertex_moved(self, index, new_pos):
        poly = self.polygon()
        poly[index] = new_pos
        self.setPolygon(poly)
        self.update_label()

    def start_vertex_edit(self):
        pass

    def end_vertex_edit(self):
        self.update_label()

    def show_edge_handles(self, show=True):
        """显示/隐藏四边调整手柄"""
        if show and not self.editing_edges:
            self.editing_edges = True
            self._updating_handles = False
            bounds = self.polygon().boundingRect()
            offset = 10  # 手柄向房间外偏移的距离
            # 上边中点(向上偏移)
            top_handle = EdgeHandle('top', self)
            top_handle.setPos(bounds.center().x(), bounds.top() - offset)
            self.edge_handles.append(top_handle)
            # 下边中点(向下偏移)
            bottom_handle = EdgeHandle('bottom', self)
            bottom_handle.setPos(bounds.center().x(), bounds.bottom() + offset)
            self.edge_handles.append(bottom_handle)
            # 左边中点(向左偏移)
            left_handle = EdgeHandle('left', self)
            left_handle.setPos(bounds.left() - offset, bounds.center().y())
            self.edge_handles.append(left_handle)
            # 右边中点(向右偏移)
            right_handle = EdgeHandle('right', self)
            right_handle.setPos(bounds.right() + offset, bounds.center().y())
            self.edge_handles.append(right_handle)
        elif not show and self.editing_edges:
            self.editing_edges = False
            for handle in self.edge_handles:
                if handle.scene():
                    handle.scene().removeItem(handle)
            self.edge_handles.clear()

    def edge_moved(self, edge_name, new_pos):
        """边手柄被拖拽时调整房间大小"""
        poly = self.polygon()
        bounds = poly.boundingRect()
        left = bounds.left()
        top = bounds.top()
        right = bounds.right()
        bottom = bounds.bottom()
        offset = 10  # 与显示时的偏移量一致

        if edge_name == 'top':
            top = snap_to_grid(new_pos.y() + offset)  # 加偏移还原实际边界
            if bottom - top < 20:
                top = bottom - 20
        elif edge_name == 'bottom':
            bottom = snap_to_grid(new_pos.y() - offset)
            if bottom - top < 20:
                bottom = top + 20
        elif edge_name == 'left':
            left = snap_to_grid(new_pos.x() + offset)
            if right - left < 20:
                left = right - 20
        elif edge_name == 'right':
            right = snap_to_grid(new_pos.x() - offset)
            if right - left < 20:
                right = left + 20

        # 重建矩形多边形
        new_poly = QPolygonF([
            QPointF(left, top),
            QPointF(right, top),
            QPointF(right, bottom),
            QPointF(left, bottom)
        ])
        self.setPolygon(new_poly)
        self.update_label()

        # 防止递归:刷新手柄位置时跳过 itemChange 回调
        self._updating_handles = True
        try:
            # 更新边手柄位置
            if self.editing_edges:
                for handle in self.edge_handles:
                    if handle.edge_name == 'top':
                        handle.setPos((left + right) / 2, top - offset)
                    elif handle.edge_name == 'bottom':
                        handle.setPos((left + right) / 2, bottom + offset)
                    elif handle.edge_name == 'left':
                        handle.setPos(left - offset, (top + bottom) / 2)
                    elif handle.edge_name == 'right':
                        handle.setPos(right + offset, (top + bottom) / 2)
            # 同步更新顶点手柄位置
            if self.editing_vertices and len(self.vertex_handles) == 4:
                corners = [
                    QPointF(left, top),
                    QPointF(right, top),
                    QPointF(right, bottom),
                    QPointF(left, bottom)
                ]
                for i, handle in enumerate(self.vertex_handles):
                    if i < len(corners):
                        handle.setPos(corners[i])
        finally:
            self._updating_handles = False

    def start_edge_edit(self):
        pass

    def end_edge_edit(self):
        self.update_label()

    def add_vertex(self, pos):
        poly = self.polygon()
        insert_index = len(poly)
        min_dist = float('inf')
        for i in range(len(poly)):
            j = (i + 1) % len(poly)
            dist = self.point_to_line_distance(pos, poly[i], poly[j])
            if dist < min_dist:
                min_dist = dist
                insert_index = j
        poly.insert(insert_index, snap_point_to_grid(pos))
        self.setPolygon(poly)
        self.update_label()
        if self.editing_vertices:
            self.show_vertex_handles(False)
            self.show_vertex_handles(True)

    def remove_vertex(self, index):
        poly = self.polygon()
        if len(poly) > 3:
            poly.remove(index)
            self.setPolygon(poly)
            self.update_label()
            if self.editing_vertices:
                self.show_vertex_handles(False)
                self.show_vertex_handles(True)

    def point_to_line_distance(self, point, line_start, line_end):
        line = QPointF(line_end - line_start)
        point_vec = QPointF(point - line_start)
        line_len_sq = line.x() ** 2 + line.y() ** 2
        if line_len_sq == 0:
            return (point - line_start).manhattanLength()
        t = max(0, min(1, (point_vec.x() * line.x() + point_vec.y() * line.y()) / line_len_sq))
        proj = QPointF(line_start.x() + t * line.x(), line_start.y() + t * line.y())
        return (point - proj).manhattanLength()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            if value:
                self.setPen(QPen(self.border_color, 3, Qt.DashLine))
                # 选中时自动显示边调整手柄
                self.show_edge_handles(True)
            else:
                self.setPen(QPen(self.border_color, 2))
                self.show_vertex_handles(False)
                self.show_edge_handles(False)
        elif change == QGraphicsItem.ItemPositionChange:
            if SNAP_TO_GRID:
                snapped = QPointF(snap_to_grid(value.x()), snap_to_grid(value.y()))
                self.update_label()
                # 移动房间时同步更新手柄位置
                if self.editing_edges:
                    self._update_handle_positions()
                return snapped
            self.update_label()
        return super().itemChange(change, value)

    def _update_handle_positions(self):
        """更新所有手柄的位置(房间移动后调用)"""
        if not self.editing_edges:
            return
        bounds = self.polygon().boundingRect()
        offset = 10
        self._updating_handles = True
        try:
            for handle in self.edge_handles:
                if handle.edge_name == 'top':
                    handle.setPos(bounds.center().x(), bounds.top() - offset)
                elif handle.edge_name == 'bottom':
                    handle.setPos(bounds.center().x(), bounds.bottom() + offset)
                elif handle.edge_name == 'left':
                    handle.setPos(bounds.left() - offset, bounds.center().y())
                elif handle.edge_name == 'right':
                    handle.setPos(bounds.right() + offset, bounds.center().y())
        finally:
            self._updating_handles = False

    def _hit_test_edge(self, pos):
        """检测点击位置是否在房间边缘附近,返回边缘名称或None"""
        margin = 10  # 边缘检测范围(像素)
        bounds = self.polygon().boundingRect()
        x, y = pos.x(), pos.y()
        left, top = bounds.left(), bounds.top()
        right, bottom = bounds.right(), bounds.bottom()

        on_top = abs(y - top) <= margin and left <= x <= right
        on_bottom = abs(y - bottom) <= margin and left <= x <= right
        on_left = abs(x - left) <= margin and top <= y <= bottom
        on_right = abs(x - right) <= margin and top <= y <= bottom

        if on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        return None

    def hoverMoveEvent(self, event):
        """鼠标悬停时根据位置改变光标形状"""
        edge = self._hit_test_edge(event.pos())
        if edge in ('top', 'bottom'):
            self.setCursor(Qt.SizeVerCursor)
        elif edge in ('left', 'right'):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeAllCursor if self.flags() & QGraphicsItem.ItemIsMovable else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开时恢复默认光标"""
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """鼠标按下:判断是调整大小还是移动"""
        if event.button() == Qt.LeftButton:
            edge = self._hit_test_edge(event.pos())
            if edge:
                # 点击在边缘,进入调整大小模式
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_pos = event.pos()
                self._resize_start_rect = self.polygon().boundingRect()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动:调整大小或移动"""
        if self._resizing and self._resize_edge:
            # 调整大小模式
            bounds = self._resize_start_rect
            delta = event.pos() - self._resize_start_pos
            left = bounds.left()
            top = bounds.top()
            right = bounds.right()
            bottom = bounds.bottom()

            edge = self._resize_edge
            if edge == 'top':
                top = snap_to_grid(bounds.top() + delta.y())
                if bottom - top < 20:
                    top = bottom - 20
            elif edge == 'bottom':
                bottom = snap_to_grid(bounds.bottom() + delta.y())
                if bottom - top < 20:
                    bottom = top + 20
            elif edge == 'left':
                left = snap_to_grid(bounds.left() + delta.x())
                if right - left < 20:
                    left = right - 20
            elif edge == 'right':
                right = snap_to_grid(bounds.right() + delta.x())
                if right - left < 20:
                    right = left + 20

            # 重建矩形多边形
            new_poly = QPolygonF([
                QPointF(left, top),
                QPointF(right, top),
                QPointF(right, bottom),
                QPointF(left, bottom)
            ])
            self.setPolygon(new_poly)
            self.update_label()

            # 同步更新手柄位置
            if self.editing_edges:
                self._updating_handles = True
                try:
                    offset = 10
                    for handle in self.edge_handles:
                        if handle.edge_name == 'top':
                            handle.setPos((left + right) / 2, top - offset)
                        elif handle.edge_name == 'bottom':
                            handle.setPos((left + right) / 2, bottom + offset)
                        elif handle.edge_name == 'left':
                            handle.setPos(left - offset, (top + bottom) / 2)
                        elif handle.edge_name == 'right':
                            handle.setPos(right + offset, (top + bottom) / 2)
                finally:
                    self._updating_handles = False
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放:结束调整大小"""
        if self._resizing:
            self._resizing = False
            self._resize_edge = None
            self._resize_start_pos = None
            self._resize_start_rect = None
            self.update_label()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.editing_edges:
                self.show_edge_handles(True)
                self.show_vertex_handles(True)
            else:
                self.show_edge_handles(False)
                self.show_vertex_handles(False)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def get_attached_items(self):
        """获取所有附着在本房间上的门窗子项"""
        attached = []
        for child in self.childItems():
            if isinstance(child, (DoorItem, WindowItem)):
                attached.append(child)
        return attached

    def to_dict(self):
        poly = self.polygon()
        points = [[p.x(), p.y()] for p in poly]
        return {
            'type': 'room',
            'room_type': self.room_type,
            'room_name': self.room_name,
            'points': points,
            'pos': [self.pos().x(), self.pos().y()],
            'fill_color': self.fill_color.name(),
            'border_color': self.border_color.name(),
        }

    @classmethod
    def from_dict(cls, data):
        points = [QPointF(p[0], p[1]) for p in data['points']]
        poly = QPolygonF(points)
        item = cls(poly, data['room_type'])
        item.setPos(data['pos'][0], data['pos'][1])
        item.set_room_name(data.get('room_name', data['room_type']))
        if 'fill_color' in data and 'border_color' in data:
            item.set_colors(data['fill_color'], data['border_color'])
        return item

# ============================================================
# 门图元(支持附着房间)
# ============================================================
class DoorItem(QGraphicsItem):
    def __init__(self, width=80, parent=None):
        super().__init__(parent)
        self.width = width
        self.door_type = '单开门'
        self.open_direction = 1
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(ITEM_Z_VALUE['door'])

    def boundingRect(self):
        return QRectF(-5, -5, self.width + 10, self.width + 10)

    def shape(self):
        path = QPainterPath()
        path.addRect(QRectF(0, -3, self.width, 6))
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor('#333333'), 2)
        painter.setPen(pen)
        painter.drawLine(0, 0, self.width, 0)
        path = QPainterPath()
        if self.open_direction > 0:
            path.moveTo(self.width, 0)
            path.arcTo(QRectF(0, -self.width, self.width * 2, self.width * 2), 90, -90)
        else:
            path.moveTo(0, 0)
            path.arcTo(QRectF(-self.width, -self.width, self.width * 2, self.width * 2), 90, 90)
        painter.setPen(QPen(QColor('#666666'), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setPen(QPen(QColor('#333333'), 2))
        if self.open_direction > 0:
            painter.drawLine(self.width, 0, self.width, -self.width)
        else:
            painter.drawLine(0, 0, 0, -self.width)
        if self.isSelected():
            painter.setPen(QPen(QColor('#2196F3'), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
        # 附着状态指示
        if self.parentItem() and isinstance(self.parentItem(), RoomItem):
            painter.setPen(QPen(QColor('#4CAF50'), 1, Qt.DotLine))
            painter.drawEllipse(self.width / 2 - 4, -8, 8, 8)

    def set_width(self, width):
        self.width = width
        self.update()

    def flip_direction(self):
        self.open_direction *= -1
        self.update()

    def is_attached(self):
        """是否已附着到房间"""
        return isinstance(self.parentItem(), RoomItem)

    def attach_to_room(self, room):
        """[新增]附着到指定房间(成为子项,移动房间时一起动)"""
        if room is None:
            self.setParentItem(None)
            return
        # 计算门在房间坐标系中的位置
        scene_pos = self.mapToScene(QPointF(0, 0))
        room_pos = room.mapFromScene(scene_pos)
        self.setParentItem(room)
        self.setPos(room_pos)

    def detach_from_room(self):
        """[新增]从房间脱离"""
        if self.parentItem():
            scene_pos = self.mapToScene(QPointF(0, 0))
            self.setParentItem(None)
            self.setPos(scene_pos)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            if SNAP_TO_GRID and not self.parentItem():
                return QPointF(snap_to_grid(value.x()), snap_to_grid(value.y()))
        return super().itemChange(change, value)

    def to_dict(self):
        # 计算场景中的绝对位置
        scene_pos = self.mapToScene(QPointF(0, 0))
        return {
            'type': 'door',
            'width': self.width,
            'door_type': self.door_type,
            'open_direction': self.open_direction,
            'pos': [scene_pos.x(), scene_pos.y()],
            'rotation': self.rotation(),
            'attached': self.is_attached(),
        }

    @classmethod
    def from_dict(cls, data):
        item = cls(data['width'])
        item.setPos(data['pos'][0], data['pos'][1])
        item.setRotation(data.get('rotation', 0))
        item.open_direction = data.get('open_direction', 1)
        item.door_type = data.get('door_type', '单开门')
        return item

# ============================================================
# 窗户图元(支持附着房间)
# ============================================================
class WindowItem(QGraphicsItem):
    def __init__(self, width=120, parent=None):
        super().__init__(parent)
        self.width = width
        self.window_type = '普通窗'
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(ITEM_Z_VALUE['window'])

    def boundingRect(self):
        return QRectF(-5, -10, self.width + 10, 20)

    def shape(self):
        path = QPainterPath()
        path.addRect(QRectF(0, -6, self.width, 12))
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor('#2196F3'), 1.5)
        painter.setPen(pen)
        for i in range(4):
            y = -6 + i * 4
            painter.drawLine(0, y, self.width, y)
        if self.isSelected():
            painter.setPen(QPen(QColor('#2196F3'), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
        # 附着状态指示
        if self.parentItem() and isinstance(self.parentItem(), RoomItem):
            painter.setPen(QPen(QColor('#4CAF50'), 1, Qt.DotLine))
            painter.setBrush(QBrush(QColor('#4CAF50')))
            painter.drawEllipse(self.width / 2 - 4, -12, 8, 8)

    def set_width(self, width):
        self.width = width
        self.update()

    def is_attached(self):
        """是否已附着到房间"""
        return isinstance(self.parentItem(), RoomItem)

    def attach_to_room(self, room):
        """[新增]附着到指定房间"""
        if room is None:
            self.setParentItem(None)
            return
        scene_pos = self.mapToScene(QPointF(0, 0))
        room_pos = room.mapFromScene(scene_pos)
        self.setParentItem(room)
        self.setPos(room_pos)

    def detach_from_room(self):
        """[新增]从房间脱离"""
        if self.parentItem():
            scene_pos = self.mapToScene(QPointF(0, 0))
            self.setParentItem(None)
            self.setPos(scene_pos)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            if SNAP_TO_GRID and not self.parentItem():
                return QPointF(snap_to_grid(value.x()), snap_to_grid(value.y()))
        return super().itemChange(change, value)

    def to_dict(self):
        scene_pos = self.mapToScene(QPointF(0, 0))
        return {
            'type': 'window',
            'width': self.width,
            'window_type': self.window_type,
            'pos': [scene_pos.x(), scene_pos.y()],
            'rotation': self.rotation(),
            'attached': self.is_attached(),
        }

    @classmethod
    def from_dict(cls, data):
        item = cls(data['width'])
        item.setPos(data['pos'][0], data['pos'][1])
        item.setRotation(data.get('rotation', 0))
        item.window_type = data.get('window_type', '普通窗')
        return item

# ============================================================
# 标注文字图元
# ============================================================
class LabelItem(QGraphicsTextItem):
    def __init__(self, text='标注', parent=None):
        super().__init__(text, parent)
        self.setDefaultTextColor(QColor('#333333'))
        self.setFont(QFont('微软雅黑', 9))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(ITEM_Z_VALUE['label'])

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            if SNAP_TO_GRID:
                return QPointF(snap_to_grid(value.x()), snap_to_grid(value.y()))
        return super().itemChange(change, value)

    def to_dict(self):
        return {
            'type': 'label',
            'text': self.toPlainText(),
            'pos': [self.pos().x(), self.pos().y()],
            'font_size': self.font().pointSize(),
        }

    @classmethod
    def from_dict(cls, data):
        item = cls(data['text'])
        item.setPos(data['pos'][0], data['pos'][1])
        font = item.font()
        font.setPointSize(data.get('font_size', 9))
        item.setFont(font)
        return item

# ============================================================
# 自定义图形场景(支持连续绘制 + 自动附着)
# ============================================================
class FloorPlanScene(QGraphicsScene):
    itemSelected = Signal(object)
    itemDeleted = Signal()
    itemMoved = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 2000, 2000)
        self.mode = 'select'
        self.temp_item = None
        self.start_point = None
        self.show_grid = True
        self.auto_attach = True  # 门窗自动附着房间

    def drawBackground(self, painter, rect):
        if not self.show_grid:
            return
        painter.fillRect(rect, QColor('#FAFAFA'))
        pen = QPen(QColor('#E0E0E0'), 0.5)
        painter.setPen(pen)
        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())
        left = (left // GRID_SIZE) * GRID_SIZE
        top = (top // GRID_SIZE) * GRID_SIZE
        x = left
        while x <= right:
            painter.drawLine(x, top, x, bottom)
            x += GRID_SIZE
        y = top
        while y <= bottom:
            painter.drawLine(left, y, right, y)
            y += GRID_SIZE
        pen = QPen(QColor('#BDBDBD'), 0.8)
        painter.setPen(pen)
        x = left
        while x <= right:
            if x % (GRID_SIZE * 5) == 0:
                painter.drawLine(x, top, x, bottom)
            x += GRID_SIZE
        y = top
        while y <= bottom:
            if y % (GRID_SIZE * 5) == 0:
                painter.drawLine(left, y, right, y)
            y += GRID_SIZE

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'select':
            self.set_editable_items(True)
        else:
            self.set_editable_items(False)

    def set_editable_items(self, editable):
        for item in self.items():
            if isinstance(item, (RoomItem, DoorItem, WindowItem, LabelItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, editable)
                item.setFlag(QGraphicsItem.ItemIsSelectable, editable)

    def find_room_at(self, scene_pos):
        """查找指定位置下的房间"""
        items = self.items(scene_pos)
        for item in items:
            if isinstance(item, RoomItem):
                return item
        return None

    def try_attach_to_room(self, item):
        """[新增]尝试将门窗附着到其位置下的房间"""
        if not self.auto_attach:
            return
        if not isinstance(item, (DoorItem, WindowItem)):
            return
        # 获取中心点场景坐标
        center = item.mapToScene(QPointF(item.width / 2, 0))
        room = self.find_room_at(center)
        if room and room != item.parentItem():
            item.attach_to_room(room)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = snap_point_to_grid(event.scenePos())

            if self.mode == 'add_room':
                self.start_point = scene_pos
                poly = QPolygonF([scene_pos, scene_pos, scene_pos, scene_pos])
                self.temp_item = RoomItem(poly, '自定义')
                self.addItem(self.temp_item)
                return

            elif self.mode == 'add_door':
                door = DoorItem(80)
                door.setPos(scene_pos)
                self.addItem(door)
                # 自动附着房间
                self.try_attach_to_room(door)
                self.clearSelection()
                door.setSelected(True)
                self.itemSelected.emit(door)
                # [修复]不自动切回select,保持连续绘制模式
                return

            elif self.mode == 'add_window':
                window = WindowItem(120)
                window.setPos(scene_pos)
                self.addItem(window)
                # 自动附着房间
                self.try_attach_to_room(window)
                self.clearSelection()
                window.setSelected(True)
                self.itemSelected.emit(window)
                # [修复]不自动切回select,保持连续绘制模式
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == 'add_room' and self.temp_item and self.start_point:
            end_pos = snap_point_to_grid(event.scenePos())
            poly = QPolygonF([
                self.start_point,
                QPointF(end_pos.x(), self.start_point.y()),
                end_pos,
                QPointF(self.start_point.x(), end_pos.y())
            ])
            self.temp_item.setPolygon(poly)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.mode == 'add_room' and self.temp_item:
                poly = self.temp_item.polygon()
                if poly.boundingRect().width() > 20 and poly.boundingRect().height() > 20:
                    self.temp_item.set_room_type('自定义')
                    self.clearSelection()
                    self.temp_item.setSelected(True)
                    self.itemSelected.emit(self.temp_item)
                else:
                    self.removeItem(self.temp_item)
                self.temp_item = None
                self.start_point = None
                # [修复]不自动切回select,保持绘制模式可连续画
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        # ESC 键退出绘制模式
        if event.key() == Qt.Key_Escape:
            if self.mode != 'select':
                self.set_mode('select')
                if self.temp_item:
                    self.removeItem(self.temp_item)
                    self.temp_item = None
                    self.start_point = None
                self.itemSelected.emit(None)
                return

        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            for item in self.selectedItems():
                if isinstance(item, (RoomItem, DoorItem, WindowItem, LabelItem)):
                    self.removeItem(item)
            self.itemDeleted.emit()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        item = self.itemAt(event.scenePos(), QTransform())
        if item is None:
            self.clearSelection()
            self.itemSelected.emit(None)

    def get_selected_item(self):
        items = self.selectedItems()
        if items:
            return items[0]
        return None

    def save_to_file(self, filename):
        data = {'items': []}
        for item in self.items():
            if isinstance(item, RoomItem):
                data['items'].append(item.to_dict())
            elif isinstance(item, DoorItem):
                data['items'].append(item.to_dict())
            elif isinstance(item, WindowItem):
                data['items'].append(item.to_dict())
            elif isinstance(item, LabelItem):
                data['items'].append(item.to_dict())
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.clear()
        # 先加载所有房间
        rooms = []
        others = []
        for item_data in data.get('items', []):
            if item_data.get('type') == 'room':
                rooms.append(item_data)
            else:
                others.append(item_data)
        # 创建房间
        room_items = {}
        for room_data in rooms:
            item = RoomItem.from_dict(room_data)
            self.addItem(item)
            room_items[id(item)] = item
        # 创建其他(门窗等)
        for item_data in others:
            item_type = item_data.get('type')
            if item_type == 'door':
                item = DoorItem.from_dict(item_data)
                self.addItem(item)
                # 尝试重新附着
                if item_data.get('attached', False):
                    center = item.mapToScene(QPointF(item.width / 2, 0))
                    room = self.find_room_at(center)
                    if room:
                        item.attach_to_room(room)
            elif item_type == 'window':
                item = WindowItem.from_dict(item_data)
                self.addItem(item)
                if item_data.get('attached', False):
                    center = item.mapToScene(QPointF(item.width / 2, 0))
                    room = self.find_room_at(center)
                    if room:
                        item.attach_to_room(room)
            elif item_type == 'label':
                item = LabelItem.from_dict(item_data)
                self.addItem(item)

# ============================================================
# 自定义图形视图
# ============================================================
class FloorPlanView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.zoom_factor = 1.0
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 0.87
            self.scale(factor, factor)
            self.zoom_factor *= factor
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.RubberBandDrag)
        super().mouseReleaseEvent(event)

    def zoom_in(self):
        self.scale(1.2, 1.2)
        self.zoom_factor *= 1.2

    def zoom_out(self):
        self.scale(0.8, 0.8)
        self.zoom_factor *= 0.8

    def reset_zoom(self):
        self.resetTransform()
        self.zoom_factor = 1.0

# ============================================================
# 模块列表面板
# ============================================================
class ModulePanel(QWidget):
    itemAddRequest = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        tip_label = QLabel('💡 拖拽 / 双击 / 右键 均可添加')
        tip_label.setStyleSheet('color: #666; font-size: 11px; padding: 2px;')
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        room_group = QGroupBox('房间模块')
        room_layout = QVBoxLayout(room_group)
        self.room_list = QListWidget()
        self.room_list.setDragEnabled(True)
        self.room_list.setAcceptDrops(False)
        self.room_list.setDropIndicatorShown(False)
        self.room_list.setViewMode(QListWidget.IconMode)
        self.room_list.setIconSize(QSize(64, 48))
        self.room_list.setSpacing(8)
        self.room_list.setMovement(QListWidget.Static)
        self.room_list.setResizeMode(QListWidget.Adjust)
        self.room_list.setSelectionMode(QListWidget.SingleSelection)
        self.room_list.setContextMenuPolicy(Qt.CustomContextMenu)

        for room_type, style in ROOM_TYPES.items():
            if room_type == '自定义':
                continue
            item = QListWidgetItem(room_type)
            item.setData(Qt.UserRole, room_type)
            item.setToolTip(f'{room_type} - 拖拽到画布或双击添加')
            pixmap = self.create_room_icon(style['color'], style['border'])
            item.setIcon(QIcon(pixmap))
            self.room_list.addItem(item)

        room_layout.addWidget(self.room_list)
        room_btn_layout = QHBoxLayout()
        self.add_room_btn = QPushButton('➕ 添加选中房间')
        self.add_room_btn.setToolTip('将选中的房间类型添加到画布中心')
        room_btn_layout.addWidget(self.add_room_btn)
        room_layout.addLayout(room_btn_layout)
        layout.addWidget(room_group)

        dw_group = QGroupBox('门窗模块')
        dw_layout = QVBoxLayout(dw_group)
        self.dw_list = QListWidget()
        self.dw_list.setDragEnabled(True)
        self.dw_list.setAcceptDrops(False)
        self.dw_list.setViewMode(QListWidget.IconMode)
        self.dw_list.setIconSize(QSize(64, 48))
        self.dw_list.setSpacing(8)
        self.dw_list.setMovement(QListWidget.Static)
        self.dw_list.setResizeMode(QListWidget.Adjust)
        self.dw_list.setSelectionMode(QListWidget.SingleSelection)
        self.dw_list.setContextMenuPolicy(Qt.CustomContextMenu)

        door_item = QListWidgetItem('🚪 门 (80cm)')
        door_item.setData(Qt.UserRole, 'door')
        door_item.setToolTip('门 - 拖拽到画布或双击添加')
        self.dw_list.addItem(door_item)
        window_item = QListWidgetItem('🪟 窗 (120cm)')
        window_item.setData(Qt.UserRole, 'window')
        window_item.setToolTip('窗户 - 拖拽到画布或双击添加')
        self.dw_list.addItem(window_item)

        dw_layout.addWidget(self.dw_list)
        dw_btn_layout = QHBoxLayout()
        self.add_dw_btn = QPushButton('➕ 添加选中门窗')
        self.add_dw_btn.setToolTip('将选中的门窗添加到画布中心')
        dw_btn_layout.addWidget(self.add_dw_btn)
        dw_layout.addLayout(dw_btn_layout)
        layout.addWidget(dw_group)

        label_group = QGroupBox('标注')
        label_layout = QVBoxLayout(label_group)
        self.add_label_btn = QPushButton('📝 添加文字标注')
        label_layout.addWidget(self.add_label_btn)
        label_group.setLayout(label_layout)
        layout.addWidget(label_group)
        layout.addStretch()

    def setup_connections(self):
        self.room_list.itemDoubleClicked.connect(self.on_room_double_clicked)
        self.dw_list.itemDoubleClicked.connect(self.on_dw_double_clicked)
        self.add_room_btn.clicked.connect(self.on_add_room_btn)
        self.add_dw_btn.clicked.connect(self.on_add_dw_btn)
        self.room_list.customContextMenuRequested.connect(self.show_room_context_menu)
        self.dw_list.customContextMenuRequested.connect(self.show_dw_context_menu)

    def create_room_icon(self, fill_color, border_color):
        pixmap = QPixmap(64, 48)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(fill_color)))
        painter.setPen(QPen(QColor(border_color), 2))
        painter.drawRect(2, 2, 60, 44)
        painter.end()
        return pixmap

    def on_room_double_clicked(self, item):
        room_type = item.data(Qt.UserRole)
        if room_type:
            self.itemAddRequest.emit(room_type)

    def on_dw_double_clicked(self, item):
        dw_type = item.data(Qt.UserRole)
        if dw_type:
            self.itemAddRequest.emit(dw_type)

    def on_add_room_btn(self):
        current_item = self.room_list.currentItem()
        if current_item:
            room_type = current_item.data(Qt.UserRole)
            if room_type:
                self.itemAddRequest.emit(room_type)
        else:
            self.itemAddRequest.emit('客厅')

    def on_add_dw_btn(self):
        current_item = self.dw_list.currentItem()
        if current_item:
            dw_type = current_item.data(Qt.UserRole)
            if dw_type:
                self.itemAddRequest.emit(dw_type)
        else:
            self.itemAddRequest.emit('door')

    def show_room_context_menu(self, pos):
        item = self.room_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            add_action = menu.addAction('添加到画布')
            add_action.triggered.connect(lambda: self.itemAddRequest.emit(item.data(Qt.UserRole)))
            menu.exec(self.room_list.mapToGlobal(pos))

    def show_dw_context_menu(self, pos):
        item = self.dw_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            add_action = menu.addAction('添加到画布')
            add_action.triggered.connect(lambda: self.itemAddRequest.emit(item.data(Qt.UserRole)))
            menu.exec(self.dw_list.mapToGlobal(pos))

    def startDrag(self, supportedActions):
        current_list = self.sender() if isinstance(self.sender(), QListWidget) else self.room_list
        items = current_list.selectedItems()
        if not items:
            return
        item = items[0]
        item_data = item.data(Qt.UserRole)
        if not item_data:
            return
        drag = QDrag(current_list)
        mime_data = QMimeData()
        byte_array = QByteArray()
        stream = QDataStream(byte_array, QIODevice.WriteOnly)
        stream.writeInt32(0)
        stream.writeInt32(0)
        stream.writeInt32(Qt.UserRole)
        stream.writeQVariant(item_data)
        stream.writeInt32(Qt.DisplayRole)
        stream.writeQVariant(item.text())
        mime_data.setData('application/x-qabstractitemmodeldatalist', byte_array)
        mime_data.setText(item_data)
        drag.setMimeData(mime_data)
        if item.icon():
            drag.setPixmap(item.icon().pixmap(64, 48))
        drag.exec(Qt.CopyAction)

# ============================================================
# 属性面板(增强:房间宽高编辑 + 门窗附着控制)
# ============================================================
class PropertyPanel(QWidget):
    propertyChanged = Signal()
    attachRequest = Signal()
    detachRequest = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_item = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.prop_group = QGroupBox('属性')
        self.prop_layout = QFormLayout(self.prop_group)

        self.pos_x_spin = QDoubleSpinBox()
        self.pos_x_spin.setRange(-10000, 10000)
        self.pos_x_spin.setSuffix(' px')
        self.pos_x_spin.valueChanged.connect(self.on_position_changed)
        self.pos_y_spin = QDoubleSpinBox()
        self.pos_y_spin.setRange(-10000, 10000)
        self.pos_y_spin.setSuffix(' px')
        self.pos_y_spin.valueChanged.connect(self.on_position_changed)
        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-360, 360)
        self.rotation_spin.setSuffix(' °')
        self.rotation_spin.valueChanged.connect(self.on_rotation_changed)

        self.prop_layout.addRow('X 坐标:', self.pos_x_spin)
        self.prop_layout.addRow('Y 坐标:', self.pos_y_spin)
        self.prop_layout.addRow('旋转角度:', self.rotation_spin)

        # [新增]房间尺寸
        self.room_widget = QWidget()
        room_layout = QFormLayout(self.room_widget)
        self.room_width_spin = QDoubleSpinBox()
        self.room_width_spin.setRange(20, 5000)
        self.room_width_spin.setSuffix(' px')
        self.room_width_spin.valueChanged.connect(self.on_room_size_changed)
        self.room_height_spin = QDoubleSpinBox()
        self.room_height_spin.setRange(20, 5000)
        self.room_height_spin.setSuffix(' px')
        self.room_height_spin.valueChanged.connect(self.on_room_size_changed)

        self.room_type_combo = QComboBox()
        self.room_type_combo.addItems(list(ROOM_TYPES.keys()))
        self.room_type_combo.currentTextChanged.connect(self.on_room_type_changed)
        self.room_name_edit = QLineEdit()
        self.room_name_edit.editingFinished.connect(self.on_room_name_changed)
        self.fill_color_btn = QPushButton('选择填充色')
        self.fill_color_btn.clicked.connect(self.on_fill_color)
        self.border_color_btn = QPushButton('选择边框色')
        self.border_color_btn.clicked.connect(self.on_border_color)
        self.area_label = QLabel('面积: -')
        self.area_label.setStyleSheet('font-weight: bold; color: #2196F3;')

        room_layout.addRow('房间宽度:', self.room_width_spin)
        room_layout.addRow('房间高度:', self.room_height_spin)
        room_layout.addRow('房间类型:', self.room_type_combo)
        room_layout.addRow('房间名称:', self.room_name_edit)
        room_layout.addRow('填充颜色:', self.fill_color_btn)
        room_layout.addRow('边框颜色:', self.border_color_btn)
        room_layout.addRow(self.area_label)

        shape_group = QGroupBox('异形编辑')
        shape_layout = QVBoxLayout(shape_group)
        self.edit_vertices_btn = QPushButton('编辑顶点 (双击房间)')
        self.edit_vertices_btn.setCheckable(True)
        self.edit_vertices_btn.toggled.connect(self.on_edit_vertices)
        self.add_vertex_btn = QPushButton('添加顶点')
        self.add_vertex_btn.clicked.connect(self.on_add_vertex)
        self.remove_vertex_btn = QPushButton('删除选中顶点')
        self.remove_vertex_btn.clicked.connect(self.on_remove_vertex)
        shape_layout.addWidget(self.edit_vertices_btn)
        shape_layout.addWidget(self.add_vertex_btn)
        shape_layout.addWidget(self.remove_vertex_btn)

        # 门属性
        self.door_widget = QWidget()
        door_layout = QFormLayout(self.door_widget)
        self.door_width_spin = QDoubleSpinBox()
        self.door_width_spin.setRange(40, 200)
        self.door_width_spin.setSuffix(' cm')
        self.door_width_spin.valueChanged.connect(self.on_door_width_changed)
        self.flip_door_btn = QPushButton('翻转开门方向')
        self.flip_door_btn.clicked.connect(self.on_flip_door)
        # 附着状态
        self.door_attach_label = QLabel('状态: 未附着')
        self.door_attach_label.setStyleSheet('color: #666;')
        self.door_attach_btn = QPushButton('附着到房间')
        self.door_attach_btn.clicked.connect(self.on_attach_clicked)
        self.door_detach_btn = QPushButton('从房间脱离')
        self.door_detach_btn.clicked.connect(self.on_detach_clicked)
        self.door_detach_btn.hide()

        door_layout.addRow('门宽度:', self.door_width_spin)
        door_layout.addRow(self.flip_door_btn)
        door_layout.addRow(self.door_attach_label)
        door_layout.addRow(self.door_attach_btn)
        door_layout.addRow(self.door_detach_btn)

        # 窗户属性
        self.window_widget = QWidget()
        window_layout = QFormLayout(self.window_widget)
        self.window_width_spin = QDoubleSpinBox()
        self.window_width_spin.setRange(40, 300)
        self.window_width_spin.setSuffix(' cm')
        self.window_width_spin.valueChanged.connect(self.on_window_width_changed)
        # 附着状态
        self.window_attach_label = QLabel('状态: 未附着')
        self.window_attach_label.setStyleSheet('color: #666;')
        self.window_attach_btn = QPushButton('附着到房间')
        self.window_attach_btn.clicked.connect(self.on_attach_clicked)
        self.window_detach_btn = QPushButton('从房间脱离')
        self.window_detach_btn.clicked.connect(self.on_detach_clicked)
        self.window_detach_btn.hide()

        window_layout.addRow('窗宽度:', self.window_width_spin)
        window_layout.addRow(self.window_attach_label)
        window_layout.addRow(self.window_attach_btn)
        window_layout.addRow(self.window_detach_btn)

        # 标签属性
        self.label_widget = QWidget()
        label_layout = QFormLayout(self.label_widget)
        self.label_text_edit = QLineEdit()
        self.label_text_edit.editingFinished.connect(self.on_label_text_changed)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        label_layout.addRow('文字内容:', self.label_text_edit)
        label_layout.addRow('字号:', self.font_size_spin)

        layout.addWidget(self.prop_group)
        layout.addWidget(self.room_widget)
        layout.addWidget(shape_group)
        layout.addWidget(self.door_widget)
        layout.addWidget(self.window_widget)
        layout.addWidget(self.label_widget)
        layout.addStretch()

        self.room_widget.hide()
        self.door_widget.hide()
        self.window_widget.hide()
        self.label_widget.hide()

    def set_item(self, item):
        self.current_item = item
        if item is None:
            self.prop_group.setEnabled(False)
            self.room_widget.hide()
            self.door_widget.hide()
            self.window_widget.hide()
            self.label_widget.hide()
            return

        self.prop_group.setEnabled(True)
        # 计算场景绝对坐标用于显示
        if hasattr(item, 'mapToScene'):
            scene_pos = item.mapToScene(QPointF(0, 0))
        else:
            scene_pos = item.pos()

        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.rotation_spin.blockSignals(True)
        self.pos_x_spin.setValue(scene_pos.x())
        self.pos_y_spin.setValue(scene_pos.y())
        self.rotation_spin.setValue(item.rotation())
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self.rotation_spin.blockSignals(False)

        self.room_widget.hide()
        self.door_widget.hide()
        self.window_widget.hide()
        self.label_widget.hide()

        if isinstance(item, RoomItem):
            self.room_widget.show()
            self.room_width_spin.blockSignals(True)
            self.room_height_spin.blockSignals(True)
            self.room_width_spin.setValue(item.get_width())
            self.room_height_spin.setValue(item.get_height())
            self.room_width_spin.blockSignals(False)
            self.room_height_spin.blockSignals(False)

            self.room_type_combo.blockSignals(True)
            self.room_type_combo.setCurrentText(item.room_type)
            self.room_type_combo.blockSignals(False)
            self.room_name_edit.setText(item.room_name)
            self.area_label.setText(f'面积: {item.calculate_area():.2f} ㎡')
            self.edit_vertices_btn.blockSignals(True)
            self.edit_vertices_btn.setChecked(item.editing_vertices)
            self.edit_vertices_btn.blockSignals(False)

        elif isinstance(item, DoorItem):
            self.door_widget.show()
            self.door_width_spin.blockSignals(True)
            self.door_width_spin.setValue(item.width)
            self.door_width_spin.blockSignals(False)
            # 更新附着状态
            self._update_door_attach_status(item)

        elif isinstance(item, WindowItem):
            self.window_widget.show()
            self.window_width_spin.blockSignals(True)
            self.window_width_spin.setValue(item.width)
            self.window_width_spin.blockSignals(False)
            # 更新附着状态
            self._update_window_attach_status(item)

        elif isinstance(item, LabelItem):
            self.label_widget.show()
            self.label_text_edit.setText(item.toPlainText())
            self.font_size_spin.blockSignals(True)
            self.font_size_spin.setValue(item.font().pointSize())
            self.font_size_spin.blockSignals(False)

    def _update_door_attach_status(self, item):
        if item.is_attached():
            self.door_attach_label.setText('状态: ✅ 已附着房间')
            self.door_attach_label.setStyleSheet('color: #4CAF50; font-weight: bold;')
            self.door_attach_btn.hide()
            self.door_detach_btn.show()
        else:
            self.door_attach_label.setText('状态: ❌ 未附着房间')
            self.door_attach_label.setStyleSheet('color: #F44336;')
            self.door_attach_btn.show()
            self.door_detach_btn.hide()

    def _update_window_attach_status(self, item):
        if item.is_attached():
            self.window_attach_label.setText('状态: ✅ 已附着房间')
            self.window_attach_label.setStyleSheet('color: #4CAF50; font-weight: bold;')
            self.window_attach_btn.hide()
            self.window_detach_btn.show()
        else:
            self.window_attach_label.setText('状态: ❌ 未附着房间')
            self.window_attach_label.setStyleSheet('color: #F44336;')
            self.window_attach_btn.show()
            self.window_detach_btn.hide()

    def update_position(self):
        if self.current_item:
            if hasattr(self.current_item, 'mapToScene'):
                scene_pos = self.current_item.mapToScene(QPointF(0, 0))
            else:
                scene_pos = self.current_item.pos()
            self.pos_x_spin.blockSignals(True)
            self.pos_y_spin.blockSignals(True)
            self.pos_x_spin.setValue(scene_pos.x())
            self.pos_y_spin.setValue(scene_pos.y())
            self.pos_x_spin.blockSignals(False)
            self.pos_y_spin.blockSignals(False)
            if isinstance(self.current_item, RoomItem):
                self.area_label.setText(f'面积: {self.current_item.calculate_area():.2f} ㎡')
                self.room_width_spin.blockSignals(True)
                self.room_height_spin.blockSignals(True)
                self.room_width_spin.setValue(self.current_item.get_width())
                self.room_height_spin.setValue(self.current_item.get_height())
                self.room_width_spin.blockSignals(False)
                self.room_height_spin.blockSignals(False)

    def on_position_changed(self):
        if self.current_item:
            # 如果是附着状态,先脱离
            if isinstance(self.current_item, (DoorItem, WindowItem)) and self.current_item.is_attached():
                self.current_item.detach_from_room()
            self.current_item.setPos(self.pos_x_spin.value(), self.pos_y_spin.value())
            self.propertyChanged.emit()

    def on_rotation_changed(self):
        if self.current_item:
            self.current_item.setRotation(self.rotation_spin.value())
            self.propertyChanged.emit()

    def on_room_size_changed(self):
        """[新增]房间尺寸变化"""
        if isinstance(self.current_item, RoomItem):
            self.current_item.set_size(
                self.room_width_spin.value(),
                self.room_height_spin.value()
            )
            self.area_label.setText(f'面积: {self.current_item.calculate_area():.2f} ㎡')
            self.propertyChanged.emit()

    def on_room_type_changed(self, room_type):
        if isinstance(self.current_item, RoomItem):
            self.current_item.set_room_type(room_type)
            self.propertyChanged.emit()

    def on_room_name_changed(self):
        if isinstance(self.current_item, RoomItem):
            self.current_item.set_room_name(self.room_name_edit.text())
            self.propertyChanged.emit()

    def on_fill_color(self):
        if isinstance(self.current_item, RoomItem):
            color = QColorDialog.getColor(self.current_item.fill_color, self, '选择填充颜色')
            if color.isValid():
                self.current_item.fill_color = color
                self.current_item.update_style()
                self.propertyChanged.emit()

    def on_border_color(self):
        if isinstance(self.current_item, RoomItem):
            color = QColorDialog.getColor(self.current_item.border_color, self, '选择边框颜色')
            if color.isValid():
                self.current_item.border_color = color
                self.current_item.update_style()
                self.propertyChanged.emit()

    def on_edit_vertices(self, checked):
        if isinstance(self.current_item, RoomItem):
            self.current_item.show_vertex_handles(checked)

    def on_add_vertex(self):
        if isinstance(self.current_item, RoomItem):
            poly = self.current_item.polygon()
            center = poly.boundingRect().center()
            self.current_item.add_vertex(center)
            self.area_label.setText(f'面积: {self.current_item.calculate_area():.2f} ㎡')

    def on_remove_vertex(self):
        if isinstance(self.current_item, RoomItem):
            poly = self.current_item.polygon()
            if len(poly) > 3:
                self.current_item.remove_vertex(len(poly) - 1)
                self.area_label.setText(f'面积: {self.current_item.calculate_area():.2f} ㎡')

    def on_door_width_changed(self, value):
        if isinstance(self.current_item, DoorItem):
            self.current_item.set_width(value)
            self.propertyChanged.emit()

    def on_flip_door(self):
        if isinstance(self.current_item, DoorItem):
            self.current_item.flip_direction()
            self.propertyChanged.emit()

    def on_window_width_changed(self, value):
        if isinstance(self.current_item, WindowItem):
            self.current_item.set_width(value)
            self.propertyChanged.emit()

    def on_attach_clicked(self):
        """附着按钮点击 - 请求主窗口处理"""
        self.attachRequest.emit()

    def on_detach_clicked(self):
        """脱离按钮点击"""
        if isinstance(self.current_item, (DoorItem, WindowItem)):
            self.current_item.detach_from_room()
            if isinstance(self.current_item, DoorItem):
                self._update_door_attach_status(self.current_item)
            else:
                self._update_window_attach_status(self.current_item)
            self.propertyChanged.emit()

    def on_label_text_changed(self):
        if isinstance(self.current_item, LabelItem):
            self.current_item.setPlainText(self.label_text_edit.text())
            self.propertyChanged.emit()

    def on_font_size_changed(self, value):
        if isinstance(self.current_item, LabelItem):
            font = self.current_item.font()
            font.setPointSize(value)
            self.current_item.setFont(font)
            self.propertyChanged.emit()

# ============================================================
# 支持拖拽放置的视图(增强右键菜单)
# ============================================================
class DragDropFloorPlanView(FloorPlanView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setAcceptDrops(True)
        self.main_window = parent

    def contextMenuEvent(self, event):
        """增强的右键菜单"""
        menu = QMenu(self)
        
        # ---- 编辑操作 ----
        edit_menu = menu.addMenu('✏️ 编辑')
        select_all_action = edit_menu.addAction('全选 (Ctrl+A)')
        select_all_action.triggered.connect(self.select_all_items)
        edit_menu.addSeparator()
        copy_action = edit_menu.addAction('复制 (Ctrl+C)')
        copy_action.triggered.connect(self.copy_selected)
        paste_action = edit_menu.addAction('粘贴 (Ctrl+V)')
        paste_action.triggered.connect(self.paste_items)
        edit_menu.addSeparator()
        delete_action = edit_menu.addAction('删除 (Del)')
        delete_action.triggered.connect(self.delete_selected_items)
        
        # ---- 视图操作 ----
        view_menu = menu.addMenu('👁️ 视图')
        zoom_in_action = view_menu.addAction('放大 (Ctrl++)')
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action = view_menu.addAction('缩小 (Ctrl+-)')
        zoom_out_action.triggered.connect(self.zoom_out)
        reset_zoom_action = view_menu.addAction('重置缩放 (Ctrl+0)')
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addSeparator()
        fit_action = view_menu.addAction('适应画布')
        fit_action.triggered.connect(self.fit_to_scene)
        
        # ---- 文件操作 ----
        file_menu = menu.addMenu('📁 文件')
        save_action = file_menu.addAction('保存 (Ctrl+S)')
        save_action.triggered.connect(self.save_file)
        save_as_action = file_menu.addAction('另存为...')
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addSeparator()
        export_action = file_menu.addAction('导出为图片...')
        export_action.triggered.connect(self.export_image)
        
        # ---- 历史记录 ----
        history_action = menu.addAction('📜 历史记录')
        history_action.triggered.connect(self.show_history)
        
        # ---- 添加模块 ----
        add_menu = menu.addMenu('➕ 添加')
        add_room_action = add_menu.addAction('房间')
        add_room_action.triggered.connect(lambda: self.add_item('客厅'))
        add_door_action = add_menu.addAction('门')
        add_door_action.triggered.connect(lambda: self.add_item('door'))
        add_window_action = add_menu.addAction('窗户')
        add_window_action.triggered.connect(lambda: self.add_item('window'))
        add_label_action = add_menu.addAction('文字标注')
        add_label_action.triggered.connect(self.add_label)
        
        # ---- 工具切换 ----
        tool_menu = menu.addMenu('🔧 工具')
        select_tool = tool_menu.addAction('选择模式')
        select_tool.triggered.connect(lambda: self.set_tool('select'))
        room_tool = tool_menu.addAction('绘制房间')
        room_tool.triggered.connect(lambda: self.set_tool('add_room'))
        door_tool = tool_menu.addAction('添加门')
        door_tool.triggered.connect(lambda: self.set_tool('add_door'))
        window_tool = tool_menu.addAction('添加窗')
        window_tool.triggered.connect(lambda: self.set_tool('add_window'))
        
        # ---- 帮助 ----
        menu.addSeparator()
        about_action = menu.addAction('ℹ️ 关于')
        about_action.triggered.connect(self.show_about)
        
        menu.exec(event.globalPos())

    def fit_to_scene(self):
        """适应画布大小"""
        scene_rect = self.scene().itemsBoundingRect()
        if not scene_rect.isEmpty():
            self.fitInView(scene_rect, Qt.KeepAspectRatio)
            self.zoom_factor = 1.0

    def add_item(self, item_type):
        if self.main_window:
            self.main_window.add_item_to_scene(item_type)

    def add_label(self):
        if self.main_window:
            self.main_window.add_label()

    def set_tool(self, mode):
        if self.main_window:
            self.main_window.set_tool_mode(mode)

    def save_file_as(self):
        if self.main_window:
            self.main_window.save_file_as()

    def export_image(self):
        if self.main_window:
            self.main_window.export_image()

    def show_about(self):
        if self.main_window:
            self.main_window.show_about()

    def select_all_items(self):
        if self.main_window:
            self.main_window.select_all()

    def delete_selected_items(self):
        if self.main_window:
            self.main_window.delete_selected()

    def copy_selected(self):
        """复制选中项"""
        scene = self.scene()
        if scene:
            selected = scene.selectedItems()
            if selected:
                items_data = []
                for item in selected:
                    if isinstance(item, (RoomItem, DoorItem, WindowItem, LabelItem)):
                        items_data.append(item.to_dict())
                if items_data:
                    clipboard = QApplication.clipboard()
                    mime_data = QMimeData()
                    mime_data.setText(json.dumps(items_data))
                    clipboard.setMimeData(mime_data)
                    if self.main_window:
                        self.main_window.statusBar().showMessage(f'已复制 {len(items_data)} 个图元', 2000)

    def paste_items(self):
        """粘贴项"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasText():
            try:
                items_data = json.loads(mime_data.text())
                scene = self.scene()
                if scene:
                    scene.clearSelection()
                    for item_data in items_data:
                        item_type = item_data.get('type')
                        if item_type == 'room':
                            room = RoomItem.from_dict(item_data)
                            room.setPos(room.pos().x() + 20, room.pos().y() + 20)
                            scene.addItem(room)
                            room.setSelected(True)
                        elif item_type == 'door':
                            door = DoorItem.from_dict(item_data)
                            door.setPos(door.pos().x() + 20, door.pos().y() + 20)
                            scene.addItem(door)
                            door.setSelected(True)
                        elif item_type == 'window':
                            window = WindowItem.from_dict(item_data)
                            window.setPos(window.pos().x() + 20, window.pos().y() + 20)
                            scene.addItem(window)
                            window.setSelected(True)
                        elif item_type == 'label':
                            label = LabelItem.from_dict(item_data)
                            label.setPos(label.pos().x() + 20, label.pos().y() + 20)
                            scene.addItem(label)
                            label.setSelected(True)
                    if self.main_window:
                        self.main_window.statusBar().showMessage(f'已粘贴 {len(items_data)} 个图元', 2000)
            except Exception as e:
                if self.main_window:
                    self.main_window.statusBar().showMessage(f'粘贴失败: {str(e)}', 2000)

    def save_file(self):
        if self.main_window:
            self.main_window.save_file()

    def show_history(self):
        if self.main_window:
            self.main_window.show_history()

    def dragEnterEvent(self, event):
        if (event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist')
                or event.mimeData().hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if (event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist')
                or event.mimeData().hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        item_type = None
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            mime_data = event.mimeData()
            byte_array = mime_data.data('application/x-qabstractitemmodeldatalist')
            stream = QDataStream(byte_array, QIODevice.ReadOnly)
            row = stream.readInt32()
            col = stream.readInt32()
            while not stream.atEnd():
                try:
                    role = stream.readInt32()
                    value = stream.readQVariant()
                    if role == Qt.UserRole and value:
                        item_type = str(value)
                        break
                except Exception:
                    break
        if not item_type and event.mimeData().hasText():
            item_type = event.mimeData().text()
        if not item_type:
            event.ignore()
            return

        scene_pos = self.mapToScene(event.position().toPoint())

        if item_type in ROOM_TYPES:
            room = RoomItem(room_type=item_type)
            room.setPos(
                snap_to_grid(scene_pos.x() - 100),
                snap_to_grid(scene_pos.y() - 75)
            )
            self.scene().addItem(room)
            self.scene().clearSelection()
            room.setSelected(True)
            if hasattr(self.scene(), 'itemSelected'):
                self.scene().itemSelected.emit(room)
            event.acceptProposedAction()

        elif item_type == 'door':
            door = DoorItem(80)
            door.setPos(snap_point_to_grid(scene_pos))
            self.scene().addItem(door)
            # 自动附着
            if hasattr(self.scene(), 'try_attach_to_room'):
                self.scene().try_attach_to_room(door)
            self.scene().clearSelection()
            door.setSelected(True)
            if hasattr(self.scene(), 'itemSelected'):
                self.scene().itemSelected.emit(door)
            event.acceptProposedAction()

        elif item_type == 'window':
            window = WindowItem(120)
            window.setPos(snap_point_to_grid(scene_pos))
            self.scene().addItem(window)
            # 自动附着
            if hasattr(self.scene(), 'try_attach_to_room'):
                self.scene().try_attach_to_room(window)
            self.scene().clearSelection()
            window.setSelected(True)
            if hasattr(self.scene(), 'itemSelected'):
                self.scene().itemSelected.emit(window)
            event.acceptProposedAction()
        else:
            event.ignore()

# ============================================================
# 历史记录对话框(增强:预览功能)
# ============================================================
class HistoryDialog(QDialog):
    """历史记录对话框 - 支持预览和加载"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("历史记录")
        self.setMinimumSize(700, 500)
        self.selected_file = None
        self.preview_scene = None
        self.setup_ui()
        self.load_history_list()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # 左侧:列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        tip_label = QLabel("📜 双击加载历史记录")
        tip_label.setStyleSheet("color: #666; padding: 5px;")
        left_layout.addWidget(tip_label)
        
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.history_list.itemClicked.connect(self.on_item_clicked)
        self.history_list.setMinimumWidth(300)
        left_layout.addWidget(self.history_list)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("📂 加载选中")
        self.load_btn.clicked.connect(self.on_load_clicked)
        btn_layout.addWidget(self.load_btn)
        
        self.delete_btn = QPushButton("🗑️ 删除选中")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        btn_layout.addWidget(self.delete_btn)
        
        btn_layout.addStretch()
        
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        left_layout.addLayout(btn_layout)
        
        # 右侧:预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_label = QLabel("预览")
        preview_label.setStyleSheet("font-weight: bold; padding: 5px;")
        right_layout.addWidget(preview_label)
        
        self.preview_view = QGraphicsView()
        self.preview_view.setRenderHint(QPainter.Antialiasing)
        self.preview_view.setStyleSheet("border: 1px solid #ccc; background: #fafafa;")
        self.preview_view.setMinimumSize(300, 300)
        self.preview_scene = QGraphicsScene()
        self.preview_view.setScene(self.preview_scene)
        right_layout.addWidget(self.preview_view)
        
        self.preview_info = QLabel("选择历史记录以预览")
        self.preview_info.setStyleSheet("color: #666; padding: 5px;")
        right_layout.addWidget(self.preview_info)
        
        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 1)

    def load_history_list(self):
        """加载历史记录列表"""
        self.history_list.clear()
        try:
            history_dir = get_history_dir()
            files = []
            for filename in os.listdir(history_dir):
                if filename.startswith("history_") and filename.endswith(".json"):
                    filepath = os.path.join(history_dir, filename)
                    mtime = os.path.getmtime(filepath)
                    # 读取文件内容统计图元数量
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            count = len(data.get('items', []))
                    except:
                        count = 0
                    files.append((filepath, mtime, count))
            files.sort(key=lambda x: x[1], reverse=True)
            
            for filepath, mtime, count in files:
                dt = datetime.fromtimestamp(mtime)
                display_text = f"{dt.strftime('%Y-%m-%d %H:%M:%S')}  ({count}个图元)"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, filepath)
                item.setToolTip(f"路径: {filepath}\n时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n图元数: {count}")
                self.history_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载历史记录列表失败: {str(e)}")

    def on_item_clicked(self, item):
        """点击历史记录项时预览"""
        filepath = item.data(Qt.UserRole)
        if filepath and os.path.exists(filepath):
            try:
                self.preview_scene.clear()
                # 加载文件并预览
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 创建临时场景预览
                temp_scene = QGraphicsScene()
                for item_data in data.get('items', []):
                    item_type = item_data.get('type')
                    if item_type == 'room':
                        room = RoomItem.from_dict(item_data)
                        temp_scene.addItem(room)
                    elif item_type == 'door':
                        door = DoorItem.from_dict(item_data)
                        temp_scene.addItem(door)
                    elif item_type == 'window':
                        window = WindowItem.from_dict(item_data)
                        temp_scene.addItem(window)
                    elif item_type == 'label':
                        label = LabelItem.from_dict(item_data)
                        temp_scene.addItem(label)
                
                # 复制到预览场景
                self.preview_scene.clear()
                for item in temp_scene.items():
                    # 简单复制:重新创建
                    if isinstance(item, RoomItem):
                        new_item = RoomItem.from_dict(item.to_dict())
                        self.preview_scene.addItem(new_item)
                    elif isinstance(item, DoorItem):
                        new_item = DoorItem.from_dict(item.to_dict())
                        self.preview_scene.addItem(new_item)
                    elif isinstance(item, WindowItem):
                        new_item = WindowItem.from_dict(item.to_dict())
                        self.preview_scene.addItem(new_item)
                    elif isinstance(item, LabelItem):
                        new_item = LabelItem.from_dict(item.to_dict())
                        self.preview_scene.addItem(new_item)
                
                # 适应预览视图
                rect = self.preview_scene.itemsBoundingRect()
                if not rect.isEmpty():
                    self.preview_view.fitInView(rect, Qt.KeepAspectRatio)
                    self.preview_info.setText(f"预览: {len(data.get('items', []))} 个图元")
                else:
                    self.preview_info.setText("预览: 空场景")
            except Exception as e:
                self.preview_info.setText(f"预览失败: {str(e)}")

    def on_item_double_clicked(self, item):
        """双击加载历史记录"""
        self.selected_file = item.data(Qt.UserRole)
        self.accept()

    def on_load_clicked(self):
        """点击加载按钮"""
        current_item = self.history_list.currentItem()
        if current_item:
            self.selected_file = current_item.data(Qt.UserRole)
            self.accept()
        else:
            QMessageBox.information(self, "提示", "请先选择要加载的历史记录")

    def on_delete_clicked(self):
        """删除选中的历史记录"""
        current_item = self.history_list.currentItem()
        if current_item:
            filepath = current_item.data(Qt.UserRole)
            reply = QMessageBox.question(self, "确认", f"确定要删除该历史记录吗?\n{os.path.basename(filepath)}")
            if reply == QMessageBox.Yes:
                try:
                    os.remove(filepath)
                    self.load_history_list()
                    self.preview_scene.clear()
                    self.preview_info.setText("已删除")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")
        else:
            QMessageBox.information(self, "提示", "请先选择要删除的历史记录")

    def get_selected_file(self):
        """获取选中的文件路径"""
        return self.selected_file

# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        # 设置实时自动保存防抖定时器(先于_apply_settings创建,避免加载触发保存)
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(500)
        self._settings_save_timer.timeout.connect(self._save_settings_now)
        self.setup_ui()
        self.setup_connections()
        self.load_autosave()  # 启动时加载自动保存的记录
        self.setWindowTitle('房屋平面图绘制工具 v2.1')
        self.resize(1400, 900)
        self._settings = load_settings()
        self._apply_settings(self._settings)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _apply_settings(self, settings):
        """应用设置:网格显示/网格吸附/自动附着/窗口几何"""
        global SNAP_TO_GRID
        SNAP_TO_GRID = settings.get('snap_to_grid', True)
        self.scene.show_grid = settings.get('show_grid', True)
        self.scene.auto_attach = settings.get('auto_attach', True)
        # 同步动作勾选状态(工具栏+菜单栏)
        self.grid_action.setChecked(self.scene.show_grid)
        self.menu_grid_action.setChecked(self.scene.show_grid)
        self.snap_action.setChecked(SNAP_TO_GRID)
        self.menu_snap_action.setChecked(SNAP_TO_GRID)
        self.auto_attach_action.setChecked(self.scene.auto_attach)
        self.menu_auto_attach_action.setChecked(self.scene.auto_attach)
        # 窗口几何恢复
        geom = settings.get('window_geometry')
        if geom:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geom.encode('utf-8')))
            except Exception:
                pass
        self._start_maximized = settings.get('window_maximized', False)

    def _autosave_settings(self):
        """实时自动保存(防抖):变更后500ms无操作才写盘"""
        self._settings_save_timer.start()

    def _save_settings_now(self):
        """立即收集并保存设置"""
        self._settings_save_timer.stop()
        settings = {
            'snap_to_grid': SNAP_TO_GRID,
            'show_grid': self.scene.show_grid,
            'auto_attach': self.scene.auto_attach,
            'window_geometry': bytes(self.saveGeometry().toBase64()).decode('utf-8'),
            'window_maximized': self.isMaximized(),
        }
        save_settings(settings)

    def setup_ui(self):
        self.scene = FloorPlanScene()
        self.view = DragDropFloorPlanView(self.scene, self)
        self.setCentralWidget(self.view)

        self.module_panel = ModulePanel()
        left_dock = QDockWidget('模块库', self)
        left_dock.setWidget(self.module_panel)
        left_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        self.property_panel = PropertyPanel()
        right_dock = QDockWidget('属性面板', self)
        right_dock.setWidget(self.property_panel)
        right_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, right_dock)

        self.create_toolbar()
        self.create_menubar()
        self.statusBar().showMessage('就绪 - 拖拽/双击/右键添加 | ESC退出绘制模式')

    def create_toolbar(self):
        toolbar = QToolBar('工具栏')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction('新建', self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_file)
        toolbar.addAction(new_action)
        open_action = QAction('打开', self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)
        save_action = QAction('保存', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)
        save_as_action = QAction('另存为', self)
        save_as_action.triggered.connect(self.save_file_as)
        toolbar.addAction(save_as_action)

        toolbar.addSeparator()

        select_action = QAction('选择', self)
        select_action.setCheckable(True)
        select_action.setChecked(True)
        select_action.triggered.connect(lambda: self.set_tool_mode('select'))
        toolbar.addAction(select_action)
        self.select_action = select_action

        room_action = QAction('绘制房间', self)
        room_action.setCheckable(True)
        room_action.triggered.connect(lambda: self.set_tool_mode('add_room'))
        toolbar.addAction(room_action)
        self.room_action = room_action

        door_action = QAction('添加门', self)
        door_action.setCheckable(True)
        door_action.triggered.connect(lambda: self.set_tool_mode('add_door'))
        toolbar.addAction(door_action)
        self.door_action = door_action

        window_action = QAction('添加窗', self)
        window_action.setCheckable(True)
        window_action.triggered.connect(lambda: self.set_tool_mode('add_window'))
        toolbar.addAction(window_action)
        self.window_action = window_action

        toolbar.addSeparator()

        zoom_in_action = QAction('放大', self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.view.zoom_in)
        toolbar.addAction(zoom_in_action)
        zoom_out_action = QAction('缩小', self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.view.zoom_out)
        toolbar.addAction(zoom_out_action)
        reset_zoom_action = QAction('重置视图', self)
        reset_zoom_action.triggered.connect(self.view.reset_zoom)
        toolbar.addAction(reset_zoom_action)

        self.grid_action = QAction('显示网格', self)
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)
        self.grid_action.triggered.connect(self.toggle_grid)
        toolbar.addAction(self.grid_action)

        global SNAP_TO_GRID
        self.snap_action = QAction('网格吸附', self)
        self.snap_action.setCheckable(True)
        self.snap_action.setChecked(SNAP_TO_GRID)
        self.snap_action.triggered.connect(self.toggle_snap)
        toolbar.addAction(self.snap_action)

        # 自动附着开关
        self.auto_attach_action = QAction('自动附着', self)
        self.auto_attach_action.setCheckable(True)
        self.auto_attach_action.setChecked(True)
        self.auto_attach_action.triggered.connect(self.toggle_auto_attach)
        toolbar.addAction(self.auto_attach_action)

        toolbar.addSeparator()

        delete_action = QAction('删除', self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(delete_action)

    def create_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件(&F)')
        new_action = QAction('新建', self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        open_action = QAction('打开...', self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        save_action = QAction('保存', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        save_as_action = QAction('另存为...', self)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        export_action = QAction('导出为图片...', self)
        export_action.triggered.connect(self.export_image)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        exit_action = QAction('退出', self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu('编辑(&E)')
        delete_action = QAction('删除选中', self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_selected)
        edit_menu.addAction(delete_action)
        edit_menu.addSeparator()
        copy_action = QAction('复制', self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_selected)
        edit_menu.addAction(copy_action)
        paste_action = QAction('粘贴', self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.paste_items)
        edit_menu.addAction(paste_action)
        edit_menu.addSeparator()
        select_all_action = QAction('全选', self)
        select_all_action.setShortcut(QKeySequence.SelectAll)
        select_all_action.triggered.connect(self.select_all)
        edit_menu.addAction(select_all_action)

        view_menu = menubar.addMenu('视图(&V)')
        zoom_in_action = QAction('放大', self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.view.zoom_in)
        view_menu.addAction(zoom_in_action)
        zoom_out_action = QAction('缩小', self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.view.zoom_out)
        view_menu.addAction(zoom_out_action)
        reset_zoom_action = QAction('重置缩放', self)
        reset_zoom_action.triggered.connect(self.view.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        view_menu.addSeparator()
        fit_action = QAction('适应画布', self)
        fit_action.triggered.connect(self.view.fit_to_scene)
        view_menu.addAction(fit_action)
        view_menu.addSeparator()
        self.menu_grid_action = QAction('显示网格', self)
        self.menu_grid_action.setCheckable(True)
        self.menu_grid_action.setChecked(True)
        self.menu_grid_action.triggered.connect(self.toggle_grid)
        view_menu.addAction(self.menu_grid_action)
        self.menu_snap_action = QAction('网格吸附', self)
        self.menu_snap_action.setCheckable(True)
        self.menu_snap_action.setChecked(True)
        self.menu_snap_action.triggered.connect(self.toggle_snap)
        view_menu.addAction(self.menu_snap_action)
        self.menu_auto_attach_action = QAction('自动附着门窗', self)
        self.menu_auto_attach_action.setCheckable(True)
        self.menu_auto_attach_action.setChecked(True)
        self.menu_auto_attach_action.triggered.connect(self.toggle_auto_attach)
        view_menu.addAction(self.menu_auto_attach_action)

        # 历史记录菜单
        history_menu = menubar.addMenu('历史(&R)')
        view_history_action = QAction('查看历史记录', self)
        view_history_action.triggered.connect(self.show_history)
        history_menu.addAction(view_history_action)
        history_menu.addSeparator()
        clear_history_action = QAction('清理历史记录', self)
        clear_history_action.triggered.connect(self.cleanup_history)
        history_menu.addAction(clear_history_action)

        help_menu = menubar.addMenu('帮助(&H)')
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_connections(self):
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.itemDeleted.connect(lambda: self.property_panel.set_item(None))
        self.module_panel.itemAddRequest.connect(self.add_item_to_scene)
        self.module_panel.add_label_btn.clicked.connect(self.add_label)
        # 附着请求
        self.property_panel.attachRequest.connect(self.on_attach_request)

    def copy_selected(self):
        self.view.copy_selected()

    def paste_items(self):
        self.view.paste_items()

    def on_attach_request(self):
        """处理属性面板的附着请求"""
        item = self.property_panel.current_item
        if not isinstance(item, (DoorItem, WindowItem)):
            return
        # 查找位置下的房间
        center = item.mapToScene(QPointF(item.width / 2, 0))
        room = self.scene.find_room_at(center)
        if room:
            item.attach_to_room(room)
            # 更新属性面板显示
            if isinstance(item, DoorItem):
                self.property_panel._update_door_attach_status(item)
            else:
                self.property_panel._update_window_attach_status(item)
            self.statusBar().showMessage('已附着到房间')
        else:
            QMessageBox.information(self, '提示', '当前位置下方没有房间,请将门/窗移动到房间上方后再尝试附着。')

    def add_item_to_scene(self, item_type):
        view_center = self.view.viewport().rect().center()
        scene_center = self.view.mapToScene(view_center)

        if item_type in ROOM_TYPES:
            room = RoomItem(room_type=item_type)
            room.setPos(
                snap_to_grid(scene_center.x() - 100),
                snap_to_grid(scene_center.y() - 75)
            )
            self.scene.addItem(room)
            self.scene.clearSelection()
            room.setSelected(True)
            self.scene.itemSelected.emit(room)
            self.statusBar().showMessage(f'已添加: {item_type}')

        elif item_type == 'door':
            door = DoorItem(80)
            door.setPos(snap_point_to_grid(scene_center))
            self.scene.addItem(door)
            self.scene.try_attach_to_room(door)
            self.scene.clearSelection()
            door.setSelected(True)
            self.scene.itemSelected.emit(door)
            self.statusBar().showMessage('已添加: 门')

        elif item_type == 'window':
            window = WindowItem(120)
            window.setPos(snap_point_to_grid(scene_center))
            self.scene.addItem(window)
            self.scene.try_attach_to_room(window)
            self.scene.clearSelection()
            window.setSelected(True)
            self.scene.itemSelected.emit(window)
            self.statusBar().showMessage('已添加: 窗户')

    def set_tool_mode(self, mode):
        self.select_action.setChecked(mode == 'select')
        self.room_action.setChecked(mode == 'add_room')
        self.door_action.setChecked(mode == 'add_door')
        self.window_action.setChecked(mode == 'add_window')

        self.scene.set_mode(mode)
        mode_names = {
            'select': '选择模式',
            'add_room': '绘制房间模式 - 拖动绘制,ESC退出',
            'add_door': '添加门模式 - 连续点击放置,ESC退出',
            'add_window': '添加窗户模式 - 连续点击放置,ESC退出',
        }
        self.statusBar().showMessage(mode_names.get(mode, ''))

    def on_selection_changed(self):
        item = self.scene.get_selected_item()
        self.property_panel.set_item(item)

    def new_file(self):
        if not self.maybe_save():
            return
        self.scene.clear()
        self.current_file = None
        self.setWindowTitle('房屋平面图绘制工具 - 未命名')
        self.statusBar().showMessage('新建文件')

    def open_file(self):
        if not self.maybe_save():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, '打开平面图', '',
            '平面图文件 (*.json);;所有文件 (*.*)'
        )
        if filename:
            try:
                self.scene.load_from_file(filename)
                self.current_file = filename
                self.setWindowTitle(f'房屋平面图绘制工具 - {os.path.basename(filename)}')
                self.statusBar().showMessage(f'已打开: {filename}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'打开文件失败: {str(e)}')

    def save_file(self):
        if self.current_file:
            try:
                self.scene.save_to_file(self.current_file)
                self.save_to_history()  # 保存时自动记录历史
                self.statusBar().showMessage(f'已保存: {self.current_file}')
                return True
            except Exception as e:
                QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')
                return False
        else:
            return self.save_file_as()

    def save_file_as(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存平面图', '未命名.json',
            '平面图文件 (*.json);;所有文件 (*.*)'
        )
        if filename:
            if not filename.endswith('.json'):
                filename += '.json'
            try:
                self.scene.save_to_file(filename)
                self.current_file = filename
                self.save_to_history()  # 保存时自动记录历史
                self.setWindowTitle(f'房屋平面图绘制工具 - {os.path.basename(filename)}')
                self.statusBar().showMessage(f'已保存: {filename}')
                return True
            except Exception as e:
                QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')
        return False

    def maybe_save(self):
        return True

    def export_image(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, '导出为图片', '平面图.png',
            'PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg)'
        )
        if filename:
            items_rect = self.scene.itemsBoundingRect()
            if items_rect.isEmpty():
                QMessageBox.warning(self, '提示', '画布为空,无法导出')
                return
            margin = 40
            rect = items_rect.adjusted(-margin, -margin, margin, margin)
            image = QPixmap(int(rect.width()), int(rect.height())).toImage()
            image.fill(Qt.white)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            self.scene.render(painter, QRectF(image.rect()), rect)
            painter.end()
            image.save(filename)
            self.statusBar().showMessage(f'已导出: {filename}')
            QMessageBox.information(self, '成功', f'图片已导出到:\n{filename}')

    def delete_selected(self):
        for item in self.scene.selectedItems():
            if isinstance(item, (RoomItem, DoorItem, WindowItem, LabelItem)):
                self.scene.removeItem(item)
        self.property_panel.set_item(None)

    def select_all(self):
        for item in self.scene.items():
            if isinstance(item, (RoomItem, DoorItem, WindowItem, LabelItem)):
                item.setSelected(True)

    def toggle_grid(self, show):
        self.scene.show_grid = show
        self.scene.update()
        self._autosave_settings()  # 实时自动保存

    def toggle_snap(self, enabled):
        global SNAP_TO_GRID
        SNAP_TO_GRID = enabled
        self.statusBar().showMessage('已开启网格吸附' if enabled else '已关闭网格吸附')
        self._autosave_settings()  # 实时自动保存

    def toggle_auto_attach(self, enabled):
        """切换自动附着功能"""
        self.scene.auto_attach = enabled
        self.statusBar().showMessage('已开启自动附着' if enabled else '已关闭自动附着')
        self._autosave_settings()  # 实时自动保存

    def add_label(self):
        label = LabelItem('标注文字')
        label.setPos(snap_point_to_grid(
            self.view.mapToScene(self.view.viewport().rect().center())
        ))
        self.scene.addItem(label)
        self.scene.clearSelection()
        label.setSelected(True)
        self.property_panel.set_item(label)

    def show_about(self):
        QMessageBox.about(
            self, '关于 房屋平面图绘制工具',
            '''<h3>房屋平面图绘制工具 v2.1</h3>
            <p>基于 PySide6 开发</p>
            <p><b>本次更新功能:</b></p>
            <ul>
                <li><b>设置持久化</b>:网格显示/网格吸附/自动附着/窗口几何实时自动保存,下次启动自动恢复</li>
                <li><b>增强右键菜单</b>:编辑/视图/文件/历史/添加/工具分类清晰</li>
                <li><b>历史记录增强</b>:支持预览、显示图元数量</li>
                <li><b>复制粘贴</b>:支持图元复制粘贴(Ctrl+C/Ctrl+V)</li>
                <li><b>自动保存</b>:关闭时自动保存,下次启动恢复</li>
            </ul>
            <p><b>操作提示:</b></p>
            <ul>
                <li>右键菜单包含所有常用操作</li>
                <li>Ctrl+S 保存, Ctrl+O 打开, Ctrl+N 新建</li>
                <li>Ctrl+C 复制, Ctrl+V 粘贴, Ctrl+A 全选</li>
                <li>保存时自动记录历史(history目录)</li>
                <li>历史记录对话框支持预览</li>
            </ul>
            '''
        )

    def save_to_history(self):
        """保存当前场景到历史记录"""
        try:
            history_dir = get_history_dir()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            history_file = os.path.join(history_dir, f'history_{timestamp}.json')
            self.scene.save_to_file(history_file)
            self.cleanup_history()  # 清理多余的历史记录
        except Exception as e:
            pass  # 静默失败,不影响主功能

    def cleanup_history(self):
        """清理历史记录,最多保留20条"""
        try:
            history_dir = get_history_dir()
            files = []
            for filename in os.listdir(history_dir):
                if filename.startswith('history_') and filename.endswith('.json'):
                    filepath = os.path.join(history_dir, filename)
                    files.append((filepath, os.path.getmtime(filepath)))
            files.sort(key=lambda x: x[1], reverse=True)
            # 保留最新的20条
            for filepath, _ in files[20:]:
                os.remove(filepath)
        except Exception:
            pass

    def show_history(self):
        """显示历史记录对话框"""
        dialog = HistoryDialog(self)
        if dialog.exec() == QDialog.Accepted:
            selected_file = dialog.get_selected_file()
            if selected_file:
                try:
                    self.scene.load_from_file(selected_file)
                    self.current_file = None  # 加载历史记录不作为当前文件
                    self.setWindowTitle('房屋平面图绘制工具 - 历史记录加载')
                    self.statusBar().showMessage(f'已加载历史记录: {os.path.basename(selected_file)}', 3000)
                except Exception as e:
                    QMessageBox.critical(self, '错误', f'无法加载历史记录: {str(e)}')

    def save_autosave(self):
        """保存自动恢复文件"""
        try:
            autosave_path = get_autosave_path()
            self.scene.save_to_file(autosave_path)
        except Exception:
            pass

    def load_autosave(self):
        """加载自动恢复文件"""
        try:
            autosave_path = get_autosave_path()
            if os.path.exists(autosave_path):
                self.scene.load_from_file(autosave_path)
                self.statusBar().showMessage('已恢复上次编辑状态', 3000)
        except Exception:
            pass

    def closeEvent(self, event):
        """关闭事件:自动保存场景 + 强制保存设置"""
        self.save_autosave()
        self._save_settings_now()  # 强制保存设置
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()

# ============================================================
# 主函数
# ============================================================
def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName('房屋平面图绘制工具')
    app.setOrganizationName('FloorPlanEditor')
    app.setStyle('Fusion')
    font = QFont('微软雅黑', 9)
    app.setFont(font)
    window = MainWindow()
    if getattr(window, '_start_maximized', False):
        window.showMaximized()
    else:
        window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()