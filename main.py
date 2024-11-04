import os
import sys
from PyQt5.QtWidgets import QApplication, QAction, QVBoxLayout, QHBoxLayout, QWidget, QDockWidget, QLabel, QTabWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon
from .name import NameTab  # Importa la clase Name para búsqueda por nombre geográfico
from .reverse import ReverseTab  # Importa la clase ReverseTab para búsqueda por coordenadas

class Geocoder:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.initGui()

    def initGui(self):
        # Evitar agregar la acción varias veces
        if self.action is None:
            # Crear una acción en el menú y en la barra de herramientas si no existe
            self.action = QAction(QIcon(f'{os.path.dirname(__file__)}/images/Logo_small.svg'), 'Gecoder Cartociudad', self.iface.mainWindow())
            self.action.triggered.connect(self.run)
            
            # Añadir la acción al menú de plugins
            self.iface.addPluginToMenu('&Gecoder Cartociudad', self.action)

            # Añadir la acción a la barra de herramientas con el logo como icono
            self.iface.addToolBarIcon(self.action)

    def unload(self):
        # Eliminar la acción del menú y la barra de herramientas cuando se desactiva el complemento
        if self.action is not None:
            self.iface.removePluginMenu('&Gecoder Cartociudad', self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None  # Asegurarse de que se pueda agregar nuevamente si es necesario

    def run(self):
        # Crear y mostrar la ventana flotante
        self.dock = MyDockWidget(self.iface)
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        self.dock.show()

class MyDockWidget(QDockWidget):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.plugin_dir = os.path.dirname(__file__)

        # Crear el widget principal
        main_widget = QWidget()
        self.setWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Logo en la parte superior
        logo_layout = QHBoxLayout()
        logo_layout.addStretch()
        label = QLabel()
        pixmap = QPixmap(f'{self.plugin_dir}/images/Logo.png')
        label.setPixmap(pixmap)
        label.setScaledContents(True)
        logo_layout.addWidget(label)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)

        # Crear las pestañas
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Añadir las pestañas
        self.add_tabs()

    def add_tabs(self):
        """Añadir las pestañas al QTabWidget"""
        # Pestaña para la localización por nombre geográfico
        name_tab = self.create_name_tab()
        self.tabs.addTab(name_tab, "Localización por nombre geográfico")

        # Pestaña para la localización por coordenadas
        reverse_tab = self.create_reverse_tab()
        self.tabs.addTab(reverse_tab, "Localización por coordenadas")

    def create_name_tab(self):
        """Crear la pestaña para la búsqueda por nombre geográfico"""
        name_tab = QWidget()
        name_layout = QVBoxLayout(name_tab)

        # Añadir el widget Name que gestiona la búsqueda por nombre
        name_layout.addWidget(NameTab(parent=self, iface=self.iface))

        return name_tab

    def create_reverse_tab(self):
        """Crear la pestaña para la búsqueda por coordenadas (Reverse geocoding)"""
        reverse_tab = QWidget()
        reverse_layout = QVBoxLayout(reverse_tab)
        # Añadir el widget Name que gestiona la búsqueda por nombre
        reverse_layout.addWidget(ReverseTab(parent=self, iface=self.iface))
        
        return reverse_tab

    

    

# Ejecución del programa principal en caso de que no esté siendo importado como módulo
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyDockWidget(iface=None)  # Suponiendo que 'iface' se pasa desde QGIS o una interfaz similar
    window.show()
    sys.exit(app.exec_())
