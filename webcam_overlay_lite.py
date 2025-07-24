import sys
import cv2
import math
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QGraphicsDropShadowEffect,
                             QMenu, QSlider, QLabel, QWidgetAction, QHBoxLayout)
from PyQt6.QtGui import (QImage, QPainter, QPainterPath, QColor, QCursor, QAction)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QRectF, QPointF)

# --- GLOBAL ADJUSTABLE PARAMETERS ---
INITIAL_SIZE = 250
MIN_SIZE = 100
MAX_SIZE = 800
RESIZE_BORDER_WIDTH = 15
SHADOW_WIDTH = 15

# --- MENU STYLE (QSS) ---
# Here we define the appearance of our custom menu.
MENU_STYLESHEET = """
    QMenu {
        background-color: #2c3e50; /* Dark background color */
        color: #ecf0f1; /* Light text color */
        border: 1px solid #34495e;
        border-radius: 8px; /* Rounded borders */
        padding: 5px;
    }
    QMenu::item {
        padding: 8px 25px 8px 20px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #3498db; /* Highlight color on hover */
    }
    QMenu::item:checkable {
        color: #ecf0f1;
    }
    QMenu::indicator:checked {
        /* Checkmark icon */
        image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAjklEQVQ4T2NkoBAwUqifYdQeOPv/v3+B2P8z/P//P8NviL//D8S/oPz/3z/D34D8/z8gfj4h/P8/In4O4v/3D2L+D2I/QPy/P0T8HMf/BwYGBkYMgA0YcADiZzB+B+L/RxD/IeL/gPg/EP8j4v8g/k8g/s/E/4/Y/sccAADGgwY+Yy3wAAAAAElFTkSuQmCC);
        padding-left: 5px;
    }
    QLabel {
        color: #ecf0f1; /* Text color for the "Zoom" label */
        padding-left: 10px;
    }
    QSlider::groove:horizontal {
        border: 1px solid #34495e;
        background: #34495e;
        height: 8px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #3498db;
        border: 1px solid #3498db;
        width: 16px;
        margin: -4px 0; 
        border-radius: 8px;
    }
    QSlider::add-page:horizontal {
        background: #7f8c8d;
    }
    QSlider::sub-page:horizontal {
        background: #3498db;
    }
"""


class WebcamWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.frame = None

    def set_frame(self, frame):
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        if self.frame is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addEllipse(QRectF(self.rect()))
            painter.setClipPath(path)
            h, w, ch = self.frame.shape
            # The format is already RGB, so we use Format_RGB888
            q_image = QImage(self.frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
            painter.drawImage(self.rect(), q_image)


class WebcamCircularApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self.is_resizing = False
        self.is_dragging = False
        self.start_geometry = self.geometry()
        self.start_mouse_pos = QPoint()

        # --- NEW STATE VARIABLES ---
        self.zoom_level = 1.0  # 1.0 = no zoom, 2.0 = 200% zoom
        self.flip_horizontal = True # Starts mirrored by default

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

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # 1. Crop to the largest possible square in the center of the webcam image
            h, w, _ = frame.shape
            side = min(h, w)
            y_start, x_start = (h - side) // 2, (w - side) // 2
            square_frame = frame[y_start:y_start+side, x_start:x_start+side]

            # --- 2. APPLY ZOOM ---
            # Calculate crop dimensions based on the zoom level
            h_q, w_q, _ = square_frame.shape
            crop_dim = int(h_q / self.zoom_level)
            
            # Ensure the crop is centered
            start_coord = (h_q - crop_dim) // 2
            end_coord = start_coord + crop_dim
            
            zoomed_frame = square_frame[start_coord:end_coord, start_coord:end_coord]
            
            # Resize the zoomed image back to the original size to fill the widget
            # Using INTER_LANCZOS4 offers better quality for resizing
            final_frame = cv2.resize(zoomed_frame, (w_q, h_q), interpolation=cv2.INTER_LANCZOS4)

            # 3. Convert color and apply mirroring (if enabled)
            rgb_image = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)
            
            if self.flip_horizontal:
                rgb_image = cv2.flip(rgb_image, 1) # 1 for horizontal flip
            
            self.webcam_widget.set_frame(rgb_image)

    # --- NEW: OPTION CONTROL FUNCTIONS ---
    def toggle_flip_horizontal(self):
        """Inverts the state of horizontal flipping."""
        self.flip_horizontal = not self.flip_horizontal

    def set_zoom(self, value):
        """Sets the zoom level from the slider value (100-400)."""
        self.zoom_level = value / 100.0

    # --- NEW: CONTEXT MENU EVENT ---
    def contextMenuEvent(self, event):
        """Creates and displays the options menu on right-click."""
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLESHEET) # Apply our custom style

        # --- Flip (Mirror) Action ---
        # CHANGED: "Rebater Imagem" to "Flip Image"
        flip_action = QAction("Flip Image", self, checkable=True)
        flip_action.setChecked(self.flip_horizontal)
        flip_action.triggered.connect(self.toggle_flip_horizontal)
        menu.addAction(flip_action)

        menu.addSeparator()

        # --- Zoom Widget (Slider) ---
        # To add a custom widget (like a slider) to a menu,
        # we need to use a QWidgetAction.
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(zoom_widget)
        zoom_layout.setContentsMargins(10, 5, 10, 5)

        # CHANGED: "Zoom:" to "Zoom:" (no change, but for consistency)
        zoom_label = QLabel("Zoom:")
        
        zoom_slider = QSlider(Qt.Orientation.Horizontal)
        zoom_slider.setMinimum(100)  # 100%
        zoom_slider.setMaximum(400)  # 400%
        zoom_slider.setValue(int(self.zoom_level * 100))
        zoom_slider.setFixedWidth(150) # Fixed size for the slider
        zoom_slider.valueChanged.connect(self.set_zoom)

        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(zoom_slider)
        
        zoom_action = QWidgetAction(menu)
        zoom_action.setDefaultWidget(zoom_widget)
        menu.addAction(zoom_action)
        
        # --- NEW: QUIT ACTION ---
        # Add a separator line before the quit action for better organization.
        menu.addSeparator()
        
        # Create a "Quit" action.
        quit_action = QAction("Quit", self)
        # Connect the action's trigger to the window's close() method.
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        # Display the menu at the cursor's position
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
        # Pass the event to the default handler if it's not the left button
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
    # CHANGED: "janela" to "window" for better readability in English
    window = WebcamCircularApp()
    window.show()
    sys.exit(app.exec())