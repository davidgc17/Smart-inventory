# 🧠 Smart Inventory
### Inventory Management System — v0.1 (tester-local)

[🇪🇸 Leer en español](README.md)

Smart Inventory is a web application for **real-world inventory management**, designed for **local use by a single user**.
Version **v0.1 (tester-local)** is technically frozen and stable, with a strong focus on **data integrity, traceability, and practical usability**.

---

## 📸 Screenshots

### 🏠 Home
<img src="imgs/home.png" width="700"/>

### 📦 Inventory (animated GIF)
<img src="imgs/inventario.gif" width="700"/>

### 🗂️ Recursive Location Manager
<img src="imgs/ubicaciones.png" width="700"/>

---

## 🚀 Features included in v0.1

- Fast input/output (QR or manual form)
- **Batch-based stock management** with expiration tracking
- Recursive hierarchical locations
- Location-based and global audits
- Stable pagination (25 items per view)
- Modern responsive UI (Tailwind + Alpine.js)
- Full movement traceability
- Customized Django admin
- Automatic database backups
- Minimal security hardening

---

## 🧩 Technical Architecture

- Backend: Django + Django REST Framework
- Frontend: TailwindCSS + Alpine.js
- Database: SQLite (local)
- Design focus: atomicity, integrity, additive-only changes

---

## 🔐 Scope and design decisions (v0.1)

- 👤 Single user
- 🌐 Local / LAN usage
- 💾 Local database (SQLite)
- 🔒 No authentication or roles
- 🔄 No sync or offline mode
- 📦 Distribution and installers **out of scope for v0.1**

---

## 🧊 Project status

**v0.1 (tester-local) — FREEZE**
- Only critical fixes allowed
- Business logic frozen
- Stable base for v0.2

---

## 📄 License

MIT License.

---

## 👤 Author

David García
