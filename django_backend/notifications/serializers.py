from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model.
    """
    class Meta:
        model = Notification
        fields = [
            'id',
            'user',
            'type',
            'title',
            'message',
            'data',
            'read',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating notifications (internal use).
    """
    class Meta:
        model = Notification
        fields = [
            'user',
            'type',
            'title',
            'message',
            'data'
        ]
