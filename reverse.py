import json
import os
from typing import List, Dict, Union

from qgis.PyQt.QtWidgets import (
    QWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
    QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QAbstractScrollArea
)
from qgis.PyQt.QtCore import Qt, QUrl, QMetaType
from qgis.PyQt import QtNetwork

from qgis.gui import QgisInterface, QgsMapToolEmitPoint
from qgis.core import (
    QgsPointXY, QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject,
    QgsFields, QgsField, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsRectangle, QgsLayerTreeLayer
)

from .compat import CompatQt as CQt


class ReverseTab(QWidget):
    # Widget para hacer el reverse y capturar coordenadas en el mapa y devuelva la dirección
    def __init__(self, parent: QWidget, iface: QgisInterface) -> None:
        super().__init__(parent)
        self.iface = iface
        self.create_layout()

    def create_layout(self) -> None:
        reverse_layout = QVBoxLayout()
        self.setLayout(reverse_layout)

        capture_button = QPushButton("Capturar coordenadas del mapa")
        capture_button.clicked.connect(self.capture_coordinates_from_map)
        reverse_layout.addWidget(capture_button)

        search_button = QPushButton("Buscar por coordenadas")
        search_button.clicked.connect(self.search_by_reverse)
        reverse_layout.addWidget(search_button)

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

        self.reverse_results_table = QTableWidget()
        self.reverse_results_table.setColumnCount(7)
        self.reverse_results_table.setHorizontalHeaderLabels(
            ['Tipo_via', 'Dirección', 'Número/pk', 'Extension', 'CCPP', 'Población', 'Municipio']
        )

        header = self.reverse_results_table.horizontalHeader()
        for col in range(self.reverse_results_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        reverse_layout.addWidget(self.reverse_results_table)

        buttons_layout = QHBoxLayout()

        clear_table_button = QPushButton("Limpiar tabla")
        clear_table_button.clicked.connect(self.clear_table)
        buttons_layout.addWidget(clear_table_button)

        clear_selection_button = QPushButton("Borrar selección")
        clear_selection_button.clicked.connect(self.clear_selection)
        buttons_layout.addWidget(clear_selection_button)

        select_all_button = QPushButton("(De)Seleccionar todo")
        select_all_button.clicked.connect(self.select_all_rows)
        buttons_layout.addWidget(select_all_button)

        create_layer_button = QPushButton("Crear capa")
        create_layer_button.clicked.connect(self.create_layer)
        buttons_layout.addWidget(create_layer_button)

        reverse_layout.addLayout(buttons_layout)

        self.reverse_results = []
        self.reverse = ReverseCoding(
            self.reverse_results_table,
            self.coord_x,
            self.coord_y,
            self.iface,
            self.reverse_results
        )

    def select_all_rows(self) -> None:
        selected_rows = self.reverse_results_table.selectionModel().selectedRows()
        if selected_rows:
            self.reverse_results_table.clearSelection()
        else:
            for row in range(self.reverse_results_table.rowCount()):
                self.reverse_results_table.selectRow(row)

    def create_layer(self) -> None:
        selected_rows = self.reverse_results_table.selectionModel().selectedRows()

        if not selected_rows:
            QMessageBox.warning(None, "¡Atención!", "No hay filas seleccionadas para crear la capa.")
            return

        selected_data = []
        for index in selected_rows:
            item = self.reverse_results_table.item(index.row(), 0)
            if item:
                data = item.data(CQt.UserRole)
                if data:
                    selected_data.append(data)

        if not selected_data:
            QMessageBox.warning(None, "Error", "No se pudo recuperar ningún dato válido de la selección.")
            return

        self.reverse.create_reverse_layer("resultados reverse", "Point", selected_data)

    def search_by_reverse(self) -> None:
        lon = self.coord_x.text().replace(',', '.')
        lat = self.coord_y.text().replace(',', '.')

        if lon and lat:
            self.reverse.search_by_coordinates(lon, lat)
        else:
            QMessageBox.warning(self, "Campos incompletos", "Debe introducir ambas coordenadas.")

    def capture_coordinates_from_map(self) -> None:
        self.reverse.start_capture()

    def clear_table(self) -> None:
        self.reverse.clear_table()

    def clear_selection(self) -> None:
        self.reverse.clear_selection()


class ReverseCoding:
    def __init__(
        self,
        table_widget: QTableWidget,
        coord_x: QLineEdit,
        coord_y: QLineEdit,
        iface: QgisInterface,
        reverse_results: list
    ) -> None:
        self.table_widget = table_widget
        self.coord_x = coord_x
        self.coord_y = coord_y
        self.iface = iface
        self.network_manager = QtNetwork.QNetworkAccessManager()
        self.layers = {}
        self.fields = None
        self.results = []
        self.reverse_results = reverse_results

        self.map_tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.handle_map_click)

        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.table_widget.setWordWrap(True)

        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

    def handle_map_click(self, point: QgsPointXY) -> None:
        crs_destino = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        crs_proyecto = QgsProject.instance().crs()
        transform = QgsCoordinateTransform(crs_proyecto, crs_destino, QgsProject.instance())
        punto_transformado = transform.transform(point)

        lon = punto_transformado.x()
        lat = punto_transformado.y()

        if self.coord_x is not None and self.coord_y is not None:
            self.coord_x.setText(str(lon))
            self.coord_y.setText(str(lat))
            print(f"Coordenadas capturadas: Lon = {lon}, Lat = {lat}")
            self.search_by_coordinates(lon, lat)
        else:
            QMessageBox.critical(None, "Error", "QLineEdit objects have been deleted.")

    def start_capture(self) -> None:
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def search_by_coordinates(self, lon: float, lat: float) -> None:
        if lon and lat:
            print(f"Buscando por coordenadas Lon: {lon}, Lat: {lat}")
            url = f"https://www.cartociudad.es/geocoder/api/geocoder/reverseGeocode?lon={lon}&lat={lat}"
            print(f"Haciendo petición a: {url}")
            req = QtNetwork.QNetworkRequest(QUrl(url))

            try:
                self.network_manager.finished.disconnect(self.handle_reverse_response)
            except TypeError:
                pass

            self.network_manager.finished.connect(self.handle_reverse_response)
            self.network_manager.get(req)

    def handle_reverse_response(self, reply: QtNetwork.QNetworkReply) -> None:
        er = reply.error()
        if er == QtNetwork.QNetworkReply.NetworkError.NoError:
            bytes_string = reply.readAll()
            response = str(bytes_string, 'utf-8')

            if not response.strip():
                QMessageBox.critical(None, "Error", "Respuesta vacía de la API.")
                self.update_table_with_no_response()
                return

            try:
                reverse_data = json.loads(response)

                if "geom" not in reverse_data:
                    QMessageBox.critical(None, "Error", "La respuesta no contiene el campo 'geom'.")
                    return

                self.results.append(reverse_data)
                self.update_table(reverse_data)

            except json.JSONDecodeError as e:
                QMessageBox.critical(None, "Error", f"Error al decodificar la respuesta JSON: {e}")
        else:
            QMessageBox.critical(
                None,
                "Error",
                f"Error en la petición Reverse Geocoding: {reply.errorString()}"
            )
            self.update_table_with_no_response()

        try:
            self.network_manager.finished.disconnect(self.handle_reverse_response)
        except TypeError:
            pass

    def update_table(self, reverse_data: Dict[str, Union[str, int]]) -> None:
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)

        tipo_via = reverse_data.get('tip_via', 'N/A')
        address = reverse_data.get('address', 'N/A')
        portal_number = reverse_data.get('portalNumber', 'N/A')
        extension = reverse_data.get('extension', 'N/A')
        postal_code = reverse_data.get('postalCode', 'N/A')
        poblacion = reverse_data.get('poblacion', 'N/A')
        municipio = reverse_data.get('muni', 'N/A')

        items = [
            QTableWidgetItem(tipo_via),
            QTableWidgetItem(address),
            QTableWidgetItem(str(portal_number)),
            QTableWidgetItem(str(extension)),
            QTableWidgetItem(str(postal_code)),
            QTableWidgetItem(poblacion),
            QTableWidgetItem(municipio)
        ]

        items[0].setData(CQt.UserRole, reverse_data)

        for col, item in enumerate(items):
            item.setFlags(item.flags() & ~CQt.ItemIsEditable)
            item.setTextAlignment(CQt.AlignLeft | CQt.AlignVCenter)
            self.table_widget.setItem(row_position, col, item)

        self.reverse_results.append(reverse_data)

        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.resizeRowsToContents()
        self.table_widget.resizeColumnsToContents()
        self.table_widget.resizeRowsToContents()

        header = self.table_widget.horizontalHeader()
        for col in range(self.table_widget.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

        self.table_widget.updateGeometry()
        self.table_widget.repaint()

    def update_table_with_no_response(self) -> None:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText("Sin respuesta")
        msg_box.setWindowTitle("Geocodificación Inversa")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def clear_table(self) -> None:
        self.table_widget.setRowCount(0)
        self.results.clear()
        self.reverse_results.clear()

    def clear_selection(self) -> None:
        selected_rows = self.table_widget.selectionModel().selectedRows()
        for index in sorted(selected_rows, reverse=True):
            self.table_widget.removeRow(index.row())
            if index.row() < len(self.results):
                del self.results[index.row()]
            if index.row() < len(self.reverse_results):
                del self.reverse_results[index.row()]

    def create_reverse_layer(self, base_layer_name, geometry_type, data_list):
        excluded_attributes = ['state', 'stateMsg', 'countryCode', 'x', 'y', 'noNumber']

        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup("Resultados_reverse")
        if not group:
            group = root.addGroup("Resultados_reverse")

        last_layer = None

        for data in data_list:
            if data is None:
                continue

            tip_via = str(data.get("tip_via", "")).strip().replace(" ", "_")
            address = str(data.get("address", "")).strip().replace(" ", "_")
            portal_number = str(data.get("portalNumber", "")).strip().replace(" ", "_")
            poblacion = str(data.get("poblacion", "")).strip().replace(" ", "_")
            extension = str(data.get("extension", "") or "").strip().replace(" ", "_")

            if extension:
                base_name = f"{tip_via}_{address}_{portal_number}{extension}_{poblacion}"
            else:
                base_name = f"{tip_via}_{address}_{portal_number}_{poblacion}"

            if not base_name or base_name == "___":
                base_name = "Sin_nombre"

            layer_name = base_name
            i = 1
            while any(child.name() == layer_name for child in group.children()):
                i += 1
                layer_name = f"{base_name}_{i}"

            existing_layer = QgsProject.instance().mapLayersByName(layer_name)
            if existing_layer:
                layer = existing_layer[0]
                group.insertChildNode(0, QgsLayerTreeLayer(layer))
                last_layer = layer
                if hasattr(self, "layers") and layer_name not in self.layers:
                    self.layers[layer_name] = layer
                continue

            layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
            pr = layer.dataProvider()

            fields = QgsFields()
            for key, value in data.items():
                if key in excluded_attributes or key == "geom":
                    continue
                if isinstance(value, int):
                    field_type = QMetaType.Type.Int
                elif isinstance(value, float):
                    field_type = QMetaType.Type.Double
                elif isinstance(value, bool):
                    field_type = QMetaType.Type.Bool
                else:
                    field_type = QMetaType.Type.QString
                fields.append(QgsField(key, type=field_type))

            pr.addAttributes(fields)
            layer.updateFields()

            base_path = os.path.dirname(__file__)
            qml_path = os.path.join(base_path, 'estilos', 'Reverse.qml')
            if os.path.exists(qml_path):
                layer.loadNamedStyle(qml_path)
                layer.triggerRepaint()

            print("geom WKT:", data.get("geom"))

            geom_wkt = data.get("geom")
            if not geom_wkt:
                print("No se encontró geometría WKT en los datos.")
                continue

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromWkt(geom_wkt))
            feature.setAttributes([data.get(field.name(), "") for field in fields])
            pr.addFeature(feature)
            layer.updateExtents()

            QgsProject.instance().addMapLayer(layer, False)
            group.insertChildNode(0, QgsLayerTreeLayer(layer))
            last_layer = layer

            if hasattr(self, "layers"):
                self.layers[layer_name] = layer

        if last_layer is not None:
            self.zoom_to_layer(last_layer)

    def create_attributes_from_json(self, location: Dict[str, Union[str, int, float]]) -> None:
        self.fields = QgsFields()
        excluded_attributes = ['stateMsg', 'state', 'countryCode']

        for attribute, value in location.items():
            if attribute != 'geom' and attribute not in excluded_attributes:
                if isinstance(value, int):
                    field_type = QMetaType.Type.Int
                elif isinstance(value, float):
                    field_type = QMetaType.Type.Double
                elif isinstance(value, bool):
                    field_type = QMetaType.Type.Bool
                else:
                    field_type = QMetaType.Type.QString
                self.fields.append(QgsField(attribute, type=field_type))

    def add_feature_to_layer(self, attributes: Dict[str, Union[str, int, float]], layer_name: str) -> None:
        layer = self.layers[layer_name]
        if layer and layer.isValid():
            feature = QgsFeature()
            feature.setFields(self.fields)

            for attribute, value in attributes.items():
                if attribute in ['stateMsg', 'state', 'countryCode']:
                    continue

                if attribute == 'geom':
                    geom = QgsGeometry.fromWkt(value)
                    feature.setGeometry(geom)
                else:
                    feature.setAttribute(attribute, value if value is not None else '')

            pr = layer.dataProvider()
            pr.addFeature(feature)
            layer.updateExtents()

    def reproject_extent(
        self,
        extent: QgsRectangle,
        source_crs: QgsCoordinateReferenceSystem,
        dest_crs: QgsCoordinateReferenceSystem
    ) -> QgsRectangle:
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        extent_transformado = transform.transformBoundingBox(extent)
        return extent_transformado

    def zoom_to_layer(self, layer: QgsVectorLayer) -> None:
        extent = layer.extent()
        if extent:
            project_crs = QgsProject.instance().crs()
            extent = self.reproject_extent(extent, layer.crs(), project_crs)

        self.iface.mapCanvas().setExtent(extent)
        self.iface.mapCanvas().refresh()

