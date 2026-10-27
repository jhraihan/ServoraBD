from django.apps import AppConfig
from django.db.models.signals import post_migrate

class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    label = "common"
    verbose_name = "Common"

    def ready(self):
        from .roles import sync_staff_roles

        post_migrate.connect(sync_staff_roles,
                             dispatch_uid="common.sync_staff_roles")
