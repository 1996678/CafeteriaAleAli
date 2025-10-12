import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple, Optional, Dict

DB_PATH = Path(__file__).resolve().parent / "datos.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

VENTA = "VENTA"
MERMA = "MERMA"

# Categorías fijas: Insumos (no vendible), Elaborados (vendible + receta/producción), Productos (vendible de proveedor)
CATS_FIJAS = ("Insumos","Elaborados","Productos")

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

# -------- Esquema / migración --------
def _col_exists(conn, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r["name"] == col for r in cur.fetchall())

def _crear_tablas_basicas(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

def _migraciones(conn):
    # Asegurar categorías fijas
    for cat in CATS_FIJAS:
        conn.execute("INSERT OR IGNORE INTO categorias(nombre) VALUES (?)", (cat,))
    # Asegurar tablas opcionales:
    conn.execute("""CREATE TABLE IF NOT EXISTS proveedores(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL, telefono TEXT, contacto TEXT, activo INTEGER NOT NULL DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cajeros(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL, activo INTEGER NOT NULL DEFAULT 1
    )""")
    # compras.proveedor_id (si falta)
    if not _col_exists(conn, "compras", "proveedor_id"):
        conn.execute("ALTER TABLE compras ADD COLUMN proveedor_id INTEGER REFERENCES proveedores(id)")

def iniciar_bd(nombre_sucursal: str):
    with conectar() as conn:
        _crear_tablas_basicas(conn)
        _migraciones(conn)
        conn.execute("INSERT OR IGNORE INTO sucursales(nombre) VALUES (?)", (nombre_sucursal,))

@contextmanager
def tx(conn=None):
    propio = False
    if conn is None:
        conn = conectar(); propio = True
    try:
        yield conn; conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        if propio: conn.close()

def _id_por_nombre(conn, tabla, nombre):
    cur = conn.execute(f"SELECT id FROM {tabla} WHERE nombre=?", (nombre,))
    fila = cur.fetchone()
    if not fila: raise ValueError(f"{tabla} '{nombre}' no existe")
    return fila["id"]

def listar_categorias() -> List[str]:
    with conectar() as conn:
        rows = conn.execute("SELECT nombre FROM categorias ORDER BY nombre").fetchall()
        return [r["nombre"] for r in rows]

# Unidades base: g/pz ; kg <-> g
def a_base(unidad:str, cantidad:float) -> float:
    if unidad == "kg": return cantidad * 1000.0
    return cantidad

def desde_base(unidad:str, cantidad_base:float) -> float:
    if unidad == "kg": return cantidad_base / 1000.0
    return cantidad_base

# Código auto para vendibles si viene vacío
def _generar_codigo_default(conn) -> str:
    pref = "PRD"
    i = 1
    while True:
        code = f"{pref}{i:04d}"
        row = conn.execute("SELECT 1 FROM productos WHERE codigo=?", (code,)).fetchone()
        if not row:
            return code
        i += 1

# -------- Catálogos: Proveedores / Cajeros --------
def crear_proveedor(nombre: str, telefono: Optional[str]=None, contacto: Optional[str]=None):
    if not nombre: raise ValueError("Nombre de proveedor obligatorio.")
    with tx() as conn:
        conn.execute("INSERT INTO proveedores(nombre, telefono, contacto) VALUES (?,?,?)", (nombre, telefono, contacto))

def listar_proveedores() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute("SELECT id, nombre, telefono, contacto FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()
        return [dict(r) for r in rows]

def crear_cajero(nombre: str):
    if not nombre: raise ValueError("Nombre de cajero obligatorio.")
    with tx() as conn:
        conn.execute("INSERT INTO cajeros(nombre) VALUES (?)", (nombre,))

def listar_cajeros() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute("SELECT id, nombre FROM cajeros WHERE activo=1 ORDER BY nombre").fetchall()
        return [dict(r) for r in rows]

# -------- Productos --------
def crear_producto(nombre: str, categoria: str, unidad: str, precio: float, codigo: Optional[str]=None, sku: Optional[str]=None):
    if categoria not in CATS_FIJAS:
        raise ValueError("La categoría debe ser 'Insumos', 'Elaborados' o 'Productos'")
    if unidad not in ("pz","g","kg"):
        raise ValueError("Unidad debe ser 'pz', 'g' o 'kg'")
    es_vendible = 1 if categoria in ("Elaborados","Productos") else 0
    with tx() as conn:
        cat_id = _id_por_nombre(conn, "categorias", categoria)
        if es_vendible == 1:
            if not codigo:
                codigo = _generar_codigo_default(conn)
        else:
            if codigo == "":
                codigo = None
        conn.execute("""INSERT INTO productos(nombre, sku, codigo, categoria_id, unidad, es_vendible, precio)
                        VALUES(?,?,?,?,?,?,?)""", (nombre, sku, codigo, cat_id, unidad, es_vendible, precio))

def listar_productos() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute("""SELECT p.id, p.nombre, p.unidad, p.es_vendible, p.precio, p.codigo, c.nombre as categoria
                               FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
                               ORDER BY p.nombre""").fetchall()
        return [dict(r) for r in rows]

def listar_insumos() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute("""SELECT id, nombre FROM productos
                               WHERE es_vendible=0 ORDER BY nombre""").fetchall()
        return [dict(r) for r in rows]

def listar_elaborados() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute("""SELECT p.id, p.nombre, p.codigo, p.precio
                               FROM productos p
                               JOIN categorias c ON c.id=p.categoria_id
                               WHERE p.es_vendible=1 AND c.nombre='Elaborados'
                               ORDER BY p.nombre""").fetchall()
        return [dict(r) for r in rows]

def listar_vendibles() -> List[Dict]:
    with conectar() as conn:
        rows = conn.execute("""SELECT id, nombre, codigo, precio FROM productos
                               WHERE es_vendible=1 ORDER BY nombre""").fetchall()
        return [dict(r) for r in rows]

def listar_para_compras() -> List[Dict]:
    """Productos que SÍ se compran al proveedor: Insumos + Productos (no 'Elaborados')."""
    with conectar() as conn:
        rows = conn.execute("""SELECT p.id, p.nombre
                               FROM productos p
                               JOIN categorias c ON c.id=p.categoria_id
                               WHERE c.nombre IN ('Insumos','Productos')
                               ORDER BY p.nombre""").fetchall()
        return [dict(r) for r in rows]

def buscar_vendible_por_codigo(codigo:str) -> Optional[Dict]:
    with conectar() as conn:
        r = conn.execute("""SELECT id, nombre, unidad, precio, codigo FROM productos
                            WHERE es_vendible=1 AND codigo=?""",(codigo,)).fetchone()
        return dict(r) if r else None

def buscar_vendibles_por_texto(q:str) -> List[Dict]:
    q_like = f"%{q}%"
    with conectar() as conn:
        rows = conn.execute("""SELECT id, nombre, codigo, precio FROM productos
                               WHERE es_vendible=1 AND (nombre LIKE ? OR codigo LIKE ?)
                               ORDER BY nombre""",(q_like,q_like)).fetchall()
        return [dict(r) for r in rows]

# -------- Recetas --------
def definir_receta_producto(producto_menu: str, componentes: List[Tuple[str, float]]):
    with tx() as conn:
        menu_id = _id_por_nombre(conn, "productos", producto_menu)
        cat = conn.execute("""SELECT c.nombre AS cat FROM productos p
                              JOIN categorias c ON c.id=p.categoria_id
                              WHERE p.id=?""", (menu_id,)).fetchone()
        if not cat or cat["cat"] != "Elaborados":
            raise ValueError("La receta solo puede definirse para productos de categoría 'Elaborados'.")
        conn.execute("DELETE FROM recetas WHERE producto_menu_id=?", (menu_id,))
        for comp_nombre, cant_base in componentes:
            comp_id = _id_por_nombre(conn, "productos", comp_nombre)
            esv = conn.execute("SELECT es_vendible FROM productos WHERE id=?", (comp_id,)).fetchone()["es_vendible"]
            if esv == 1:
                raise ValueError("Solo se pueden agregar componentes NO vendibles (insumos)")
            if cant_base <= 0: raise ValueError("La cantidad debe ser > 0")
            conn.execute("""INSERT INTO recetas(producto_menu_id, componente_producto_id, cantidad_base)
                            VALUES(?,?,?)""", (menu_id, comp_id, cant_base))

def obtener_receta(producto_menu: str) -> List[Dict]:
    with conectar() as conn:
        sql = """SELECT pm.nombre as menu, pc.nombre as componente, r.cantidad_base
                 FROM recetas r
                 JOIN productos pm ON pm.id=r.producto_menu_id
                 JOIN productos pc ON pc.id=r.componente_producto_id
                 WHERE pm.nombre=?"""
        rows = conn.execute(sql, (producto_menu,)).fetchall()
        return [dict(r) for r in rows]

# -------- Inventario --------
def inventario_actual() -> List[Dict]:
    with conectar() as conn:
        sql = """SELECT p.nombre, p.unidad, p.costo, i.cantidad_base
                 FROM inventario i JOIN productos p ON p.id=i.producto_id
                 ORDER BY p.nombre"""
        rows = conn.execute(sql).fetchall()
        arr = []
        for r in rows:
            arr.append({
                "nombre": r["nombre"],
                "unidad": r["unidad"],
                "cantidad": desde_base(r["unidad"], r["cantidad_base"]),
                "costo_unitario": r["costo"] or 0.0
            })
        return arr

def ajustar(producto: str, delta: float, nota: str="Ajuste"):
    with tx() as conn:
        pid = _id_por_nombre(conn, "productos", producto)
        prod = conn.execute("SELECT unidad FROM productos WHERE id=?", (pid,)).fetchone()
        r = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        if not r: raise ValueError("No hay sucursal registrada.")
        suc_id = r["id"]
        conn.execute("INSERT OR IGNORE INTO inventario(producto_id, sucursal_id, cantidad_base) VALUES(?,?,0)", (pid, suc_id))
        base = a_base(prod["unidad"], delta)
        conn.execute("UPDATE inventario SET cantidad_base = cantidad_base + ? WHERE producto_id=? AND sucursal_id=?", (base, pid, suc_id))
        conn.execute("""INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota)
                        VALUES(?,?,?,?,?,?,?)""", (pid, suc_id, base, "AJUSTE", "inventario", None, nota))

# -------- Compras (con proveedor opcional) --------
def registrar_compra(items: List[Tuple[str,float,float]], proveedor: Optional[str]=None, nota: str="") -> int:
    with tx() as conn:
        r = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        if not r: raise ValueError("No hay sucursal registrada.")
        suc_id = r["id"]

        proveedor_id = None
        if proveedor:
            prow = conn.execute("SELECT id FROM proveedores WHERE nombre=? AND activo=1", (proveedor,)).fetchone()
            if not prow:
                raise ValueError(f"Proveedor '{proveedor}' no existe o está inactivo")
            proveedor_id = prow["id"]

        cur = conn.execute("INSERT INTO compras(sucursal_id, total, proveedor_id) VALUES (?,?,?)", (suc_id, 0, proveedor_id))
        compra_id = cur.lastrowid

        total_compra = 0.0
        for nombre, cant, costo_total in items:
            pid_row = conn.execute("SELECT id, unidad FROM productos WHERE nombre=?", (nombre,)).fetchone()
            if not pid_row: raise ValueError(f"Producto '{nombre}' no existe")
            pid = pid_row["id"]; unidad = pid_row["unidad"]
            if cant <= 0: raise ValueError("Cantidad debe ser > 0")
            if costo_total < 0: raise ValueError("Costo total no puede ser negativo")
            costo_unitario = (costo_total / cant) if cant != 0 else 0.0
            conn.execute("""INSERT INTO compras_detalle(compra_id, producto_id, cantidad, costo_total, costo_unitario)
                            VALUES(?,?,?,?,?)""", (compra_id, pid, cant, costo_total, costo_unitario))
            conn.execute("UPDATE productos SET costo=? WHERE id=?", (costo_unitario, pid))
            conn.execute("INSERT OR IGNORE INTO inventario(producto_id, sucursal_id, cantidad_base) VALUES(?,?,0)", (pid, suc_id))
            base = a_base(unidad, cant)
            conn.execute("UPDATE inventario SET cantidad_base = cantidad_base + ? WHERE producto_id=? AND sucursal_id=?", (base, pid, suc_id))
            conn.execute("""INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota)
                            VALUES(?,?,?,?,?,?,?)""",(pid, suc_id, base, "COMPRA", "compras", compra_id, nota))
            total_compra += costo_total

        conn.execute("UPDATE compras SET total=? WHERE id=?", (total_compra, compra_id))
        return compra_id

# -------- Producción (solo para Elaborados) --------
def registrar_produccion(producto_menu: str, cantidad: float, nota: str="") -> int:
    if cantidad <= 0:
        raise ValueError("La cantidad a producir debe ser > 0")
    with tx() as conn:
        r = conn.execute("""SELECT p.id, p.unidad, c.nombre AS cat
                            FROM productos p JOIN categorias c ON c.id=p.categoria_id
                            WHERE p.nombre=?""", (producto_menu,)).fetchone()
        if not r: raise ValueError(f"Producto '{producto_menu}' no existe")
        if r["cat"] != "Elaborados":
            raise ValueError("Solo se puede producir un producto de categoría 'Elaborados'")
        menu_id = r["id"]; unidad_menu = r["unidad"]
        suc = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        suc_id = suc["id"]
        receta = conn.execute("SELECT componente_producto_id, cantidad_base FROM recetas WHERE producto_menu_id=?", (menu_id,)).fetchall()
        if not receta:
            raise ValueError("El producto no tiene receta definida")
        # Validación stock
        for row in receta:
            comp_id, por_u = row["componente_producto_id"], row["cantidad_base"]
            req = por_u * cantidad
            cur = conn.execute("SELECT cantidad_base FROM inventario WHERE producto_id=? AND sucursal_id=?", (comp_id, suc_id)).fetchone()
            if not cur or cur["cantidad_base"] < req:
                raise ValueError("Stock insuficiente de componentes para producir")
        # Consumir insumos
        for row in receta:
            comp_id, por_u = row["componente_producto_id"], row["cantidad_base"]
            req = por_u * cantidad
            conn.execute("UPDATE inventario SET cantidad_base = cantidad_base - ? WHERE producto_id=? AND sucursal_id=?", (req, comp_id, suc_id))
            conn.execute("""INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota)
                            VALUES(?,?,?,?,?,?,?)""",(comp_id, suc_id, -req, "PRODUCCION", "producciones", None, nota))
        # Sumar producto elaborado
        base_u = a_base(unidad_menu, cantidad)
        conn.execute("UPDATE inventario SET cantidad_base = cantidad_base + ? WHERE producto_id=? AND sucursal_id=?", (base_u, menu_id, suc_id))
        cur = conn.execute("INSERT INTO producciones(producto_id, sucursal_id, cantidad, nota) VALUES(?,?,?,?)", (menu_id, suc_id, cantidad, nota))
        prod_id = cur.lastrowid
        conn.execute("""INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota)
                        VALUES(?,?,?,?,?,?,?)""",(menu_id, suc_id, base_u, "PRODUCCION", "producciones", prod_id, nota))
        return prod_id

# -------- Ventas / Merma --------
def registrar_venta(tipo: str, items: List[Tuple[int,float]], cajero: Optional[str]=None, nota: str="") -> int:
    if tipo not in (VENTA, MERMA):
        raise ValueError("tipo debe ser 'VENTA' o 'MERMA'")
    with tx() as conn:
        r = conn.execute("SELECT id FROM sucursales LIMIT 1").fetchone()
        if not r: raise ValueError("No hay sucursal registrada.")
        suc_id = r["id"]
        cur = conn.execute("INSERT INTO ventas(tipo, sucursal_id, cajero) VALUES (?,?,?)", (tipo, suc_id, cajero))
        venta_id = cur.lastrowid
        total = 0.0
        for pid, cant in items:
            prod = conn.execute("SELECT id, es_vendible, precio, unidad, nombre FROM productos WHERE id=?", (pid,)).fetchone()
            if not prod: raise ValueError("Producto no existe")
            if prod["es_vendible"] != 1:
                raise ValueError("Solo se venden productos vendibles en esta ventana")
            precio_unit = 0.0 if tipo == MERMA else float(prod["precio"])
            subtotal = precio_unit * cant
            conn.execute("""INSERT INTO ventas_detalle(venta_id, producto_id, cantidad, precio_unitario, subtotal)
                            VALUES(?,?,?,?,?)""",(venta_id, prod["id"], cant, precio_unit, subtotal))
            total += subtotal
            base = a_base(prod["unidad"], cant)
            curq = conn.execute("SELECT cantidad_base FROM inventario WHERE producto_id=? AND sucursal_id=?", (prod["id"], suc_id)).fetchone()
            if not curq or curq["cantidad_base"] < base:
                raise ValueError(f"Stock insuficiente de '{prod['nombre']}'")
            conn.execute("UPDATE inventario SET cantidad_base = cantidad_base - ? WHERE producto_id=? AND sucursal_id=?", (base, prod["id"], suc_id))
            conn.execute("""INSERT INTO movimientos_inventario(producto_id, sucursal_id, cantidad_base, motivo, ref_tabla, ref_id, nota)
                            VALUES(?,?,?,?,?,?,?)""",(prod["id"], suc_id, -base, tipo, "ventas", venta_id, nota))
        conn.execute("UPDATE ventas SET total=? WHERE id=?", (total, venta_id))
        return venta_id

# -------- Reportes --------
def reporte_ventas_detallado(desde:str=None,hasta:str=None):
    params=[]; where=["v.tipo='VENTA'"]
    if desde: where.append("date(v.creado_en)>=date(?)"); params.append(desde)
    if hasta: where.append("date(v.creado_en)<=date(?)"); params.append(hasta)
    where_sql="WHERE "+ " AND ".join(where)
    sql=f"""SELECT v.creado_en as fecha, p.nombre as producto, d.cantidad,
                    d.precio_unitario, p.costo as costo_unitario, d.subtotal
            FROM ventas v
            JOIN ventas_detalle d ON d.venta_id=v.id
            JOIN productos p ON p.id=d.producto_id
            {where_sql}
            ORDER BY v.creado_en, p.nombre"""
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

def reporte_merma_detallado(desde:str=None,hasta:str=None):
    params=[]; where=["v.tipo='MERMA'"]
    if desde: where.append("date(v.creado_en)>=date(?)"); params.append(desde)
    if hasta: where.append("date(v.creado_en)<=date(?)"); params.append(hasta)
    where_sql="WHERE "+ " AND ".join(where)
    sql=f"""SELECT v.creado_en as fecha, p.nombre as producto, d.cantidad,
                    p.costo as costo_unitario, (p.costo * d.cantidad) as total_costo
            FROM ventas v
            JOIN ventas_detalle d ON d.venta_id=v.id
            JOIN productos p ON p.id=d.producto_id
            {where_sql}
            ORDER BY v.creado_en, p.nombre"""
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

def top_productos(lim:int=10,desde:str=None,hasta:str=None):
    params=[]; where=["v.tipo='VENTA'"]
    if desde: where.append("date(v.creado_en)>=date(?)"); params.append(desde)
    if hasta: where.append("date(v.creado_en)<=date(?)"); params.append(hasta)
    where_sql="WHERE "+ " AND ".join(where)
    sql=f"""SELECT p.nombre, SUM(d.cantidad) as cantidad, SUM(d.subtotal) as ingreso
            FROM ventas_detalle d JOIN productos p ON p.id=d.producto_id
            JOIN ventas v ON v.id=d.venta_id {where_sql}
            GROUP BY p.nombre ORDER BY ingreso DESC LIMIT ?"""
    params.append(lim)
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

def bajo_stock(umbral_base:float=500.0):
    sql = """SELECT p.nombre, p.unidad, i.cantidad_base FROM inventario i JOIN productos p ON p.id=i.producto_id
             WHERE i.cantidad_base <= ? ORDER BY i.cantidad_base ASC, p.nombre"""
    with conectar() as conn:
        rows = conn.execute(sql,(umbral_base,)).fetchall()
        arr=[]
        for r in rows:
            arr.append({"nombre":r["nombre"], "cantidad":desde_base(r["unidad"], r["cantidad_base"]), "unidad":r["unidad"]})
        return arr

def kardex(producto:str):
    sql = """SELECT m.creado_en, m.cantidad_base, m.motivo, m.nota, p.unidad
             FROM movimientos_inventario m JOIN productos p ON p.id=m.producto_id
             WHERE p.nombre=? ORDER BY m.creado_en"""
    with conectar() as conn:
        rows = conn.execute(sql,(producto,)).fetchall()
        arr=[]
        for r in rows:
            arr.append({"creado_en":r["creado_en"], "cantidad":desde_base(r["unidad"], r["cantidad_base"]), "motivo":r["motivo"], "nota":r["nota"]})
        return arr
