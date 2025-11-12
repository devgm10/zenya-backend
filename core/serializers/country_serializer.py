from rest_framework import serializers
from core.models import Country

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        exclude = ['created_at', 'updated_at']