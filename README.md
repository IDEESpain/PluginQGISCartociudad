# Plugin Geocoder CartoCiudad 

## ✍️ Descripción del plugin

CartoCiudad ofrece diferentes servicios web de geolocalización de direcciones postales, topónimos, poblaciones y límites administrativos de España.
 
Para poder utilizar estos servicios web en QGIS y así poder geolocalizar y descargar todos los elementos almacenados en CartoCiudad, se ha creado este complemento de QGIS, que está basado en servicio REST «Geocoder».

 ![Captura de la pantalla principal](docs/inicio.png)
 
Este complemento permiete localizar y descragar objetos geográficos de España por identificadores geográficos y/o por coordenadas geográficas. 

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

### 🚂 Funcionalidades

#### Localicación por nombre geográfico

Permite realizar búsquedas de los diferentes elementos geográficos contenidos de CartoCiudad.

Para ello se añade en *Localización* el elemento a buscar, por ejemplo la vía *General Ibañez de Íbero, Madrid*
