# 🧠 Smart Inventory

An intelligent inventory management system designed for **real-world use**, featuring
QR scanning, audits, hierarchical locations, and desktop distribution.

**Current status:**  
✅ Stable release **v0.1**  
🔄 Active project — currently in **PHASE 5 of the general roadmap**

---

## 📌 What is Smart Inventory?

Smart Inventory is a Django-based application designed to manage inventory in a clear and
robust way for local environments (home, workshop, small warehouse, laboratory).

It is designed to:
- run in a desktop browser,
- be accessed from mobile devices on a local network (PWA),
- be distributed as a standalone Windows `.exe`.

---

## 🖥️ Application overview

### Home
![Home](imgs/home.png)

### Inventory and movements (IN / OUT / Audits)
![Inventory](imgs/inventario.gif)

### Hierarchical location manager
![Locations](imgs/ubicaciones.png)

---

## ✅ Project status (v0.1)

Version **v0.1** is considered **stable and usable** for:

- ✔️ Real local usage
- ✔️ Mobile access over local network (LAN + PWA)
- ✔️ Windows executable distribution (.exe)
- ✔️ Persistent data stored outside the binary
- ✔️ Reliable audits (critical backend bug fixed)

This is not a demo or a prototype: it is a solid base to continue building on.

---

## 🔧 Main features

- 📦 Product and batch management
- 📍 Hierarchical locations (tree structure)
- 🔄 Inventory movements:
  - `IN` (input)
  - `OUT` (output)
  - `AUD` (location audit)
  - `AUDTOTAL` (global audit)
- 📷 QR code generation and scanning
- 📱 Mobile access (local PWA)
- 🖥️ Windows executable built with PyInstaller
- 🧾 Persistent logging
- 💾 Stable local database

---

## 🧭 Roadmap (summary)

**PHASE 1 – Inventory core**  
✔️ Completed

**PHASE 2 – Business logic**  
✔️ Completed

**PHASE 3 – UX / UI**  
🔄 Partially completed (stable functional base)

**PHASE 4 – Authentication and users**  
⏳ Pending (out of scope for v0.1)

**PHASE 5 – Hardening and security**  
🔄 *CURRENT PHASE*

**PHASE 6 – Advanced distribution**  
⏳ Pending

**PHASE 7 – Analytics**  
⏳ Pending

**PHASE 8 – Machine Learning**  
⏳ Pending (low priority)

---

## 🧠 Project philosophy

- Stability first, features second
- Real bugs over shiny features
- Closed, documented releases
- Each phase provides a solid base for the next one

---

## 📜 License

MIT License.

---

## 👤 Author

David García  
Project developed as a real inventory system and technical portfolio.
