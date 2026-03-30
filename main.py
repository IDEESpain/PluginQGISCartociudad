import os
import sys

from qgis.PyQt.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QWidget, QDockWidget,
    QLabel, QTabWidget, QSplitter, QToolButton, QTextEdit, QScrollArea
)
from qgis.PyQt.QtCore import Qt, QByteArray
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtGui import QPixmap, QIcon, QPainter, QAction

from .compat import CompatQt as CQt
from .name import NameTab
from .reverse import ReverseTab


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
    svg_bytes = QByteArray(svg.encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(size, size)
    pixmap.fill(CQt.Transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class Geocoder:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.initGui()

    def initGui(self):
        # Evitar agregar la acción varias veces
        if self.action is None:
            icon_path = os.path.join(os.path.dirname(__file__), "images", "Logo_small.svg")
            self.action = QAction(
                QIcon(icon_path),
                "Gecoder Cartociudad",
                self.iface.mainWindow()
            )
            self.action.triggered.connect(self.run)

            # Añadir la acción al menú de plugins
            self.iface.addPluginToMenu("&Gecoder Cartociudad", self.action)

            # Añadir la acción a la barra de herramientas con el logo como icono
            self.iface.addToolBarIcon(self.action)

    def unload(self):
        # Eliminar la acción del menú y la barra de herramientas cuando se desactiva el complemento
        if self.action is not None:
            self.iface.removePluginMenu("&Gecoder Cartociudad", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    def run(self):
        # Evitar abrir múltiples docks
        if self.dock is None:
            self.dock = MyDockWidget(self.iface)
            self.iface.addDockWidget(CQt.LeftDockWidgetArea, self.dock)

        self.dock.show()
        self.dock.raise_()


class MyDockWidget(QDockWidget):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setAllowedAreas(CQt.LeftDockWidgetArea)
        self.plugin_dir = os.path.dirname(__file__)
        self.setWindowTitle("Geocoder CartoCiudad")

        # Crear el widget principal
        main_widget = QWidget()
        self.setWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Logo en la parte superior
        logo_layout = QHBoxLayout()
        logo_layout.addStretch()

        label = QLabel()
        pixmap = QPixmap(os.path.join(self.plugin_dir, "images", "Logo.png"))
        label.setPixmap(pixmap)
        label.setMaximumHeight(80)
        logo_layout.addWidget(label)

        logo_layout.addStretch()
        layout.addLayout(logo_layout)

        # Crear las pestañas
        self.tabs = QTabWidget()
        self.add_tabs()

        # Splitter principal
        self.splitter = QSplitter(CQt.Horizontal)
        self.splitter.addWidget(self.tabs)

        # Widget de ayuda
        self.help_widget = QTextEdit("Aquí va la información de ayuda de tu plugin.")
        self.help_widget.setReadOnly(True)
        self.splitter.addWidget(self.help_widget)

        self.splitter.setSizes([400, 200])
        self.splitter.setCollapsible(0, False)

        # Conectar el cambio de pestaña a la función de ayuda
        self.tabs.currentChanged.connect(self.update_help_text)
        self.update_help_text(self.tabs.currentIndex())
        self.tabs.setUsesScrollButtons(False)

        layout.addWidget(self.splitter)

        # Botón de colapso en el handle del splitter
        self.splitter_handle = self.splitter.handle(1)
        self.splitter.splitterMoved.connect(self.splitterChanged)
        self.mHelpCollapsed = False
        self.mSplitterState = QByteArray()

        handle_layout = QVBoxLayout()
        handle_layout.setContentsMargins(0, 0, 0, 0)

        self.button_collapse = QToolButton(self.splitter_handle)
        self.button_collapse.setFixedSize(24, 24)
        self.button_collapse.setCursor(CQt.ArrowCursor)
        self.button_collapse.setArrowType(CQt.RightArrow)
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
        self.button_collapse.clicked.connect(self.toggleCollapsed)

    def splitterChanged(self, pos, index):
        if self.splitter.sizes()[1] == 0:
            self.mHelpCollapsed = True
            self.button_collapse.setArrowType(CQt.LeftArrow)
        else:
            self.mHelpCollapsed = False
            self.button_collapse.setArrowType(CQt.RightArrow)

    def toggleCollapsed(self):
        if self.mHelpCollapsed:
            if not self.mSplitterState.isEmpty():
                self.splitter.restoreState(self.mSplitterState)
            else:
                self.splitter.setSizes([400, 200])
            self.button_collapse.setArrowType(CQt.RightArrow)
        else:
            self.mSplitterState = self.splitter.saveState()
            self.splitter.setSizes([1, 0])
            self.button_collapse.setArrowType(CQt.LeftArrow)

        self.mHelpCollapsed = not self.mHelpCollapsed

    def update_help_text(self, index):
        if index == 0:
            self.help_widget.hide()
        else:
            self.help_widget.show()

            if index == 1:
                self.help_widget.setText(
                    "<h2>Localización por nombre geográfico</h2>"
                    "<p>Permite realizar búsquedas de los diferentes elementos geográficos contenidos de CartoCiudad. "
                    "El servicio, a partir de una petición, busca y devuelve candidatos con resultados con similitud "
                    "fonética al nombre geográfico buscado, junto con una serie de parámetros de información asociada. "
                    "Es importante mencionar que el orden de estos resultados sigue un orden intrínseco por tipología "
                    "y que el número de registros también está determinado por tipología.</p><br>"
                    "Para ello se añade en <i>Localización</i> el elemento a buscar. A continuación, se puede pulsar "
                    "el botón de <i>Buscar</i> o la tecla <i>Enter</i>.</br>"
                    "<h3>(Opcional) Búsqueda de un elemento filtrando por código postal</h3>"
                    "<p>Permite realizar una búsqueda de cualquier elemento geográfico contenido en un "
                    "<i>código postal</i>.</p><br>"
                    "Para ello hay que introducir el elemento a buscar y además hay que añadir en Filtro por código postal "
                    "el número del código postal deseado. Así mismo, se puede filtrar por varios códigos "
                    "postales y, para ello, hay que introducirlos seguidos de comas y sin espacios. De nuevo, se puede "
                    "pulsar el botón de <i>Buscar</i> o la tecla <i>Enter</i>.</br>"
                    "<h3>(Opcional) Selección de filtros por unidades administrativas</h3>"
                    "<p>Permite realizar una búsqueda de cualquier elemento geográfico contenido en un "
                    "<b>municipios, provincias o comunidades y ciudades autónomas</b>.</p><br>"
                    "Por defecto, la búsqueda se realiza para todas las unidades administrativas. "
                    "Para ello hay que seleccionar la unidad o unidades administrativas deseadas en el desplegable, "
                    "pulsar la tecla <i>aceptar</i> y, a continuación, se puede pulsar el botón de <i>Buscar</i>"
                    "o la tecla <i>Enter</i>.</br>"
                    "<h3>(Opcional) Selección de tipología de elementos para acotar la búsqueda</h3>"
                    "<p>Permite realizar una búsqueda de cualquier tipo de elemento de la siguiente lista de tipos: <br>"
                    "<b>Entidades de población, municipios, provincias, comunidades y ciudades autónomas, topónimos o POI, viales (urbanos o interurbanos), portales o puntos kilométricos, "
                    "expendidurías, puntos de recarga eléctrica, referencias catastrales o topónimos orográficos (NGBE) "
                    "de España.</b></p><br>"
                    "Por defecto, la búsqueda se realiza para todos los tipos de elementos, también, si se "
                    "deseleccionan todos los tipos, la búsqueda también se realizará para todos ellos. "
                    "Para ello hay que introducir el o los tipos deseados. Así mismo, se puede pulsar el botón de "
                    "<i>Buscar</i> o la tecla <i>Enter</i>."
                )

            elif index == 2:
                self.help_widget.setText(
                    "<h2>Localización por coordenadas geográficas</h2>"
                    "<p>Se puede obtener la dirección postal de cualquier punto del territorio español a partir de sus "
                    "coordenadas. Los campos longitud y latitud que se devuelven no son los que se muestran como "
                    "parámetros de entrada en la petición, sino los correspondientes a la entidad que se devuelve "
                    "en el resultado.</p><br>"
                    "Para ello hay dos métodos:</br>"
                    "<ul>"
                    "<li><b>Capturar coordenadas en el mapa:</b> Una vez seleccionado el botón de "
                    "<i>Capturar coordenadas del mapa</i>, hay que seleccionar cualquier punto en el proyecto de "
                    "trabajo y, si el servicio REST Geocoder geolocaliza una dirección, devuelve el resultado.</li>"
                    "<br>"
                    "<li><b>Buscar por coordenadas</b> También se puede buscar una dirección si se tienen sus "
                    "coordenadas geográficas (latitud y longitud en WGS84; EPSG:4326 )."
                    "<ol>"
                    "<li>Rellenar los dos campos:"
                    "<ul>"
                    "<li><i>Introduzca la longitud geográfica</i></li>"
                    "<li><i>Introduzca la latitud geográfica</i></li>"
                    "</ul>"
                    "</li>"
                    "<li>Pulsar el botón <i>Buscar por coordenadas</i> o la tecla <i>Enter</i>.</li>"
                    "</ol>"
                    "</li>"
                    "</ul>"
                )
            else:
                self.help_widget.setText("")

    def add_tabs(self):
        welcome_tab = self.create_welcome_tab()
        self.tabs.addTab(welcome_tab, "CartoCiudad")

        name_tab = self.create_name_tab()
        self.tabs.addTab(name_tab, "Localización por nombre geográfico")

        reverse_tab = self.create_reverse_tab()
        self.tabs.addTab(reverse_tab, "Localización por coordenadas")

    def create_welcome_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel(
            "<p><b>NOTA: Esta versión del plugin solo está disponible para verisones de QGIS 3.42.0 o superiores.</b></p>"
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
        label.setWordWrap(True)
        label.setTextFormat(CQt.RichText)
        label.setOpenExternalLinks(True)
        label.setStyleSheet("padding: 8px 16px 16px 8px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)
        scroll.setContentsMargins(8, 8, 16, 8)

        layout.addWidget(scroll)
        return tab

    def create_name_tab(self):
        name_tab = QWidget()
        name_layout = QVBoxLayout(name_tab)
        name_layout.addWidget(NameTab(parent=self, iface=self.iface))
        return name_tab

    def create_reverse_tab(self):
        reverse_tab = QWidget()
        reverse_layout = QVBoxLayout(reverse_tab)
        reverse_layout.addWidget(ReverseTab(parent=self, iface=self.iface))
        return reverse_tab


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyDockWidget(iface=None)
    window.show()
    sys.exit(app.exec())
