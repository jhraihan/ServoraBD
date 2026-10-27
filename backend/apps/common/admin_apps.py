from django.contrib.admin.apps import AdminConfig


class ServoraAdminConfig(AdminConfig):
    default_site = "apps.common.admin_site.ServoraAdminSite"
