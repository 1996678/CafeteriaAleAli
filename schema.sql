PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sucursales(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS categorias(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL CHECK(nombre IN ('Insumos','Elaborados','Productos'))
);

CREATE TABLE IF NOT EXISTS productos(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT UNIQUE,
  codigo TEXT UNIQUE,
  nombre TEXT NOT NULL UNIQUE,
  categoria_id INTEGER REFERENCES categorias(id),
  unidad TEXT NOT NULL CHECK(unidad IN ('Pieza','Gramo','Kilo')),
  es_vendible INTEGER NOT NULL DEFAULT 0,
  precio REAL NOT NULL DEFAULT 0.0,
  costo REAL NOT NULL DEFAULT 0.0,
  activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recetas(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  producto_menu_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
  componente_producto_id INTEGER NOT NULL REFERENCES productos(id),
  cantidad_base REAL NOT NULL CHECK(cantidad_base > 0),
  UNIQUE(producto_menu_id, componente_producto_id)
);

CREATE TABLE IF NOT EXISTS inventario(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
  cantidad_base REAL NOT NULL DEFAULT 0,
  UNIQUE(producto_id, sucursal_id)
);

CREATE TABLE IF NOT EXISTS movimientos_inventario(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
  cantidad_base REAL NOT NULL,
  motivo TEXT NOT NULL,
  ref_tabla TEXT,
  ref_id INTEGER,
  nota TEXT,
  creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proveedores(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL,
  telefono TEXT,
  activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS compras(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now')),
  total REAL NOT NULL DEFAULT 0,
  proveedor_id INTEGER REFERENCES proveedores(id)
);

CREATE TABLE IF NOT EXISTS compras_detalle(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  compra_id INTEGER NOT NULL REFERENCES compras(id) ON DELETE CASCADE,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  cantidad REAL NOT NULL CHECK(cantidad > 0),
  costo_total REAL NOT NULL CHECK(costo_total >= 0),
  costo_unitario REAL NOT NULL CHECK(costo_unitario >= 0)
);

CREATE TABLE IF NOT EXISTS cajeros(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ventas(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT NOT NULL CHECK(tipo IN ('VENTA','MERMA')) DEFAULT 'VENTA',
  sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
  cajero TEXT,
  creado_en TEXT NOT NULL DEFAULT (datetime('now')),
  total REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ventas_detalle(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  cantidad REAL NOT NULL CHECK(cantidad > 0),
  precio_unitario REAL NOT NULL CHECK(precio_unitario >= 0),
  subtotal REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS producciones(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
  cantidad REAL NOT NULL CHECK(cantidad > 0),
  nota TEXT,
  creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER IF NOT EXISTS inventario_despues_producto
AFTER INSERT ON productos
BEGIN
  INSERT OR IGNORE INTO inventario(producto_id, sucursal_id, cantidad_base)
  SELECT NEW.id, s.id, 0 FROM sucursales s;
END;

CREATE TRIGGER IF NOT EXISTS inventario_despues_sucursal
AFTER INSERT ON sucursales
BEGIN
  INSERT OR IGNORE INTO inventario(producto_id, sucursal_id, cantidad_base)
  SELECT p.id, NEW.id, 0 FROM productos p;
END;
