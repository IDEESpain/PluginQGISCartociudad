import os
import json
import csv
import pandas as pd
from io import StringIO
from typing import List, Dict, Any, Union, Optional

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QMessageBox, QHeaderView,
    QDialogButtonBox, QListWidgetItem, QListWidget, QDialog, QSizePolicy,
    QToolButton, QFrame
)
from qgis.PyQt.QtCore import QUrl, Qt, QMetaType
from qgis.PyQt import QtNetwork
from qgis.PyQt.QtGui import QBrush, QColor, QPalette

from qgis.gui import QgisInterface
from qgis.core import (
    QgsProject, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsVectorLayer, QgsGeometry, QgsFeature, QgsFields, QgsField, QgsWkbTypes,
    QgsLayerTreeLayer
)

from .compat import CompatQt as CQt

try:
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen, URLError


LIMIT = 35
API_GEOCODER = 'https://www.cartociudad.es/geocoder/api/geocoder'


def _looks_like_html(raw_bytes, headers) -> bool:
    """Devuelve True si la respuesta parece HTML por content-type o contenido."""
    try:
        ct = headers.get_content_type()
        if ct and 'html' in ct.lower():
            return True
    except Exception:
        pass
    try:
        txt = raw_bytes.decode('utf-8', errors='ignore')
        if '<html' in txt.lower() or '<!doctype html' in txt.lower() or '<table' in txt.lower():
            return True
    except Exception:
        pass
    return False


def _detect_delimiter(sample_text: str) -> str:
    """Detecta el delimitador del CSV."""
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text)
        return dialect.delimiter
    except Exception:
        first = sample_text.splitlines()[0] if sample_text.splitlines() else ''
        return ';' if first.count(';') > first.count(',') else ','


class ComboDialog(QDialog):
    def __init__(self, items, selected_keys=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar elementos")
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for key, label in items.items():
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | CQt.ItemIsUserCheckable)
            item.setCheckState(CQt.Checked if selected_keys and key in selected_keys else CQt.Unchecked)
            item.setData(CQt.UserRole, key)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
        self.setFixedSize(self.size())

    def get_selected_items(self):
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == CQt.Checked:
                selected.append(item.data(CQt.UserRole))
        return selected


