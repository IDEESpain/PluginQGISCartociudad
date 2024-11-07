import json
from typing import List, Dict, Union

from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, QMessageBox
from PyQt5.QtCore import Qt, QUrl, QVariant
from PyQt5 import QtNetwork
from qgis.gui import QgisInterface, QgsMapToolEmitPoint
from qgis.core import QgsPointXY, QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject, QgsFields, QgsField, QgsCoordinateReferenceSystem

class ReverseTab(QWidget):
    """
    ReverseTab is a QWidget subclass used for reverse geocoding in QGIS.
    This widget allows the user to capture coordinates from a map, search by geographic coordinates (longitude and latitude), and display the 
    results in a table with options to create a layer from the results.
    """
    
    def __init__(self, parent: QWidget, iface: QgisInterface) -> None:
        """
        Initializes the ReverseTab widget.

        Args:
            parent (QWidget): The parent widget.
            iface (QgisInterface): The QGIS interface object.
        """
        super().__init__(parent)
        self.iface = iface
        self.create_layout()
        
    def create_layout(self) -> None:
        """
        Creates the layout of the reverse geocoding tab.
        
        This includes input fields for coordinates, buttons for capturing and searching coordinates, and a table to display results.
        """
        reverse_layout = QVBoxLayout()
        self.setLayout(reverse_layout)
        
        # Botón para capturar coordenadas desde el mapa de QGIS
        capture_button = QPushButton("Capturar coordenadas del mapa")
        capture_button.clicked.connect(self.capture_coordinates_from_map)
        reverse_layout.addWidget(capture_button)

        # Botón para buscar por coordenadas
        search_button = QPushButton("Buscar por coordenadas")
        search_button.clicked.connect(self.search_by_reverse)
        reverse_layout.addWidget(search_button)

        # Fila para las coordenadas X e Y
        input_layout = QHBoxLayout()
        self.coord_x = QLineEdit()
        self.coord_x.setPlaceholderText("Introduzca longitud geográfica")
        self.coord_y = QLineEdit()
        self.coord_y.setPlaceholderText("Introduzca latitud geográfica")
        input_layout.addWidget(self.coord_x)
        input_layout.addWidget(self.coord_y)
        reverse_layout.addLayout(input_layout)

        # Tabla de resultados con seis columnas
        self.reverse_results_table = QTableWidget()
        self.reverse_results_table.setColumnCount(7)
        self.reverse_results_table.setHorizontalHeaderLabels(['Tipo_via','Dirección', 'Número/pk', 'Extension', 'CCPP','Población','Municipio'])
        reverse_layout.addWidget(self.reverse_results_table)

        # Añadir los botones de acciones debajo de la tabla
        buttons_layout = QHBoxLayout()

        # Botón "Limpiar tabla"
        clear_table_button = QPushButton("Limpiar tabla")
        clear_table_button.clicked.connect(self.clear_table)
        buttons_layout.addWidget(clear_table_button)

        # Botón "Limpiar selección"
        clear_selection_button = QPushButton("Borrar selección")
        clear_selection_button.clicked.connect(self.clear_selection)
        buttons_layout.addWidget(clear_selection_button)

        # Botón "Crear capa"
        create_layer_button = QPushButton("Crear capa")
        create_layer_button.clicked.connect(self.create_layer)
        buttons_layout.addWidget(create_layer_button)

        reverse_layout.addLayout(buttons_layout)

        # Inicializar la clase Reverse con la tabla de resultados
        self.reverse = ReverseCoding(self.reverse_results_table, self.coord_x, self.coord_y, self.iface)
        
    def create_layer(self) -> None:
        """
        Creates a new layer in QGIS based on selected rows in the results table.
        
        If there are no selected rows, a message is shown. Otherwise, the selected data is used to create a vector layer.
        """
        # Obtener los datos necesarios para crear la capa
        selected_rows = self.reverse_results_table.selectionModel().selectedRows()

        if selected_rows:
            selected_indices = [index.row() for index in selected_rows]
            # Definir el nombre de la capa y el tipo de geometría
            layer_name = "resultados reverse"
            geometry_type = "Point"

            # Llamar a create_reverse_layer en Reverse con los índices de las ubicaciones seleccionadas
            self.reverse.create_reverse_layer(layer_name, geometry_type, selected_indices)
        else:
            QMessageBox.warning(None, "¡Atención!", "No hay filas seleccionadas para crear la capa.")
            
    def search_by_reverse(self) -> None:
        """
        Searches for address information using reverse geocoding based on input longitude and latitude.
        
        This function retrieves the coordinates entered by the user and initiates a reverse geocoding request.
        """
        lon = self.coord_x.text()
        lat = self.coord_y.text()

        # Llamar al método de la clase Reverse
        self.reverse.search_by_coordinates(lon, lat)

    def capture_coordinates_from_map(self) -> None:
        """
        Initiates the process of capturing coordinates directly from the QGIS map canvas.
        
        When the map is clicked, the coordinates are retrieved and displayed in the coordinate input fields.
        """
        self.reverse.start_capture()

    def clear_table(self) -> None:
        """
        Clears all the rows in the results table.
        """
        self.reverse.clear_table()

    def clear_selection(self) -> None:
        """
        Clears the currently selected rows from the results table.
        """
        self.reverse.clear_selection()

    
