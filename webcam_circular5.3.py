import sys
import cv2
import math
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QGraphicsDropShadowEffect)
from PyQt6.QtGui import QImage, QPainter, QPainterPath, QColor, QCursor
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, QPointF

# --- PARÂMETROS GLOBAIS AJUSTÁVEIS ---
TAMANHO_INICIAL = 250
TAMANHO_MINIMO = 100
TAMANHO_MAXIMO = 800
LARGURA_BORDA_REDIM = 15
LARGURA_SOMBRA = 15

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

        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar_frame)
        self.timer.start(30)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(LARGURA_SOMBRA, LARGURA_SOMBRA, LARGURA_SOMBRA, LARGURA_SOMBRA)
        
        self.webcam_widget = WebcamWidget()
        shadow = QGraphicsDropShadowEffect(blurRadius=LARGURA_SOMBRA, color=QColor(0, 0, 0, 160), xOffset=0, yOffset=0)
        self.webcam_widget.setGraphicsEffect(shadow)
        
        layout.addWidget(self.webcam_widget)
        self.resize(TAMANHO_INICIAL + LARGURA_SOMBRA * 2, TAMANHO_INICIAL + LARGURA_SOMBRA * 2)

    def atualizar_frame(self):
        ret, frame = self.cap.read()
        if ret:
            h, w, _ = frame.shape
            lado = min(h, w)
            y_inicio, x_inicio = (h - lado) // 2, (w - lado) // 2
            frame_quadrado = frame[y_inicio:y_inicio+lado, x_inicio:x_inicio+lado]
            rgb_image = cv2.cvtColor(frame_quadrado, cv2.COLOR_BGR2RGB)
            rgb_image = cv2.flip(rgb_image, 1)
            self.webcam_widget.set_frame(rgb_image)

    def is_on_resize_border(self, pos: QPointF) -> bool:
        """Verifica se a posição do mouse está na borda de redimensionamento do círculo."""
        # Centro do widget da webcam, relativo à janela principal
        center = QPointF(self.webcam_widget.geometry().center())
        radius = self.webcam_widget.width() / 2
        
        distance_from_center = math.sqrt((pos.x() - center.x())**2 + (pos.y() - center.y())**2)
        
        return abs(distance_from_center - radius) < LARGURA_BORDA_REDIM

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # USA A DETECÇÃO DE PERÍMETRO CIRCULAR
            if self.is_on_resize_border(event.position()):
                self.is_resizing = True
                self.start_geometry = self.geometry()
                self.start_mouse_pos = event.globalPosition().toPoint()
            else:
                self.is_dragging = True
                self.start_mouse_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            delta = event.globalPosition().toPoint() - self.start_mouse_pos
            # A nova dimensão é a inicial + a maior variação do mouse (para manter proporção)
            diff = max(delta.x(), delta.y()) if (delta.x() > 0 and delta.y() > 0) else min(delta.x(), delta.y())
            new_size = self.start_geometry.width() + diff
            
            min_dim = TAMANHO_MINIMO + LARGURA_SOMBRA * 2
            max_dim = TAMANHO_MAXIMO + LARGURA_SOMBRA * 2
            new_size = max(min_dim, min(new_size, max_dim))
            
            self.resize(new_size, new_size)
            
        elif self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.start_mouse_pos)
        else:
            # USA A DETECÇÃO DE PERÍMETRO CIRCULAR PARA MUDAR O CURSOR
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
    janela = WebcamCircularApp()
    janela.show()
    sys.exit(app.exec())