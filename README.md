# Plugin Geocoder CartoCiudad 

## ✍️ Descripción del plugin

CartoCiudad ofrece diferentes servicios web de geolocalización de direcciones postales, topónimos, poblaciones y límites administrativos de España.
 
Para poder utilizar estos servicios web en QGIS y así poder geolocalizar y descargar todos los elementos almacenados en CartoCiudad, se ha creado este **complemento de QGIS**, que está basado en servicio REST «Geocoder».
 
 ![PluginQGIS](docs/inicio.png)
 
---

<a name="contenidos"></a>

## 📇 Contenidos

* 🛠 [Funcionalidades](#funcionalidades)
  * 🔸 [Localización por nombre geográfico](#nombregeografico)
  * 🔸 [Localización por coordenadas geográficas](#coordenadas)
* 🚀 [Instalación](#instalacion)
* 📁 [Estructura del código](#estructura)
* ⛲️ [Referencias](#referencias)

---

## 🛠 Funcionalidades <a name="funcionalidades"></a>

Este complemento permiete localizar y descargar objetos geográficos de España por identificadores geográficos y/o por coordenadas geográficas. 

Se pueden localizar los siguientes objetos geográficos:
 
  * Direcciones postales
 
  * Topónimos
 
  * Puntos de Interés
 
  * Unidades administrativas
 
  * Poblaciones
 
  * Códigos postales
 
  * Referencias catastrales (Servicios SOAP. Dirección General de Catastro)
 
La información que se devuelve puede ser puntual (portales, PK, códigos postales, puntos de interés y referencias catastrales), lineal (viales) y superficial (unidades administrativas y entidades de población).
tiene menú contextual

---

### 🔸Localicación por nombre geográfico <a name="nombregeografico"></a>

[👆 Volver](#contenidos)

Permite realizar búsquedas de los diferentes elementos geográficos contenidos de CartoCiudad.

Para ello se añade en *Localización* el elemento a buscar, por ejemplo la vía *General Ibañez de Íbero, Madrid*

 *Ejemplo de búsqueda de un vial*:

![Ejemplo busqueda](docs/ejemplo_ng.png)


🔹 **Búsqueda de un elemento filtrando por código postal**

Permite realizar una búsqueda de cualquier elemento geográfico contenido en un código postal. 
Para ello hay que introducir el elemento a buscar y además hay que añadir en *Filtrar por código postal* el número del código postal deseado. Así mismo, se puede filtrar por varios códigos postales, y para ello, hay que introducirlos seguidos de comas y sin espacios.

 *Ejemplo de búsqueda del Instituto Geográfico Nacional*:

![Ejemplo busqueda filtro 1](docs/filtro1.png)

 *Ejemplo de búsqueda del Instituto Geográfico Nacional del código postal 28003*:
 
![Ejemplo busqueda filtro 2](docs/filtro2.png)

---

### 🔸Localicación por coordenadas geográficas <a name="coordenadas"></a>

[👆 Volver](#contenidos)


---

## 🚀 Instalación <a name="instalacion"></a>


---

## 📁 Estructura del código <a name="estructura"></a>

[👆 Volver](#contenidos)

```any
/
├── docs 📁               # Recursos de imágenes del REDMINE
├── images 🌈             # Imágenes usadas en el plugin
├── LICENSE 📢            # Licencia              
├── metadata.txt 📁       # Metadatos
├── main.py 📁            # Integración de elementos
├── name.py 📁            # Localización por nombre geográfico
├── reverse 📁            # Localización por coordenadas
└── ...
```
---

## ⛲️ Referencias <a name="referencias"></a>

[👆 Volver](#contenidos)

* [Portal CartoCiudad](https://www.cartociudad.es/web/portal)
* [Guía Técnica de Servicios Web](https://www.idee.es/resources/documentos/Cartociudad/CartoCiudad_ServiciosWeb.pdf)
* [Ayuda proyecto CartoCiudad](https://www.idee.es/resources/documentos/Cartociudad/StoryMap.html)
