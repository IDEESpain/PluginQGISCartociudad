import json
from typing import List, Dict, Any, Union, Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox
from PyQt5.QtCore import QUrl, Qt, QVariant
from PyQt5.QtGui import QBrush, QColor
from PyQt5 import QtNetwork
from PyQt5.QtWidgets import QHeaderView
from qgis.gui import QgisInterface
from qgis.core import (QgsProject, QgsCoordinateReferenceSystem,
                       QgsVectorLayer, QgsGeometry, QgsFeature, QgsFields, QgsField, QgsWkbTypes)

LIMIT = 35
API_GEOCODER = 'https://www.cartociudad.es/geocoder/api/geocoder'

class NameTab(QWidget):
    def __init__(self, parent: QWidget, iface: QgisInterface) -> None:
        """
        Initialize the NameTab widget.

        Args:
            parent (QWidget): The parent widget.
            iface (QgisInterface): The QGIS interface to interact with the map canvas and layers.
        """
        super().__init__(parent)
        self.iface = iface
        self.layers = {}
        self.create_layout()

    def create_layout(self) -> None:
        """
        Create and set up the layout for the NameTab widget.

        This includes input fields for location and postal codes,
        a search button, and a table for displaying results.
        """
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Campo de búsqueda por localización
        lbl_localizacion = QLabel('Localización:')
        layout.addWidget(lbl_localizacion)
        self.localizacion = QLineEdit()
        self.localizacion.setPlaceholderText('Topónimo, dirección, población, unidad administrativa o referencia catastral')
        layout.addWidget(self.localizacion)

        # Campo de búsqueda por código postal
        lbl_cp = QLabel('Filtrar por código postal:')
        layout.addWidget(lbl_cp)
        self.cp = QLineEdit()
        self.cp.setPlaceholderText('Uno o más C.P. separados por comas y sin espacios')
        layout.addWidget(self.cp)

        # Botón de búsqueda
        self.buscar = QPushButton('Buscar')
        layout.addWidget(self.buscar)

        # Tabla de resultados
        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(2)
        self.tabla_resultados.setHorizontalHeaderLabels(['Candidatos', 'Tipo'])

        # Configurar la selección para que sea por fila completa
        self.tabla_resultados.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_resultados.setSelectionMode(QAbstractItemView.SingleSelection)

        # Ajustar el comportamiento de las columnas para que se expandan
        self.tabla_resultados.horizontalHeader().setStretchLastSection(True)
        self.tabla_resultados.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Añadir la tabla al layout
        layout.addWidget(self.tabla_resultados)

        # Conectar el botón de búsqueda a la función
        self.buscar.clicked.connect(self.on_search_name)
        # Conectar el evento de doble clic en la celda y número de fila
        self.tabla_resultados.cellDoubleClicked.connect(self.find_location)
        self.tabla_resultados.verticalHeader().sectionDoubleClicked.connect(self.handle_row_double_click)

    def on_search_name(self) -> None:
        """
        Handle the search for candidates based on the user input for location and postal codes.

        Constructs the URL for the API request and clears previous results before making a new search.
        """
        # Construcción de la URL para la búsqueda
        url = f'{API_GEOCODER}/candidates?q={self.localizacion.text()}&limit={LIMIT}'

        # Filtrar por código postal
        if self.cp.text() != '':
            codigos = self.cp.text().split(',')
            codigos = [codigo.strip() for codigo in codigos]
            if all(codigo.isdigit() and len(codigo) == 5 for codigo in codigos):
                codigos_str = ','.join(codigos)
                url += f'&cod_postal_filter={codigos_str}'
            else:
                QMessageBox.critical(None, "Error", "Algunos códigos postales no son válidos")
                return  # Si hay un error con los códigos postales, salimos de la búsqueda

        print(f'Buscar: {url}')
        # Limpiar la tabla antes de la nueva búsqueda
        self.tabla_resultados.clearContents()
        self.tabla_resultados.setRowCount(0)
        # Hacer la solicitud de búsqueda
        self.get_candidates(url)

    def get_candidates(self, url: str) -> None:
        """
        Make a network request to get the candidates based on the constructed URL.

        Args:
            url (str): The URL for the API request.
        """
        print(f"Haciendo petición a la URL: {url}")
        self.manager_candidates = QtNetwork.QNetworkAccessManager()
        self.manager_candidates.finished.connect(self.show_candidates)
        req = QtNetwork.QNetworkRequest(QUrl(url))
        self.manager_candidates.get(req)

    def show_candidates(self, reply: QtNetwork.QNetworkReply) -> None:
        """
        Process the reply from the candidates API request and display the candidates in the results table.

        Args:
            reply (QtNetwork.QNetworkReply): The reply from the network request.
        """
        er = reply.error()
        if er == QtNetwork.QNetworkReply.NoError:
            print("Respuesta de la API recibida correctamente.")
            bytes_string = reply.readAll()
            response = str(bytes_string, 'utf-8')
            print(f"Respuesta JSON de la API: {response}")  # Mostrar el JSON devuelto
            candidates = json.loads(response)

            if not candidates:
                QMessageBox.warning(None, "¡Atención!", "No se encontraron candidatos.")
                # Mostrar mensaje en la tabla cuando no hay resultados
                self.tabla_resultados.setRowCount(1)
                no_result_item = QTableWidgetItem("No se encontraron resultados")
                no_result_item.setFlags(Qt.ItemIsEnabled)  # No seleccionable
                no_result_item.setForeground(QBrush(QColor(255, 0, 0)))  # Color rojo

                type_item = QTableWidgetItem("No se encontraron resultados")
                type_item.setFlags(Qt.ItemIsEnabled)  # No seleccionable
                type_item.setForeground(QBrush(QColor(255, 0, 0)))  # Color rojo

                self.tabla_resultados.setItem(0, 0, no_result_item)
                self.tabla_resultados.setItem(0, 1, type_item)
                self.tabla_resultados.resizeColumnsToContents()
                self.tabla_resultados.resizeRowsToContents()
                return

            print(f"Número de candidatos encontrados: {len(candidates)}")

            # Actualizar la tabla de resultados de una vez, sin procesar cada fila individualmente
            self.tabla_resultados.setRowCount(len(candidates))

            for index, candidate in enumerate(candidates):
                print(f"Candidato {index + 1}: {candidate['address']}, Tipo: {candidate['type']}")

                # Crear el item con la dirección (solo estos elementos serán seleccionables)
                item_address = QTableWidgetItem(candidate['address'])
                item_address.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # Solo los candidatos son seleccionables
                # Guardar el ID del candidato en el UserRole del item
                item_address.setData(Qt.UserRole, candidate['id'])

                # Crear el item con el tipo de candidato (no seleccionable)
                item_type = QTableWidgetItem(candidate['type'])
                item_type.setFlags(Qt.ItemIsEnabled)  # No seleccionable

                # Agregar ambos items a la fila
                self.tabla_resultados.setItem(index, 0, item_address)
                self.tabla_resultados.setItem(index, 1, item_type)

            # Redimensionar columnas y filas solo una vez después de que se hayan añadido todos los datos
            self.tabla_resultados.resizeColumnsToContents()
            self.tabla_resultados.resizeRowsToContents()
        else:
            QMessageBox.critical(None, "Error", f"Error en la petición: {er}")

    def find_location(self, row:int, column: int) -> None:
        """
        Find the location based on the selected row in the results table and make an API request to get details.

        Args:
            row (int): The row number of the selected candidate.
            column (int): The column number of the selected item (not used but included for consistency).
        """
        # Asegurarse de seleccionar la fila completa cuando se selecciona una celda
        self.tabla_resultados.selectRow(row)

        # Obtiene el texto de la celda seleccionada, que contiene la dirección
        address = self.tabla_resultados.item(row, 0).text()
        # Ahora obtenemos el ID del candidato asociado a esa fila
        candidate_id = self.tabla_resultados.item(row, 0).data(Qt.UserRole)

        # También obtenemos el valor del tipo de la celda correspondiente
        candidate_type = self.tabla_resultados.item(row, 1).text()
        # Construimos la URL con la dirección, el id y el tipo
        url = f'{API_GEOCODER}/find?q={address}&id={candidate_id}&type={candidate_type}'
        self.get_location(url)
        print(f'Buscar: {url}')

    def handle_row_double_click(self, row):
        """
        Handle double-click events on the row number in the vertical header.

        Args:
            row (int): The row number that was double-clicked.
        """
        # Selecciona la fila completa cuando se hace doble clic en el número de la fila
        self.tabla_resultados.selectRow(row)
        # Llamamos a la misma función find_location que cuando se hace clic en una celda
        self.find_location(row, 0)  # Pasamos la fila y columna 0 por defecto

    def get_location(self, url):
        """
        Make a network request to get the location details based on the constructed URL.

        Args:
            url (str): The URL for the API request.
        """
        self.manager_locate = QtNetwork.QNetworkAccessManager()
        self.manager_locate.finished.connect(self.draw_location)
        req = QtNetwork.QNetworkRequest(QUrl(url))
        self.manager_locate.get(req)

    def draw_location(self, reply: QtNetwork.QNetworkReply) -> None:
        """
        Process the reply from the location API request and add the found location to the QGIS map.

        Args:
            reply (QtNetwork.QNetworkReply): The reply from the network request.
        """
        print('Recibiendo respuesta del servicio find...')
        er = reply.error()
        if er == QtNetwork.QNetworkReply.NoError:
            bytes_string = reply.readAll()
            response = str(bytes_string, 'utf-8')
            location = json.loads(response)
            print('Localización: ')
            print(location)
            # Procesar la ubicación en función del tipo
            self.handle_location(location)

    def handle_location(self, location: Dict[str, Union[Any, List[Any]]]) -> None:
        """
        Handle the provided location dictionary, creating layers and adding geometries as needed.

        Args:
            location (Dict[str, Union[Any, List[Any]]]): A dictionary containing location data, including 
                                                          geometry (WKT format) and type.
        """
        wkt = location['geom']
        location_type = location['type']
        new_geometry_type = self.get_geometry_type(wkt)

        # Definir el nombre de la capa según el tipo
        if location_type in ['callejero', 'carretera']:
            layer_name = 'Viales'
        elif location_type in ['expendeduria', 'punto_recarga_electrica', 'ngbe', 'toponimo']:
            layer_name = 'Puntos_interes'
        elif location_type == 'poblacion':
            layer_name = 'Poblaciones'
        elif location_type == 'portal':
            layer_name = 'Portales_pk'
        elif location_type == 'Municipio':
            layer_name = 'Municipios'
        elif location_type == 'provincia':
            layer_name = 'Provincias'
        elif location_type == 'comunidad autonoma':
            layer_name = 'Comunidades_sim'
        elif location_type == 'Codpost':
            layer_name = 'Codigos_postales'
        elif location_type == 'refcatastral':
            layer_name = 'Referencia_catastral'
        else:
            QMessageBox.warning(None, "¡Atención!", f"Tipo no reconocido: {location_type}")
            return

        # Verificar si la capa aún existe
        if layer_name in self.layers and not QgsProject.instance().mapLayersByName(layer_name):
            del self.layers[layer_name]  # Eliminar la referencia a la capa eliminada

        # Crear la capa si no existe
        if layer_name not in self.layers or self.layers[layer_name] is None:
            self.create_layer(layer_name, new_geometry_type, location)

        # Agregar la geometría a la capa correspondiente
        self.add_feature_to_layer(location, layer_name)

    def create_layer(self, layer_name: str, geometry_type: str, location: Dict[str, Union[str, List[str]]]) -> None:
        """
        Create a new vector layer with the specified name and geometry type, and add attributes from location data.

        Args:
            layer_name (str): The name of the layer to be created.
            geometry_type (str): The geometry type (e.g., 'Point', 'LineString', 'Polygon').
            location (Dict[str, Union[str, List[str]]]): A dictionary containing location data.
        """
        self.layers[layer_name] = QgsVectorLayer(geometry_type, layer_name, "memory")
        crs = QgsCoordinateReferenceSystem('EPSG:4258')
        self.layers[layer_name].setCrs(crs)
        self.fields = QgsFields()
        
        # Excluir los atributos no deseados: 'stateMsg', 'state' y 'countryCode'
        self.create_attributes_from_json(location, exclude_keys=['stateMsg', 'state', 'countryCode'])
        
        pr = self.layers[layer_name].dataProvider()
        pr.addAttributes(self.fields)
        self.layers[layer_name].updateFields()
        QgsProject.instance().addMapLayer(self.layers[layer_name])

    def get_geometry_type(self, wkt: str) -> str:
        """
        Determine the geometry type based on the WKT string.

        Args:
            wkt (str): The WKT representation of the geometry.

        Returns:
            str: The type of geometry (e.g., 'Point', 'LineString', 'Polygon').

        Raises:
            ValueError: If the WKT string does not match any known geometry types.
        """
        if wkt.startswith('POINT'):
            return 'Point'
        elif wkt.startswith('LINESTRING'):
            return 'LineString'
        elif wkt.startswith('POLYGON'):
            return 'Polygon'
        elif wkt.startswith('MULTIPOINT'):
            return 'MultiPoint'
        elif wkt.startswith('MULTILINESTRING'):
            return 'MultiLineString'
        elif wkt.startswith('MULTIPOLYGON'):
            return 'MultiPolygon'
        else:
            raise ValueError(f"Tipo de geometría no soportado: {wkt}")

    def create_attributes_from_json(self, location: Dict[str, Union[str, List[str]]], exclude_keys: Optional[List[str]] = None) -> None:
        """
        Create attributes for the layer from the provided location dictionary, excluding specified keys.

        Args:
            location (Dict[str, Union[str, List[str]]]): A dictionary containing location data.
            exclude_keys (Optional[List[str]]): A list of keys to exclude when creating attributes.
        """
        if exclude_keys is None:
            exclude_keys = []

        for attribute, value in location.items():
            # Excluir los atributos específicos
            if attribute not in exclude_keys and attribute != 'geom':
                self.fields.append(QgsField(attribute, QVariant.String))

    def add_feature_to_layer(self, attributes: Dict[str, Union[Any, List[Any]]], layer_name: str) -> None:
        """
        Add a feature (point or polygon) to the specified layer and zoom to its geometry.

        Args:
            attributes (Dict[str, Union[Any, List[Any]]]): A dictionary containing attribute data, including geometry.
            layer_name (str): The name of the layer to which the feature will be added.
        """
        # Agregar una característica (punto o polígono) a la capa y hacer zoom en esa geometría
        layer = self.layers[layer_name]
        if layer and layer.isValid():  # Verificar que la capa es válida
            feature = QgsFeature()
            feature.setFields(self.fields)

            for attribute, value in attributes.items():
                if attribute == 'geom':
                    geom = QgsGeometry.fromWkt(value)

                    # Verificar si la geometría es válida
                    if not geom.isGeosValid():
                        print(f"Geometría no válida detectada. Intentando corregir...")

                        # Aplicar una corrección básica para corregir autointersecciones
                        geom = geom.buffer(0, 5)  # Esto puede corregir intersecciones propias

                        # Validar de nuevo después de la corrección
                        if not geom.isGeosValid():
                            QMessageBox.warning(None, "¡Atención!", "La geometría no es válida.")
                            print("La geometría sigue siendo inválida después de la corrección.")
                            return  # Si sigue siendo inválida, no continuar

                    # Asignar la geometría al feature
                    feature.setGeometry(geom)

                else:
                    # Verificar que el atributo existe en los campos antes de asignarlo
                    if attribute in [field.name() for field in self.fields]:
                        feature.setAttribute(attribute, str(value))

            # Añadir el feature solo una vez, después de procesar los atributos y geometría
            pr = layer.dataProvider()
            pr.addFeature(feature)
            layer.updateExtents()

            # Si la geometría es válida, hacer zoom a su extensión
            if geom.wkbType() in [QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon]:
                self.zoom_to_bounding_box(geom)
            else:
                self.zoom_to_geometry(geom)

    def zoom_to_bounding_box(self, geom: QgsGeometry) -> None:
        """
        Zoom to the bounding box of the provided geometry (polygon or multipolygon).

        Args:
            geom (QgsGeometry): The geometry to zoom to.
        """
        # Calcular y hacer zoom al bounding box de la geometría (polígono o multipolígono)
        if geom is not None and geom.isGeosValid():
            extent = geom.boundingBox()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()

    def zoom_to_geometry(self, geom: QgsGeometry) -> None:
        """
        Center the map on the provided geometry (point or line).

        Args:
            geom (QgsGeometry): The geometry to center on.
        """
        # Centrar el mapa en la geometría proporcionada (punto o línea)
        if geom is not None and geom.isGeosValid():
            extent = geom.boundingBox()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