class FilterDialog(QDialog):
    def __init__(self, filters: dict, selected: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Unidades Administrativas")
        layout = QVBoxLayout(self)
        self.lists = {}
        self.parent_tab = parent

        for key, options in filters.items():
            btn = QToolButton(self)
            btn.setText(key.replace('_', ' ').title())
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.setToolButtonStyle(CQt.ToolButtonTextBesideIcon)
            btn.setArrowType(CQt.RightArrow)
            layout.addWidget(btn)

            frame = QFrame(self)
            frame_layout = QVBoxLayout(frame)
            frame.setVisible(False)

            listw = QListWidget(self)
            listw.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            listw.setSizePolicy(
                QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            )
            listw.setMinimumHeight(140)

            for opt in options:
                it = QListWidgetItem(opt)
                it.setFlags(it.flags() | CQt.ItemIsUserCheckable)
                checked = False
                if selected and key in selected and opt in selected[key]:
                    checked = True
                it.setCheckState(CQt.Checked if checked else CQt.Unchecked)
                listw.addItem(it)

            listw.itemChanged.connect(lambda item, k=key: self.on_item_changed(k, item))
            frame_layout.addWidget(listw)
            layout.addWidget(frame)

            def make_toggler(f=frame, b=btn):
                def toggle(checked):
                    b.setArrowType(CQt.DownArrow if checked else CQt.RightArrow)
                    f.setVisible(checked)
                    try:
                        self.adjustSize()
                    except Exception:
                        pass
                return toggle

            btn.toggled.connect(make_toggler())
            self.lists[key] = listw

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()

    def get_checked_values(self, key: str) -> List[str]:
        res = []
        listw = self.lists.get(key)
        if not listw:
            return res
        for i in range(listw.count()):
            it = listw.item(i)
            if it.checkState() == CQt.Checked:
                res.append(it.text())
        return res

    def on_item_changed(self, key: str, item: QListWidgetItem) -> None:
        self.update_dependent_filters(key)

    def update_dependent_filters(self, parent_key: str) -> None:
        if self.parent_tab is None:
            return

        filter_configs = getattr(self.parent_tab, 'filter_configs', {})
        filters_rows = getattr(self.parent_tab, 'filters_rows', {})

        for child_key, child_config in filter_configs.items():
            if child_config.get('parent_filter') == parent_key:
                self._apply_dependent_filter(parent_key, child_key, child_config, filters_rows)

    def _apply_dependent_filter(
        self,
        parent_key: str,
        child_key: str,
        child_config: dict,
        filters_rows: dict
    ) -> None:
        selected_parents = self.get_checked_values(parent_key)

        parent_rows = filters_rows.get(parent_key, [])
        child_rows = filters_rows.get(child_key, [])

        parent_key_field = child_config.get('parent_key')
        child_parent_field = child_config.get('parent_column')
        display_field = child_config.get('column')

        if not parent_key_field or not child_parent_field or not display_field:
            return

        parent_config = getattr(self.parent_tab, 'filter_configs', {}).get(parent_key, {})
        parent_display_field = parent_config.get('column')
        if not parent_display_field:
            return

        parent_ids = set()
        if selected_parents:
            for prow in parent_rows:
                display = (prow.get(parent_display_field) or '').strip()
                if display in selected_parents:
                    parent_id = (prow.get(parent_key_field) or '').strip()
                    if parent_id:
                        parent_ids.add(parent_id)

        allowed_values = set()
        if parent_ids:
            for child_row in child_rows:
                link = (child_row.get(child_parent_field) or '').strip()
                disp = (child_row.get(display_field) or '').strip()
                if link in parent_ids and disp:
                    allowed_values.add(disp)
        else:
            for child_row in child_rows:
                disp = (child_row.get(display_field) or '').strip()
                if disp:
                    allowed_values.add(disp)

        allowed_values = sorted(list(allowed_values))
        self._set_list_allowed_values(child_key, allowed_values)
        self.update_dependent_filters(child_key)

    def _set_list_allowed_values(self, key: str, allowed: List[str]) -> None:
        listw = self.lists.get(key)
        if listw is None:
            return

        current_checks = {}
        for i in range(listw.count()):
            it = listw.item(i)
            current_checks[it.text()] = (it.checkState() == CQt.Checked)

        listw.blockSignals(True)
        listw.clear()
        for val in allowed:
            it = QListWidgetItem(val)
            it.setFlags(it.flags() | CQt.ItemIsUserCheckable)
            checked = current_checks.get(val, False)
            it.setCheckState(CQt.Checked if checked else CQt.Unchecked)
            listw.addItem(it)
        listw.blockSignals(False)
        self.adjustSize()

    def get_selected(self) -> dict:
        res = {}
        for key, listw in self.lists.items():
            selected = []
            for i in range(listw.count()):
                item = listw.item(i)
                if item.checkState() == CQt.Checked:
                    selected.append(item.text())
            if selected:
                res[key] = selected
        return res


class NameTab(QWidget):
    def __init__(self, parent: QWidget, iface: QgisInterface) -> None:
        super().__init__(parent)

        base_path = os.path.dirname(__file__)
        svg_path = os.path.join(base_path, 'estilos', 'svg')
        svg_paths = QgsApplication.svgPaths()
        if svg_path not in svg_paths:
            svg_paths.append(svg_path)
            QgsApplication.setDefaultSvgPaths(svg_paths)

        print(QgsApplication.svgPaths())

        self.iface = iface
        self.layers = {}
        self.selected_elements = []

        self.filters_data = {
            'codigo_postal': [],
            'comunidad_autonoma': [],
            'provincia': [],
            'municipio': []
        }

        self.filters_rows: Dict[str, List[Dict[str, str]]] = {}
        self.filter_configs: Dict[str, Dict[str, Any]] = {}
        self.filter_selection = {}

        self.create_layout()

    def create_layout(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        lbl_localizacion = QLabel('Localización:')
        lbl_localizacion.setStyleSheet("font-weight: bold")
        layout.addWidget(lbl_localizacion)

        self.localizacion = QLineEdit()
        self.localizacion.setPlaceholderText(
            'Unidad administrativa, código postal o referencia catastral'
        )
        layout.addWidget(self.localizacion)

        lbl_cp = QLabel('(Opcional) Filtro por código postal:')
        layout.addWidget(lbl_cp)

        self.cp = QLineEdit()
        self.cp.setPlaceholderText('Uno o más CC.PP. separados por comas y sin espacios')
        layout.addWidget(self.cp)

        lbl_filters = QLabel('(Opcional) Filtros por unidades administrativas:')
        layout.addWidget(lbl_filters)

        self.btn_filters = QPushButton("Seleccionar Unidades Administrativas")

        self.btn_filters.clicked.connect(self.open_filter_dialog)
        layout.addWidget(self.btn_filters)

        self.filters_label = QLabel("Unidades administrativas seleccionadas: Todas")
        layout.addWidget(self.filters_label)

        lbl_process = QLabel('(Opcional) Filtro por tipo de elemento:')
        layout.addWidget(lbl_process)

        self.btn_open_dialog = QPushButton("Seleccionar Elementos")
        self.btn_open_dialog.clicked.connect(self.open_dialog)
        layout.addWidget(self.btn_open_dialog)

        self.selected_label = QLabel("Elementos seleccionados: Todos")
        layout.addWidget(self.selected_label)

        self.buscar = QPushButton('Buscar')
        self.buscar.setStyleSheet('font-weight: bold;')
        layout.addWidget(self.buscar)

        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(2)
        self.tabla_resultados.setHorizontalHeaderLabels(['Candidatos', 'Tipo'])

        self.tabla_resultados.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.tabla_resultados.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.tabla_resultados.horizontalHeader().setStretchLastSection(False)
        self.tabla_resultados.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.tabla_resultados)

        self.buscar.clicked.connect(self.on_search_name)
        self.localizacion.returnPressed.connect(self.on_search_name)
        self.cp.returnPressed.connect(self.on_search_name)
        self.tabla_resultados.cellDoubleClicked.connect(self.find_location)
        self.tabla_resultados.verticalHeader().sectionDoubleClicked.connect(
            self.handle_row_double_click
        )
        self.tabla_resultados.itemSelectionChanged.connect(self.highlight_tipo_column)

    def open_filter_dialog(self) -> None:
        if not any(self.filters_data.values()):
            self.load_filters_from_github()

        filters_for_dialog = {k: v for k, v in self.filters_data.items() if k != 'codigo_postal'}
        dlg = FilterDialog(filters_for_dialog, getattr(self, 'filter_selection', {}), self)

        if dlg.exec():
            self.filter_selection = dlg.get_selected()
            if self.filter_selection:
                parts = []
                for k, vals in self.filter_selection.items():
                    suffix = '...' if len(vals) > 3 else ''
                    parts.append(f"{k.replace('_',' ')}: {', '.join(vals[:3])}{suffix}")
                self.filters_label.setText("Unidades administrativas seleccionadas: " + " | ".join(parts))
            else:
                self.filters_label.setText("Unidades administrativas seleccionadas: Todas")

            self.localizacion.setFocus()

    def load_filters_from_github(self) -> None:
        filter_mapping = {
            'comunidad_autonoma': {
                'url': 'https://raw.githubusercontent.com/IDEESpain/PluginQGISCartociudad/main/Documentacion_auxiliar/cartociudad.comunidad_autonoma.csv',
                'backup_url': 'https://www.idee.es/resources/documentos/Cartociudad/cartociudad.comunidad_autonoma.csv',
                'column': 'nom_comunidad',
                'parent_key': 'id_com',
                'defaults': ['No se han cargado los datos']
            },
            'provincia': {
                'url': 'https://raw.githubusercontent.com/IDEESpain/PluginQGISCartociudad/main/Documentacion_auxiliar/cartociudad.provincia.csv',
                'backup_url': 'https://www.idee.es/resources/documentos/Cartociudad/cartociudad.provincia.csv',
                'column': 'nom_provincia',
                'parent_filter': 'comunidad_autonoma',
                'parent_key': 'id_com',
                'parent_column': 'id_com',
                'defaults': ['No se han cargado los datos']
            },
            'municipio': {
                'url': 'https://raw.githubusercontent.com/IDEESpain/PluginQGISCartociudad/main/Documentacion_auxiliar/cartociudad.municipio.csv',
                'backup_url': 'https://www.idee.es/resources/documentos/Cartociudad/cartociudad.municipio.csv',
                'column': 'nom_municipio',
                'parent_filter': 'provincia',
                'parent_key': 'ine_prov',
                'parent_column': 'ine_prov',
                'defaults': ['No se han cargado los datos']
            }
        }

        self.filter_configs = filter_mapping

        for filter_key, config in filter_mapping.items():
            self._load_filter_from_github(filter_key, config)

    def _load_filter_from_github(self, filter_key: str, config: Dict[str, Any]) -> None:
        github_url = config['url']
        column_name = config['column']
        defaults: List[str] = config.get('defaults', [])

        raw_backup = config.get('backup_url', [])
        if isinstance(raw_backup, str):
            backup_urls = [raw_backup] if raw_backup.strip() else []
        elif isinstance(raw_backup, list):
            backup_urls = [u.strip() for u in raw_backup if isinstance(u, str) and u.strip()]
        else:
            backup_urls = []

        used_source = None
        last_error = None
        csv_text = None

        try:
            print(f"Cargando {filter_key} desde GitHub: {github_url}")
            response = urlopen(github_url, timeout=10)
            raw = response.read()
            if _looks_like_html(raw, getattr(response, 'headers', {})):
                raise ValueError(
                    "La URL principal devolvió HTML (no es CSV raw). Usa el enlace Raw."
                )
            csv_text = raw.decode('utf-8')
            used_source = f"GitHub-CSV ({github_url})"
        except Exception as e:
            last_error = e
            print(f"Error cargando {filter_key} desde GitHub: {e}")

        if csv_text is None and backup_urls:
            for bu in backup_urls:
                try:
                    print(f"Reintentando {filter_key} desde backup_url: {bu}")
                    response = urlopen(bu, timeout=10)
                    raw = response.read()
                    if _looks_like_html(raw, getattr(response, 'headers', {})):
                        raise ValueError("El backup devolvió HTML (no es CSV raw).")
                    csv_text = raw.decode('utf-8')
                    used_source = f"Backup-CSV ({bu})"
                    break
                except Exception as e:
                    last_error = e
                    print(f"Error cargando {filter_key} desde backup_url {bu}: {e}")

        if csv_text is None:
            print(f"No se pudo cargar {filter_key} de ninguna fuente. Último error: {last_error}")
            self.filters_data[filter_key] = defaults
            self.filters_rows[filter_key] = []
            print(f"Usando valores por defecto para {filter_key}")
            return

        try:
            delimiter = _detect_delimiter(csv_text)
            reader = csv.DictReader(StringIO(csv_text), delimiter=delimiter)

            clean_rows: List[dict] = []
            for row in reader:
                if not row:
                    continue
                clean = {
                    (k.replace('\ufeff', '').strip() if isinstance(k, str) else k):
                    (v.strip() if isinstance(v, str) else v)
                    for k, v in row.items()
                }
                clean_rows.append(clean)

            if not clean_rows:
                raise ValueError(f"El archivo para {filter_key} está vacío ({used_source})")

            target_col = column_name.replace('\ufeff', '').strip()
            cols = set([
                (c.replace('\ufeff', '').strip() if isinstance(c, str) else c)
                for c in clean_rows[0].keys()
            ])

            if target_col not in cols:
                candidate = None
                for c in cols:
                    if isinstance(c, str) and c.strip().lower() == target_col.lower():
                        candidate = c
                        break
                if candidate:
                    print(f"La columna '{column_name}' no coincide exactamente; usando '{candidate}'.")
                    target_col = candidate
                else:
                    raise KeyError(
                        f"No se encontró la columna '{column_name}' en {used_source}. "
                        f"Columnas disponibles: {sorted(list(cols))}"
                    )

            self.filters_rows[filter_key] = clean_rows

            items = self._parse_csv_column(csv_text, target_col, delimiter)

            if items:
                self.filters_data[filter_key] = items
                print(f"Se cargaron {len(items)} registros para {filter_key} desde {used_source}")
            else:
                raise ValueError(
                    f"La fuente de {filter_key} ({used_source}) no contiene datos "
                    f"en la columna '{target_col}'."
                )

        except Exception as e:
            print(f"✗ Error procesando {filter_key} desde {used_source}: {e}")
            self.filters_data[filter_key] = defaults
            self.filters_rows[filter_key] = []
            print(f"Usando valores por defecto para {filter_key}")

    def _parse_csv_column(self, csv_content: str, column_name: str, delimiter: str = ',') -> List[str]:
        items = set()

        try:
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            column_name = column_name.replace('\ufeff', '').strip()

            for row in reader:
                if not row:
                    continue

                clean_row = {
                    k.replace('\ufeff', '').strip(): (v.strip() if isinstance(v, str) else v)
                    for k, v in row.items()
                }

                if column_name in clean_row:
                    value = clean_row[column_name]
                    item = value.strip() if isinstance(value, str) else value
                    if item:
                        items.add(item)

        except Exception as e:
            print(f"Error parseando CSV: {e}")
            return []

        return sorted(list(items))

    def open_dialog(self):
        todos_elementos = {
            'poblacion': 'Entidades de Población',
            'municipio': 'Municipios',
            'provincia': 'Provincias',
            'comunidad autonoma': 'Comunidades y ciudades autónomas',
            'toponimo': 'Topónimos y POI',
            'callejero': 'Viales (urbanos)',
            'carretera': 'Viales (interurbanos)',
            'portal': 'Portales y puntos kilométricos',
            'expendeduria': 'Expendedurías',
            'punto_recarga_electrica': 'Puntos de recarga eléctrica',
            'ngbe': 'Topónimos orográficos (NGBE)'
        }

        dialog = ComboDialog(todos_elementos, getattr(self, "selected_elements", []), self)

        if dialog.exec():
            self.selected_elements = dialog.get_selected_items()
            texto = (
                ", ".join([todos_elementos[elem] for elem in self.selected_elements])
                if self.selected_elements else "Todos"
            )
            self.selected_label.setWordWrap(True)
            self.selected_label.setSizePolicy(
                QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            )
            self.selected_label.setText("Elementos seleccionados: " + texto)

        self.localizacion.setFocus()

    def on_search_name(self) -> None:
        url = f'{API_GEOCODER}/candidates?q={self.localizacion.text()}&limit={LIMIT}'

        if self.filter_selection.get('comunidad_autonoma'):
            comunidades = self.filter_selection['comunidad_autonoma']
            comunidades_str = ','.join([c.strip() for c in comunidades if c.strip()])
            if comunidades_str:
                url += f'&comunidad_autonoma_filter={comunidades_str}'

        if self.filter_selection.get('provincia'):
            provincias = self.filter_selection['provincia']
            provincias_str = ','.join([p.strip() for p in provincias if p.strip()])
            if provincias_str:
                url += f'&provincia_filter={provincias_str}'

        if self.filter_selection.get('municipio'):
            municipios = self.filter_selection['municipio']
            municipios_str = ','.join([m.strip() for m in municipios if m.strip()])
            if municipios_str:
                url += f'&municipio_filter={municipios_str}'

        if self.cp.text() != '':
            codigos = self.cp.text().split(',')
            codigos = [codigo.strip() for codigo in codigos]
            if all(codigo.isdigit() and len(codigo) == 5 for codigo in codigos):
                codigos_str = ','.join(codigos)
                url += f'&cod_postal_filter={codigos_str}'
            else:
                QMessageBox.critical(None, "Error", "Algunos códigos postales no son válidos")
                return

        print(f'Buscar: {url}')

        todos_elementos = [
            'poblacion', 'municipio', 'provincia', 'comunidad autonoma',
            'toponimo', 'callejero', 'carretera', 'portal',
            'expendeduria', 'punto_recarga_electrica', 'ngbe'
        ]

        seleccionados = self.selected_elements
        seleccionados_norm = [s.strip().lower() for s in seleccionados]
        todos_norm = [t.strip().lower() for t in todos_elementos]

        if seleccionados_norm:
            if all(s in todos_norm for s in seleccionados_norm):
                elementos_excluir = [
                    todos_elementos[idx]
                    for idx, t in enumerate(todos_norm)
                    if t not in seleccionados_norm
                ]
                elementos_excluir_str = ','.join(elementos_excluir)
                url += f'&no_process={elementos_excluir_str}'
                print(
                    f'[DEBUG] elementos_incluir={seleccionados}, '
                    f'elementos_excluir={elementos_excluir_str}'
                )
            else:
                QMessageBox.critical(None, "Error", "Algunos elementos seleccionados no son válidos")
                return

        print(f'Buscar: {url}')

        self.tabla_resultados.clearContents()
        self.tabla_resultados.setRowCount(0)
        self.get_candidates(url)

    def get_candidates(self, url: str) -> None:
        print(f"Haciendo petición a la URL: {url}")
        self.manager_candidates = QtNetwork.QNetworkAccessManager()
        self.manager_candidates.finished.connect(self.show_candidates)
        req = QtNetwork.QNetworkRequest(QUrl(url))
        self.manager_candidates.get(req)

    def show_candidates(self, reply: QtNetwork.QNetworkReply) -> None:
        er = reply.error()
        if er == QtNetwork.QNetworkReply.NetworkError.NoError:
            print("Respuesta de la API recibida correctamente.")
            bytes_string = reply.readAll()
            response = str(bytes_string, 'utf-8')
            print(f"Respuesta JSON de la API: {response}")
            candidates = json.loads(response)

            if not candidates:
                QMessageBox.warning(None, "¡Atención!", "No se encontraron candidatos.")
                self.tabla_resultados.setRowCount(1)

                no_result_item = QTableWidgetItem("No se encontraron resultados")
                no_result_item.setFlags(CQt.ItemIsEnabled)
                no_result_item.setForeground(QBrush(QColor(255, 0, 0)))

                type_item = QTableWidgetItem("No se encontraron resultados")
                type_item.setFlags(CQt.ItemIsEnabled)
                type_item.setForeground(QBrush(QColor(255, 0, 0)))

                self.tabla_resultados.setItem(0, 0, no_result_item)
                self.tabla_resultados.setItem(0, 1, type_item)
                self.tabla_resultados.resizeColumnsToContents()
                self.tabla_resultados.resizeRowsToContents()
                return

            print(f"Número de candidatos encontrados: {len(candidates)}")
            self.tabla_resultados.setRowCount(len(candidates))

            for index, candidate in enumerate(candidates):
                print(f"Candidato {index + 1}: {candidate['address']}, Tipo: {candidate['type']}")

                item_address = QTableWidgetItem(candidate['address'])
                item_address.setFlags(CQt.ItemIsSelectable | CQt.ItemIsEnabled)
                item_address.setData(CQt.UserRole, candidate['id'])

                item_type = QTableWidgetItem(candidate['type'])
                item_type.setFlags(CQt.ItemIsEnabled)

                self.tabla_resultados.setItem(index, 0, item_address)
                self.tabla_resultados.setItem(index, 1, item_type)

            self.tabla_resultados.horizontalHeader().setStretchLastSection(True)
            self.tabla_resultados.resizeColumnsToContents()
            self.tabla_resultados.resizeRowsToContents()

            header = self.tabla_resultados.horizontalHeader()
            for col in range(self.tabla_resultados.columnCount()):
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

            self.tabla_resultados.updateGeometry()
            self.tabla_resultados.repaint()
        else:
            QMessageBox.critical(None, "Error", f"Error en la petición: {er}")

    def find_location(self, row: int, column: int) -> None:
        self.tabla_resultados.selectRow(row)

        address_item = self.tabla_resultados.item(row, 0)
        type_item = self.tabla_resultados.item(row, 1)

        if address_item is None or type_item is None:
            return

        candidate_id = address_item.data(CQt.UserRole)
        candidate_type = type_item.text()

        url = f'{API_GEOCODER}/find?id={candidate_id}&type={candidate_type}'
        self.get_location(url)
        print(f'Buscar: {url}')

    def handle_row_double_click(self, row):
        self.tabla_resultados.selectRow(row)
        self.find_location(row, 0)

    def get_location(self, url):
        self.manager_locate = QtNetwork.QNetworkAccessManager()
        self.manager_locate.finished.connect(self.draw_location)
        req = QtNetwork.QNetworkRequest(QUrl(url))
        self.manager_locate.get(req)

    def draw_location(self, reply: QtNetwork.QNetworkReply) -> None:
        print('Recibiendo respuesta del servicio find...')
        er = reply.error()
        if er == QtNetwork.QNetworkReply.NetworkError.NoError:
            bytes_string = reply.readAll()
            response = str(bytes_string, 'utf-8')
            location = json.loads(response)
            print('Localización: ')
            print(location)
            self.handle_location(location)
        else:
            QMessageBox.critical(None, "Error", f"Error en la petición: {er}")

    def handle_location(self, location: Dict[str, Union[Any, List[Any]]]) -> None:
        wkt = location['geom']
        new_geometry_type = self.get_geometry_type(wkt)
        layer_name = self.create_layer(new_geometry_type, location)
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

        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(group_name)
        if group is None:
            group = root.addGroup(group_name)

        group_layer_names = [
            child.layer().name()
            for child in group.children()
            if isinstance(child, QgsLayerTreeLayer)
        ]

        if group_name == "Municipios":
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
            extension = str(location.get("extension", "") or "").strip().replace(" ", "_")
            if extension:
                base_name = f"{tip_via}_{location_address}_{portal}{extension}_{poblacion}"
            else:
                base_name = f"{tip_via}_{location_address}_{portal}_{poblacion}"
        else:
            base_name = (
                str(location_address).strip().replace(" ", "_")
                if location_address else "Sin_nombre"
            )

        layer_name = base_name
        i = 1
        while layer_name in group_layer_names:
            i += 1
            layer_name = f"{base_name}_{i}"

        if layer_name in self.layers and self.layers[layer_name] is not None:
            return layer_name

        layer = QgsVectorLayer(geometry_type, layer_name, "memory")
        crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        layer.setCrs(crs)

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

        qml_path = None
        if group_name in ['Viales', 'Puntos_interes']:
            qml_dict = estilo_por_grupo.get(group_name, {})
            qml_path = qml_dict.get(location_type)
        else:
            qml_path = estilo_por_grupo.get(group_name)

        if qml_path and os.path.exists(qml_path):
            layer.loadNamedStyle(qml_path)
            layer.triggerRepaint()

        self.fields = QgsFields()
        self.create_attributes_from_json(
            location,
            exclude_keys=['geom', 'stateMsg', 'state', 'countryCode', 'noNumber']
        )

        layer.dataProvider().addAttributes(self.fields)
        layer.updateFields()

        self.layers[layer_name] = layer
        QgsProject.instance().addMapLayer(layer, False)
        group.addLayer(layer)

        return layer_name

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

    def create_attributes_from_json(
        self,
        location: Dict[str, Union[str, List[str]]],
        exclude_keys: Optional[List[str]] = None
    ) -> None:
        if exclude_keys is None:
            exclude_keys = []

        for attribute, value in location.items():
            if attribute not in exclude_keys and attribute != 'geom':
                self.fields.append(QgsField(attribute, QMetaType.Type.QString))

    def add_feature_to_layer(self, attributes: Dict[str, Union[Any, List[Any]]], layer_name: str) -> None:
        layer = self.layers.get(layer_name)

        if (
            layer is None
            or not QgsProject.instance().mapLayersByName(layer_name)
            or not layer.isValid()
        ):
            if layer_name in self.layers:
                del self.layers[layer_name]

            geometry_type = self.get_geometry_type(attributes['geom'])
            layer_name = self.create_layer(geometry_type, attributes)
            layer = self.layers[layer_name]

        feature = QgsFeature()
        feature.setFields(layer.fields())

        geom = None

        for attribute, value in attributes.items():
            if attribute == 'geom':
                geom = QgsGeometry.fromWkt(value)
                if not geom.isGeosValid():
                    print("Geometría no válida detectada. Intentando corregir...")
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

        if geom is None:
            return

        if geom.wkbType() in [QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon]:
            self.zoom_to_bounding_box(geom, layer.crs())
        else:
            self.zoom_to_geometry(geom, layer.crs())

    def zoom_to_bounding_box(self, geom: QgsGeometry, layer_crs: QgsCoordinateReferenceSystem) -> None:
        if geom is not None and geom.isGeosValid():
            geom = self.reproject_geometry(geom, layer_crs)
            extent = geom.boundingBox()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()

    def zoom_to_geometry(self, geom: QgsGeometry, layer_crs: QgsCoordinateReferenceSystem) -> None:
        if geom is not None and geom.isGeosValid():
            geom = self.reproject_geometry(geom, layer_crs)
            extent = geom.boundingBox()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()

    def reproject_geometry(self, geom: QgsGeometry, layer_crs: QgsCoordinateReferenceSystem) -> QgsGeometry:
        crs_dest = self.iface.mapCanvas().mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(layer_crs, crs_dest, QgsProject.instance())
        geom.transform(transform)
        return geom

    def highlight_tipo_column(self):
        for row in range(self.tabla_resultados.rowCount()):
            item = self.tabla_resultados.item(row, 1)
            if item:
                item.setBackground(QBrush())
                item.setForeground(QBrush())

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
                selection_color = self.tabla_resultados.palette().color(QPalette.ColorRole.Highlight)
                tipo_item.setBackground(QBrush(selection_color))
                tipo_item.setForeground(QBrush(QColor(255, 255, 255)))

            if col == 0 and header:
                font.setBold(True)
                header.setFont(font)

