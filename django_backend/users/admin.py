from django.contrib import admin

from .models import GitHubInstallation, StudentRepo


@admin.register(GitHubInstallation)
class GitHubInstallationAdmin(admin.ModelAdmin):
    list_display = (
        'installation_id',
        'user',
        'github_account_login',
        'github_account_type',
        'repository_selection',
        'is_active',
        'created_at',
    )
    list_filter = ('github_account_type', 'repository_selection')
    search_fields = ('installation_id', 'github_account_login', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(boolean=True, description='Active?')
    def is_active(self, obj):
        return obj.is_active


@admin.register(StudentRepo)
class StudentRepoAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'user',
        'is_active',
        'is_private',
        'default_branch',
        'granted_at',
    )
    list_filter = ('is_active', 'is_private')
    search_fields = ('full_name', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'granted_at', 'removed_at')
