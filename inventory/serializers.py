from rest_framework import serializers
from .models import Product, Location, Movement, Batch

# --------------------------------------------
# LOCATION SERIALIZER
# --------------------------------------------
class LocationSerializer(serializers.ModelSerializer):
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = "__all__"

    def get_full_path(self, obj):
        """Devuelve la ruta completa de la ubicación."""
        return obj.full_path() if obj else None


# --------------------------------------------
# PRODUCT SERIALIZER
# --------------------------------------------
class ProductSerializer(serializers.ModelSerializer):
    location_path = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"

    def get_location_path(self, obj):
        """Ruta completa de la ubicación del producto."""
        if obj.location:
            return obj.location.full_path()
        return None


# --------------------------------------------
# MOVEMENT SERIALIZER
# --------------------------------------------
class MovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    location_path = serializers.SerializerMethodField()

    class Meta:
        model = Movement
        fields = "__all__"

    def get_location_path(self, obj):
        """Ruta completa de la ubicación asociada al movimiento."""
        if obj.location:
            return obj.location.full_path()
        return None


# --------------------------------------------
# BATCH SERIALIZER
# --------------------------------------------
class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    location_path = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = "__all__"

    def get_location_path(self, obj):
        """Ruta completa de la ubicación del producto vinculado al lote."""
        if obj.product and obj.product.location:
            return obj.product.location.full_path()
        return None
