from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    """
    Notification model for storing user notifications.
    """
    NOTIFICATION_TYPES = [
        ('new_finding', 'New Finding'),
        ('skill_improvement', 'Skill Improvement'),
        ('weekly_summary', 'Weekly Summary'),
        ('team_update', 'Team Update'),
        ('batch_summary', 'Batch Analysis Summary'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default='new_finding'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.type} - {self.title} ({self.user.email})"
