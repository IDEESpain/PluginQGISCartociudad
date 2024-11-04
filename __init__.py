def classFactory(iface):
    from .main import Geocoder
    return Geocoder(iface)
