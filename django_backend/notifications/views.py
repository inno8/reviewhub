from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer, NotificationCreateSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        """Return notifications for the current user."""
        return Notification.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Use different serializer for create action."""
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new notification (internal use).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def list(self, request, *args, **kwargs):
        """
        List all notifications for the current user.
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='read')
    def mark_as_read(self, request, pk=None):
        """
        Mark a notification as read.
        """
        notification = self.get_object()
        notification.read = True
        notification.save()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Mark all notifications as read for the current user.
        """
        updated_count = Notification.objects.filter(
            user=request.user,
            read=False
        ).update(read=True)
        
        return Response({
            'message': f'{updated_count} notifications marked as read',
            'count': updated_count
        })

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """
        Get the count of unread notifications for the current user.
        """
        count = Notification.objects.filter(
            user=request.user,
            read=False
        ).count()
        
        return Response({'unread_count': count})
