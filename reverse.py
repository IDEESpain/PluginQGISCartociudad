import json
import os
from typing import List, Dict, Union

from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, QMessageBox
from PyQt5.QtCore import Qt, QUrl, QVariant
from PyQt5 import QtNetwork
from qgis.gui import QgisInterface, QgsMapToolEmitPoint
from qgis.core import QgsPointXY, QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject, QgsFields, QgsField, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle, QgsLayerTreeLayer

class ReverseTab(QWidget):
    
    # Widget para hacer el reverse y capturar coordenadas en el mapa y devuelva la dirección o capturar las coordenadas y devuelva dirección
    def __init__(self, parent: QWidget, iface: QgisInterface) -> None:
   
        super().__init__(parent)
        self.iface = iface
        self.create_layout()
        
    def create_layout(self) -> None:

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
        self.coord_x.returnPressed.connect(self.search_by_reverse)
        self.coord_x.setPlaceholderText("Introduzca longitud geográfica")
        self.coord_y = QLineEdit()
        self.coord_y.returnPressed.connect(self.search_by_reverse)
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

        # Botón "Seleccionar todo"
        select_all_button = QPushButton("(De)Seleccionar todo")
        select_all_button.clicked.connect(self.select_all_rows)
        buttons_layout.addWidget(select_all_button)

        # Botón "Crear capa"
        create_layer_button = QPushButton("Crear capa")
        create_layer_button.clicked.connect(self.create_layer)
        buttons_layout.addWidget(create_layer_button)

        reverse_layout.addLayout(buttons_layout)

        # Inicializar la clase Reverse con la tabla de resultados
        
        self.reverse_results = []
        self.reverse = ReverseCoding(self.reverse_results_table, self.coord_x, self.coord_y, self.iface, self.reverse_results)

    def select_all_rows(self) -> None:
        selected_rows = self.reverse_results_table.selectionModel().selectedRows()
        if selected_rows:
            # Si hay alguna fila seleccionada, deselecciona todas
            self.reverse_results_table.clearSelection()
        else:
            # Si no hay ninguna seleccionada, selecciona todas
            for row in range(self.reverse_results_table.rowCount()):
                self.reverse_results_table.selectRow(row)

    def create_layer(self) -> None:
        # Obtener los datos necesarios para crear la capa
        selected_rows = self.reverse_results_table.selectionModel().selectedRows()

        if not selected_rows:
            QMessageBox.warning(None, "¡Atención!", "No hay filas seleccionadas para crear la capa.")
            return

        selected_data = []
        for index in selected_rows:
            item = self.reverse_results_table.item(index.row(), 0)
            if item:
                data = item.data(Qt.UserRole)
                if data:
                    selected_data.append(data)

        if not selected_data:
            QMessageBox.warning(None, "Error", "No se pudo recuperar ningún dato válido de la selección.")
            return

        # Crear la capa directamente con los datos seleccionados
        self.reverse.create_reverse_layer("resultados reverse", "Point", selected_data)

    def search_by_reverse(self) -> None:

        lon = self.coord_x.text().replace(',', '.')
        lat = self.coord_y.text().replace(',', '.')
        if lon and lat:
            self.reverse.search_by_coordinates(lon, lat)
        else:
            QMessageBox.warning(self, "Campos incompletos", "Debe introducir ambas coordenadas.")


        # Llamar al método de la clase Reverse
        self.reverse.search_by_coordinates(lon, lat)

    #Capturar  coordenadas en mapa
    def capture_coordinates_from_map(self) -> None:

        self.reverse.start_capture()

    def clear_table(self) -> None:
 
        self.reverse.clear_table()

    def clear_selection(self) -> None:

        self.reverse.clear_selection()

    
