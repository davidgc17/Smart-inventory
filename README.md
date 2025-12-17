# 🧠 Smart Inventory

📘 **English version:** [README_EN.md](README_EN.md)

Smart Inventory es una aplicación de gestión de inventario diseñada para uso real,
pensada para ser clara, estable y fácil de usar tanto en entornos domésticos
como en pequeños contextos profesionales.

El objetivo del proyecto es ofrecer una herramienta que no solo registre productos,
sino que permita controlar stock, caducidades y ubicaciones de forma estructurada,
con una base técnica sólida y extensible.

---

## 🚀 Uso básico (v0.1)

Smart Inventory v0.1 está diseñada para uso local en un PC, con acceso opcional desde un móvil en la misma red.

1. Inicia la aplicación.
2. Accede desde el navegador a `http://localhost:8000`.
3. Inicia sesión o regístrate con un usuario.
4. Desde un móvil conectado a la misma WiFi, accede a:
   `http://IP_DEL_PC:8000`.

### Modos principales
- **Entrada**: registrar nuevos productos o lotes.
- **Salida**: retirar stock mediante QR o búsqueda manual (FIFO).
- **Auditoría**: comprobar el estado de un producto concreto.
- **Auditoría total**: revisión global del inventario.

Las auditorías están limitadas a **25 ítems por página** para garantizar estabilidad y buen rendimiento.

---

## 📱 Uso desde móvil

La aplicación puede utilizarse desde el navegador del móvil si ambos dispositivos están en la misma red local.

Desde el menú de la aplicación es posible añadir un acceso directo a la pantalla de inicio (Android),
permitiendo abrir Smart Inventory como si fuera una aplicación.

---

## ⚠️ Limitaciones conocidas (v0.1)

- Uso local únicamente (sin acceso desde Internet).
- Base de datos SQLite local.
- Versión orientada a testing real y validación de estabilidad antes de nuevas fases.
