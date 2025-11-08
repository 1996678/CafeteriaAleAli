import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from db import *
import platform
from tkinter import font as tkfont  
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

            crear_proveedor(nombre, telefono)

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
        self.p_unidad = ttk.Combobox(frm, values=["Pieza","Gramo","Kilo"], width=10, state="readonly")
        self.p_unidad.set("Pieza")
        self.p_unidad.grid(row=r, column=1, padx=6); r += 1

        ttk.Label(frm, text="Precio al público (solo vendibles):").grid(row=r, column=0, sticky="w", padx=6, pady=4)
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

    def _titulo_nombre(self, *args):
        v = self.var_nombre.get()
        u = v.title()
        if v != u:
            self.var_nombre.set(u)

    def _titulo_codigo(self, *args):
        v = self.var_codigo.get()
        u = v.upper()  
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
            codigo    = (self.var_codigo.get() or "").strip().upper()

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
                    (p.get("codigo","") or "").upper(),
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

        # Cambiado: "Cantidad por pieza"
        nota = ttk.Label(frm, text="Las recetas aceptan solo INSUMOS como componentes. Cantidades en g o pz por pieza vendida.")
        nota.pack(anchor="w", padx=4)

        lf = ttk.LabelFrame(frm, text="Agregar/actualizar componente")
        lf.pack(fill="x", padx=2, pady=6)
        self.comp = ttk.Combobox(lf, values=[p["nombre"] for p in listar_insumos()], width=30, state="readonly"); self.comp.pack(side="left", padx=6, pady=6)
        ttk.Label(lf, text="Cantidad por pieza (g/pz):").pack(side="left", padx=6)
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
        for c,t in zip(cols,["Componente","Cant. por pieza (g/pz)","Total a consumir (g/pz)"]):
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

        add = ttk.Frame(lf); add.pack(fill="x", padx=6, pady=6)

        productos = listar_para_compras()
        self._unidades = {p["nombre"]: (p.get("unidad") or "unidad") for p in productos}

        self.prod = ttk.Combobox(add, values=[p["nombre"] for p in productos], width=40, state="readonly")
        self.prod.pack(side="left")
        self.prod.bind("<<ComboboxSelected>>", self._on_prod_change)

        qty_box = ttk.LabelFrame(add, text="Cantidad")
        qty_box.pack(side="left", padx=8)
        self.cant = ttk.Entry(qty_box, width=10)
        self.cant.insert(0, "1")
        self.cant.pack(side="left", padx=(6, 4), pady=4)
        self.lbl_unidad = ttk.Label(qty_box, text="unidad")
        self.lbl_unidad.pack(side="left", padx=(2, 6))

        cost_box = ttk.LabelFrame(add, text="Costo total")
        cost_box.pack(side="left", padx=8)
        self.costo_total = ttk.Entry(cost_box, width=10)
        self.costo_total.insert(0, "0")
        self.costo_total.pack(side="left", padx=6, pady=4)

        ttk.Button(add, text="Agregar partida", command=self.add).pack(side="left", padx=6)

        ttk.Button(frm, text="Registrar compra", command=self.registrar).pack(pady=8)

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
        self.title("Ventas / Merma (Búsqueda)")
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=8, pady=8)

        row = ttk.Frame(frm); row.pack(fill="x", padx=2, pady=2)
        ttk.Label(row, text="Tipo:").pack(side="left")
        self.tipo = ttk.Combobox(row, values=["VENTA","MERMA"], width=10, state="readonly")
        self.tipo.set("VENTA"); self.tipo.pack(side="left")

        ttk.Label(row, text="Nota:").pack(side="left", padx=6)
        self.nota = ttk.Entry(row, width=30); self.nota.pack(side="left")

        ttk.Button(row, text="Registrar venta", command=self.registrar).pack(side="right", padx=6)

        busc_box = ttk.LabelFrame(frm, text="Buscar por código o descripción")
        busc_box.pack(fill="both", padx=6, pady=6)
        top = ttk.Frame(busc_box); top.pack(fill="x")
        ttk.Label(top, text="Buscar:").pack(side="left")
        self.q = ttk.Entry(top, width=24); self.q.pack(side="left", padx=6)
        ttk.Button(top, text="Buscar", command=self.buscar).pack(side="left")
        ttk.Label(top, text="Cantidad (pz):").pack(side="left", padx=6)
        self.cant_busq = ttk.Entry(top, width=8); self.cant_busq.insert(0,"1"); self.cant_busq.pack(side="left")
        ttk.Button(top, text="Agregar producto", command=self.add_seleccion).pack(side="left", padx=6)

        cols=("codigo","producto","precio")
        self.result = ttk.Treeview(busc_box, columns=cols, show="headings", height=8)
        for c,t,w in [("codigo","Código",120),("producto","Producto",280),("precio","Precio",100)]:
            self.result.heading(c, text=t); self.result.column(c, width=w)
        self.result.pack(fill="both", expand=True, padx=6, pady=6)

        cols=("codigo","producto","cantidad","precio","subtotal")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=9)
        for c,t,w in [("codigo","Código",100),("producto","Producto",240),("cantidad","Cantidad",90),("precio","Precio unit.",100),("subtotal","Subtotal",100)]:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        actions = ttk.Frame(frm); actions.pack(fill="x", padx=6, pady=(0,6))
        ttk.Label(frm, text="Solo productos vendibles (Elaborados y Productos); los Insumos NO se venden aquí.").pack(anchor="w", padx=6)
        ttk.Button(actions, text="Borrar seleccionado", command=self.borrar_seleccionado).pack(side="left", padx=4)

        self.q.bind("<Return>", lambda e: self.buscar())
        self.cant_busq.bind("<Return>", lambda e: self.add_seleccion())
        self.result.bind("<Double-1>", lambda e: self.add_seleccion())

        self.q.focus_set()

        self.items_by_iid = {}
    

    def add_codigo(self):
        codigo = self.cod.get().strip()
        try:
            cant = float(self.cant_cod.get())
        except:
            messagebox.showerror("Error", "Cantidad inválida"); return
        if not codigo:
            messagebox.showerror("Error", "Ingresa un código"); return

        r = buscar_vendible_por_codigo(codigo)
        if not r:
            messagebox.showerror("No encontrado", "No hay producto vendible con ese código."); return

        # Validar stock antes de agregar al ticket
        disp = stock_disponible_producto(r["id"])
        if cant > disp:
            messagebox.showerror("Stock insuficiente",
                                f"Disponible de '{r['nombre']}': {disp:.3f}.\nNo se agregó al ticket.")
            return

        self._insert_ticket_row(r["id"], r["nombre"], r["codigo"], r["precio"], cant)
        self.cod.delete(0, "end")
        self.cant_cod.delete(0, "end"); self.cant_cod.insert(0, "1")

    
    def add_seleccion(self):
        sel = self.result.selection()
        if not sel:
            messagebox.showerror("Error", "Selecciona un producto de la lista")
            return

        iid = sel[0]
        codigo, nombre, _ = self.result.item(iid, "values")
        try:
            cant = float(self.cant_busq.get())
        except:
            messagebox.showerror("Error", "Cantidad inválida")
            return

        r = buscar_vendible_por_codigo(codigo)
        if not r:
            messagebox.showerror("Error", "El código seleccionado ya no es válido")
            return

        disp = stock_disponible_producto(r["id"])
        if cant > disp:
            messagebox.showerror("Stock insuficiente",
                                f"Disponible de '{r['nombre']}': {disp:.3f}.\nNo se agregó al ticket.")
            return

        self._insert_ticket_row(r["id"], nombre, r["codigo"], r["precio"], cant)

        self.cant_busq.delete(0, "end")
        self.cant_busq.insert(0, "1")
        self.result.selection_remove(iid)
        self.result.focus("")
        self.q.delete(0, "end")           
        for kid in self.result.get_children():  
            self.result.delete(kid)
        self.result.selection_remove(iid)
        self.result.focus("")

        self.q.focus_set()

    
    def _insert_ticket_row(self, pid, nombre, codigo, precio, cantidad):
        subtotal = (precio * cantidad) if self.tipo.get()=="VENTA" else 0.0
        iid = self.tree.insert("", "end", values=(codigo, nombre, cantidad, f"{precio:.2f}", f"{subtotal:.2f}"))
        self.items_by_iid[iid] = (pid, cantidad, precio, codigo, nombre)


    def buscar(self):
        q = self.q.get().strip()
        for i in self.result.get_children():
            self.result.delete(i)
        if not q:
            return
        rows = buscar_vendibles_por_texto(q)
        for r in rows:
            self.result.insert("", "end", values=(r["codigo"] or "", r["nombre"], f'{r["precio"]:.2f}'))
        kids = self.result.get_children()
        if kids:
            self.result.selection_set(kids[0])
            self.result.focus(kids[0])
            self.result.see(kids[0])

    

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
            messagebox.showerror("Error", "Agrega partidas")
            return

        tipo = self.tipo.get()
        nota = self.nota.get().strip() or ""

        faltantes = []
        for (pid, cant, _precio, _codigo, nombre) in self.items_by_iid.values():
            disp = stock_disponible_producto(pid) 
            if cant > disp:
                faltantes.append((nombre, disp, cant))

        if faltantes:
            msg = "Stock insuficiente en:\n" + "\n".join(
                f"• {n}: disponible {d:.3f}, solicitado {c:.3f}" for (n, d, c) in faltantes
            )
            messagebox.showerror("Stock insuficiente", msg)
            return

        payload = [(pid, cant) for (pid, cant, _precio, _codigo, _nombre) in self.items_by_iid.values()]
        try:
            vid = registrar_venta(tipo, payload, None, nota) 
            self.items_by_iid.clear()
            for iid in self.tree.get_children():
                self.tree.delete(iid)
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
        ttk.Label(top, text="Proveedor:").pack(side="left", padx=(10,2))
        self.cb_prov = ttk.Combobox(
            top, values=[], width=22, state="disabled"
        )
        self.cb_prov.pack(side="left")

        self.btn_prov_upd = ttk.Button(top, text="Actualizar", command=self._aplicar_filtro_proveedor, state="disabled")
        self.btn_prov_upd.pack(side="left", padx=4)
        self.cb_prov.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro_proveedor())

        self.btn_prov_clear = ttk.Button(top, text="Limpiar", command=self._limpiar_prov, state="disabled")
        self.btn_prov_clear.pack(side="left", padx=2)


        btns = ttk.Frame(self); btns.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns, text="Ventas DETALLADO", command=self.rp_ventas_det).pack(side="left", padx=4)
        ttk.Button(btns, text="Merma DETALLADO", command=self.rp_merma_det).pack(side="left", padx=4)
        ttk.Button(btns, text="Compras DETALLADO", command=self.rp_compras_det).pack(side="left", padx=4) 
        ttk.Button(btns, text="Ganancias DETALLADO", command=self.rp_ganancias).pack(side="left", padx=4)
        ttk.Button(btns, text="Top productos", command=self.rp_top).pack(side="left", padx=4)
        ttk.Button(btns, text="Exportar Excel", command=self.exportar_csv).pack(side="right", padx=4)

        cols = ("c1","c2","c3","c4","c5","c6","c7","c8","c9") 
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=160)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.tag_configure("total", font=("Segoe UI", 10, "bold"), background="#F5FBFE")
        self._headers_actuales = []  

    def _clear(self, headers):
        self._headers_actuales = headers[:]
        for i in self.tree.get_children():
            self.tree.delete(i)

        total_cols = len(self.tree["columns"])  
        for i, h in enumerate(headers):
            col = f"c{i+1}"
            self.tree.heading(col, text=h)
            self.tree.column(col, width=220 if i == 1 else 160)

        for j in range(len(headers), total_cols):
            col = f"c{j+1}"
            self.tree.heading(col, text="")
            self.tree.column(col, width=0)
    
    def _aplicar_filtro_proveedor(self):
        if str(self.cb_prov.cget("state")) == "disabled":
            return
        self.rp_compras_det()
    
    def _set_prov_filter_active(self, active: bool):
        """Activa/desactiva el filtro de proveedor (solo compras)."""
        if active:
            self.cb_prov.config(state="readonly")
            self.btn_prov_upd.config(state="normal")
            self.btn_prov_clear.config(state="normal")
            if not self.cb_prov["values"]:
                self._refrescar_prov()
            if not self.cb_prov.get():
                self.cb_prov.set("(Todos)")
        else:
            self.cb_prov.config(state="disabled")
            self.btn_prov_upd.config(state="disabled")
            self.btn_prov_clear.config(state="disabled")

    def _refrescar_prov(self):
        nombres = [p["nombre"] for p in listar_proveedores()]
        actual = self.cb_prov.get().strip()
        vals = ["(Todos)"] + nombres
        self.cb_prov["values"] = vals
        if actual in vals:
            self.cb_prov.set(actual)
        else:
            self.cb_prov.set("(Todos)")

    def _limpiar_prov(self):
        if str(self.cb_prov.cget("state")) != "disabled":
            self.cb_prov.set("(Todos)")
            self.rp_compras_det()



    def rp_ventas_det(self):
        self._set_prov_filter_active(False)
        d = self.desde.get().strip() or None; h = self.hasta.get().strip() or None
        self._clear(["Fecha","Producto","Unidades vendidas","Precio unit. público","Costo unitario","Total ingresos"])
        
        tot_cant = 0.0
        tot_total = 0.0
        try:
            rows = reporte_ventas_detallado(d,h)
            for r in rows:
                q = float(r["cantidad"] or 0)
                total = float(r["subtotal"] or 0)
                tot_cant += q
                tot_total += total
                self.tree.insert(
                    "", "end",
                    values=(
                        r["fecha"], r["producto"], q,
                        f'${(r["precio_unitario"] or 0):.2f}',
                        f'${(r["costo_unitario"] or 0):.2f}',
                        f'${total:.2f}'
                    )
                )
            self.tree.insert(
                "", "end",
                values=("","","", "", "TOTAL:", f'${tot_total:.2f}'),
                tags=("total",)
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def rp_merma_det(self):
        self._set_prov_filter_active(False)
        d = self.desde.get().strip() or None; h = self.hasta.get().strip() or None
        self._clear(["Fecha","Producto","Unidades vendidas","Precio unit. público","Pérdida"])
        tot_unidades = 0.0
        tot_perdida = 0.0
        try:
            rows = reporte_merma_detallado(d,h)
            for r in rows:
                q = float(r["cantidad"] or 0)
                perd = float(r["perdida"] or 0)
                tot_unidades += q
                tot_perdida += perd
                self.tree.insert(
                    "", "end",
                    values=(
                        r["fecha"], r["producto"], q,
                        f'${(r["precio_venta"] or 0):.2f}',
                        f'${perd:.2f}'
                    )
                )
            self.tree.insert(
                "", "end",
                values=("", "TOTAL:", f'{tot_unidades:.2f}', "", f'${tot_perdida:.2f}'),
                tags=("total",)
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def rp_compras_det(self):
        self._set_prov_filter_active(True) 
        d = self.desde.get().strip() or None
        h = self.hasta.get().strip() or None
        raw = (self.cb_prov.get().strip() if hasattr(self, "cb_prov") else "")
        prov = None if (raw == "" or raw == "(Todos)") else raw

        self._clear(["Fecha","Proveedor","Producto","Unidades compradas","UoM","Costo unitario","Costo total"])

        tot_ct = 0.0
        try:
            rows = reporte_compras_detallado(d, h, prov)
            for r in rows:
                q  = float(r["cantidad"] or 0)
                cu = float(r["costo_unitario"] or 0)
                ct = float(r["costo_total"] or 0)
                tot_ct += ct
                self.tree.insert(
                    "", "end",
                    values=(r["fecha"], r["proveedor"], r["producto"], q, r["unidad"], f"${cu:.2f}", f"${ct:.2f}")
                )
            self.tree.insert(
                "", "end",
                values=("", "TOTAL:", "", "", "", "", f"${tot_ct:.2f}"),
                tags=("total",)
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def rp_top(self):
        self._set_prov_filter_active(False)
        d = self.desde.get().strip() or None; h = self.hasta.get().strip() or None
        self._clear(["Producto","Unidades vendidas","Ingreso"])
        tot_cant = 0.0
        tot_ing  = 0.0
        try:
            rows = top_productos(10,d,h)
            for r in rows:
                q = float(r["cantidad"] or 0)
                ing = float(r["ingreso"] or 0)
                tot_cant += q
                tot_ing  += ing
                self.tree.insert("", "end", values=(r["nombre"], q, f'{ing:.2f}'))
            self.tree.insert("", "end", values=("TOTAL:", f'{tot_cant:.2f}', f'${tot_ing:.2f}'),
            tags=("total",)
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    def rp_ganancias(self):
        d = self.desde.get().strip() or None
        h = self.hasta.get().strip() or None

        self._clear(["Fecha","Producto","Cantidad","Precio unit. público","Total ingreso","Costo unit.","Margen unit.","Margen total","% Margen"])

        tot_ingreso = 0.0
        tot_costo   = 0.0
        tot_margen  = 0.0

        try:
            rows = reporte_ventas_detallado(d, h)
            for r in rows:
                cantidad = float(r["cantidad"])
                precio_u = float(r["precio_unitario"])
                costo_u  = float(r["costo_unitario"])
                ingreso  = float(r.get("subtotal", precio_u * cantidad))

                margen_unit = float(r.get("margen_unit")) if r.get("margen_unit") is not None else (precio_u - costo_u)
                margen_total = float(r.get("margen_total")) if r.get("margen_total") is not None else (margen_unit * cantidad)
                pct = float(r.get("margen_pct")) if r.get("margen_pct") is not None else (
                    (margen_unit / precio_u * 100.0) if precio_u > 0 else 0.0
                )

                tot_ingreso += ingreso
                tot_costo   += (costo_u * cantidad)
                tot_margen  += margen_total

                self.tree.insert("", "end", values=(
                    r["fecha"],
                    r["producto"],
                    cantidad,
                    f"${precio_u:.2f}",
                    f"${ingreso:.2f}",
                    f"${costo_u:.2f}",
                    f"${margen_unit:.2f}",
                    f"${margen_total:.2f}",
                    f"{pct:.2f}%"
                ))

            pct_total = (tot_margen / tot_ingreso * 100.0) if tot_ingreso > 0 else 0.0

            self.tree.insert("", "end",
                values=(
                    "", "TOTAL:", "",
                    "",                           # Precio unit. no aplica en total
                    f"${tot_ingreso:.2f}",         # Total ingreso del periodo
                    f"${tot_costo:.2f}",           # Costo total estimado
                    "",                           # Margen unit. (no aplica)
                    f"${tot_margen:.2f}",          # Margen total
                    f"{pct_total:.2f}%"           # % Margen ponderado
                ),
                tags=("total",)
            )
            self.tree.tag_configure("total", font=("Segoe UI", 10, "bold"))
            try:
                self.tree.tag_configure("total", background=PALETTE.get("total_bg", "#F5FBFE"))
            except:
                pass

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
                    w.writerow(list(vals)[:len(self._headers_actuales)])
            messagebox.showinfo("OK", f"CSV guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el CSV:\n{e}")

# --------- Paletas de color ---------
PALETTES = {
    "light": {
        "bg": "#F7F7F9",
        "panel": "#FFFFFF",
        "fg": "#23262B",
        "muted": "#6B7280",
        "border": "#E5E7EB",
        "accent": "#0E7490",
        "accent2": "#10B981",
        "warn": "#EF4444",
        "sel_bg": "#D0F0F7",
        "row_alt": "#FAFAFC",
        "heading": "#0B5568",
        "total_bg": "#F5FBFE"
    },
    "dark": {
        "bg": "#1E1E22",
        "panel": "#2A2B2F",
        "fg": "#F5F5F5",
        "muted": "#A1A1AA",
        "border": "#3F3F46",
        "accent": "#0EA5E9",
        "accent2": "#22C55E",
        "warn": "#EF4444",
        "sel_bg": "#083344",
        "row_alt": "#232427",
        "heading": "#7DD3FC",
        "total_bg": "#0F172A"
    }
}

CURRENT_THEME = "light"

def apply_theme(root: tk.Tk, mode: str = None):
    global CURRENT_THEME, PALETTE
    if mode:
        CURRENT_THEME = mode
    PALETTE = PALETTES[CURRENT_THEME]
    root.configure(bg=PALETTE["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    base_font = tkfont.nametofont("TkDefaultFont")
    base_font.configure(family="Segoe UI", size=10)
    root.option_add("*Font", base_font)

    style.configure(".", background=PALETTE["bg"], foreground=PALETTE["fg"])

    style.configure("TFrame", background=PALETTE["bg"])
    style.configure("TLabelframe", background=PALETTE["panel"], bordercolor=PALETTE["border"])
    style.configure("TLabelframe.Label",
                    background=PALETTE["panel"],
                    foreground=PALETTE["heading"],
                    font=("Segoe UI", 10, "bold"))

    style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["fg"])
    style.configure("Muted.TLabel", foreground=PALETTE["muted"], background=PALETTE["bg"])

    style.configure("TButton",
        background=PALETTE["accent"],
        foreground="white",
        borderwidth=0,
        padding=(10, 6)
    )
    style.map("TButton",
        background=[("active", "#0C6A83"), ("pressed", "#0A5B71")],
        relief=[("pressed", "sunken"), ("!pressed", "flat")]
    )

    sec_bg = "#E6F5F9" if CURRENT_THEME == "light" else "#253037"
    sec_bg_active = "#D9EEF4" if CURRENT_THEME == "light" else "#2B3840"
    style.configure("Secondary.TButton",
        background=sec_bg,
        foreground=PALETTE["heading"],
        borderwidth=0,
        padding=(10, 6)
    )
    style.map("Secondary.TButton",
        background=[("active", sec_bg_active)]
    )

    entry_conf = dict(
        fieldbackground=PALETTE["panel"],
        background=PALETTE["panel"],
        foreground=PALETTE["fg"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["accent"],
        darkcolor=PALETTE["border"],
        padding=4
    )
    style.configure("TEntry", **entry_conf)
    style.configure("TCombobox", **entry_conf)
    style.map("TCombobox",
        fieldbackground=[("readonly", PALETTE["panel"])],
        foreground=[("readonly", PALETTE["fg"])],
        background=[("readonly", PALETTE["panel"])]
    )

    # Treeview (tablas)
    style.configure("Treeview",
        background=PALETTE["panel"],
        fieldbackground=PALETTE["panel"],
        foreground=PALETTE["fg"],
        bordercolor=PALETTE["border"],
        rowheight=26
    )
    style.map("Treeview",
        background=[("selected", PALETTE["sel_bg"])],
        foreground=[("selected", PALETTE["fg"])]
    )
    # Headings
    head_bg = "#F1F5F9" if CURRENT_THEME == "light" else "#33363B"
    head_active = "#E8EEF4" if CURRENT_THEME == "light" else "#3B3E44"
    style.configure("Treeview.Heading",
        background=head_bg,
        foreground=PALETTE["heading"],
        relief="flat",
        padding=(6, 4),
        font=("Segoe UI", 10, "bold"),
        bordercolor=PALETTE["border"]
    )
    style.map("Treeview.Heading",
        background=[("active", head_active)]
    )
    
# ---------- Main ---------
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cafetería Alé Alí— Inventario y Ventas")
        self.geometry("1000x680")
        
        self.modo_inicial = CURRENT_THEME
        apply_theme(self, self.modo_inicial)
  
        
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
        ttk.Label(cont, text="Cafetería Alé Alí", font=("Segoe UI", 16, "bold")).pack(pady=10)
        ttk.Label(cont, text="Menú principal", font=("Segoe UI", 14, "bold")).pack(pady=10)
        grid = ttk.Frame(cont); grid.pack(pady=10)

        botones = [
            ("Registro de Productos",  lambda: VentanaProductos(self)),
            ("Registro de recetas",    lambda: VentanaRecetas(self)),
            ("Compras (Entradas)", lambda: VentanaCompras(self)),
            ("Producción de elaborados", lambda: VentanaProduccion(self)),
            ("Control de Ventas / Merma", lambda: VentanaVentas(self)),
            ("Inventario", lambda: VentanaInventario(self)),
            ("Reportes",   lambda: VentanaReportes(self)),
            ("Registro de Proveedores", lambda: VentanaProveedores(self)),
        ]
        for i,(txt,cmd) in enumerate(botones):
            ttk.Button(grid, text=txt, width=28, command=cmd).grid(row=i//2, column=i%2, padx=10, pady=10, sticky="ew")
            
        def toggle_tema():
            global CURRENT_THEME
            nuevo = "dark" if CURRENT_THEME == "light" else "light"
            apply_theme(self, nuevo)
            btn_tema.config(text=f"Modo {'claro' if nuevo == 'dark' else 'oscuro'}")

        btn_tema = ttk.Button(cont, text="Modo oscuro", style="Secondary.TButton", command=toggle_tema)
        btn_tema.pack(pady=(20, 0))


if __name__ == "__main__":
    MainApp().mainloop()