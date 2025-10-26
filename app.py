import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from db import *

# ---------- Proveedores ----------

class VentanaProveedores(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Proveedores")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        top = ttk.LabelFrame(frm, text="Agregar proveedor")
        top.pack(fill="x", padx=4, pady=6)

        ttk.Label(top, text="Nombre:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(top, text="Teléfono (10 dígitos):").grid(row=1, column=0, sticky="w", padx=6, pady=4)

        # nombre: Title Case al teclear
        self._updating_nom = False
        self.var_nom = tk.StringVar()
        self.p_nom = ttk.Entry(top, width=30, textvariable=self.var_nom)
        self.p_nom.grid(row=0, column=1, padx=6, pady=4)
        self.var_nom.trace_add("write", self._titlecase_all)

        self.p_tel = ttk.Entry(top, width=30); self.p_tel.grid(row=1, column=1, padx=6, pady=4)

        ttk.Button(top, text="Guardar", command=self.add).grid(row=0, column=2, rowspan=2, padx=8, pady=4, sticky="ns")

        cols = ("nombre", "telefono")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        self.tree.heading("nombre", text="Nombre");   self.tree.column("nombre",  width=280)
        self.tree.heading("telefono", text="Teléfono"); self.tree.column("telefono", width=180)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Button(frm, text="Refrescar", command=self.refrescar).pack(pady=6)
        self.refrescar()

    # ---- Helpers para Title Case (maneja espacios, guiones y apóstrofes) ----
    def _cap_piece(self, s: str) -> str:
        return s[:1].upper() + s[1:].lower() if s else ""

    def _cap_word(self, w: str) -> str:
        for sep in ("-", "'"):
            if sep in w:
                return sep.join(self._cap_piece(p) for p in w.split(sep))
        return self._cap_piece(w)

    def _titlecase_all(self, *args):
        if self._updating_nom:
            return
        v = self.var_nom.get()
        if v == "":
            return
        new = " ".join(self._cap_word(w) for w in v.split(" "))
        if new != v:
            self._updating_nom = True
            pos = self.p_nom.index("insert")
            self.var_nom.set(new)
            self.p_nom.icursor(min(pos, len(new)))
            self._updating_nom = False

    def add(self):
        try:
            # Normaliza nuevamente a Title Case por si vino pegado/externo
            nombre_raw = self.var_nom.get().strip()
            nombre = " ".join(self._cap_word(w) for w in nombre_raw.split(" "))
            tel_raw = self.p_tel.get().strip()
            telefono = "".join(ch for ch in tel_raw if ch.isdigit())

            if not nombre:
                raise ValueError("El nombre es obligatorio.")
            if tel_raw and len(telefono) != 10:
                raise ValueError("El teléfono debe tener exactamente 10 dígitos.")
            if not tel_raw:
                telefono = None

            crear_proveedor(nombre, telefono)  # firma: (nombre, telefono)

            self.var_nom.set("")
            self.p_tel.delete(0, "end")
            self.refrescar()
            messagebox.showinfo("OK", "Proveedor guardado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refrescar(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in listar_proveedores():
            self.tree.insert("", "end", values=(r.get("nombre",""), r.get("telefono","")))



# ---------- Cajeros ----------
class VentanaCajeros(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Cajeros")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        top = ttk.LabelFrame(frm, text="Agregar cajero")
        top.pack(fill="x", padx=4, pady=6)
        ttk.Label(top, text="Nombre:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.c_nom = ttk.Entry(top, width=30); self.c_nom.grid(row=0, column=1, padx=6, pady=4)
        ttk.Button(top, text="Guardar", command=self.add).grid(row=0, column=2, padx=8)

        self.tree = ttk.Treeview(frm, columns=("nombre",), show="headings", height=14)
        self.tree.heading("nombre", text="Nombre"); self.tree.column("nombre", width=300)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        ttk.Button(frm, text="Refrescar", command=self.refrescar).pack(pady=6)
        self.refrescar()

    def add(self):
        try:
            crear_cajero(self.c_nom.get().strip())
            self.c_nom.delete(0,"end")
            self.refrescar()
            messagebox.showinfo("OK","Cajero guardado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refrescar(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in listar_cajeros():
            self.tree.insert("", "end", values=(r["nombre"],))

# ---------- Productos ----------
class VentanaProductos(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Productos (Insumos / Elaborados / Productos)")

        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        r = 0
        ttk.Label(frm, text="Nombre:").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.var_nombre = tk.StringVar()
        self.p_nombre = ttk.Entry(frm, width=24, textvariable=self.var_nombre)
        self.p_nombre.grid(row=r, column=1, padx=6); r += 1
        self.var_nombre.trace_add("write", self._titulo_nombre)

        ttk.Label(frm, text="Categoría:").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.p_categoria = ttk.Combobox(frm, values=["Insumos","Elaborados","Productos"], width=20, state="readonly")
        self.p_categoria.set("Insumos")
        self.p_categoria.grid(row=r, column=1, padx=6); r += 1
        self.p_categoria.bind("<<ComboboxSelected>>", self._toggle_campos_vendible)

        ttk.Label(frm, text="Unidad (Pieza/Gramo/Kilo):").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.p_unidad = ttk.Combobox(frm, values=["Pieza","Gramo","Kilo"], width=6, state="readonly")
        self.p_unidad.set("Pieza")
        self.p_unidad.grid(row=r, column=1, padx=6); r += 1

        ttk.Label(frm, text="Precio (solo vendibles):").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.p_precio = ttk.Entry(frm, width=10); self.p_precio.insert(0,"0"); self.p_precio.grid(row=r, column=1, padx=6); r += 1

        ttk.Label(frm, text="Código (obligatorio; si vacío, se autogenera):").grid(row=r, column=0, sticky="w", padx=6, pady=4)
        self.var_codigo = tk.StringVar()
        self.p_codigo = ttk.Entry(frm, width=14, textvariable=self.var_codigo)
        self.p_codigo.grid(row=r, column=1, padx=6); r += 1
        self.var_codigo.trace_add("write", self._titulo_codigo)

        ttk.Button(frm, text="Crear producto", command=self.crear_producto).grid(row=r, column=0, columnspan=2, pady=8); r += 1

        cols = ("nombre","categoria","unidad","vendible","precio","codigo")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        headers = ["Nombre","Categoría","Unidad","Vendible","Precio","Código"]
        widths  = [160,120,80,80,90,120]
        for c,h,w in zip(cols,headers,widths):
            self.tree.heading(c, text=h); self.tree.column(c, width=w)
        self.tree.grid(row=r, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        frm.grid_rowconfigure(r, weight=1); frm.grid_columnconfigure(1, weight=1)

        ttk.Button(frm, text="Refrescar", command=self.refrescar).grid(row=r+1, column=0, columnspan=2, pady=6)

        self._toggle_campos_vendible()
        self.refrescar()

    # Título (solo inicial en mayúscula)
    def _titulo_nombre(self, *args):
        v = self.var_nombre.get()
        u = v.title()
        if v != u:
            self.var_nombre.set(u)

    def _titulo_codigo(self, *args):
        v = self.var_codigo.get()
        u = v.title()
        if v != u:
            self.var_codigo.set(u)

    def _toggle_campos_vendible(self, *_):
        cat = self.p_categoria.get().strip().title()
        es_insumo = (cat == "Insumos")
        self.p_precio.config(state="disabled" if es_insumo else "normal")
        if es_insumo:
            self.p_precio.delete(0, "end"); self.p_precio.insert(0, "0")

    def crear_producto(self):
        try:
            nombre    = self.var_nombre.get().strip().title()
            categoria = self.p_categoria.get().strip().title()
            unidad    = self.p_unidad.get().strip().title()
            precio    = float(self.p_precio.get() or 0)
            codigo    = (self.var_codigo.get() or "").strip().title()

            if not nombre:
                raise ValueError("El nombre es obligatorio.")

            crear_producto(nombre, categoria, unidad, precio, codigo)
            self.refrescar()
            messagebox.showinfo("OK","Producto creado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refrescar(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in listar_productos():
            self.tree.insert(
                "",
                "end",
                values=(
                    (p.get("nombre","") or "").title(),
                    (p.get("categoria","") or "").title(),
                    (p.get("unidad","") or "").title(),
                    "Sí" if p.get("es_vendible") else "No",
                    f'{float(p.get("precio",0)):.2f}',
                    (p.get("codigo","") or "").title(),
                ),
            )


# ---------- Recetas ----------
class VentanaRecetas(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Recetas (BOM) — solo para Elaborados")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        top = ttk.Frame(frm); top.pack(fill="x", padx=2, pady=4)
        ttk.Label(top, text="Producto Elaborado:").pack(side="left")
        self.menu = ttk.Combobox(top, values=[p["nombre"] for p in listar_elaborados()], width=30, state="readonly"); self.menu.pack(side="left", padx=6)
        ttk.Button(top, text="Refrescar", command=self.refrescar).pack(side="left", padx=6)

        nota = ttk.Label(frm, text="Las recetas aceptan solo INSUMOS como componentes. Cantidades en g o pz por unidad vendida.")
        nota.pack(anchor="w", padx=4)

        lf = ttk.LabelFrame(frm, text="Agregar/actualizar componente")
        lf.pack(fill="x", padx=2, pady=6)
        self.comp = ttk.Combobox(lf, values=[p["nombre"] for p in listar_insumos()], width=30, state="readonly"); self.comp.pack(side="left", padx=6, pady=6)
        ttk.Label(lf, text="Cantidad por unidad (g/pz):").pack(side="left", padx=6)
        self.cant = ttk.Entry(lf, width=10); self.cant.insert(0,"1"); self.cant.pack(side="left", padx=6)
        ttk.Button(lf, text="Guardar en receta", command=self.agregar).pack(side="left", padx=6)

        cols=("componente","cantidad_base")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        self.tree.heading("componente", text="Componente (insumo)")
        self.tree.heading("cantidad_base", text="Cant. base (g/pz)")
        self.tree.column("componente", width=260); self.tree.column("cantidad_base", width=140)
        self.tree.pack(fill="both", expand=True, padx=2, pady=6)

    def refrescar(self):
        self.comp["values"] = [p["nombre"] for p in listar_insumos()]
        self.menu["values"] = [p["nombre"] for p in listar_elaborados()]
        for i in self.tree.get_children(): self.tree.delete(i)
        m = self.menu.get().strip()
        if not m: return
        try:
            for r in obtener_receta(m):
                self.tree.insert("", "end", values=(r["componente"], r["cantidad_base"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def agregar(self):
        m = self.menu.get().strip(); c = self.comp.get().strip()
        if not m or not c:
            messagebox.showerror("Error","Selecciona elaborado y componente"); return
        try:
            q = float(self.cant.get())
        except:
            messagebox.showerror("Error","Cantidad inválida"); return
        try:
            actuales = obtener_receta(m)
            comp_list = [(x["componente"], x["cantidad_base"]) for x in actuales]
            for i,(n,_) in enumerate(comp_list):
                if n == c: comp_list[i]=(c,q); break
            else:
                comp_list.append((c,q))
            definir_receta_producto(m, comp_list)
            self.refrescar()
            messagebox.showinfo("OK","Receta actualizada.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

# ---------- Producción ----------
class VentanaProduccion(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Producción (Lotes) — solo Elaborados")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)
        row = ttk.Frame(frm); row.pack(fill="x", padx=2, pady=2)
        ttk.Label(row, text="Producto Elaborado:").pack(side="left")
        self.menu = ttk.Combobox(row, values=[p["nombre"] for p in listar_elaborados()], width=30, state="readonly"); self.menu.pack(side="left", padx=6)
        ttk.Label(row, text="Cantidad a producir (pz):").pack(side="left", padx=6)
        self.cant = ttk.Entry(row, width=10); self.cant.insert(0,"1"); self.cant.pack(side="left")
        ttk.Label(row, text="Nota:").pack(side="left", padx=6)
        self.nota = ttk.Entry(row, width=30); self.nota.pack(side="left", padx=6)
        ttk.Button(row, text="Registrar producción", command=self.producir).pack(side="left", padx=8)

        cols=("componente","cant_por_u","cant_total")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=12)
        for c,t in zip(cols,["Componente","Cant. por unidad (g/pz)","Total a consumir (g/pz)"]):
            self.tree.heading(c, text=t); self.tree.column(c, width=220 if c=="componente" else 180)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        ttk.Button(frm, text="Calcular consumo", command=self.calcular).pack(pady=6)

    def calcular(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        m = self.menu.get().strip()
        if not m: return
        try:
            q = float(self.cant.get())
        except:
            messagebox.showerror("Error","Cantidad inválida"); return
        try:
            for r in obtener_receta(m):
                total = r["cantidad_base"] * q
                self.tree.insert("", "end", values=(r["componente"], r["cantidad_base"], total))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def producir(self):
        m = self.menu.get().strip()
        try:
            q = float(self.cant.get())
        except:
            messagebox.showerror("Error","Cantidad inválida"); return
        try:
            pid = registrar_produccion(m, q, self.nota.get().strip() or "")
            messagebox.showinfo("OK", f"Producción registrada #{pid}")
            self.calcular()
        except Exception as e:
            messagebox.showerror("Error", str(e))

# ---------- Compras ----------
class VentanaCompras(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Compras (Entradas)")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        sel = ttk.Frame(frm); sel.pack(fill="x", padx=2, pady=4)
        ttk.Label(sel, text="Proveedor:").pack(side="left")
        self.cb_prov = ttk.Combobox(sel, values=[p["nombre"] for p in listar_proveedores()], width=30, state="readonly")
        self.cb_prov.pack(side="left", padx=6)
        ttk.Button(sel, text="Actualizar lista", command=self._refrescar_provs).pack(side="left", padx=4)

        lf = ttk.LabelFrame(frm, text="Partidas (Producto, Cantidad, Costo TOTAL)")
        lf.pack(fill="both", expand=True, padx=2, pady=6)

        self.tree = ttk.Treeview(lf, columns=("producto","cantidad","costo_total"), show="headings", height=12)
        self.tree.heading("producto", text="Producto")
        self.tree.heading("cantidad", text="Cantidad (unidad declarada)")
        self.tree.heading("costo_total", text="Costo TOTAL")
        self.tree.column("producto", width=260)
        self.tree.column("cantidad", width=180)
        self.tree.column("costo_total", width=140)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        # ----- Captura de partidas con títulos y unidad visible -----
        add = ttk.Frame(lf); add.pack(fill="x", padx=6, pady=6)

        # Productos disponibles y mapa nombre -> unidad
        productos = listar_para_compras()  # idealmente cada item: {"nombre": ..., "unidad" o "unidad_medida": ...}
        self._unidades = {
            p["nombre"]: (p.get("unidad_medida") or p.get("unidad") or "unidad")
            for p in productos
        }

        # Producto (combobox)
        self.prod = ttk.Combobox(add, values=[p["nombre"] for p in productos], width=40, state="readonly")
        self.prod.pack(side="left")
        self.prod.bind("<<ComboboxSelected>>", self._on_prod_change)

        # Contenedor de Cantidad (con título) + etiqueta de unidad
        qty_box = ttk.LabelFrame(add, text="Cantidad")
        qty_box.pack(side="left", padx=8)
        self.cant = ttk.Entry(qty_box, width=10)
        self.cant.insert(0, "1")
        self.cant.pack(side="left", padx=(6, 4), pady=4)
        # Unidad visible a la derecha de la cantidad
        self.lbl_unidad = ttk.Label(qty_box, text="unidad")
        self.lbl_unidad.pack(side="left", padx=(2, 6))

        # Contenedor de Costo TOTAL (con título)
        cost_box = ttk.LabelFrame(add, text="Costo total")
        cost_box.pack(side="left", padx=8)
        self.costo_total = ttk.Entry(cost_box, width=10)
        self.costo_total.insert(0, "0")
        self.costo_total.pack(side="left", padx=6, pady=4)

        ttk.Button(add, text="Agregar partida", command=self.add).pack(side="left", padx=6)

        ttk.Button(frm, text="Registrar compra", command=self.registrar).pack(pady=8)

        # Inicializa la unidad si hay un producto preseleccionado
        if self.prod.get():
            self._on_prod_change()

    def _refrescar_provs(self):
        self.cb_prov["values"] = [p["nombre"] for p in listar_proveedores()]

    def _on_prod_change(self, *args):
        nombre = (self.prod.get() or "").strip()
        unidad = self._unidades.get(nombre, "unidad")
        self.lbl_unidad.config(text=unidad)

    def add(self):
        p = self.prod.get().strip()
        try:
            c = float(self.cant.get())
            ct = float(self.costo_total.get())
        except:
            messagebox.showerror("Error", "Cantidad o costo inválidos")
            return
        if not p:
            return
        self.tree.insert("", "end", values=(p, c, ct))

    def registrar(self):
        items = []
        for iid in self.tree.get_children():
            p, c, ct = self.tree.item(iid, "values")
            items.append((p, float(c), float(ct)))
        if not items:
            messagebox.showerror("Error", "Agrega partidas")
            return
        try:
            prov = self.cb_prov.get().strip() or None
            cid = registrar_compra(items, proveedor=prov)
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            messagebox.showinfo("OK", f"Compra registrada #{cid}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ---------- Ventas ----------
class VentanaVentas(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Ventas / Merma (Código o Búsqueda)")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)
        row = ttk.Frame(frm); row.pack(fill="x", padx=2, pady=2)
        ttk.Label(row, text="Tipo:").pack(side="left")
        self.tipo = ttk.Combobox(row, values=["VENTA","MERMA"], width=10, state="readonly"); self.tipo.set("VENTA"); self.tipo.pack(side="left")

        ttk.Label(row, text="Cajero:").pack(side="left", padx=6)
        self.caj = ttk.Combobox(row, values=[c["nombre"] for c in listar_cajeros()], width=20, state="readonly"); self.caj.pack(side="left")
        ttk.Button(row, text="Actualizar lista", command=self._refrescar_caj).pack(side="left", padx=4)

        ttk.Label(row, text="Nota:").pack(side="left", padx=6); self.nota = ttk.Entry(row, width=30); self.nota.pack(side="left")
        ttk.Button(row, text="Registrar ticket", command=self.registrar).pack(side="right", padx=6)

        codigo_box = ttk.LabelFrame(frm, text="Agregar por CÓDIGO")
        codigo_box.pack(fill="x", padx=6, pady=6)
        ttk.Label(codigo_box, text="Código:").pack(side="left")
        self.cod = ttk.Entry(codigo_box, width=14); self.cod.pack(side="left", padx=6)
        ttk.Label(codigo_box, text="Cantidad (pz):").pack(side="left")
        self.cant_cod = ttk.Entry(codigo_box, width=8); self.cant_cod.insert(0,"1"); self.cant_cod.pack(side="left", padx=6)
        ttk.Button(codigo_box, text="Agregar", command=self.add_codigo).pack(side="left", padx=6)

        busc_box = ttk.LabelFrame(frm, text="Buscar por código o descripción")
        busc_box.pack(fill="both", padx=6, pady=6)
        top = ttk.Frame(busc_box); top.pack(fill="x")
        ttk.Label(top, text="Buscar:").pack(side="left")
        self.q = ttk.Entry(top, width=24); self.q.pack(side="left", padx=6)
        ttk.Button(top, text="Buscar", command=self.buscar).pack(side="left")
        ttk.Label(top, text="Cantidad (pz):").pack(side="left", padx=6)
        self.cant_busq = ttk.Entry(top, width=8); self.cant_busq.insert(0,"1"); self.cant_busq.pack(side="left")
        ttk.Button(top, text="Agregar seleccionado", command=self.add_seleccion).pack(side="left", padx=6)

        cols=("codigo","producto","precio")
        self.result = ttk.Treeview(busc_box, columns=cols, show="headings", height=8)
        for c,t,w in [("codigo","Código",120),("producto","Producto",280),("precio","Precio",100)]:
            self.result.heading(c, text=t); self.result.column(c, width=w)
        self.result.pack(fill="both", expand=True, padx=6, pady=6)

        cols=("codigo","producto","cantidad","precio","subtotal")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=12)
        for c,t,w in [("codigo","Código",100),("producto","Producto",240),("cantidad","Cantidad",90),("precio","Precio unit.",100),("subtotal","Subtotal",100)]:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        actions = ttk.Frame(frm); actions.pack(fill="x", padx=6)
        ttk.Label(frm, text="Solo productos vendibles (Elaborados y Productos); los Insumos NO se venden aquí.").pack(anchor="w", padx=6)
        ttk.Button(actions, text="Borrar seleccionado", command=self.borrar_seleccionado).pack(side="left", padx=4)

        self.items_by_iid = {}

    def _refrescar_caj(self):
        self.caj["values"] = [c["nombre"] for c in listar_cajeros()]

    def _insert_ticket_row(self, pid, nombre, codigo, precio, cantidad):
        subtotal = (precio * cantidad) if self.tipo.get()=="VENTA" else 0.0
        iid = self.tree.insert("", "end", values=(codigo, nombre, cantidad, f"{precio:.2f}", f"{subtotal:.2f}"))
        self.items_by_iid[iid] = (pid, cantidad, precio, codigo, nombre)

    def add_codigo(self):
        codigo = self.cod.get().strip()
        try: cant = float(self.cant_cod.get())
        except: messagebox.showerror("Error","Cantidad inválida"); return
        if not codigo:
            messagebox.showerror("Error","Ingresa un código"); return
        r = buscar_vendible_por_codigo(codigo)
        if not r:
            messagebox.showerror("No encontrado","No hay producto vendible con ese código."); return
        self._insert_ticket_row(r["id"], r["nombre"], r["codigo"], r["precio"], cant)
        self.cod.delete(0,"end"); self.cant_cod.delete(0,"end"); self.cant_cod.insert(0,"1")

    def buscar(self):
        q = self.q.get().strip()
        for i in self.result.get_children(): self.result.delete(i)
        if not q: return
        rows = buscar_vendibles_por_texto(q)
        for r in rows:
            self.result.insert("", "end", values=(r["codigo"] or "", r["nombre"], f'{r["precio"]:.2f}'))

    def add_seleccion(self):
        sel = self.result.selection()
        if not sel:
            messagebox.showerror("Error","Selecciona un producto de la lista"); return
        iid = sel[0]
        codigo, nombre, _ = self.result.item(iid,"values")
        try: cant = float(self.cant_busq.get())
        except: messagebox.showerror("Error","Cantidad inválida"); return
        r = buscar_vendible_por_codigo(codigo)
        if not r:
            messagebox.showerror("Error","El código seleccionado ya no es válido"); return
        self._insert_ticket_row(r["id"], nombre, r["codigo"], r["precio"], cant)

    def borrar_seleccionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atención","Selecciona una línea del ticket para borrar.")
            return
        for iid in sel:
            if iid in self.items_by_iid:
                del self.items_by_iid[iid]
            self.tree.delete(iid)

    def registrar(self):
        if not self.items_by_iid:
            messagebox.showerror("Error","Agrega partidas"); return
        cajero_nombre = self.caj.get().strip()
        if not cajero_nombre:
            messagebox.showerror("Error","Selecciona un cajero."); return
        tipo = self.tipo.get(); nota = self.nota.get().strip() or ""
        payload = [(pid, cant) for (pid, cant, precio, codigo, nombre) in self.items_by_iid.values()]
        try:
            vid = registrar_venta(tipo, payload, cajero_nombre, nota)
            self.items_by_iid.clear()
            for iid in self.tree.get_children(): self.tree.delete(iid)
            messagebox.showinfo("OK", f"{'Merma' if tipo=='MERMA' else 'Venta'} registrada #{vid}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

# ---------- Inventario ----------
class VentanaInventario(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Inventario")
        cols=("producto","stock","unidad","tipo")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        headers=["Producto","Stock","Unidad","Tipo"]
        widths=[260,120,80,140]
        for c,h,w in zip(cols,headers,widths):
            self.tree.heading(c, text=h); self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self, text="Refrescar", command=self.refrescar).pack(pady=6)
        self.refrescar()

    def refrescar(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            for r in inventario_actual():
                self.tree.insert("", "end", values=(r["nombre"], f'{r["cantidad"]:.3f}', r["unidad"], r["categoria"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

# ---------- Reportes ----------
class VentanaReportes(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Reportes")
        top = ttk.Frame(self); top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Desde (YYYY-MM-DD):").pack(side="left"); self.desde = ttk.Entry(top, width=12); self.desde.pack(side="left", padx=4)
        ttk.Label(top, text="Hasta (YYYY-MM-DD):").pack(side="left"); self.hasta = ttk.Entry(top, width=12); self.hasta.pack(side="left", padx=4)

        btns = ttk.Frame(self); btns.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns, text="Ventas DETALLADO", command=self.rp_ventas_det).pack(side="left", padx=4)
        ttk.Button(btns, text="Merma DETALLADO", command=self.rp_merma_det).pack(side="left", padx=4)
        ttk.Button(btns, text="Top productos", command=self.rp_top).pack(side="left", padx=4)
        ttk.Button(btns, text="Exportar CSV", command=self.exportar_csv).pack(side="right", padx=4)

        cols=("c1","c2","c3","c4","c5","c6")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c); self.tree.column(c, width=160)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self._headers_actuales = []  # para exportación

    def _clear(self, headers):
        self._headers_actuales = headers[:]
        for i in self.tree.get_children(): self.tree.delete(i)
        for i,h in enumerate(headers):
            col = f"c{i+1}"
            self.tree.heading(col, text=h)
            self.tree.column(col, width=220 if i==1 else 140)
        # Vacía columnas remanentes si headers < 6
        for j in range(len(headers), 6):
            col = f"c{j+1}"
            self.tree.heading(col, text="")
            self.tree.column(col, width=0)

    def rp_ventas_det(self):
        d = self.desde.get().strip() or None; h = self.hasta.get().strip() or None
        self._clear(["Fecha","Producto","Cantidad","Precio","Costo unit.","Total"])
        try:
            for r in reporte_ventas_detallado(d,h):
                self.tree.insert("", "end", values=(r["fecha"], r["producto"], r["cantidad"], f'{r["precio_unitario"]:.2f}', f'{r["costo_unitario"]:.2f}', f'{r["subtotal"]:.2f}'))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def rp_merma_det(self):
        d = self.desde.get().strip() or None; h = self.hasta.get().strip() or None
        self._clear(["Fecha","Producto","Unidades","Precio (venta)","Pérdida","-"])
        try:
            for r in reporte_merma_detallado(d,h):
                self.tree.insert("", "end", values=(r["fecha"], r["producto"], r["cantidad"], f'{(r["precio_venta"] or 0):.2f}', f'{(r["perdida"] or 0):.2f}', ""))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def rp_top(self):
        d = self.desde.get().strip() or None; h = self.hasta.get().strip() or None
        self._clear(["Producto","Cantidad","Ingreso","-","-","-"])
        try:
            for r in top_productos(10,d,h):
                self.tree.insert("", "end", values=(r["nombre"], r["cantidad"], f'{(r["ingreso"] or 0):.2f}', "", "", ""))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def exportar_csv(self):
        if not self._headers_actuales:
            messagebox.showwarning("Atención","No hay reporte para exportar.")
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV","*.csv")],
            title="Guardar reporte como CSV"
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(self._headers_actuales)
                for iid in self.tree.get_children():
                    vals = self.tree.item(iid, "values")
                    # Solo exportar tantas columnas como headers visibles
                    w.writerow(list(vals)[:len(self._headers_actuales)])
            messagebox.showinfo("OK", f"CSV guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el CSV:\n{e}")

# ---------- Main ----------
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cafetería — Inventario y Ventas — v2.7")
        self.geometry("1000x680")
        self._verificar_bd()
        self._menu_principal()

    def _verificar_bd(self):
        with conectar() as conn:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sucursales'").fetchone()
            if row is None:
                from db import _crear_tablas_basicas
                _crear_tablas_basicas(conn)

        need_init = False
        with conectar() as conn:
            from db import _migraciones
            _migraciones(conn)
            r = conn.execute("SELECT COUNT(*) c FROM sucursales").fetchone()
            if r["c"] == 0:
                need_init = True

        if need_init:
            nombre = simpledialog.askstring("Inicializar", "Nombre de la sucursal:")
            if not nombre:
                messagebox.showerror("Error","Debes indicar un nombre de sucursal.")
                self.destroy()
                return
            iniciar_bd(nombre)

    def _menu_principal(self):
        cont = ttk.Frame(self); cont.pack(fill="both", expand=True, padx=20, pady=20)
        ttk.Label(cont, text="Menú principal", font=("Segoe UI", 16, "bold")).pack(pady=10)
        grid = ttk.Frame(cont); grid.pack(pady=10)

        botones = [
            ("Registro de Productos",  lambda: VentanaProductos(self)),
            ("Recetas",    lambda: VentanaRecetas(self)),
            ("Compras (Entradas)", lambda: VentanaCompras(self)),
            ("Producción (Lotes)", lambda: VentanaProduccion(self)),
            ("Ventas / Merma", lambda: VentanaVentas(self)),
            ("Inventario", lambda: VentanaInventario(self)),
            ("Reportes",   lambda: VentanaReportes(self)),
            ("Registro de Proveedores", lambda: VentanaProveedores(self)),
            ("Cajeros",     lambda: VentanaCajeros(self)),
        ]
        for i,(txt,cmd) in enumerate(botones):
            ttk.Button(grid, text=txt, width=28, command=cmd).grid(row=i//2, column=i%2, padx=10, pady=10, sticky="ew")

if __name__ == "__main__":
    MainApp().mainloop()