class ReverseCoding:
    """
    A class to handle reverse geocoding operations and manage interactions with the QGIS map.
    """
    
    def __init__(self, table_widget: QTableWidget, coord_x: QLineEdit, coord_y: QLineEdit, iface: QgisInterface) -> None:
        """
        Initializes the ReverseCoding class.

        Args:
            table_widget (QTableWidget): The table widget to display results.
            coord_x (QLineEdit): The input field for longitude.
            coord_y (QLineEdit): The input field for latitude.
            iface (QgisInterface): The QGIS interface object.
        """
        # Inicializar la clase Reverse con el widget de tabla, cajas de coordenadas y la interfaz de QGIS
        self.table_widget = table_widget  # Referencia a la tabla de resultados
        self.coord_x = coord_x  # Caja de texto para coordenada X (lon)
        self.coord_y = coord_y  # Caja de texto para coordenada Y (lat)
        self.iface = iface  # Referencia a la interfaz de QGIS
        self.network_manager = QtNetwork.QNetworkAccessManager()  # Manager de red para hacer las peticiones
        self.layers = {}  # Diccionario para manejar las capas dinámicamente
        self.fields = None
        self.results = []  # Lista para almacenar los resultados de la petición
        
        # Habilitar el uso del clic en el mapa de QGIS para capturar coordenadas
        self.map_tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.handle_map_click)

        # Configurar el comportamiento de la tabla para ajustarse a la ventana
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # *** Selección de múltiples filas completas ***
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)  # Selección por fila completa
        self.table_widget.setSelectionMode(QAbstractItemView.MultiSelection)  # Permitir selección múltiple

    def handle_map_click(self, point: QgsPointXY) -> None:
        """
        Handles the event when the user clicks on the QGIS map canvas.

        Args:
            point (QgsPointXY): The point clicked on the map, containing the longitude and latitude.
        """
        # Capturar el clic en el mapa de QGIS y reflejar las coordenadas en las cajas de texto, luego buscar automáticamente
        lon = point.x()
        lat = point.y()
        if self.coord_x is not None and self.coord_y is not None:
            self.coord_x.setText(str(lon))
            self.coord_y.setText(str(lat))
            print(f"Coordenadas capturadas: Lon = {lon}, Lat = {lat}", 5000)
            self.search_by_coordinates(lon, lat)
        else:
            QMessageBox.critical(None, "Error", "QLineEdit objects have been deleted.")

    def start_capture(self) -> None:
        """
        Sets the QGIS map tool to capture coordinates when clicked on the map canvas.
        """
        # Método para iniciar la captura de coordenadas desde el mapa
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def search_by_coordinates(self, lon: float, lat: float) -> None:
        """
        Sends a reverse geocoding request to the CartoCiudad API based on the provided longitude and latitude.

        Args:
            lon (float): The longitude coordinate.
            lat (float): The latitude coordinate.
        """
        # Función para realizar la petición Reverse Geocoding con las coordenadas
        if lon and lat:
            print(f"Buscando por coordenadas Lon: {lon}, Lat: {lat}")
            url = f"https://www.cartociudad.es/geocoder/api/geocoder/reverseGeocode?lon={lon}&lat={lat}"
            print(f"Haciendo petición a: {url}")
            req = QtNetwork.QNetworkRequest(QUrl(url))
            # Desconectar posibles conexiones previas para evitar ejecuciones múltiples
            try:
                self.network_manager.finished.disconnect(self.handle_reverse_response)
            except TypeError:
                # Ignorar si no estaba previamente conectado
                pass
            # Conectar la solicitud
            self.network_manager.finished.connect(self.handle_reverse_response)
            self.network_manager.get(req)  # Hacer la solicitud GET

    def handle_reverse_response(self, reply: QtNetwork.QNetworkReply) -> None:
        """
        Handles the response from the reverse geocoding request and updates the table with the results.

        Args:
            reply (QtNetwork.QNetworkReply): The reply object containing the server's response.
        """
        # Manejar la respuesta del servidor para la búsqueda Reverse Geocoding
        er = reply.error()
        if er == QtNetwork.QNetworkReply.NoError:
            bytes_string = reply.readAll()
            response = str(bytes_string, 'utf-8')

            # Comprobar si la respuesta está vacía
            if not response.strip():
                QMessageBox.critical(None, "Error", "Respuesta vacía de la API.")
                self.update_table_with_no_response()
                return

            try:
                reverse_data = json.loads(response)
                self.results.append(reverse_data)  # Almacenar el resultado
                self.update_table(reverse_data)
            except json.JSONDecodeError as e:
                QMessageBox.critical(None, "Error", f"Error al decodificar la respuesta JSON: {e}")
        else:
            QMessageBox.critical(None, "Error", f"Error en la petición Reverse Geocoding: {reply.errorString()}")
            self.update_table_with_no_response()

        # Desconectar la señal para evitar múltiples ejecuciones
        self.network_manager.finished.disconnect(self.handle_reverse_response)

    def update_table(self, reverse_data: Dict[str, Union[str, int]]) -> None:
        """
        Updates the results table with the data received from the reverse geocoding response.

        Args:
            reverse_data (Dict[str, Union[str, int]]): The dictionary containing the geocoding result data.
        """
        # Actualizar la tabla con los resultados obtenidos del Reverse Geocoding
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)

        # Datos que queremos mostrar en la tabla
        tipo_via = reverse_data.get('tip_via', 'N/A')
        address = reverse_data.get('address', 'N/A')
        portal_number = reverse_data.get('portalNumber', 'N/A')
        extension = reverse_data.get('extension', 'N/A')
        postal_code = reverse_data.get('postalCode', 'N/A')
        poblacion = reverse_data.get('poblacion', 'N/A')
        municipio = reverse_data.get('muni', 'N/A')

        # Crear items no editables y mostrarlos en la tabla
        items = [
            QTableWidgetItem(tipo_via),
            QTableWidgetItem(address),
            QTableWidgetItem(str(portal_number)),
            QTableWidgetItem(str(extension)),
            QTableWidgetItem(str(postal_code)),
            QTableWidgetItem(poblacion),
            QTableWidgetItem(municipio)
        ]

        for col, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Hacer los items no editables
            self.table_widget.setItem(row_position, col, item)

        # Ajuste explícito de la última columna
        self.table_widget.horizontalHeader().setStretchLastSection(True)

        # Ajustar el layout y las filas después de insertar nuevas filas
        self.table_widget.resizeRowsToContents()  # Ajustar el tamaño de las filas
        self.table_widget.updateGeometry()  # Actualizar la geometría del layout del widget
        self.table_widget.repaint()  # Redibujar la tabla para forzar el ajuste visual

    def update_table_with_no_response(self) -> None:
        """
        Updates the table when no response is returned from the API, indicating an error.
        """
        # Mostrar una ventana de mensaje cuando no haya respuesta de la API
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("Sin respuesta")
        msg_box.setWindowTitle("Geocodificación Inversa")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def clear_table(self) -> None:
        """Clear all items from the results table and reset stored results.

        This method removes all rows from the QTableWidget associated with
        this instance and clears the list of results stored in memory.
        """
        # Limpiar todos los elementos de la tabla
        self.table_widget.setRowCount(0)
        self.results.clear()  # Limpiar los resultados almacenados

    def clear_selection(self) -> None:
        """Remove selected items from the results table.

        This method deletes the currently selected rows from the QTableWidget
        and ensures that the corresponding entries in the results list are also
        removed. It sorts the selected rows in reverse order to avoid indexing issues
        when removing multiple items.

        Attributes:
            selected_rows (list): List of currently selected rows in the table.
        """
        # Eliminar los elementos seleccionados en la tabla
        selected_rows = self.table_widget.selectionModel().selectedRows()
        for index in sorted(selected_rows, reverse=True):
            self.table_widget.removeRow(index.row())
            del self.results[index.row()]  # Eliminar también de la lista de resultados

    def create_reverse_layer(self, layer_name:str, geometry_type: str, selected_indices: List[int]) -> None:
        """Create or recreate a new layer and add attributes from the JSON response.

        This method checks if a layer with the given name already exists.
        If it does and it has been deleted, it removes the reference.
        A new layer is created if it doesn't exist, and attributes are added based on
        the first selected item. Finally, features are added to the layer.

        Args:
            layer_name (str): Name of the layer to create or update.
            geometry_type (str): Type of geometry for the layer (e.g., "Point").
            selected_indices (List[int]): Indices of the selected results to be added as features.
        """
        # Crear o recrear una capa nueva y agregar los atributos completos de la respuesta JSON
        # Primero, intentamos eliminar la capa existente si ya fue eliminada en QGIS
        if layer_name in self.layers:
            try:
                # Intentar acceder a la capa, si ha sido eliminada, esto lanzará una excepción
                layer = self.layers[layer_name]
                if not QgsProject.instance().mapLayer(layer.id()):
                    raise RuntimeError("La capa ha sido eliminada")
            except RuntimeError:
                # Si se captura el error, eliminamos la referencia a la capa
                del self.layers[layer_name]
                layer = None

        # Crear una nueva capa si no existe o si fue eliminada
        if layer_name not in self.layers:
            self.layers[layer_name] = QgsVectorLayer(geometry_type, layer_name, "memory")
            layer = self.layers[layer_name]
            crs = QgsCoordinateReferenceSystem('EPSG:4258')
            layer.setCrs(crs)
            self.fields = QgsFields()

            # Crear los atributos usando la primera selección para definir la estructura de la capa
            if selected_indices:
                self.create_attributes_from_json(self.results[selected_indices[0]])

            pr = layer.dataProvider()
            pr.addAttributes(self.fields)
            layer.updateFields()
            QgsProject.instance().addMapLayer(layer)
        else:
            layer = self.layers[layer_name]

        # Agregar características a la capa existente o nueva
        for index in selected_indices:
            location = self.results[index]
            self.add_feature_to_layer(location, layer_name)

        # Asegúrate de que la extensión se actualice correctamente
        layer.updateExtents()

        # Realiza el zoom a la capa recién creada o actualizada
        self.zoom_to_layer(layer)

    def create_attributes_from_json(self, location: Dict[str, Union[str, int, float]]) -> None:
        """Create attributes in the layer from JSON response.

        This method defines the attributes for the layer by examining the keys
        in the provided JSON response while excluding certain attributes
        such as stateMsg, state, and countryCode. It establishes the field types
        based on the data type of each attribute.

        Args:
            location (Dict[str, Union[str, int, float]]): A dictionary representing a single location
                from the JSON response.
        """
        # Crear atributos en la capa desde la respuesta JSON, excluyendo stateMsg, state y countryCode
        self.fields = QgsFields()
        excluded_attributes = ['stateMsg', 'state', 'countryCode']  # Atributos a excluir
        for attribute, value in location.items():
            if attribute != 'geom' and attribute not in excluded_attributes:
                if isinstance(value, int):
                    field_type = QVariant.Int
                elif isinstance(value, float):
                    field_type = QVariant.Double
                elif isinstance(value, bool):
                    field_type = QVariant.Bool
                else:
                    field_type = QVariant.String
                self.fields.append(QgsField(attribute, field_type))

    def add_feature_to_layer(self, attributes: Dict[str, Union[str, int, float]], layer_name:str) -> None:
        """Add a feature to the specified layer.

        This method constructs a new feature using the provided attributes
        and adds it to the specified layer in memory. It excludes certain
        attributes that are not relevant for the layer.

        Args:
            attributes (Dict[str, Union[str, int, float]]): A dictionary of attributes for the feature.
            layer_name (str): Name of the layer to which the feature will be added.
        """
        # Agregar una característica a la capa
        layer = self.layers[layer_name]
        if layer and layer.isValid():  # Verificar que la capa es válida
            feature = QgsFeature()
            feature.setFields(self.fields)
        
        for attribute, value in attributes.items():
            # Excluir los atributos que no queremos incluir en la capa
            if attribute in ['stateMsg', 'state', 'countryCode']:
                continue  # Saltar estos atributos
            
            if attribute == 'geom':
                geom = QgsGeometry.fromWkt(value)
                feature.setGeometry(geom)
            else:
                feature.setAttribute(attribute, value if value is not None else '')

        pr = layer.dataProvider()
        pr.addFeature(feature)
        layer.updateExtents()

    def zoom_to_layer(self, layer: QgsVectorLayer) -> None:
        """Zoom to the extent of the specified layer.

        This method centers the map on the newly created or updated layer by
        setting the map canvas extent to the layer's extent and refreshing the canvas.

        Args:
            layer (QgsVectorLayer): The layer whose extent will be zoomed to.
        """
        # Centrar el mapa en la capa recién creada
        extent = layer.extent()
        if extent:
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
