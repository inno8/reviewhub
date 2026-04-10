# Generated manually for LLM auth methods (API key / access token / Google OAuth)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_git_provider_connection'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmconfiguration',
            name='auth_method',
            field=models.CharField(
                choices=[
                    ('api_key', 'API key'),
                    ('access_token', 'Access token'),
                    ('oauth_google', 'Google OAuth'),
                ],
                default='api_key',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='llmconfiguration',
            name='_oauth_refresh_token',
            field=models.BinaryField(blank=True, db_column='oauth_refresh_token', null=True),
        ),
        migrations.AddField(
            model_name='llmconfiguration',
            name='_oauth_access_token',
            field=models.BinaryField(blank=True, db_column='oauth_access_token', null=True),
        ),
        migrations.AddField(
            model_name='llmconfiguration',
            name='oauth_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='llmconfiguration',
            name='_api_key',
            field=models.BinaryField(blank=True, db_column='api_key', null=True),
        ),
    ]
