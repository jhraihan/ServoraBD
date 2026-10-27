from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.permissions import ADMIN_AUTHENTICATION, IsAdminUser

from . import selectors
from .models import JobRun


class JobRunSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = JobRun
        fields = ["id", "job", "status", "started_at", "finished_at",
                  "duration_seconds", "rows_affected", "message"]
        read_only_fields = fields


class JobHealthSerializer(serializers.Serializer):
    job = serializers.CharField()
    purpose = serializers.CharField()
    cron = serializers.CharField()
    every_minutes = serializers.IntegerField()
    last_status = serializers.CharField(allow_null=True)
    last_run_at = serializers.DateTimeField(allow_null=True)
    last_success_at = serializers.DateTimeField(allow_null=True)
    last_message = serializers.CharField(allow_blank=True)
    overdue = serializers.BooleanField()
    stuck = serializers.BooleanField()
    healthy = serializers.BooleanField()


class JobHealthView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def get(self, request):
        health = selectors.job_health()
        runs = selectors.recent_runs(job=request.query_params.get("job"))
        return Response({
            "healthy": all(row["healthy"] for row in health),
            "jobs": JobHealthSerializer(health, many=True).data,
            "recent": JobRunSerializer(runs, many=True).data,
        })
