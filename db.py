import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "datos.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

VENTA = "VENTA"
MERMA = "MERMA"

CATS_FIJAS = ("Insumos", "Elaborados", "Productos")


def _now_str() -> str:
    # Fecha/hora local de la computadora, formato estable para SQLite
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _col_exists(conn, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r["name"] == col for r in cur.fetchall())


def _crear_tablas_basicas(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def _generar_codigo_default(conn) -> str:
    pref = "PRD"
    i = 1
    while True:
        code = f"{pref}{i:04d}"
        row = conn.execute("SELECT 1 FROM productos WHERE codigo=?", (code,)).fetchone()
        if not row:
            return code
        i += 1


def _autofill_codigos(conn):
    rows = conn.execute(
        "SELECT id FROM productos WHERE codigo IS NULL OR TRIM(codigo)=''"
    ).fetchall()
    for r in rows:
        nuevo = _generar_codigo_default(conn)
        conn.execute("UPDATE productos SET codigo=? WHERE id=?", (nuevo, r["id"]))


def _migraciones(conn):
    for cat in CATS_FIJAS:
        conn.execute("INSERT OR IGNORE INTO categorias(nombre) VALUES (?)", (cat,))

    conn.execute(
        """CREATE TABLE IF NOT EXISTS proveedores(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            telefono TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        )"""
    )
    # Tabla 'cajeros' puede permanecer o ignorarse; ya no se usa en la UI.

    cur = conn.execute("PRAGMA table_info(compras)")
    cols = {r["name"]: r for r in cur.fetchall()}
    if "proveedor_id" not in cols:
        conn.execute(
            "ALTER TABLE compras ADD COLUMN proveedor_id INTEGER REFERENCES proveedores(id)"
        )

    # Normalizar unidades de versiones anteriores
    conn.execute("UPDATE productos SET unidad='Pieza' WHERE unidad='pz'")
    conn.execute("UPDATE productos SET unidad='Gramo' WHERE unidad='g'")
    conn.execute("UPDATE productos SET unidad='Kilo'  WHERE unidad='kg'")

    # Índices útiles
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_cat ON productos(categoria_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inv_prod_suc ON inventario(producto_id, sucursal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mvto_prod_suc ON movimientos_inventario(producto_id, sucursal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ventas_tipo_fecha ON ventas(tipo, creado_en)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vdet_venta ON ventas_detalle(venta_id)")

    _autofill_codigos(conn)


def iniciar_bd(nombre_sucursal: str):
    with conectar() as conn:
        _crear_tablas_basicas(conn)
        _migraciones(conn)
        conn.execute(
            "INSERT OR IGNORE INTO sucursales(nombre) VALUES (?)", (nombre_sucursal,)
        )


@contextmanager
def tx(conn=None):
    propio = False
    if conn is None:
        conn = conectar()
        propio = True
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if propio:
            conn.close()


def _id_por_nombre(conn, tabla, nombre):
    cur = conn.execute(f"SELECT id FROM {tabla} WHERE nombre=?", (nombre,))
    fila = cur.fetchone()
    if not fila:
        raise ValueError(f"{tabla} '{nombre}' no existe")
    return fila["id"]


def listar_categorias() -> List[str]:
    with conectar() as conn:
        rows = conn.execute("SELECT nombre FROM categorias ORDER BY nombre").fetchall()
        return [r["nombre"] for r in rows]


def a_base(unidad: str, cantidad: float) -> float:
    if unidad == "Kilo":
        return cantidad * 1000.0
    return cantidad


def desde_base(unidad: str, cantidad_base: float) -> float:
    if unidad == "Kilo":
        return cantidad_base / 1000.0
    return cantidad_base


# ------- Catálogos -------
def crear_proveedor(
    nombre: str, telefono: Optional[str] = None, contacto: Optional[str] = None
):
    if not nombre:
        raise ValueError("Nombre de proveedor obligatorio.")
    with tx() as conn:
        conn.execute(
            "INSERT INTO proveedores(nombre, telefono) VALUES (?,?)",
            (nombre, telefono),
        )


def listar_proveedores() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute(
            "SELECT id, nombre, telefono FROM proveedores WHERE activo=1 ORDER BY nombre"
        ).fetchall()
        return [dict(r) for r in rows]


# ------- Productos -------
def crear_producto(
    nombre: str,
    categoria: str,
    unidad: str,
    precio: float,
    codigo: Optional[str] = None,
    sku: Optional[str] = None,
):
    if categoria not in CATS_FIJAS:
        raise ValueError("La categoría debe ser 'Insumos', 'Elaborados' o 'Productos'")
    if unidad not in ("Pieza", "Gramo", "Kilo"):
        raise ValueError("Unidad debe ser 'Pieza', 'Gramo' o 'Kilo'")
    es_vendible = 1 if categoria in ("Elaborados", "Productos") else 0
    with tx() as conn:
        cat_id = _id_por_nombre(conn, "categorias", categoria)
        if not codigo or not codigo.strip():
            codigo = _generar_codigo_default(conn)
        precio_final = precio if es_vendible else 0.0
        conn.execute(
            """INSERT INTO productos(nombre, sku, codigo, categoria_id, unidad, es_vendible, precio)
               VALUES(?,?,?,?,?,?,?)""",
            (nombre, sku, codigo.strip(), cat_id, unidad, es_vendible, precio_final),
        )


def listar_productos() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute(
            """SELECT p.id, p.nombre, p.unidad, p.es_vendible, p.precio, p.codigo, c.nombre as categoria
               FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
               ORDER BY p.nombre"""
        ).fetchall()
        return [dict(r) for r in rows]


def listar_insumos() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute(
            """SELECT id, nombre FROM productos
               WHERE es_vendible=0 ORDER BY nombre"""
        ).fetchall()
        return [dict(r) for r in rows]


def listar_elaborados() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute(
            """SELECT p.id, p.nombre, p.codigo, p.precio
               FROM productos p
               JOIN categorias c ON c.id=p.categoria_id
               WHERE p.es_vendible=1 AND c.nombre='Elaborados'
               ORDER BY p.nombre"""
        ).fetchall()
        return [dict(r) for r in rows]


def listar_vendibles() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute(
            """SELECT id, nombre, codigo, precio FROM productos
               WHERE es_vendible=1 ORDER BY nombre"""
        ).fetchall()
        return [dict(r) for r in rows]


def listar_para_compras() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute(
            """SELECT p.id, p.nombre, p.unidad
               FROM productos p
               JOIN categorias c ON c.id=p.categoria_id
               WHERE c.nombre IN ('Insumos','Productos')
               ORDER BY p.nombre"""
        ).fetchall()
        return [dict(r) for r in rows]


def buscar_vendible_por_codigo(codigo: str) -> Optional[Dict]:
    with conectar() as conn:
        r = conn.execute(
            """SELECT id, nombre, unidad, precio, codigo FROM productos
               WHERE es_vendible=1 AND codigo=?""",
            (codigo,),
        ).fetchone()
        return dict(r) if r else None


def buscar_vendibles_por_texto(q: str) -> List[Dict]:
    q_like = f"%{q}%"
    with conectar() as conn:
        rows = conn.execute(
            """SELECT id, nombre, codigo, precio FROM productos
               WHERE es_vendible=1 AND (nombre LIKE ? OR codigo LIKE ?)
               ORDER BY nombre""",
            (q_like, q_like),
        ).fetchall()
        return [dict(r) for r in rows]


# ------- Recetas -------
def definir_receta_producto(producto_menu: str, componentes: List[Tuple[str, float]]):
    with tx() as conn:
        menu_id = _id_por_nombre(conn, "productos", producto_menu)
        cat = conn.execute(
            """SELECT c.nombre AS cat FROM productos p
               JOIN categorias c ON c.id=p.categoria_id
               WHERE p.id=?""",
            (menu_id,),
        ).fetchone()
        if not cat or cat["cat"] != "Elaborados":
            raise ValueError(
                "La receta solo puede definirse para productos de categoría 'Elaborados'."
            )
        conn.execute("DELETE FROM recetas WHERE producto_menu_id=?", (menu_id,))
        for comp_nombre, cant_base in componentes:
            comp_id = _id_por_nombre(conn, "productos", comp_nombre)
            esv = conn.execute(
                "SELECT es_vendible FROM productos WHERE id=?", (comp_id,)
            ).fetchone()["es_vendible"]
            if esv == 1:
                raise ValueError("Solo se pueden agregar componentes NO vendibles (insumos)")
            if cant_base <= 0:
                raise ValueError("La cantidad debe ser > 0")
            conn.execute(
                """INSERT INTO recetas(producto_menu_id, componente_producto_id, cantidad_base)
                   VALUES(?,?,?)""",
                (menu_id, comp_id, cant_base),
            )


def obtener_receta(producto_menu: str) -> List[Dict]:
    with conectar() as conn:
        sql = """SELECT pm.nombre as menu, pc.nombre as componente, r.cantidad_base
                 FROM recetas r
                 JOIN productos pm ON pm.id=r.producto_menu_id
                 JOIN productos pc ON pc.id=r.componente_producto_id
                 WHERE pm.nombre=?"""
        rows = conn.execute(sql, (producto_menu,)).fetchall()
        return [dict(r) for r in rows]


# ------- Inventario -------
def inventario_actual() -> List[Dict]:
    with conectar() as conn:
        sql = """SELECT p.nombre, p.unidad, p.costo, i.cantidad_base, c.nombre AS categoria
                 FROM inventario i
                 JOIN productos p ON p.id=i.producto_id
                 LEFT JOIN categorias c ON c.id=p.categoria_id
                 ORDER BY p.nombre"""
        rows = conn.execute(sql).fetchall()
        arr = []
        for r in rows:
            arr.append(
                {
                    "nombre": r["nombre"],
                    "unidad": r["unidad"],
                    "cantidad": desde_base(r["unidad"], r["cantidad_base"]),
                    "costo_unitario": r["costo"] or 0.0,
                    "categoria": r["categoria"] or "",
                }
            )
        return arr


def _insert_mov_inv(conn, producto_id: int, sucursal_id: int, cantidad_base: float, motivo: str, ref_tabla: str, ref_id: Optional[int], nota: str):
    # Inserta movimiento con fecha local si la columna existe
    if _col_exists(conn, "movimientos_inventario", "creado_en"):
        conn.execute(
            """INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota, creado_en)
               VALUES(?,?,?,?,?,?,?,?)""",
            (producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota, _now_str()),
        )
    else:
        conn.execute(
            """INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota)
               VALUES(?,?,?,?,?,?,?)""",
            (producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota),
        )


def ajustar(producto: str, delta: float, nota: str = "Ajuste"):
    with tx() as conn:
        pid = _id_por_nombre(conn, "productos", producto)
        prod = conn.execute("SELECT unidad FROM productos WHERE id=?", (pid,)).fetchone()
        r = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        if not r:
            raise ValueError("No hay sucursal registrada.")
        suc_id = r["id"]
        conn.execute(
            "INSERT OR IGNORE INTO inventario(producto_id, sucursal_id, cantidad_base) VALUES(?,?,0)",
            (pid, suc_id),
        )
        base = a_base(prod["unidad"], delta)
        conn.execute(
            "UPDATE inventario SET cantidad_base = cantidad_base + ? WHERE producto_id=? AND sucursal_id=?",
            (base, pid, suc_id),
        )
        _insert_mov_inv(conn, pid, suc_id, base, "AJUSTE", "inventario", None, nota)


# ------- Compras -------
def registrar_compra(
    items: List[Tuple[str, float, float]],
    proveedor: Optional[str] = None,
    nota: str = "",
) -> int:
    with tx() as conn:
        r = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        if not r:
            raise ValueError("No hay sucursal registrada.")
        suc_id = r["id"]

        proveedor_id = None
        if proveedor:
            prow = conn.execute(
                "SELECT id FROM proveedores WHERE nombre=? AND activo=1", (proveedor,)
            ).fetchone()
            if not prow:
                raise ValueError(f"Proveedor '{proveedor}' no existe o está inactivo")
            proveedor_id = prow["id"]

        # Inserta compra con fecha local si la columna existe
        if _col_exists(conn, "compras", "creado_en"):
            cur = conn.execute(
                "INSERT INTO compras(sucursal_id, total, proveedor_id, creado_en) VALUES (?,?,?,?)",
                (suc_id, 0, proveedor_id, _now_str()),
            )
        else:
            cur = conn.execute(
                "INSERT INTO compras(sucursal_id, total, proveedor_id) VALUES (?,?,?)",
                (suc_id, 0, proveedor_id),
            )
        compra_id = cur.lastrowid

        total_compra = 0.0
        for nombre, cant, costo_total in items:
            pid_row = conn.execute(
                "SELECT id, unidad FROM productos WHERE nombre=?", (nombre,)
            ).fetchone()
            if not pid_row:
                raise ValueError(f"Producto '{nombre}' no existe")
            pid = pid_row["id"]
            unidad = pid_row["unidad"]
            if cant <= 0:
                raise ValueError("Cantidad debe ser > 0")
            if costo_total < 0:
                raise ValueError("Costo total no puede ser negativo")
            costo_unitario = (costo_total / cant) if cant != 0 else 0.0
            conn.execute(
                """INSERT INTO compras_detalle(compra_id, producto_id, cantidad, costo_total, costo_unitario)
                   VALUES(?,?,?,?,?)""",
                (compra_id, pid, cant, costo_total, costo_unitario),
            )
            conn.execute("UPDATE productos SET costo=? WHERE id=?", (costo_unitario, pid))
            conn.execute(
                "INSERT OR IGNORE INTO inventario(producto_id, sucursal_id, cantidad_base) VALUES(?,?,0)",
                (pid, suc_id),
            )
            base = a_base(unidad, cant)
            conn.execute(
                "UPDATE inventario SET cantidad_base = cantidad_base + ? WHERE producto_id=? AND sucursal_id=?",
                (base, pid, suc_id),
            )
            _insert_mov_inv(conn, pid, suc_id, base, "COMPRA", "compras", compra_id, nota)
            total_compra += costo_total

        conn.execute("UPDATE compras SET total=? WHERE id=?", (total_compra, compra_id))
        return compra_id


# ------- Producción -------
def registrar_produccion(producto_menu: str, cantidad: float, nota: str = "") -> int:
    if cantidad <= 0:
        raise ValueError("La cantidad a producir debe ser > 0")
    with tx() as conn:
        r = conn.execute(
            """SELECT p.id, p.unidad, c.nombre AS cat
               FROM productos p JOIN categorias c ON c.id=p.categoria_id
               WHERE p.nombre=?""",
            (producto_menu,),
        ).fetchone()
        if not r:
            raise ValueError(f"Producto '{producto_menu}' no existe")
        if r["cat"] != "Elaborados":
            raise ValueError("Solo se puede producir un producto de categoría 'Elaborados'")
        menu_id = r["id"]
        unidad_menu = r["unidad"]
        suc = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        suc_id = suc["id"]
        receta = conn.execute(
            "SELECT componente_producto_id, cantidad_base FROM recetas WHERE producto_menu_id=?",
            (menu_id,),
        ).fetchall()
        if not receta:
            raise ValueError("El producto no tiene receta definida")

        # Validación stock
        for row in receta:
            comp_id, por_u = row["componente_producto_id"], row["cantidad_base"]
            req = por_u * cantidad
            cur = conn.execute(
                "SELECT cantidad_base FROM inventario WHERE producto_id=? AND sucursal_id=?",
                (comp_id, suc_id),
            ).fetchone()
            if not cur or cur["cantidad_base"] < req:
                raise ValueError("Stock insuficiente de componentes para producir")

        # Consumir componentes
        for row in receta:
            comp_id, por_u = row["componente_producto_id"], row["cantidad_base"]
            req = por_u * cantidad
            conn.execute(
                "UPDATE inventario SET cantidad_base = cantidad_base - ? WHERE producto_id=? AND sucursal_id=?",
                (req, comp_id, suc_id),
            )
            _insert_mov_inv(conn, comp_id, suc_id, -req, "PRODUCCION", "producciones", None, nota)

        # Abonar elaborado
        base_u = a_base(unidad_menu, cantidad)
        conn.execute(
            "UPDATE inventario SET cantidad_base = cantidad_base + ? WHERE producto_id=? AND sucursal_id=?",
            (base_u, menu_id, suc_id),
        )
        # Producción con fecha local si existe la columna
        if _col_exists(conn, "producciones", "creado_en"):
            cur = conn.execute(
                "INSERT INTO producciones(producto_id, sucursal_id, cantidad, nota, creado_en) VALUES(?,?,?,?,?)",
                (menu_id, suc_id, cantidad, nota, _now_str()),
            )
        else:
            cur = conn.execute(
                "INSERT INTO producciones(producto_id, sucursal_id, cantidad, nota) VALUES(?,?,?,?)",
                (menu_id, suc_id, cantidad, nota),
            )
        prod_id = cur.lastrowid
        _insert_mov_inv(conn, menu_id, suc_id, base_u, "PRODUCCION", "producciones", prod_id, nota)
        return prod_id


# ------- Ventas / Merma -------
def registrar_venta(
    tipo: str, items: List[Tuple[int, float]], cajero: Optional[str] = None, nota: str = ""
) -> int:
    if tipo not in (VENTA, MERMA):
        raise ValueError("tipo debe ser 'VENTA' o 'MERMA'")
    with tx() as conn:
        r = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        if not r:
            raise ValueError("No hay sucursal registrada.")
        suc_id = r["id"]

        # Insertar venta con fecha local si existe la columna
        if _col_exists(conn, "ventas", "creado_en"):
            cur = conn.execute(
                "INSERT INTO ventas(tipo, sucursal_id, cajero, creado_en) VALUES (?,?,?,?)",
                (tipo, suc_id, None, _now_str()),
            )
        else:
            cur = conn.execute(
                "INSERT INTO ventas(tipo, sucursal_id, cajero) VALUES (?,?,?)",
                (tipo, suc_id, None),
            )
        venta_id = cur.lastrowid

        total = 0.0
        for pid, cant in items:
            prod = conn.execute(
                "SELECT id, es_vendible, precio, unidad, nombre FROM productos WHERE id=?",
                (pid,),
            ).fetchone()
            if not prod:
                raise ValueError("Producto no existe")
            if prod["es_vendible"] != 1:
                raise ValueError("Solo se venden productos vendibles en esta ventana")

            precio_catalogo = float(prod["precio"])
            precio_unit = 0.0 if tipo == MERMA else precio_catalogo
            subtotal = precio_unit * cant  # MERMA => 0

            # Guardamos precio histórico en el detalle SIEMPRE (en MERMA, el de catálogo del día)
            conn.execute(
                """INSERT INTO ventas_detalle(venta_id, producto_id, cantidad, precio_unitario, subtotal)
                   VALUES(?,?,?,?,?)""",
                (venta_id, prod["id"], cant, (precio_catalogo if tipo == MERMA else precio_unit), subtotal),
            )
            total += subtotal

            # Descontar stock del producto vendido (elaborado/producto)
            base = a_base(prod["unidad"], cant)
            curq = conn.execute(
                "SELECT cantidad_base FROM inventario WHERE producto_id=? AND sucursal_id=?",
                (prod["id"], suc_id),
            ).fetchone()
            if not curq or curq["cantidad_base"] < base:
                raise ValueError(f"Stock insuficiente de '{prod['nombre']}'")
            conn.execute(
                "UPDATE inventario SET cantidad_base = cantidad_base - ? WHERE producto_id=? AND sucursal_id=?",
                (base, prod["id"], suc_id),
            )
            _insert_mov_inv(conn, prod["id"], suc_id, -base, tipo, "ventas", venta_id, nota)

        conn.execute("UPDATE ventas SET total=? WHERE id=?", (total, venta_id))
        return venta_id


# ------- Reportes -------
def reporte_ventas_detallado(desde: str = None, hasta: str = None):
    params = []
    where = ["v.tipo='VENTA'"]
    if desde:
        where.append("date(v.creado_en)>=date(?)"); params.append(desde)
    if hasta:
        where.append("date(v.creado_en)<=date(?)"); params.append(hasta)
    where_sql = "WHERE " + " AND ".join(where)

    sql = f"""SELECT v.creado_en as fecha,
                     p.id   as producto_id,
                     p.nombre as producto,
                     d.cantidad, d.precio_unitario, d.subtotal
              FROM ventas v
              JOIN ventas_detalle d ON d.venta_id=v.id
              JOIN productos p      ON p.id=d.producto_id
              {where_sql}
              ORDER BY v.creado_en, p.nombre"""

    rows_out = []
    with conectar() as conn:
        for r in conn.execute(sql, tuple(params)).fetchall():
            cantidad = float(r["cantidad"] or 0)
            p_venta  = float(r["precio_unitario"] or 0)
            costo_u  = float(costo_estimado_producto(r["producto_id"]) or 0)
            margen_u = p_venta - costo_u
            margen_t = margen_u * cantidad
            margen_pct = (margen_u / p_venta * 100.0) if p_venta > 0 else 0.0

            rows_out.append({
                "fecha": r["fecha"],
                "producto": r["producto"],
                "cantidad": cantidad,
                "precio_unitario": p_venta,
                "costo_unitario": round(costo_u, 2),
                "margen_unit": round(margen_u, 2),
                "margen_total": round(margen_t, 2),
                "margen_pct": round(margen_pct, 2),
                "subtotal": float(r["subtotal"] or 0)
            })
    return rows_out


def reporte_merma_detallado(desde: str = None, hasta: str = None):
    params = []
    where = ["v.tipo='MERMA'"]
    if desde:
        where.append("date(v.creado_en)>=date(?)")
        params.append(desde)
    if hasta:
        where.append("date(v.creado_en)<=date(?)")
        params.append(hasta)
    where_sql = "WHERE " + " AND ".join(where)
    sql = f"""SELECT v.creado_en as fecha,
                     p.nombre as producto,
                     d.cantidad,
                     d.precio_unitario as precio_venta,
                     (d.precio_unitario * d.cantidad) as perdida
              FROM ventas v
              JOIN ventas_detalle d ON d.venta_id=v.id
              JOIN productos p ON p.id=d.producto_id
              {where_sql}
              ORDER BY v.creado_en, p.nombre"""
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def reporte_compras_detallado(desde: str = None, hasta: str = None, proveedor: str = None):
    """
    Reporte de compras: fecha, proveedor, producto, cantidad, UNIDAD, costo unitario, costo total.
    Permite filtrar por proveedor (nombre exacto).
    """
    params = []
    where = []
    if desde:
        where.append("date(c.creado_en)>=date(?)"); params.append(desde)
    if hasta:
        where.append("date(c.creado_en)<=date(?)"); params.append(hasta)
    if proveedor:
        where.append("IFNULL(pr.nombre,'') = ?"); params.append(proveedor)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT c.creado_en as fecha,
               IFNULL(pr.nombre,'') as proveedor,
               p.nombre as producto,
               cd.cantidad,
               p.unidad as unidad,
               cd.costo_unitario,
               cd.costo_total
        FROM compras c
        JOIN compras_detalle cd ON cd.compra_id=c.id
        JOIN productos p ON p.id=cd.producto_id
        LEFT JOIN proveedores pr ON pr.id=c.proveedor_id
        {where_sql}
        ORDER BY c.creado_en, pr.nombre, p.nombre
    """
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def top_productos(lim: int = 10, desde: str = None, hasta: str = None):
    params = []
    where = ["v.tipo='VENTA'"]
    if desde:
        where.append("date(v.creado_en)>=date(?)")
        params.append(desde)
    if hasta:
        where.append("date(v.creado_en)<=date(?)")
        params.append(hasta)
    where_sql = "WHERE " + " AND ".join(where)
    sql = f"""SELECT p.nombre, SUM(d.cantidad) as cantidad, SUM(d.subtotal) as ingreso
              FROM ventas_detalle d JOIN productos p ON p.id=d.producto_id
              JOIN ventas v ON v.id=d.venta_id {where_sql}
              GROUP BY p.nombre ORDER BY ingreso DESC LIMIT ?"""
    params.append(lim)
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

def stock_disponible_producto(producto_id: int) -> float:
    """Devuelve el stock disponible convertido a la unidad del producto (Pieza/Gramo/Kilo)."""
    with conectar() as conn:
        r = conn.execute(
            """
            SELECT p.unidad, IFNULL(i.cantidad_base, 0) AS base
            FROM productos p
            LEFT JOIN inventario i ON i.producto_id = p.id
            JOIN sucursales s ON 1=1      
            WHERE p.id=? AND (i.sucursal_id = s.id OR i.sucursal_id IS NULL)
            LIMIT 1
            """,
            (producto_id,)
        ).fetchone()
        if not r:
            return 0.0
        return desde_base(r["unidad"], r["base"])


def _ultimo_costo_unitario(conn, pid: int) -> float:
    """Último costo_unitario pagado por ese producto (según compras_detalle)."""
    r = conn.execute(
        "SELECT costo_unitario FROM compras_detalle WHERE producto_id=? ORDER BY id DESC LIMIT 1",
        (pid,)
    ).fetchone()
    if r and r["costo_unitario"] is not None:
        return float(r["costo_unitario"])
    r = conn.execute("SELECT costo FROM productos WHERE id=?", (pid,)).fetchone()
    return float(r["costo"] or 0.0)


def costo_estimado_producto(pid: int) -> float:
    """
    Costo por UNIDAD DE VENTA del producto:
    - Insumo/Producto simple: último costo_unitario.
    - Elaborado: suma de (costo del componente segun unidad × cantidad_base de receta).
      cantidad_base está en g o pz POR pieza vendida del elaborado.
    """
    with conectar() as conn:
        p = conn.execute(
            """SELECT p.id, p.unidad, p.es_vendible, c.nombre AS categoria
               FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
               WHERE p.id=?""",
            (pid,)
        ).fetchone()
        if not p:
            return 0.0

        # Si NO es elaborado, devolvemos su último costo unitario
        if p["categoria"] != "Elaborados":
            return _ultimo_costo_unitario(conn, pid)

        # Es elaborado: calcular por receta
        receta = conn.execute(
            "SELECT componente_producto_id, cantidad_base FROM recetas WHERE producto_menu_id=?",
            (pid,)
        ).fetchall()
        if not receta:
            return 0.0

        total = 0.0
        for row in receta:
            comp_id = row["componente_producto_id"]
            cant    = float(row["cantidad_base"] or 0.0)  # g o pz por pieza
            comp = conn.execute(
                "SELECT unidad FROM productos WHERE id=?",
                (comp_id,)
            ).fetchone()
            if not comp:
                continue
            costo_u = _ultimo_costo_unitario(conn, comp_id)

            # Convertir por UNIDAD del componente
            u = comp["unidad"]  # "Pieza", "Gramo", "Kilo"
            if u == "Pieza":
                total += costo_u * cant                   # cant en pz
            elif u == "Gramo":
                total += costo_u * cant                   # costo_u ya es por gramo
            elif u == "Kilo":
                total += costo_u * (cant / 1000.0)        # cant en gramos → kilos
            else:
                total += costo_u * cant

        return round(total, 6) 