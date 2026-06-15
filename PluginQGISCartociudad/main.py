
# Importacion de módulos y librerias necesarias para el funcionamiento del complemento.

import os
import sys

from qgis.PyQt.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QWidget, QDockWidget,
    QLabel, QTabWidget, QScrollArea, QDialog, QPushButton, QTextEdit
)
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtGui import QPixmap, QIcon, QPainter, QAction
from qgis.PyQt import QtNetwork

from .compat import CompatQt as CQt
from .errors import _get_error_message, _get_url_error_message
from .name import NameTab
from .reverse import ReverseTab



#Crea las ventanas de diálogo de ayuda para cada pestaña
class HelpDialog(QDialog):
    def __init__(self, parent=None, tab_index=0):
        super().__init__(parent)
        self.setWindowTitle("Ayuda - CartoCiudad")
        self.setGeometry(100, 100, 600, 500)
        
        layout = QVBoxLayout(self)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        help_texts = {
            1: "<h2>Localización por nombre geográfico</h2>"
                "<p>Permite realizar búsquedas de los diferentes elementos geográficos contenidos de CartoCiudad. "
                "El servicio, a partir de una petición, busca y devuelve como resultados candidatos con similitud "
                "fonética al nombre geográfico buscado junto con una serie de parámetros de información asociada. "
                "Es importante mencionar que el orden de estos resultados y el número de registros devueltos "
                "está determinado por tipología.</p><br>"
                "Para realizar una búsqueda, se añade en <i>Localización</i> el elemento a buscar. A continuación, se puede pulsar "
                "el botón de <i>Buscar</i> o la tecla <i>Enter</i>.</br>"
                "<h3>(Opcional) Búsqueda de un elemento filtrando por código postal</h3>"
                "<p>Permite realizar una búsqueda de cualquier elemento geográfico contenido en un "
                "<i>código postal</i>.</p><br>"
                "Para ello hay que introducir el elemento en <i>Localización</i> y añadir el número del código postal deseado en "
                "<i>Filtro por código postal</i>. También, se puede filtrar por varios códigos "
                "postales, para ello, hay que introducirlos seguidos de comas y sin espacios. De nuevo, se puede "
                "pulsar el botón de <i>Buscar</i> o la tecla <i>Enter</i>.</br>"
                "<h3>(Opcional) Selección de filtros por unidades administrativas</h3>"
                "<p>Permite realizar una búsqueda de cualquier elemento geográfico contenido en "
                "<b>municipios, provincias y/o comunidades y ciudades autónomas</b>.</p><br>"
                "Para ello hay que seleccionar la unidad o unidades administrativas deseadas en el desplegable, "
                "pulsar la tecla <i>aceptar</i> y, a continuación, se puede pulsar el botón de <i>Buscar</i>"
                "o la tecla <i>Enter</i>.</br>"
                "Por defecto, la búsqueda se realiza para todas las unidades administrativas."
                "<h3>(Opcional) Selección de tipología de elementos para acotar la búsqueda</h3>"
                "<p>Permite realizar una búsqueda según tipología del elemento."
                "Para ello hay que introducir el o los tipos deseados, y a continuación se puede pulsar el botón de "
                "<i>Buscar</i> o la tecla <i>Enter</i>. "
                "Por defecto la búsqueda se realiza para todos los tipos de elementos, del mismo modo que si se deseleccionan todos los elementos.",
            2: "<h2>Localización por coordenadas geográficas</h2>"
                "<p>Se puede obtener la dirección postal de cualquier punto del territorio español a partir de sus "
                "coordenadas. Los campos longitud y latitud que se devuelven no son los que se muestran como "
                "parámetros de entrada en la petición, sino los correspondientes a la entidad que se devuelve "
                "en el resultado.</p><br>"
                "Para realizar la búsqueda hay dos métodos:</br>"
                "<ul>"
                "<li><b>Capturar coordenadas en el mapa:</b> Una vez seleccionado el botón de "
                "<i>Capturar coordenadas del mapa</i>, hay que seleccionar cualquier punto en el proyecto de "
                "trabajo y, si el servicio REST Geocoder geolocaliza una dirección, devuelve el resultado.</li>"
                "<br>"
                "<li><b>Buscar por coordenadas</b> También se puede buscar una dirección si se tienen sus "
                "coordenadas geográficas (latitud y longitud en WGS84; EPSG:4326)."
                "<ol>"
                "<li>Rellenar los dos campos (puede usarse tanto punto como coma de separador decimal):"
                "<ul>"
                "<li><i>Introduzca la longitud geográfica</i></li>"
                "<li><i>Introduzca la latitud geográfica</i></li>"
                "</ul>"
                "</li>"
                "<li>A continuación, pulsar el botón <i>Buscar por coordenadas</i> o la tecla <i>Enter</i>.</li>"
                "</ol>"
                "</li>"
                "</ul>"
        }
        
        text_edit.setText(help_texts.get(tab_index, ""))
        layout.addWidget(text_edit)
        
        button_close = QPushButton("Cerrar")
        button_close.clicked.connect(self.accept)
        layout.addWidget(button_close)

