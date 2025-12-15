# 🧠 Smart Inventory
### Sistema de Gestión de Inventario — v0.1 (tester-local)

[🇬🇧 Read this in English](README_EN.md)

Smart Inventory es una aplicación web para la **gestión real de inventario** (doméstico u organizacional), diseñada para **uso local por una sola persona**.
Esta versión **v0.1 (tester-local)** está técnicamente cerrada, es estable y se ha desarrollado con especial foco en **integridad de datos, trazabilidad y usabilidad real**, no como demo.

---

## 📸 Capturas de pantalla

### 🏠 Home
<img src="imgs/home.png" width="700"/>

### 📦 Inventario (GIF animado)
<img src="imgs/inventario.gif" width="700"/>

### 🗂️ Gestor de ubicaciones recursivas
<img src="imgs/ubicaciones.png" width="700"/>

---

## 🚀 Funcionalidades incluidas en v0.1

- Entradas y salidas rápidas (QR o formulario manual)
- Gestión por **lotes**, con caducidades y estado de apertura
- Ubicaciones **jerárquicas recursivas**
- Auditoría por ubicación y auditoría total
- Paginación estable (25 ítems) en todas las vistas
- UI moderna y responsive (Tailwind + Alpine.js)
- Trazabilidad completa de movimientos
- Admin personalizado en Django
- Backups automáticos de la base de datos
- Hardening mínimo (DEBUG, ALLOWED_HOSTS, logs de error)

---

## 🧩 Arquitectura técnica

- Backend: Django + Django REST Framework
- Frontend: TailwindCSS + Alpine.js
- Base de datos: SQLite (local)
- Enfoque: integridad, atomicidad y cambios solo aditivos

---

## 🔐 Alcance y decisiones de diseño (v0.1)

- 👤 Usuario único
- 🌐 Uso local / LAN
- 💾 Base de datos local (SQLite)
- 🔒 Sin login ni roles
- 🔄 Sin sincronización ni modo offline
- 📦 Distribución e instalación **fuera del alcance de v0.1**

Esta versión actúa como **base sólida y congelada** para futuras iteraciones.

---

## 🔧 Instalación (entorno local)

```bash
git clone https://github.com/tu-usuario/smart-inventory.git
cd smart-inventory
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

---

## 📚 Documentación técnica

Disponible en `docs/`:
- `smart_inventory.tex`
- `smart_inventory.pdf`

---

## 🧊 Estado del proyecto

**v0.1 (tester-local) — FREEZE**
- Solo se aceptan correcciones críticas
- No se modifica la lógica de negocio
- Base estable para v0.2 (distribución y UX)

---

## 📄 Licencia

MIT License.

---

## 👤 Autor

David García
