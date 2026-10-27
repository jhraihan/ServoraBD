from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import services as account_services
from apps.accounts.models import User
from apps.common.testing import verified_admin_client
from apps.operations import selectors
from apps.operations.jobs import SCHEDULE, get_job
from apps.operations.models import JobRun

pytestmark = pytest.mark.django_db


def _run(job, *, minutes_ago, status=JobRun.Status.SUCCEEDED):
    started = timezone.now() - timezone.timedelta(minutes=minutes_ago)
    return JobRun.objects.create(
        job=job, status=status, started_at=started,
        finished_at=None if status == JobRun.Status.RUNNING else started,
    )


def _health(job):
    return next(row for row in selectors.job_health() if row["job"] == job)


def test_successful_job_records_a_run():
    call_command("expire_requests", stdout=StringIO())

    run = JobRun.objects.get(job="expire_requests")
    assert run.status == JobRun.Status.SUCCEEDED
    assert run.finished_at is not None
    assert run.message == "Expired 0 request(s)."
    assert run.duration_seconds >= 0


def test_rows_affected_is_recorded():
    from apps.accounts.models import PhoneOTP

    for n in range(3):
        otp = PhoneOTP.objects.create(phone="+88017123456%02d" % n,
                                      code_hash="x" * 64,
                                      expires_at=timezone.now())
        PhoneOTP.objects.filter(pk=otp.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=48))

    call_command("purge_otps", stdout=StringIO())
    assert JobRun.objects.get(job="purge_otps").rows_affected == 3


def test_failing_job_records_failure_and_exits_non_zero():
    with mock.patch("apps.bookings.services.expire_stale_requests",
                    side_effect=RuntimeError("database went away")):
        with pytest.raises(RuntimeError):
            call_command("expire_requests", stdout=StringIO())

    run = JobRun.objects.get(job="expire_requests")
    assert run.status == JobRun.Status.FAILED
    assert "database went away" in run.message


def test_reconcile_discrepancy_is_recorded_as_a_failed_run():
    with mock.patch("apps.payments.services.reconcile_provider",
                    return_value=[{"booking": 1, "issue": "missing_payment"}]):
        account_services.register_user(phone="+8801712345678",
                                       password="testpass123",
                                       role=User.Role.PROVIDER)
        with pytest.raises(CommandError):
            call_command("reconcile_earnings", stdout=StringIO(),
                         stderr=StringIO())

    assert JobRun.objects.get(job="reconcile_earnings").status == \
        JobRun.Status.FAILED


def test_every_registered_job_has_a_command_that_records_runs():
    for job in SCHEDULE:
        call_command(job.name, stdout=StringIO(), stderr=StringIO())
    recorded = set(JobRun.objects.values_list("job", flat=True))
    assert recorded == {job.name for job in SCHEDULE}


def test_never_run_job_is_overdue():
    row = _health("expire_requests")
    assert row["overdue"] is True
    assert row["healthy"] is False


def test_recent_success_is_healthy():
    _run("expire_requests", minutes_ago=10)
    row = _health("expire_requests")
    assert row["overdue"] is False
    assert row["healthy"] is True


def test_overdue_after_twice_the_interval():
    interval = get_job("expire_requests").every_minutes
    _run("expire_requests", minutes_ago=interval * 2 - 1)
    assert _health("expire_requests")["overdue"] is False

    JobRun.objects.all().delete()
    _run("expire_requests", minutes_ago=interval * 2 + 1)
    assert _health("expire_requests")["overdue"] is True


def test_latest_failure_is_unhealthy_even_if_recently_succeeded():
    _run("auto_confirm", minutes_ago=30)
    _run("auto_confirm", minutes_ago=1, status=JobRun.Status.FAILED)
    row = _health("auto_confirm")
    assert row["overdue"] is False
    assert row["last_status"] == JobRun.Status.FAILED
    assert row["healthy"] is False


def test_long_running_job_is_flagged_stuck():
    _run("purge_otps", minutes_ago=5)
    _run("purge_otps", minutes_ago=30, status=JobRun.Status.RUNNING)
    JobRun.objects.filter(status=JobRun.Status.RUNNING).update(
        started_at=timezone.now() - timezone.timedelta(minutes=30))
    assert _health("purge_otps")["stuck"] is True


def test_old_runs_are_pruned_but_recent_ones_kept():
    _run("purge_otps", minutes_ago=60 * 24 * 40)
    call_command("purge_otps", stdout=StringIO())
    assert JobRun.objects.filter(job="purge_otps").count() == 1


def test_run_scheduled_jobs_runs_each_job_in_order():
    call_command("run_scheduled_jobs", stdout=StringIO(), stderr=StringIO())

    order = list(
        JobRun.objects.order_by("started_at", "id").values_list("job", flat=True)
    )
    assert order == [job.name for job in SCHEDULE]


def test_run_scheduled_jobs_continues_past_a_failure():
    out, err = StringIO(), StringIO()
    with mock.patch("apps.bookings.services.expire_stale_requests",
                    side_effect=RuntimeError("boom")):
        with pytest.raises(CommandError) as exc:
            call_command("run_scheduled_jobs", stdout=out, stderr=err)

    assert "expire_requests" in str(exc.value)
    assert JobRun.objects.filter(status=JobRun.Status.SUCCEEDED).count() == \
        len(SCHEDULE) - 1


def test_run_scheduled_jobs_rejects_unknown_names():
    with pytest.raises(CommandError):
        call_command("run_scheduled_jobs", "--only", "nonsense",
                     stdout=StringIO())


def test_crontab_covers_every_job_with_production_settings():
    out = StringIO()
    call_command("crontab", "--root", "/srv/app/backend", stdout=out)
    text = out.getvalue()

    assert "DJANGO_SETTINGS_MODULE=config.settings.prod" in text
    for job in SCHEDULE:
        assert "%s  cd /srv/app/backend" % job.cron in text or \
            ("manage.py %s " % job.name) in text
        assert job.cron in text
    assert "/srv/app/backend/venv/bin/python manage.py" in text


def test_job_health_endpoint_is_admin_only(db):
    anon = APIClient()
    assert anon.get(reverse("operations:job-health")).status_code == 401

    provider = account_services.register_user(
        phone="+8801712345678", password="testpass123",
        role=User.Role.PROVIDER,
    )
    client = APIClient()
    token = client.post(reverse("accounts:login"),
                        {"phone": provider.phone, "password": "testpass123"},
                        format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION="Bearer %s" % token)
    assert client.get(reverse("operations:job-health")).status_code == 403


def test_job_health_endpoint_reports_every_job(db):
    admin_user = User.objects.create_superuser(phone="+8801611112222",
                                               password="adminpass123")
    _run("expire_requests", minutes_ago=5)

    client = verified_admin_client(admin_user)
    resp = client.get(reverse("operations:job-health"))

    assert resp.status_code == 200
    assert {row["job"] for row in resp.data["jobs"]} == \
        {job.name for job in SCHEDULE}
    assert resp.data["healthy"] is False
    assert len(resp.data["recent"]) == 1
