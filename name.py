import os
import json
from typing import List, Dict, Any, Union, Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox
from PyQt5.QtCore import QUrl, Qt, QVariant
from PyQt5.QtGui import QBrush, QColor
from PyQt5 import QtNetwork
from PyQt5.QtWidgets import QHeaderView
from qgis.gui import QgisInterface
from qgis.core import (QgsProject, QgsApplication, QgsCoordinateReferenceSystem,QgsCoordinateTransform,
                       QgsVectorLayer, QgsGeometry, QgsFeature, QgsFields, QgsField, QgsWkbTypes, QgsLayerTreeLayer, QgsSymbol, QgsSingleSymbolRenderer)


LIMIT = 35
API_GEOCODER = 'https://www.cartociudad.es/geocoder/api/geocoder'

class NameTab(QWidget):
    def __init__(self, parent: QWidget, iface: QgisInterface) -> None:

        super().__init__(parent)

        # Añadir carpeta SVG personalizada a las rutas de QGIS
        base_path = os.path.dirname(__file__)
        svg_path = os.path.join(base_path, 'estilos','svg')
        svg_paths = QgsApplication.svgPaths()
        if svg_path not in svg_paths:
            svg_paths.append(svg_path)
            QgsApplication.setDefaultSvgPaths(svg_paths)
        print(QgsApplication.svgPaths())
        self.iface = iface
        self.layers = {}
        self.create_layout()

    def create_layout(self) -> None:

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
        self.tabla_resultados.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tabla_resultados.setSelectionMode(QAbstractItemView.SingleSelection)

        # Ajustar el comportamiento de las columnas para que se expandan
        self.tabla_resultados.horizontalHeader().setStretchLastSection(True)
        self.tabla_resultados.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Añadir la tabla al layout
        layout.addWidget(self.tabla_resultados)

        # Conectar el botón de búsqueda a la función
        self.buscar.clicked.connect(self.on_search_name)
        self.localizacion.returnPressed.connect(self.on_search_name) 
        self.cp.returnPressed.connect(self.on_search_name)
        # Conectar el evento de doble clic en la celda y número de fila
        self.tabla_resultados.cellDoubleClicked.connect(self.find_location)
        self.tabla_resultados.verticalHeader().sectionDoubleClicked.connect(self.handle_row_double_click)
        # Resaltar la columna de tipo al seleccionar una fila:
        self.tabla_resultados.itemSelectionChanged.connect(self.highlight_tipo_column)

    def on_search_name(self) -> None:

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

        print(f"Haciendo petición a la URL: {url}")
        self.manager_candidates = QtNetwork.QNetworkAccessManager()
        self.manager_candidates.finished.connect(self.show_candidates)
        req = QtNetwork.QNetworkRequest(QUrl(url))
        self.manager_candidates.get(req)

    def show_candidates(self, reply: QtNetwork.QNetworkReply) -> None:

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

        # Asegurarse de seleccionar la fila completa cuando se selecciona una celda
        self.tabla_resultados.selectRow(row)

        # Obtiene el texto de la celda seleccionada, que contiene la dirección
        address = self.tabla_resultados.item(row, 0).text()
        # Ahora obtenemos el ID del candidato asociado a esa fila
        candidate_id = self.tabla_resultados.item(row, 0).data(Qt.UserRole)

        # También obtenemos el valor del tipo de la celda correspondiente
        candidate_type = self.tabla_resultados.item(row, 1).text()
        # Construimos la URL con la dirección, el id y el tipo
        url = f'{API_GEOCODER}/find?id={candidate_id}&type={candidate_type}'
        self.get_location(url)
        print(f'Buscar: {url}')

    def handle_row_double_click(self, row):

        # Selecciona la fila completa cuando se hace doble clic en el número de la fila
        self.tabla_resultados.selectRow(row)
        # Llamamos a la misma función find_location que cuando se hace clic en una celda
        self.find_location(row, 0)  # Pasamos la fila y columna 0 por defecto

    def get_location(self, url):

        self.manager_locate = QtNetwork.QNetworkAccessManager()
        self.manager_locate.finished.connect(self.draw_location)
        req = QtNetwork.QNetworkRequest(QUrl(url))
        self.manager_locate.get(req)

    def draw_location(self, reply: QtNetwork.QNetworkReply) -> None:

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
        wkt = location['geom']
        location_type = location['type']
        new_geometry_type = self.get_geometry_type(wkt)

        # Crear la capa (si no existe) y obtener su nombre
        layer_name = self.create_layer(new_geometry_type, location)

        # Agregar la geometría a la capa correspondiente
        self.add_feature_to_layer(location, layer_name)

    
    
    def create_layer(self, geometry_type: str, location: Dict[str, Union[str, List[str]]]) -> str:
        location_type = location.get("type", "").lower()
        location_address = location.get("address")

        if not location_type:
            raise ValueError("El campo 'type' no está definido en la ubicación.")

        grupos = {
            'callejero': 'Viales',
            'carretera': 'Viales',
            'expendeduria': 'Puntos_interes',
            'punto_recarga_electrica': 'Puntos_interes',
            'ngbe': 'Puntos_interes',
            'toponimo': 'Puntos_interes',
            'poblacion': 'Poblaciones',
            'portal': 'Portales_pk',
            'municipio': 'Municipios',
            'provincia': 'Provincias',
            'comunidad autonoma': 'Comunidades_sim',
            'codpost': 'Codigos_postales',
            'refcatastral': 'Referencia_catastral'
        }

        group_name = grupos.get(location_type, "Otro")

        # Obtener o crear el grupo en el panel de capas
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(group_name)
        if group is None:
            group = root.addGroup(group_name)

        # Obtener nombres de capas solo dentro de este grupo
        group_layer_names = [child.layer().name() for child in group.children() if isinstance(child, QgsLayerTreeLayer)]

        # Personalización del nombre según el grupo
        if group_name in "Municipios":
            municipio = (location.get("muni") or "").strip().replace(" ", "_") 
            base_name = f"{municipio}_{location_type}"
        elif group_name == "Poblaciones":
            poblacion = (location.get("poblacion") or "").strip().replace(" ", "_")
            base_name = f"{poblacion}_{location_type}"
        elif group_name == "Provincias":
            provincia = (location.get("province") or "").strip().replace(" ", "_")
            base_name = f"{provincia}_{location_type}"
        elif group_name == "Viales":
            tip_via = (location.get("tip_via") or "").strip().replace(" ", "_")
            poblacion = (location.get("poblacion") or "").strip().replace(" ", "_")
            base_name = f"{tip_via}_{location_address}_{poblacion}"
        elif group_name == "Codigos_postales":
            cod_postal = (location.get("postalCode") or "").strip().replace(" ", "_")  
            base_name = f"{cod_postal}" 
        elif group_name == "Portales_pk":
            tip_via = (location.get("tip_via") or "").strip().replace(" ", "_")
            portal = str(location.get("portalNumber") or "").strip().replace(" ", "_")
            poblacion = (location.get("poblacion") or "").strip().replace(" ", "_")
            extension= location.get("extension", "").strip().replace(" ", "_")
            base_name = f"{tip_via}_{location_address}_{portal}{extension}_{poblacion}"
        else:
            base_name = str(location_address).strip().replace(" ", "_") if location_address else "Sin_nombre"

        # Asegurar nombre único dentro del grupo
        layer_name = base_name
        i = 1
        while layer_name in group_layer_names:
            i += 1
            layer_name = f"{base_name}_{i}"

        # Si ya existe en self.layers, no crearla de nuevo
        if layer_name in self.layers and self.layers[layer_name] is not None:
            return layer_name

        # Crear la capa
        layer = QgsVectorLayer(geometry_type, layer_name, "memory")
        crs = QgsCoordinateReferenceSystem('EPSG:4326')
        layer.setCrs(crs)

        # Aplicar estilo QML si existe
        base_path = os.path.dirname(__file__)

        estilo_por_grupo = {
            'Viales': {
                'carretera': os.path.join(base_path, 'estilos', 'Carretera_Viales.qml'),
                'callejero': os.path.join(base_path, 'estilos', 'Callejero_Viales.qml')
            },
            'Puntos_interes': {
                'expendeduria': os.path.join(base_path, 'estilos', 'Puntos_interes_expendeduria.qml'),
                'punto_recarga_electrica': os.path.join(base_path, 'estilos', 'Puntos_interes_recarga.qml'),
                'ngbe': os.path.join(base_path, 'estilos', 'Puntos_interes_ngbe.qml'),
                'toponimo': os.path.join(base_path, 'estilos', 'Puntos_interes_toponimo.qml')
            },
            'Poblaciones': os.path.join(base_path, 'estilos', 'Poblaciones.qml'),
            'Portales_pk': os.path.join(base_path, 'estilos', 'Portales_pk.qml'),
            'Municipios': os.path.join(base_path, 'estilos', 'Municipios.qml'),
            'Provincias': os.path.join(base_path, 'estilos', 'Provincias.qml'),
            'Comunidades_sim': os.path.join(base_path, 'estilos', 'Comunidades_sim.qml'),
            'Codigos_postales': os.path.join(base_path, 'estilos', 'Codigos_postales.qml'),
            'Referencia_catastral': os.path.join(base_path, 'estilos', 'Referencia_catastral.qml')
        }

        _path = None
        if group_name in ['Viales', 'Puntos_interes']:
            qml_dict = estilo_por_grupo.get(group_name, {})
            qml_path = qml_dict.get(location_type)
        else:
            qml_path = estilo_por_grupo.get(group_name)

        if qml_path and os.path.exists(qml_path):
            layer.loadNamedStyle(qml_path)
            layer.triggerRepaint()

        # Crear los campos desde los atributos del JSON
        self.fields = QgsFields()
        self.create_attributes_from_json(location, exclude_keys=['geom', 'stateMsg', 'state', 'countryCode', 'noNumber'])

        # Añadir los campos a la capa
        layer.dataProvider().addAttributes(self.fields)
        layer.updateFields()

        # Guardar la capa
        self.layers[layer_name] = layer
        QgsProject.instance().addMapLayer(layer, False)

        # Añadir al grupo correspondiente
        group.addLayer(layer)

        return layer_name



        
        pr = self.layers[layer_name].dataProvider()
        pr.addAttributes(self.fields)
        self.layers[layer_name].updateFields()
        # QgsProject.instance().addMapLayer(self.layers[layer_name])

    def get_geometry_type(self, wkt: str) -> str:

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

        if exclude_keys is None:
            exclude_keys = []
        
        for attribute, value in location.items():
            # Excluir los atributos específicos
            if attribute not in exclude_keys and attribute != 'geom':
                self.fields.append(QgsField(attribute, QVariant.String))

    def add_feature_to_layer(self, attributes: Dict[str, Union[Any, List[Any]]], layer_name: str) -> None:
        layer = self.layers.get(layer_name)

        # Si la capa no existe o ha sido eliminada, la recreamos automáticamente
        if (
            layer is None
            or not QgsProject.instance().mapLayersByName(layer_name)
            or not layer.isValid()
        ):
            # Eliminar referencia interna si la capa ya no existe
            if layer_name in self.layers:
                del self.layers[layer_name]
            # Recrear la capa usando los atributos actuales
            geometry_type = self.get_geometry_type(attributes['geom'])
            layer_name = self.create_layer(geometry_type, attributes)
            layer = self.layers[layer_name]

        # Agregar una característica (punto o polígono) a la capa y hacer zoom en esa geometría
        feature = QgsFeature()
        feature.setFields(layer.fields())

        for attribute, value in attributes.items():
            if attribute == 'geom':
                geom = QgsGeometry.fromWkt(value)
                if not geom.isGeosValid():
                    print(f"Geometría no válida detectada. Intentando corregir...")
                    geom = geom.buffer(0, 5)
                    if not geom.isGeosValid():
                        QMessageBox.warning(None, "¡Atención!", "La geometría no es válida.")
                        print("La geometría sigue siendo inválida después de la corrección.")
                        return
                feature.setGeometry(geom)
            else:
                if attribute in [field.name() for field in layer.fields()]:
                    feature.setAttribute(attribute, str(value))

        pr = layer.dataProvider()
        pr.addFeature(feature)
        layer.updateExtents()

        if geom.wkbType() in [QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon]:
            self.zoom_to_bounding_box(geom, layer.crs())
        else:
            self.zoom_to_geometry(geom, layer.crs())

    def zoom_to_bounding_box(self, geom: QgsGeometry, layer_crs: QgsCoordinateReferenceSystem) -> None:
        # Calcular y hacer zoom al bounding box de la geometría (polígono o multipolígono)
        if geom is not None and geom.isGeosValid():
            geom = self.reproject_geometry(geom, layer_crs)
            extent = geom.boundingBox()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()

    def zoom_to_geometry(self, geom: QgsGeometry, layer_crs: QgsCoordinateReferenceSystem) -> None:
        # Centrar el mapa en la geometría proporcionada (punto o línea)
        if geom is not None and geom.isGeosValid():
            geom = self.reproject_geometry(geom, layer_crs)
            extent = geom.boundingBox()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()

    def reproject_geometry(self, geom: QgsGeometry, layer_crs: QgsCoordinateReferenceSystem) -> QgsGeometry:
        # Reproyectar la geometría al sistema de coordenadas del proyecto
        crs_dest = self.iface.mapCanvas().mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(layer_crs, crs_dest, QgsProject.instance())
        geom.transform(transform)
        return geom



    def highlight_tipo_column(self):
        # Limpia el fondo y el color de texto de todas las celdas de la columna "Tipo"
        for row in range(self.tabla_resultados.rowCount()):
            item = self.tabla_resultados.item(row, 1)
            if item:
                item.setBackground(QBrush())
                item.setForeground(QBrush())

        # Por defecto, encabezado "Tipo" no en negrita
        header = self.tabla_resultados.horizontalHeaderItem(1)
        if header:
            font = header.font()
            font.setBold(False)
            header.setFont(font)

        selected_items = self.tabla_resultados.selectedItems()
        if selected_items:
            selected_item = selected_items[0]
            row = selected_item.row()
            col = selected_item.column()
            tipo_item = self.tabla_resultados.item(row, 1)
            if tipo_item:
                selection_color = self.tabla_resultados.palette().color(self.tabla_resultados.palette().Highlight)
                tipo_item.setBackground(QBrush(selection_color))
                tipo_item.setForeground(QBrush(QColor(255, 255, 255)))
            # Si la celda seleccionada es de la columna "Candidatos", poner encabezado "Tipo" en negrita
            if col == 0 and header:
                font.setBold(True)
                header.setFont(font)
