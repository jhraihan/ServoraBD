from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import ProviderProfile
from apps.common.exceptions import NotFound
from apps.providers.permissions import (
    ADMIN_AUTHENTICATION, IsAdminUser, IsProvider,
)

from . import engine
from .models import TrustSnapshot
from .serializers import TrustAuditSerializer, TrustSnapshotSerializer

def _get_provider_or_404(provider_id):
    provider = (
        ProviderProfile.objects
        .select_related("user")
        .filter(pk=provider_id)
        .first()
    )
    if provider is None:
        raise NotFound("No such provider.", code="provider_not_found")
    return provider

class ProviderTrustView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, provider_id):
        provider = _get_provider_or_404(provider_id)
        return Response(engine.breakdown(provider))

class MyTrustHistoryView(ListAPIView):
    permission_classes = [IsProvider]
    serializer_class = TrustSnapshotSerializer

    def get_queryset(self):
        return TrustSnapshot.objects.filter(
            provider=self.request.user.provider_profile
        )

class TrustAuditView(ListAPIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION
    serializer_class = TrustAuditSerializer

    def get_queryset(self):
        return TrustSnapshot.objects.filter(
            provider_id=self.kwargs["provider_id"]
        )

class RecomputeTrustView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def post(self, request, provider_id):
        snapshot = engine.recompute(
            provider_id, trigger=TrustSnapshot.Trigger.MANUAL,
        )
        return Response(TrustAuditSerializer(snapshot).data)
