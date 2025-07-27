import sys
import cv2
import math
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QGraphicsDropShadowEffect,
                             QMenu, QSlider, QLabel, QWidgetAction, QHBoxLayout)
from PyQt6.QtGui import (QImage, QPainter, QPainterPath, QColor, QCursor, QAction, QPen,
                         QActionGroup)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QRectF, QPointF)

# --- GLOBAL ADJUSTABLE PARAMETERS ---
INITIAL_SIZE = 250
MIN_SIZE = 100
MAX_SIZE = 800
RESIZE_BORDER_WIDTH = 15
SHADOW_WIDTH = 15

# --- MENU STYLE (QSS) ---
MENU_STYLESHEET = """
    QMenu {
        background-color: #2c3e50; color: #ecf0f1; border: 1px solid #34495e;
        border-radius: 8px; padding: 5px;
    }
    QMenu::item { padding: 8px 25px 8px 20px; border-radius: 4px; }
    QMenu::item:selected { background-color: #3498db; }
    QMenu::item:checkable { color: #ecf0f1; }
    QMenu::right-arrow {
        image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAARElEQVQoU2NkYGD4z0AAMIIgHgaigKEmwGYw4AFEC2AMJg4gzwCoY8A6oB4I8iAqA+B6oDYgLsMMsDRQFYgywQAAoF4Z4JzhM1YAAAAASUVORK5CYII=);
        padding-right: 5px;
    }
    QMenu::indicator:checked {
        image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAjklEQVQ4T2NkoBAwUqifYdQeOPv/v3+B2P8z/P//P8NviL//D8S/oPz/3z/D34D8/z8gfj4h/P8/In4O4v/3D2L+D2I/QPy/P0T8HMf/BwYGBkYMgA0YcADiZzB+B+L/RxD/IeL/gPg/EP8j4v8g/k8g/s/E/4/Y/sccAADGgwY+Yy3wAAAAAElFTkSuQmCC);
        padding-left: 5px;
    }
    QLabel { color: #ecf0f1; padding: 0 10px; }
    QSlider::groove:horizontal { border: 1px solid #34495e; background: #34495e; height: 8px; border-radius: 4px; }
    QSlider::handle:horizontal { background: #3498db; border: 1px solid #3498db; width: 16px; margin: -4px 0; border-radius: 8px; }
    QSlider::sub-page:horizontal { background: #3498db; }
"""

class WebcamWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.frame = None
        self.mask_shape = "Circle"
        self.corner_radius = 15.0

    def set_frame(self, frame):
        self.frame = frame
        self.update()

    # --- NEW: Sets shape properties from the main app ---
    def set_shape_properties(self, shape, radius):
        self.mask_shape = shape
        self.corner_radius = radius
        self.update()

    # --- NEW: Creates the clipping mask based on the selected shape ---
    def _create_path(self) -> QPainterPath:
        path = QPainterPath()
        rectF = QRectF(self.rect())
        radius = self.corner_radius

        if self.mask_shape == "Circle":
            path.addEllipse(rectF)
        elif self.mask_shape == "Rounded Portrait Rectangle":
            # Create a rectangle with 70% of the widget's width, centered
            w, h = rectF.width(), rectF.height()
            new_w = w * 0.7
            new_x = rectF.left() + (w - new_w) / 2
            portrait_rect = QRectF(new_x, rectF.top(), new_w, h)
            path.addRoundedRect(portrait_rect, radius, radius)
        else: # Default to circle if something goes wrong
            path.addEllipse(rectF)
        return path

    def paintEvent(self, event):
        if self.frame is None: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Use the new method to create the path for clipping
        path = self._create_path()
        painter.setClipPath(path)

        h, w, ch = self.frame.shape
        q_image = QImage(self.frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        painter.drawImage(self.rect(), q_image)


class WebcamOverlayAppLite(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self.is_resizing = False
        self.is_dragging = False
        self.start_geometry = self.geometry()
        self.start_mouse_pos = QPoint()

        # --- STATE VARIABLES ---
        self.zoom_level = 1.0
        self.flip_horizontal = True
        self.mask_shape = "Circle" # Current shape
        self.corner_radius = 15.0 # Current corner radius

        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SHADOW_WIDTH, SHADOW_WIDTH, SHADOW_WIDTH, SHADOW_WIDTH)
        
        self.webcam_widget = WebcamWidget()
        shadow = QGraphicsDropShadowEffect(blurRadius=SHADOW_WIDTH, color=QColor(0, 0, 0, 160), xOffset=0, yOffset=0)
        self.webcam_widget.setGraphicsEffect(shadow)
        
        layout.addWidget(self.webcam_widget)
        self.resize(INITIAL_SIZE + SHADOW_WIDTH * 2, INITIAL_SIZE + SHADOW_WIDTH * 2)

    def _update_webcam_widget_properties(self):
        """Helper function to pass all properties to the drawing widget."""
        self.webcam_widget.set_shape_properties(
            self.mask_shape, self.corner_radius)

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            h, w, _ = frame.shape
            side = min(h, w)
            y_start, x_start = (h - side) // 2, (w - side) // 2
            square_frame = frame[y_start:y_start+side, x_start:x_start+side]

            h_q, w_q, _ = square_frame.shape
            crop_dim = int(h_q / self.zoom_level)
            start_coord = (h_q - crop_dim) // 2
            end_coord = start_coord + crop_dim
            zoomed_frame = square_frame[start_coord:end_coord, start_coord:end_coord]
            final_frame = cv2.resize(zoomed_frame, (w_q, h_q), interpolation=cv2.INTER_LANCZOS4)

            rgb_image = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)
            if self.flip_horizontal:
                rgb_image = cv2.flip(rgb_image, 1)
            
            self.webcam_widget.set_frame(rgb_image)

    # --- OPTION CONTROL FUNCTIONS ---
    def toggle_flip_horizontal(self):
        self.flip_horizontal = not self.flip_horizontal

    def set_zoom(self, value):
        self.zoom_level = value / 100.0

    # --- NEW: Functions to control shape and radius ---
    def set_mask_shape(self, action):
        shape_name = action.data()
        if shape_name:
            self.mask_shape = shape_name
            self._update_webcam_widget_properties()
    
    def set_corner_radius(self, value):
        self.corner_radius = float(value)
        self._update_webcam_widget_properties()

    # --- HELPER: Function to add a slider to a menu (from pro version) ---
    def add_slider_to_menu(self, menu, label_text, min_val, max_val, current_val, callback_func):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        label = QLabel(label_text)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(current_val)
        slider.setFixedWidth(120)
        slider.valueChanged.connect(callback_func)
        layout.addWidget(label)
        layout.addWidget(slider)
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)

    # --- UPDATED: CONTEXT MENU EVENT ---
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLESHEET)

        # --- Image Options ---
        flip_action = QAction("Flip Image", self, checkable=True)
        flip_action.setChecked(self.flip_horizontal)
        flip_action.triggered.connect(self.toggle_flip_horizontal)
        menu.addAction(flip_action)
        self.add_slider_to_menu(menu, "Zoom", 100, 400, int(self.zoom_level * 100), self.set_zoom)
        menu.addSeparator()

        # --- NEW: Mask Shape Options (Submenu) ---
        mask_menu = menu.addMenu("Mask Shape")
        shape_group = QActionGroup(mask_menu)
        shape_group.setExclusive(True)
        shape_group.triggered.connect(self.set_mask_shape)
        
        shapes = ["Circle", "Rounded Portrait Rectangle"]
        for shape in shapes:
            action = QAction(shape, mask_menu, checkable=True)
            action.setData(shape)
            if self.mask_shape == shape:
                action.setChecked(True)
            shape_group.addAction(action)
            mask_menu.addAction(action)

        # Add the corner radius slider inside the shape menu
        self.add_slider_to_menu(mask_menu, "Corner Radius", 0, 100, int(self.corner_radius), self.set_corner_radius)
        menu.addSeparator()

        # --- Quit Option ---
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        menu.exec(event.globalPos())

    def is_on_resize_border(self, pos: QPointF) -> bool:
        center = QPointF(self.webcam_widget.geometry().center())
        radius = self.webcam_widget.width() / 2
        distance_from_center = math.sqrt((pos.x() - center.x())**2 + (pos.y() - center.y())**2)
        return abs(distance_from_center - radius) < RESIZE_BORDER_WIDTH

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_on_resize_border(event.position()):
                self.is_resizing = True
                self.start_geometry = self.geometry()
                self.start_mouse_pos = event.globalPosition().toPoint()
            else:
                self.is_dragging = True
                self.start_mouse_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            delta = event.globalPosition().toPoint() - self.start_mouse_pos
            diff = max(delta.x(), delta.y()) if (delta.x() > 0 and delta.y() > 0) else min(delta.x(), delta.y())
            new_size = self.start_geometry.width() + diff
            
            min_dim = MIN_SIZE + SHADOW_WIDTH * 2
            max_dim = MAX_SIZE + SHADOW_WIDTH * 2
            new_size = max(min_dim, min(new_size, max_dim))
            
            self.resize(new_size, new_size)
        elif self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.start_mouse_pos)
        else:
            if self.is_on_resize_border(event.position()):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.is_resizing = False
        self.is_dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def closeEvent(self, event):
        self.cap.release()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Use the new class name
    window = WebcamOverlayAppLite()
    window.show()
    sys.exit(app.exec())
