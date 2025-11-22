# 🧠 Inventario Inteligente — Sistema de Gestión Simplificada

Aplicación web desarrollada con **Django** y **Tailwind CSS** para la gestión de inventarios domésticos o técnicos, con soporte para escaneo QR, control de ubicaciones jerárquicas y auditorías automáticas.

---

## 🚀 Características principales

- **Entradas y salidas rápidas** mediante formulario o escaneo QR.
- **Ubicaciones jerárquicas anidadas** (ejemplo: *Cocina → Armario 1 → Caja Roja*).
- **Registro histórico de movimientos** (IN / OUT / AUD / ADJ).
- **Control de lotes y caducidades**, con agrupación automática por producto.
- **Sistema de auditoría:**
  - Auditoría por ubicación (`AUD`)
  - Auditoría total (`AUDTOTAL`)
- **Panel de administración mejorado**:
  - Búsqueda y filtros rápidos.
  - Visualización jerárquica de ubicaciones.
  - Resaltado visual de stock y caducidades.

---

## ⚙️ Tecnologías utilizadas

| Componente | Tecnología |
|-------------|-------------|
| Backend | Django + Django REST Framework |
| Frontend | Tailwind CSS + JavaScript |
| Base de datos | SQLite (modo desarrollo) |
| Escaneo QR | [html5-qrcode](https://github.com/mebjas/html5-qrcode) |
| Generación QR | [QRious](https://github.com/neocotic/qrious) |

---

## 🧩 Estructura principal

```
inventory/
│
├── models.py          # Definición de Product, Location, Movement, Batch
├── api.py             # Endpoints REST (IN, OUT, AUD, AUDTOTAL)
├── admin.py           # Personalización del panel administrativo
├── serializers.py     # Serializadores DRF con rutas jerárquicas
└── templates/
    └── inventory/
        └── scan.html  # Interfaz principal de escaneo y registro
```

---

## 💡 Tipos de movimiento disponibles

| Código | Descripción | Requiere Payload | Requiere Ubicación |
|---------|--------------|------------------|--------------------|
| `IN` | Entrada de producto nuevo o existente | ❌ No | ✅ Sí |
| `OUT` | Salida de producto existente | ✅ Sí (`PRD:<uuid>`) | ✅ Sí |
| `AUD` | Auditoría de una ubicación concreta | ❌ No | ✅ Sí |
| `AUDTOTAL` | Auditoría global de todo el inventario | ❌ No | ❌ No |
| `ADJ` | Ajuste manual (en desarrollo) | ❌ No | ✅ Sí |

---

## 🧠 Estructura jerárquica de ubicaciones

El modelo `Location` permite anidar ubicaciones sin límite de profundidad.  
Cada objeto almacena automáticamente su **ruta completa** (`full_path`) para búsquedas y auditorías.

Ejemplo:
```
Cocina / Armario 1 / Caja Roja
```

---

## 🧾 Próximas fases

- 🧱 Mejoras visuales en la interfaz de auditoría (`scan.html`).
- 🔐 Aislamiento por usuario (inventarios personales).
- 📊 Dashboard de estadísticas y consumo.
- 🧮 Control de stock mínimo con alertas visuales.

---

## 👨‍💻 Autor

Desarrollado por **David García**.  
📦 Proyecto en evolución — primeras pruebas funcionales completadas (Fase 3).

REVISA LA CARPETA DOCS PARA DETALLES MAS TÉCNICOS
