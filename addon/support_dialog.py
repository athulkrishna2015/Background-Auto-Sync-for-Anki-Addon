import os
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QPixmap,
    Qt,
    QApplication,
)

from .constants import get_auto_sync_icon

class SupportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Support / Donate')
        self.setWindowIcon(get_auto_sync_icon())
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)

        # Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Introduction
        intro_label = QLabel("If you find this add-on useful, consider supporting its development!")
        intro_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro_label.setWordWrap(True)
        main_layout.addWidget(intro_label)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)

        # Scroll widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)

        # Support details
        support_items = [
            {
                "title": "UPI",
                "id": "athulkrishnasv2015-2@okhdfcbank",
                "img": "UPI.jpg"
            },
            {
                "title": "Bitcoin (BTC)",
                "id": "bc1qrrek3m7sr33qujjrktj949wav6mehdsk057cfx",
                "img": "BTC.jpg"
            },
            {
                "title": "Ethereum (ETH)",
                "id": "0xce6899e4903EcB08bE5Be65E44549fadC3F45D27",
                "img": "ETH.jpg"
            }
        ]

        addon_path = os.path.dirname(__file__)

        for item in support_items:
            # Group box or frame equivalent setup
            item_widget = QWidget()
            item_layout = QVBoxLayout()
            item_widget.setLayout(item_layout)

            # Title
            title_label = QLabel(f"<b>{item['title']}</b>")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(title_label)

            # QR Code
            qr_label = QLabel()
            qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_path = os.path.join(addon_path, "Support", item["img"])
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                # Ensure the QR code is decently sized but fits
                pixmap = pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                qr_label.setPixmap(pixmap)
            else:
                qr_label.setText("(Image not found)")
            item_layout.addWidget(qr_label)

            # ID and Copy Button layout
            id_layout = QHBoxLayout()
            id_label = QLabel(item["id"])
            id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            
            copy_button = QPushButton("Copy")
            copy_button.setMaximumWidth(80)
            copy_button.clicked.connect(lambda checked, text=item["id"]: self.copy_to_clipboard(text))

            id_layout.addWidget(id_label)
            id_layout.addWidget(copy_button)
            item_layout.addLayout(id_layout)

            # Add some spacing between items
            item_layout.setContentsMargins(0, 10, 0, 20)
            scroll_layout.addWidget(item_widget)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_button)
        main_layout.addLayout(btn_layout)

    def copy_to_clipboard(self, text):
        cb = QApplication.clipboard()
        cb.setText(text)
