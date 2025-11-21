# from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Location
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import Product, Movement, Location
import json

def locations_manager(request):
    return render(request, "inventory/location_manager.html")

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

def scan_view(request):
    # ubicaciones ordenadas por nombre (puedes cambiar el orden si quieres)
    locations_qs = Location.objects.select_related("parent").order_by("name")

    # le añadimos un atributo .path a cada objeto
    locations = []
    for loc in locations_qs:
        loc.path = build_location_path(loc)
        locations.append(loc)

    # el resto igual que lo tuvieras antes
    categories = (
        Product.objects.values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    units = (
        Product.objects.values_list("unit", flat=True)
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