# Crea la interfaz gráfica del plugin dentro de QGIS
class Geocoder:

    #Define las caracteristicas iniciales de la interfaz gráfica del plugin
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.initGui()
        self._session_filters = {} 

    #Crea el botón del plugin en la barra de herramientas y en el menú de complementos de QGIS. 
    def initGui(self):
        # Evita agregar el plugin varias veces
        if self.action is None:
            icon_path = os.path.join(os.path.dirname(__file__), "images", "Logo_small.svg")
            self.action = QAction(
                QIcon(icon_path),
                "Geocoder Cartociudad",
                self.iface.mainWindow()
            )
            # Define que hace si se pulsa el botón del plugin
            self.action.triggered.connect(self.run)

            # Añade la acción al menú de plugins
            self.iface.addPluginToMenu("&Geocoder Cartociudad", self.action)

            # Añade la acción a la barra de herramientas con el logo como icono
            self.iface.addToolBarIcon(self.action)

    #Elimina el botón del plugin y del panel lateral cuando se desactiva
    def unload(self):
        # Elimina el plugin del menú y la barra de herramientas cuando se desactiva el complemento
        if self.action is not None:
            self.iface.removePluginMenu("&Geocoder Cartociudad", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

        # Elimina el plugin del panel lateral cuando se desactiva el complemento
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    #Crea el panel del plugin si aún no existe y lo pone en la izquierda en primer plano. En el caso de que exista simplemente lo muestra y lo pone en primer plano.
    def run(self):
        # Evitar abrir múltiples docks
        if self.dock is None:
            self.dock = MyDockWidget(self.iface)
            self.iface.addDockWidget(CQt.LeftDockWidgetArea, self.dock)

        self.dock.show()
        self.dock.raise_()

#Crea la interfaz gráfica del panel principal del plugin
class MyDockWidget(QDockWidget):

    #Define las caracteristicas iniciales del panel principal del plugin
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setAllowedAreas(CQt.LeftDockWidgetArea)
        self.plugin_dir = os.path.dirname(__file__)
        self.setWindowTitle("Geocoder CartoCiudad")

        # Crea el widget principal, lo asigna al panel y establece la interfaz
        main_widget = QWidget()
        self.setWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Crea un layout horizontal para el logo
        logo_layout = QHBoxLayout()
        # Agrega un espacio flexible a la izquierda del logo para centrarlo
        logo_layout.addStretch()
        # Crea una etiqueta para mostrar el logo y carga la imagen del logo desde el directorio del plugin
        label = QLabel()
        # Carga la imagen del logo desde el directorio del plugin y la muestra en la etiqueta
        pixmap = QPixmap(os.path.join(self.plugin_dir, "images", "Logo.png"))
        label.setPixmap(pixmap)
        label.setMaximumHeight(80)
        logo_layout.addWidget(label)
        # Agrega un espacio flexible a la derecha del logo para centrarlo
        logo_layout.addStretch()
        # Agrega el layout del logo al layout principal del panel
        layout.addLayout(logo_layout)

        # Crea las pestañas
        self.tabs = QTabWidget()
        self.add_tabs()
        # No permite el scroll horizontal, no es necesario con 3 pestañas
        self.tabs.setUsesScrollButtons(False)
        # Añade las pestañas al layout principal del panel
        layout.addWidget(self.tabs)

    # Muestra el diálogo de ayuda correspondiente a cada pestaña
    def show_help_dialog(self, tab_index):
        dialog = HelpDialog(self, tab_index)
        dialog.exec()

    # Añade las pestañas al panel principal del plugin
    def add_tabs(self):
        # Crea cada pestaña y la añade su contenido al panel de cada pestaña
        welcome_tab = self.create_welcome_tab()
        self.tabs.addTab(welcome_tab, "CartoCiudad")

        name_tab = self.create_name_tab()
        self.tabs.addTab(name_tab, "Localización por nombre geográfico")

        reverse_tab = self.create_reverse_tab()
        self.tabs.addTab(reverse_tab, "Localización por coordenadas")


    # Crea el el contenido de la pestaña de bienvenida
    def create_welcome_tab(self):
        # Crea la pesataña 
        tab = QWidget()
        # Crea el layout de la pestaña y lo asigna a la pestaña
        layout = QVBoxLayout(tab)
        # Crea la etiqueta con el texto de bienvenida.
        label = QLabel(
            "<p><b>NOTA: A partir de la versión 2.0 el plugin solo estará disponible para versiones de QGIS 3.42.0 o superiores.</b></p>"
            "<h2>Descripción del Geocoder CartoCiudad</h2>"
            "<p>CartoCiudad ofrece diferentes servicios web de geolocalización de direcciones postales, topónimos, "
            "poblaciones y límites administrativos de España. Para poder utilizar estos servicios web en QGIS y así "
            "poder geolocalizar y descargar todos los elementos almacenados en CartoCiudad, se ha creado este "
            "<b>complemento de QGIS</b>, que está basado en el servicio REST «Geocoder».</p>"
            "<p>Este complemento permite <b>localizar</b> y <b>descargar</b> objetos geográficos de España por "
            "identificadores geográficos y/o por coordenadas geográficas. Se pueden localizar los siguientes "
            "objetos geográficos:</p>"
            "<ul>"
            "<li>Direcciones postales</li>"
            "<li>Topónimos</li>"
            "<li>Puntos de interés</li>"
            "<li>Unidades administrativas (Comunidades y ciudades autónomas, provincias y municipios)</li>"
            "<li>Entidades de población</li>"
            "<li>Códigos postales</li>"
            "<li>Referencias catastrales (Servicios SOAP. Dirección General del Catastro)</li>"
            "</ul>"
            "<p>La información que se devuelve puede ser <b>puntual</b> (portales, PK, códigos postales, puntos de "
            "interés, topónimos y referencias catastrales), <b>lineal</b> (viales) y <b>superficial</b> (unidades "
            "administrativas y entidades de población).</p>"
            "<h2>Referencias</h2>"
            "<p>Más información en:</p>"
            "<ul>"
            "<li><a href='https://www.cartociudad.es/web/portal'>Portal CartoCiudad</a></li>"
            "<li><a href='https://github.com/IDEESpain/Cartociudad'>Servicio REST Geocoder</a></li>"
            "<li><a href='https://www.idee.es/resources/documentos/Cartociudad/StoryMap.html'>Ayuda Proyecto CartoCiudad</a></li>"
            "</ul>"
            "<h2>Contacto</h2>"
            "<p>¿Dudas o sugerencias? Escríbenos por correo a: "
            "<a href='mailto:cartociudad@transportes.gob.es?subject=Consulta/Sugerencia%20Plugin%20Cartociudad&body=Hola%2C%0A%0AIndica%20tu%20consulta/sugerencia%20aquí.'>"
            "cartociudad@transportes.gob.es"
            "</a>"
            "</p>"
        )
        #Permite que el texto se divida en varias lineas
        label.setWordWrap(True)
        #Permite interpretar el texto como HTML para mostrar enlaces y formato enriquecido
        label.setTextFormat(CQt.RichText)
        label.setOpenExternalLinks(True)
        label.setStyleSheet("padding: 8px 16px 16px 8px;")
        #Crea un área de scroll para la etiqueta, para que se pueda desplazar el texto
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)
        scroll.setContentsMargins(8, 8, 16, 8)

        layout.addWidget(scroll)
        return tab
    # Crea la pestaña de localización por nombre geográfico y añade su contenido
    def create_name_tab(self):
        name_tab = QWidget()
        name_layout = QVBoxLayout(name_tab)
        
        # Botón de Ayuda
        button_help = QPushButton("Ayuda")
        button_help.setMaximumWidth(100)
        button_help.clicked.connect(lambda: self.show_help_dialog(1))
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(button_help)
        button_layout.addStretch()
        name_layout.addLayout(button_layout)
        
        name_layout.addWidget(NameTab(parent=self, iface=self.iface))
        return name_tab
    # Crea la pestaña de localización por coordenadas geográficas y añade su contenido
    def create_reverse_tab(self):
        reverse_tab = QWidget()
        reverse_layout = QVBoxLayout(reverse_tab)
        
        # Botón de Ayuda
        button_help = QPushButton("Ayuda")
        button_help.setMaximumWidth(100)
        button_help.clicked.connect(lambda: self.show_help_dialog(2))
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(button_help)
        button_layout.addStretch()
        reverse_layout.addLayout(button_layout)
        
        reverse_layout.addWidget(ReverseTab(parent=self, iface=self.iface))
        return reverse_tab

# Permite ejecutar el plugin de forma independiente para pruebas y desarrollo sin necesidad de cargarlo en QGIS
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyDockWidget(iface=None)
    window.show()
    sys.exit(app.exec())