class ReverseCoding:

    
    def __init__(self, table_widget: QTableWidget, coord_x: QLineEdit, coord_y: QLineEdit, iface: QgisInterface, reverse_results: list) -> None:

        # Inicializar la clase Reverse con el widget de tabla, cajas de coordenadas y la interfaz de QGIS
        self.table_widget = table_widget  # Referencia a la tabla de resultados
        self.coord_x = coord_x  # Caja de texto para coordenada X (lon)
        self.coord_y = coord_y  # Caja de texto para coordenada Y (lat)
        self.iface = iface  # Referencia a la interfaz de QGIS
        self.network_manager = QtNetwork.QNetworkAccessManager()  # Manager de red para hacer las peticiones
        self.layers = {}  # Diccionario para manejar las capas dinámicamente
        self.fields = None
        self.results = []  # Lista para almacenar los resultados de la petición
        self.reverse_results = reverse_results
        
        # Habilitar el uso del clic en el mapa de QGIS para capturar coordenadas
        self.map_tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.handle_map_click)

        # Configurar el comportamiento de la tabla para ajustarse a la ventana
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Selección de múltiples filas completas
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)  # Selección por fila completa
        self.table_widget.setSelectionMode(QAbstractItemView.MultiSelection)  # Permitir selección múltiple

    def handle_map_click(self, point: QgsPointXY) -> None:
        # Definir el sistema de referencia de destino (EPSG:4326)
        crs_destino = QgsCoordinateReferenceSystem(4326)
    
        # Obtener el sistema de referencia del proyecto actual
        crs_proyecto = QgsProject.instance().crs()
    
        # Crear el transformador de coordenadas
        transform = QgsCoordinateTransform(crs_proyecto, crs_destino, QgsProject.instance())
    
        # Transformar el punto
        punto_transformado = transform.transform(point)
    
        # Capturar las coordenadas transformadas
        lon = punto_transformado.x()
        lat = punto_transformado.y()
    
        if self.coord_x is not None and self.coord_y is not None:
            self.coord_x.setText(str(lon))
            self.coord_y.setText(str(lat))
            print(f"Coordenadas capturadas: Lon = {lon}, Lat = {lat}", 5000)
            self.search_by_coordinates(lon, lat)
        else:
            QMessageBox.critical(None, "Error", "QLineEdit objects have been deleted.")

    def start_capture(self) -> None:

        # Método para iniciar la captura de coordenadas desde el mapa
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def search_by_coordinates(self, lon: float, lat: float) -> None:

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

                # Verificar que 'geom' esté presente
                if "geom" not in reverse_data:
                    QMessageBox.critical(None, "Error", "La respuesta no contiene el campo 'geom'.")
                    return

                self.results.append(reverse_data)
                self.update_table(reverse_data)

            except json.JSONDecodeError as e:
                QMessageBox.critical(None, "Error", f"Error al decodificar la respuesta JSON: {e}")
        else:
            QMessageBox.critical(None, "Error", f"Error en la petición Reverse Geocoding: {reply.errorString()}")
            self.update_table_with_no_response()

        # Desconectar la señal para evitar múltiples ejecuciones
        self.network_manager.finished.disconnect(self.handle_reverse_response)

    def update_table(self, reverse_data: Dict[str, Union[str, int]]) -> None:

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
        
        # Guardar reverse_data en el primer item
        items[0].setData(Qt.UserRole, reverse_data)

        for col, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Hacer los items no editables
            self.table_widget.setItem(row_position, col, item)

        self.reverse_results.append(reverse_data)

        # Ajuste explícito de la última columna
        self.table_widget.horizontalHeader().setStretchLastSection(True)

        # Ajustar el layout y las filas después de insertar nuevas filas
        self.table_widget.resizeRowsToContents()  # Ajustar el tamaño de las filas
        self.table_widget.updateGeometry()  # Actualizar la geometría del layout del widget
        self.table_widget.repaint()  # Redibujar la tabla para forzar el ajuste visual

    def update_table_with_no_response(self) -> None:
 
        # Mostrar una ventana de mensaje cuando no haya respuesta de la API
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("Sin respuesta")
        msg_box.setWindowTitle("Geocodificación Inversa")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def clear_table(self) -> None:

        # Limpiar todos los elementos de la tabla
        self.table_widget.setRowCount(0)
        self.results.clear()  # Limpiar los resultados almacenados

    def clear_selection(self) -> None:

        # Eliminar los elementos seleccionados en la tabla
        selected_rows = self.table_widget.selectionModel().selectedRows()
        for index in sorted(selected_rows, reverse=True):
            self.table_widget.removeRow(index.row())
            del self.results[index.row()]  # Eliminar también de la lista de resultados

    def create_reverse_layer(self, base_layer_name, geometry_type, data_list):

        # Campos a excluir
        excluded_attributes = ['state', 'stateMsg', 'countryCode', 'x', 'y', 'noNumber']

        # Crear o obtener el grupo "reverse"
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup("Resultados_reverse")
        if not group:
            group = root.addGroup("Resultados_reverse")

        last_layer = None  # Para guardar la última capa creada

        for data in data_list:
            if data is None:
                    continue
            tip_via = str(data.get("tip_via", "")).strip().replace(" ", "_")
            address = str(data.get("address", "")).strip().replace(" ", "_")
            portalNumber = str(data.get("portalNumber", "")).strip().replace(" ", "_")
            poblacion = str(data.get("poblacion", "")).strip().replace(" ", "_")
            extension = str(data.get("extension", "") or "").strip().replace(" ", "_")

            # Construir el nombre de la capa
            if extension:
                base_name = f"{tip_via}_{address}_{portalNumber}{extension}_{poblacion}"
            else:
                base_name = f"{tip_via}_{address}_{portalNumber}_{poblacion}"

            # Verificar si base_name está vacío o es igual a "___"
            if not base_name or base_name == "___":
                base_name = "Sin_nombre"

            
            # Asegurar nombre único dentro del grupo
            layer_name = base_name
            i = 1
            while any(child.name() == layer_name for child in group.children()):
                i += 1
                layer_name = f"{base_name}_{i}"

            
            # Si la capa ya existe en el proyecto, volver a insertarla en el grupo
            existing_layer = QgsProject.instance().mapLayersByName(layer_name)
            if existing_layer:
                layer = existing_layer[0]
                group.insertChildNode(0, QgsLayerTreeLayer(layer))
                last_layer = layer
                # Si ya existe en self.layers, no crearla de nuevo
                if hasattr(self, "layers") and layer_name not in self.layers:
                    self.layers[layer_name] = layer
                continue
                
            # Crear la capa de memoria con todos los atributos menos los excluidos
            layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
            pr = layer.dataProvider()

            # Crear campos dinámicamente según los atributos del JSON, excluyendo los no deseados
            fields = QgsFields()
            for key, value in data.items():
                if key in excluded_attributes or key == "geom":
                    continue
                if isinstance(value, int):
                    field_type = QVariant.Int
                elif isinstance(value, float):
                    field_type = QVariant.Double
                elif isinstance(value, bool):
                    field_type = QVariant.Bool
                else:
                    field_type = QVariant.String
                fields.append(QgsField(key, type=field_type))
            pr.addAttributes(fields)
            layer.updateFields()

            # Aplicar estilo QML si existe
            base_path = os.path.dirname(__file__)
            qml_path = os.path.join(base_path, 'estilos', 'Reverse.qml')  # Cambia por tu archivo QML
            if os.path.exists(qml_path):
                layer.loadNamedStyle(qml_path)
                layer.triggerRepaint()


            # Usar la geometría WKT si está disponible
            print("geom WKT:", data.get("geom"))
            
            geom_wkt = data.get("geom")
            if not geom_wkt:
                print("No se encontró geometría WKT en los datos.")
                continue

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromWkt(geom_wkt))
        
           # Asignar todos los atributos en el mismo orden que los campos
            feature.setAttributes([data.get(field.name(), "") for field in fields])
            pr.addFeature(feature)
            layer.updateExtents()

            QgsProject.instance().addMapLayer(layer, False)
            group.insertChildNode(0, QgsLayerTreeLayer(layer))
            last_layer = layer  # Guarda la referencia a la última capa creada

            # Registrar capa si usas self.layers
            if hasattr(self, "layers"):
                self.layers[layer_name] = layer

        # Al final del bucle, haz zoom solo una vez
        if last_layer is not None:
            self.zoom_to_layer(last_layer)

    def create_attributes_from_json(self, location: Dict[str, Union[str, int, float]]) -> None:

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
                self.fields.append(QgsField(attribute, type=field_type))

    def add_feature_to_layer(self, attributes: Dict[str, Union[str, int, float]], layer_name:str) -> None:

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


    def reproject_extent(self, extent: QgsRectangle, source_crs: QgsCoordinateReferenceSystem, dest_crs: QgsCoordinateReferenceSystem) -> QgsRectangle:
        # Crear el transformador de coordenadas
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())

        # Transformar el extent
        extent_transformado = transform.transformBoundingBox(extent)
    
        return extent_transformado

    def zoom_to_layer(self, layer: QgsVectorLayer) -> None:
        # Centrar el mapa en la capa recién creada
        extent = layer.extent()
        if extent:
            # Obtener el sistema de referencia del proyecto actual
            project_crs = QgsProject.instance().crs()
        
        # Reproyectar el extent al sistema de referencia del proyecto
            extent = self.reproject_extent(extent, layer.crs(), project_crs)
        
        self.iface.mapCanvas().setExtent(extent)
        self.iface.mapCanvas().refresh()


