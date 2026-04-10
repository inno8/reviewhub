"""
Signals for evaluation events
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Finding


@receiver(post_save, sender=Finding)
def create_finding_notification(sender, instance, created, **kwargs):
    """
    Create a notification when a new finding is created.
    """
    if not created:
        return

    # Only create notification if the evaluation has an author
    if not instance.evaluation.author:
        return

    # Skip individual notifications for batch evaluations
    if getattr(instance.evaluation, '_batch_skip_notifications', False):
        return
    
    from notifications.models import Notification
    
    # Determine title based on severity
    severity_emoji = {
        'critical': '🚨',
        'warning': '⚠️',
        'info': 'ℹ️'
    }
    
    emoji = severity_emoji.get(instance.severity.lower(), '🔍')
    title = f'{emoji} New {instance.get_severity_display()} Finding'
    
    # Create notification message
    message = f'Found in {instance.file_path}'
    if instance.line_start:
        message += f' at line {instance.line_start}'
    
    # Build notification data
    notification_data = {
        'finding_id': instance.id,
        'evaluation_id': instance.evaluation.id,
        'commit_sha': instance.evaluation.commit_sha,
        'file_path': instance.file_path,
        'line_start': instance.line_start,
        'severity': instance.severity
    }
    
    # Create notification for the commit author
    Notification.objects.create(
        user=instance.evaluation.author,
        type='new_finding',
        title=title,
        message=message,
        data=notification_data
    )
