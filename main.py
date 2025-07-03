import os
import sys
from PyQt5.QtWidgets import (QApplication, QAction, QVBoxLayout, QHBoxLayout, QWidget, QDockWidget, QLabel, 
                                QTabWidget, QSplitter, QToolButton, QTextEdit, QScrollArea)
from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QPixmap, QIcon, QPainter

from .name import NameTab  # Importa la clase Name para búsqueda por nombre geográfico
from .reverse import ReverseTab  # Importa la clase ReverseTab para búsqueda por coordenadas

def create_triangle_icon(direction="right", size=16):
    # SVG path for a triangle pointing right or left
    if direction == "right":
        points = "2,2 14,8 2,14"
    else:  # left
        points = "14,2 2,8 14,14"
    svg = f"""
    <svg width="{size}" height="{size}" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
      <polygon points="{points}" fill="black"/>
    </svg>
    """
    svg_bytes = QByteArray(svg.encode('utf-8'))
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

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
        label.setMaximumHeight(80)  # O el alto que prefieras
        logo_layout.addWidget(label)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)

        # Crear las pestañas
        self.tabs = QTabWidget()
        self.add_tabs()

         # --- Splitter principal ---
        self.splitter = QSplitter(Qt.Horizontal)
        # Widget 1: Localización por nombre geográfico
        self.splitter.addWidget(self.tabs)

        # Widget 2: Ayuda
        self.help_widget = QTextEdit("Aquí va la información de ayuda de tu plugin.")
        self.help_widget.setReadOnly(True)
        self.splitter.addWidget(self.help_widget)

        self.splitter.setSizes([400, 200])  # Ajusta el tamaño inicial de los paneles
        self.splitter.setCollapsible(0, False)  # Solo el panel de ayuda es colapsable

        # Conectar el cambio de pestaña a la función de ayuda
        self.tabs.currentChanged.connect(self.update_help_text)
        self.update_help_text(self.tabs.currentIndex())  # Para mostrar la ayuda inicial
        self.tabs.setUsesScrollButtons(False)
    
        # Botón de colapso en el handle del splitter
        layout.addWidget(self.splitter)
        self.splitter_handle = self.splitter.handle(1)
        self.splitter.splitterMoved.connect(self.splitterChanged)
        self.mHelpCollapsed = False
        self.mSplitterState = QByteArray()
        handle_layout = QVBoxLayout()
        handle_layout.setContentsMargins(0, 0, 0, 0)
        # create the collapse button
        self.button_collapse = QToolButton(self.splitter_handle)
        self.button_collapse.setFixedSize(24, 24)  # Tamaño estándar
        self.button_collapse.setCursor(Qt.ArrowCursor)
        self.button_collapse.setArrowType(Qt.RightArrow)  # Flecha estándar Qt
        self.button_collapse.setToolTip("Mostrar/ocultar ayuda")
        self.button_collapse.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            QToolButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        self.button_collapse.setText("")

        handle_layout.addStretch()
        handle_layout.addWidget(self.button_collapse)
        handle_layout.addStretch()
        self.splitter_handle.setLayout(handle_layout)
        self.splitter_handle.setMinimumHeight(40) 
        self.button_collapse.clicked.connect(self.toggleCollapsed) # Fuerza altura mínima del handle


    def splitterChanged(self, pos, index):
        if self.splitter.sizes()[1] == 0:
            self.mHelpCollapsed = True
            self.button_collapse.setArrowType(Qt.LeftArrow)
        else:
            self.mHelpCollapsed = False
            self.button_collapse.setArrowType(Qt.RightArrow)

 

    def toggleCollapsed(self):
        if self.mHelpCollapsed:
            if not self.mSplitterState.isEmpty():
                self.splitter.restoreState(self.mSplitterState)
            else:
                self.splitter.setSizes([400, 200])
            self.button_collapse.setArrowType(Qt.RightArrow)
        else:
            self.mSplitterState = self.splitter.saveState()
            self.splitter.setSizes([1, 0])
            self.button_collapse.setArrowType(Qt.LeftArrow)
        self.mHelpCollapsed = not self.mHelpCollapsed
    
    
    def update_help_text(self, index):
        if index == 0:
            self.help_widget.hide()  # Oculta el panel de ayuda
        else:
            self.help_widget.show()  # Muestra el panel de ayuda
            if index == 1:
                self.help_widget.setText("<h2>Localización por nombre geográfico</h2>"
                                        "<p>Permite realizar búsquedas de los diferentes elementos geográficos contenidos de CartoCiudad.</p><br>"
                                        "Para ello se añade en <i>Localización</i> el elemento a buscar. A continuación, se le puede dar al botón de <i>Buscar</i> o a la tecla <i>Enter</i>.</br>"
                                        "<h3>Búsqueda de un elemento filtrando por código postal</h3>"
                                        "<p>Permite realizar una búsqueda de cualquier elemento geográfico contenido en un <i>código postal</i>.</p><br> "
                                        "Para ello hay que introducir el elemento a buscar y además hay que añadir en Filtrar por código postal el número del código postal deseado. Así mismo, se puede filtrar por varios códigos postales, y para ello, hay que introducirlos seguidos de comas y sin espacios. De nuevo, se le puede dar al botón de <i>Buscar</i> o a la tecla <i>Enter</i>.</br>"
                                    )
            elif index == 2:
                self.help_widget.setText("<h2>Localización por coordenadas geográficas</h2>"
                                        "<p>Se puede obtener la dirección postal de cualquier punto del territorio español a partir de sus coordenadas.</p><br>"
                                        "Para ello hay dos métodos:</br>"
                                        "<ul>"
                                        "<li><b>Capturar coordenadas en el mapa:</b> Una vez seleccionado el botón de <i>Capturar coordenadas del mapa</i>, hay que seleccionar cualquier punto en el proyecto de trabajo, y si el servicio REST Geocoder geolocaliza una dirección, devuelve el resultado.</li>"
                                        "<br>"
                                        "<li><b>Buscar por coordenadas</b> También se puede buscar una dirección si se tienen sus coordenadas geográficas (latitud y longitud en WGS84)."
                                        "<ol>"
                                        "<li>Rellenar los dos campos:"
                                        "<ul>"
                                        "<li><i>Introduzca la longitud geográfica</i></li>"
                                        "<li><i>Introduzca la latitud geográfica</i></li>"
                                        "</ul>"
                                        "</li>"
                                        "<li>Dar al botón <i>Buscar por coordenadas</i> o pulsar la tecla <i>Enter</i>.</li>"
                                        "</ol>"
                                        "</li>"
                                        "</ul>"            
                                    )
            else:
                self.help_widget.setText("")

    def add_tabs(self):
        """Añadir las pestañas al QTabWidget"""
        # Pestaña de bienvenida
        welcome_tab = self.create_welcome_tab()
        self.tabs.addTab(welcome_tab, "CartoCiudad")

        # Pestaña para la localización por nombre geográfico
        name_tab = self.create_name_tab()
        self.tabs.addTab(name_tab, "Localización por nombre geográfico")

        # Pestaña para la localización por coordenadas
        reverse_tab = self.create_reverse_tab()
        self.tabs.addTab(reverse_tab, "Localización por coordenadas")

    def create_welcome_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel(
            "<h2>Descripción del Geocoder CartoCiudad</h2>"
            "<p>CartoCiudad ofrece diferentes servicios web de geolocalización de direcciones postales, topónimos, poblaciones y límites administrativos de España. Para poder utilizar estos servicios web en QGIS y así poder geolocalizar y descargar todos los elementos almacenados en CartoCiudad, se ha creado este <b>complemento de QGIS</b>, que está basado en servicio REST «Geocoder».</p>"
            "<p>Este complemento permite <b>localizar</b> y <b>descargar</b> objetos geográficos de España por identificadores geográficos y/o por coordenadas geográficas. Se pueden localizar los siguientes objetos geográficos:</p>"
            "<ul>"
            "<li>Direcciones postales</li>"
            "<li>Topónimos</li>"            
            "<li>Puntos de interés</li>"
            "<li>Unidades administrativas</li>"
            "<li>Poblaciones</li>"
            "<li>Códigos postales</li>"
            "<li>Referencias catastrales (Servicios SOAP. Dirección General de Catastro)</li>"
            "</ul>"
            "<p>La información que se devuelve puede ser <b>puntual</b> (portales, PK, códigos postales, puntos de interés y referencias catastrales), <b>lineal</b> (viales) y <b>superficial</b> (unidades administrativas y entidades de población).</p>"
            "<h2>Referencias</h2>"
            "<p>Más información en:</p>"
            "<ul>"
            "<li><a href='https://www.cartociudad.es/web/portal'>Portal CartoCiudad</a></li>"
            "<li><a href='https://www.idee.es/resources/documentos/Cartociudad/CartoCiudad_ServiciosWeb.pdf'>Guía Técnica de Servicios Web</a></li>"
            "<li><a href='https://www.idee.es/resources/documentos/Cartociudad/StoryMap.html'>Ayuda Proyecto CartoCiudad</a></li>"
            "</ul>"
        )
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)  # Permite abrir enlaces en el navegador
        # layout.addWidget(label)
        label.setStyleSheet("padding: 8px 16px 16px 8px;")  # arriba, derecha, abajo, izquierda

        # Crear el scroll area 
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)
        scroll.setContentsMargins(8, 8, 16, 8)  # margen exterior: izq, arriba, der, abajo

       

        layout.addWidget(scroll)
        
        return tab
                    
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
