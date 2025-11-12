from rest_framework import serializers
from core.models import Status

class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        exclude = ['created_at', 'updated_at']