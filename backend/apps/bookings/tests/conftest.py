from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts import services as account_services
from apps.accounts.models import User
from apps.catalogue.models import Location, Service, ServiceCategory
from apps.providers import services as provider_services


@pytest.fixture
def category(db):
    return ServiceCategory.objects.create(name="AC & Refrigeration")


@pytest.fixture
def service(category):
    return Service.objects.create(
        category=category, name="AC servicing",
        suggested_price_min=Decimal("1200"),
        suggested_price_max=Decimal("2500"),
        typical_duration_minutes=90,
    )


@pytest.fixture
def dhaka(db):
    return Location.objects.create(name="Dhaka", level=Location.Level.CITY)


@pytest.fixture
def dhanmondi(dhaka):
    return Location.objects.create(name="Dhanmondi",
                                   level=Location.Level.THANA, parent=dhaka)


@pytest.fixture
def customer_user(db):
    return account_services.register_user(
        phone="+8801912345678", password="testpass123",
        full_name="Rumana Akter", role=User.Role.CUSTOMER,
    )


@pytest.fixture
def customer(customer_user):
    return customer_user.customer_profile


@pytest.fixture
def provider_user(db):
    return account_services.register_user(
        phone="+8801712345678", password="testpass123",
        full_name="Kamal Hossain", role=User.Role.PROVIDER,
    )


@pytest.fixture
def provider(provider_user, service, dhanmondi):
    profile = provider_user.provider_profile
    provider_services.add_offering(
        provider_id=profile.id, service_id=service.id,
        price=Decimal("1800"),
    )
    provider_services.set_service_areas(
        provider_id=profile.id, location_ids=[dhanmondi.id],
    )
    return profile


@pytest.fixture
def other_provider(db, service, dhanmondi):
    user = account_services.register_user(
        phone="+8801812345678", password="testpass123",
        full_name="Shakib Rahman", role=User.Role.PROVIDER,
    )
    profile = user.provider_profile
    provider_services.add_offering(
        provider_id=profile.id, service_id=service.id,
        price=Decimal("1500"),
    )
    provider_services.set_service_areas(
        provider_id=profile.id, location_ids=[dhanmondi.id],
    )
    return profile


@pytest.fixture
def future_window():
    start = timezone.now() + timezone.timedelta(days=2)
    return start, start + timezone.timedelta(hours=3)


@pytest.fixture
def gulshan_free(dhaka):
    return Location.objects.create(name="Gulshan",
                                   level=Location.Level.THANA, parent=dhaka)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        phone="+8801612345678", password="adminpass123",
    )
