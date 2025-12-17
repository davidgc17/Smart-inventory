# 🧠 Smart Inventory

📕 **Spanish version:** [README.md](README.md)

Smart Inventory is a **Django-based inventory management application** designed for real-world usage.  
It aims to be **clear, stable, and easy to use** for home setups and small professional contexts, prioritizing a solid technical foundation over unnecessary complexity.

The project goal is not only to register products, but to **track stock, expiration dates, and locations in a structured way**, with an architecture intended to evolve after real testing.

---

## 🖼️ Screenshots / GIFs (v0.1)

> The following media reflects the real state of the application in **v0.1**.

- **Home screen:**  
  ![Home](imgs/home.png)

- **Locations management:**  
  ![Locations](imgs/ubicaciones.png)

- **Inventory (GIF):**  
  ![Inventory](imgs/inventario.gif)

---

## 🚀 Application usage (v0.1)

Smart Inventory v0.1 is designed for **local use on a PC**, with optional access from a mobile device on the same network.

### 🖥️ PC startup
1. Start the application.
2. Open `http://localhost:8000` in your browser.
3. Log in or register a user.

### 📱 Mobile access (same network)
From a mobile device connected to the same WiFi, open:  
`http://PC_IP_ADDRESS:8000`

On Android, you can **add a shortcut to the home screen**, so Smart Inventory can be opened like an app.

---

## 🧭 Available modes

- **Input**: register new products or batches.  
- **Output (QR + FIFO)**: remove stock using QR scanning or manual search, following FIFO logic.  
- **Audit**: check the status of a specific product.  
- **Full audit (paginated)**: global inventory review.

---

## ⚙️ Important behavior details

- Audits are **paginated at 25 items per page** to ensure stability and performance.
- The app is designed for **controlled local usage**, without unnecessary external dependencies.

---

## ⚠️ Real limitations of v0.1

- **Local-only** usage (no Internet access).
- **SQLite** database.
- Version intended for **real testing and stability validation** before expanding scope.

---

## 🗺️ High-level roadmap

- **PHASE 1 — Inventory core**: ✔️ Completed  
- **PHASE 2 — Business logic**: ✔️ Completed  
- **PHASE 3 — UX / UI**: 🔄 In progress (post-v0.1 improvements)  
- **PHASE 4 — Login and user management**: ⏳ Planned (not included in v0.1)  
- **PHASE 5 — Security hardening**: ⏳ Planned  
- **PHASE 6 — Distribution and access**: ⏳ Planned  
- **PHASE 7 — Analytics and dashboards**: ⏳ Planned  
- **PHASE 8 — Machine Learning**: ⏳ Exploratory  

---

**Developed by David García**
