from qgis.PyQt.QtCore import Qt


def qt_enum(namespace_name, *attr_names):
    namespace = getattr(Qt, namespace_name, None)
    if namespace is not None:
        for attr_name in attr_names:
            if hasattr(namespace, attr_name):
                return getattr(namespace, attr_name)
    for attr_name in attr_names:
        if hasattr(Qt, attr_name):
            return getattr(Qt, attr_name)
    raise AttributeError(
        f"No se encontró ninguno de {attr_names} en Qt.{namespace_name} ni en Qt"
    )


class CompatQt:
    ItemIsUserCheckable = qt_enum("ItemFlag", "ItemIsUserCheckable")
    ItemIsSelectable = qt_enum("ItemFlag", "ItemIsSelectable")
    ItemIsEnabled = qt_enum("ItemFlag", "ItemIsEnabled")
    ItemIsEditable = qt_enum("ItemFlag", "ItemIsEditable")

    Checked = qt_enum("CheckState", "Checked")
    Unchecked = qt_enum("CheckState", "Unchecked")

    UserRole = qt_enum("ItemDataRole", "UserRole")

    AlignLeft = qt_enum("AlignmentFlag", "AlignLeft")
    AlignVCenter = qt_enum("AlignmentFlag", "AlignVCenter")

    ToolButtonTextBesideIcon = qt_enum("ToolButtonStyle", "ToolButtonTextBesideIcon")

    RightArrow = qt_enum("ArrowType", "RightArrow")
    LeftArrow = qt_enum("ArrowType", "LeftArrow")
    DownArrow = qt_enum("ArrowType", "DownArrow")

    ArrowCursor = qt_enum("CursorShape", "ArrowCursor")

    RichText = qt_enum("TextFormat", "RichText")

    Transparent = qt_enum("GlobalColor", "transparent", "Transparent")

    Horizontal = qt_enum("Orientation", "Horizontal")
    LeftDockWidgetArea = qt_enum("DockWidgetArea", "LeftDockWidgetArea")