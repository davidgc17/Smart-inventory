# 🧠 Smart Inventory

📘 **Versión en español:** [README.md](README.md)

Smart Inventory is an inventory management application designed for real-world use,
focused on clarity, stability and ease of use in both home and small professional environments.

The goal of the project is to provide a tool that not only registers products,
but also allows structured control of stock, expiration dates and locations,
built on a solid and extensible technical foundation.

---

## 🚀 Basic usage (v0.1)

Smart Inventory v0.1 is designed for local use on a PC, with optional access from a mobile device on the same network.

1. Start the application.
2. Open your browser at `http://localhost:8000`.
3. Log in or register a user account.
4. From a mobile device connected to the same WiFi network, open:
   `http://PC_IP:8000`.

### Main modes
- **Input**: register new products or batches.
- **Output**: remove stock using QR or manual search (FIFO).
- **Audit**: check the status of a single product.
- **Full audit**: global inventory review.

Audits are limited to **25 items per page** to ensure stability and performance.

---

## 📱 Mobile usage

The application can be accessed from a mobile browser when both devices are connected
to the same local network.

From the application menu, it is possible to add a shortcut to the home screen (Android),
allowing Smart Inventory to be opened like an app.

---

## ⚠️ Known limitations (v0.1)

- Local use only (no Internet access).
- Local SQLite database.
- Version focused on real-world testing and stability validation before further phases.
