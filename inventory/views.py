from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Location
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import Product, Movement, Location, Batch, DEFAULT_TENANT
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout 
from django.conf import settings
from django.db import transaction
import json, os

@login_required
def home_view(request):
    return render(request, "inventory/home.html")

@login_required
def locations_manager(request):
    return render(request, "inventory/location_manager.html")

def register(request):
    """
    Registro básico de usuario.
    Crea un usuario nuevo y lo inicia sesión, luego redirige a 'home'.
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # login automático tras crear el usuario
            auth_login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "inventory/register.html", {"form": form})

def logout_view(request):
    """
    Cierra la sesión del usuario y lo manda a la pantalla de login.
    Acepta GET para simplificar el flujo en esta app.
    """
    auth_logout(request)
    return redirect("login")



def build_location_path(loc):
    """
    Construye la ruta completa: raíz > ... > hijo
    usando la cadena de padres.
    """
    names = []
    current = loc
    while current is not None:
        names.append(current.name)
        current = current.parent  # FK a sí misma
    # invertimos para que quede: raíz > ... > hijo
    return " > ".join(reversed(names))

@login_required
def scan_view(request):
    # Determinar el tenant del usuario actual
    if request.user.is_authenticated and hasattr(request.user, "organization"):
        tenant_id = request.user.organization.id
    else:
        tenant_id = DEFAULT_TENANT

    # ubicaciones de ESTE tenant, ordenadas por nombre
    locations_qs = (
        Location.objects
        .filter(tenant_id=tenant_id)
        .select_related("parent")
        .order_by("name")
    )

    # le añadimos un atributo .path a cada objeto
    locations = []
    for loc in locations_qs:
        loc.path = build_location_path(loc)
        locations.append(loc)

    # categorías y unidades SOLO de productos de este tenant
    categories = (
        Product.objects.filter(tenant_id=tenant_id)
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    units = (
        Product.objects.filter(tenant_id=tenant_id)
        .values_list("unit", flat=True)
        .distinct()
        .order_by("unit")
    )

    return render(
        request,
        "inventory/scan.html",
        {
            "locations": locations,
            "categories": categories,
            "units": units,
        },
    )

@login_required
def scan_qr_view(request):
    """
    Procesa un QR concreto (ej: /scan/qr/?qr=PRD:xxxx)
    y decide si extraer automáticamente o preguntar.
    """
    qr = request.GET.get("qr")
    if not qr:
        messages.error(request, "No se recibió ningún código QR.")
        return redirect("scan")  # volvemos a la página de escaneo normal

    try:
        product = Product.objects.get(qr_payload=qr)
    except Product.DoesNotExist:
        messages.error(request, "Código QR no válido.")
        return redirect("scan")

    tenant_id = product.tenant_id  # si luego usas otro sistema de tenant, cámbialo aquí

    action, batch = Batch.choose_for_scan(product, tenant_id)

    # Sin stock
    if action == Batch.ACTION_NO_STOCK or batch is None:
        return render(request, "inventory/scan_no_stock.html", {
            "product": product,
        })

    # Acciones automáticas: consumimos directamente
    if action in (Batch.ACTION_AUTO_CONSUME, Batch.ACTION_CONSUME_OPEN):
        try:
            with transaction.atomic():
                batch.consume_one()
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("scan")

        return render(request, "inventory/scan_result.html", {
            "product": product,
            "batch": batch,
            "auto_consumed": True,
        })

    # Hay stock pero ninguna unidad abierta: preguntar
    if action == Batch.ACTION_ASK_OPEN_OR_CONSUME:
        return render(request, "inventory/scan_decision.html", {
            "product": product,
            "batch": batch,
        })

    messages.error(request, "No se pudo procesar la acción de escaneo.")
    return redirect("scan")


@login_required
def qr_list_view(request):
    qr_dir = os.path.join(settings.MEDIA_ROOT, "qr")
    qr_files = []

    if os.path.exists(qr_dir):
        for fname in os.listdir(qr_dir):
            if fname.lower().endswith(".png"):
                qr_files.append({
                    "name": fname.replace("qr-", "").replace(".png", ""),
                    "url": f"{settings.MEDIA_URL}qr/{fname}",
                })

    return render(request, "inventory/qr_list.html", {
        "qr_files": qr_files,
        "MEDIA_URL": settings.MEDIA_URL
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def scan_action_view(request, batch_id):
    """
    Procesa la decisión del usuario después de la pantalla de decisión:
    - mode=consume → extraer 1 unidad.
    - mode=open    → marcar 1 unidad como abierta (con días tras abrir).
    """
    batch = get_object_or_404(Batch, id=batch_id)
    product = batch.product

    if request.method != "POST":
        messages.error(request, "Método no permitido.")
        return redirect("scan")

    mode = request.POST.get("mode")

    if mode == "consume":
        try:
            with transaction.atomic():
                batch.consume_one()
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("scan")

        return render(request, "inventory/scan_result.html", {
            "product": product,
            "batch": batch,
            "auto_consumed": False,
        })

    elif mode == "open":
        days = request.POST.get("days")

        if not days:
            days = product.default_open_shelf_life_days

        try:
            days = int(days)
        except Exception:
            messages.error(request, "Debes indicar un número de días válido.")
            return redirect("scan")

        if days <= 0:
            messages.error(request, "Los días tras abrir deben ser mayores que 0.")
            return redirect("scan")

        try:
            with transaction.atomic():
                batch.open_one(shelf_life_days=days)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("scan")

        return render(request, "inventory/scan_result.html", {
            "product": product,
            "batch": batch,
            "auto_consumed": False,
        })

    else:
        messages.error(request, "Acción no válida.")
        return redirect("scan")






# ============================================================
# LEGACY ENDPOINT - NO USAR
# Se mantiene solo como referencia histórica.
# La API oficial de movimientos es /api/scan/ (ScanEndpoint en api.py).
# ============================================================
@csrf_exempt
@require_http_methods(["POST"])
def api_scan(request):
    try:
        data = json.loads(request.body)
        mtype = data.get("movement_type")

        if mtype == "IN":
            name = data.get("name")
            category = data.get("category")
            unit = data.get("unit", "unit")
            min_stock = int(data.get("min_stock", 0))
            expiration_date = data.get("expiration_date") or None
            consumption_date = data.get("consumption_date") or None
            notes = data.get("notes", "")
            nfc_tag_uid = data.get("nfc_tag_uid", "").strip() or None

            if not name or not category:
                return JsonResponse({"ok": False, "error": "Faltan campos obligatorios."}, status=400)

            product = Product.objects.create(
                name=name,
                category=category,
                unit=unit,
                min_stock=min_stock,
                expiration_date=expiration_date,
                consumption_date=consumption_date,
                notes=notes,
                nfc_tag_uid=nfc_tag_uid,
            )

            return JsonResponse({
                "ok": True,
                "product_id": product.id,
                "qr_filename": qr_filename,
                "message": f"Producto '{product.name}' creado correctamente."
            })


        elif mtype == "OUT":
            payload = data.get("payload")
            quantity = int(data.get("quantity", 1))
            location_code = data.get("location")
            location = Location.objects.filter(name=location_code).first()

            if not payload or not payload.startswith("PRD:"):
                return JsonResponse({"ok": False, "error": "Payload inválido"}, status=400)

            product_id = payload[4:]
            product = Product.objects.filter(id=product_id).first()

            if not product or not location:
                return JsonResponse({"ok": False, "error": "Producto o ubicación no encontrados."}, status=404)

            Movement.objects.create(
                product=product,
                location=location,
                quantity=quantity,
                movement_type=mtype
            )

            return JsonResponse({
                "ok": True,
                "message": f"Movimiento OUT registrado para '{product.name}'"
            })

        else:
            return JsonResponse({"ok": False, "error": "Tipo de movimiento no soportado."}, status=400)

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)