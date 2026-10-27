from functools import reduce
from operator import or_

from django.db.models import Q

STAFF_ROLES = {
    "Support": [
        "accounts.view_user", "accounts.change_user",
        "accounts.view_customerprofile", "accounts.view_providerprofile",
        "bookings.view_servicerequest", "bookings.view_booking",
        "bookings.change_booking", "bookings.view_bookingevent",
        "bookings.view_providerresponse", "payments.view_payment",
        "reviews.view_review",
    ],
    "Moderator": [
        "accounts.view_providerprofile", "accounts.change_providerprofile",
        "providers.view_verificationdocument",
        "providers.change_verificationdocument",
        "providers.view_workphoto", "providers.delete_workphoto",
        "reviews.view_review", "reviews.change_review",
        "reviews.view_providerreply", "reviews.view_customerrating",
        "reviews.view_reviewedit", "trust.view_trustsnapshot",
    ],
    "Finance": [
        "accounts.view_providerprofile", "bookings.view_booking",
        "payments.view_payment", "payments.change_payment",
        "payments.view_ledgerentry", "payments.add_ledgerentry",
    ],
    "Catalogue editor": [
        "%s.%s_%s" % ("catalogue", verb, model)
        for model in ("servicecategory", "service", "location")
        for verb in ("view", "add", "change")
    ],
}


def sync_staff_roles(using="default", **kwargs):
    from django.contrib.auth.models import Group, Permission

    for name, labels in STAFF_ROLES.items():
        lookup = reduce(or_, (
            Q(content_type__app_label=app_label, codename=codename)
            for app_label, codename in (label.split(".") for label in labels)
        ))
        group, _ = Group.objects.using(using).get_or_create(name=name)
        group.permissions.set(
            Permission.objects.using(using).filter(lookup))
