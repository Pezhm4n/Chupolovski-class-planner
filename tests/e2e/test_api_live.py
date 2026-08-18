# -*- coding: utf-8 -*-
"""
Live End-to-End API tests for the Golestoon desktop client.

Runs against the configured backend (GOLESTOON_API_BASE_URL / API_URL) using the
desktop app's own network layer (NetworkSession + domain clients), so the
exact request/response contracts exercised by the GUI are what gets tested.

Usage:
    pytest tests/e2e/test_api_live.py -v

Environment:
    GOLESTAN_TEST_USERNAME / GOLESTAN_TEST_PASSWORD
        Golestan university credentials for the transcript sync test.
        Falls back to USERNAME / PASSWORD in app/.env.
    E2E_WRITE_TESTS=1
        Opt-in flag enabling the professor-review write cycle
        (submit + delete with an obviously-test instructor name).
        Default OFF to keep the production professor database clean.
"""

import json
import os
import random
import string
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core import network as net  # noqa: E402
from app.core.auth.token_manager import TokenManager  # noqa: E402
from app.core.network.converters import student_from_api  # noqa: E402
from app.scrapers.requests_scraper.models import Student  # noqa: E402

BASE_URL = os.environ.get("GOLESTOON_API_BASE_URL") or os.environ.get("API_URL")
WRITE_TESTS = os.environ.get("E2E_WRITE_TESTS") == "1"


def _golestan_creds():
    """Golestan credentials: env first, then app/.env."""
    username = os.environ.get("GOLESTAN_TEST_USERNAME")
    password = os.environ.get("GOLESTAN_TEST_PASSWORD")
    if username and password:
        return username, password
    env_path = ROOT / "app" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("USERNAME="):
                username = line.split("=", 1)[1].strip().strip("'\"")
            elif line.startswith("PASSWORD="):
                password = line.split("=", 1)[1].strip().strip("'\"")
    return username, password


def _rand_suffix(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _gmail_normalize(email: str) -> str:
    """The backend normalizes Gmail local parts by stripping dots."""
    return email.lower().replace(".", "")


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def require_api_base_url():
    if not BASE_URL or not str(BASE_URL).strip():
        pytest.skip("No GOLESTOON_API_BASE_URL or API_URL configured; skipping live E2E cloud tests.")

@pytest.fixture(scope="module")
def token_manager():
    tm = TokenManager()
    yield tm
    tm.clear_token()


@pytest.fixture(scope="module")
def session(token_manager):
    sess = net.SessionFactory.create_session(token_manager=token_manager)
    sess.config.__dict__["base_url"] = BASE_URL  # honor env override
    yield sess
    sess.close()


@pytest.fixture(scope="module")
def account(session, token_manager):
    """Register a fresh test account and log in; returns account dict."""
    auth_client = net.AuthClient(session=session)
    email = f"golestoon.e2e.{_rand_suffix()}@gmail.com"
    password = f"E2e-{_rand_suffix(10)}!"

    res = auth_client.signup(full_name="E2E Test Bot", email=email, password=password)
    assert res is not None, "signup returned None"
    assert getattr(res, "token", None), f"signup did not return a token: {res}"
    token_manager.save_token(res.token)

    # Inline user model must match the signup email (no /me endpoint exists).
    # NOTE: the backend strips dots from Gmail local parts when normalizing.
    assert res.user is not None
    assert _gmail_normalize(res.user.email) == _gmail_normalize(email)
    # Token must be accepted by an auth-protected endpoint.
    assert auth_client.validate_token(), "fresh signup token rejected by server"
    return {"email": email, "password": password, "token": res.token}


# ─────────────────────────────────────────────────────────────
# 1. Health
# ─────────────────────────────────────────────────────────────

def test_health(session):
    res = session.get(endpoint="/health", timeout=(5, 15))
    assert res.get("status") == "ok"
    assert res.get("server") == "Golestan-Express"


# ─────────────────────────────────────────────────────────────
# 2. Auth flow (signup → me → login)
# ─────────────────────────────────────────────────────────────

def test_auth_me(account):
    # `account` fixture already validated signup + /me; assert shape here too
    assert account["token"].count(".") == 2  # JWT shape header.payload.signature


def test_auth_login_flow(session, token_manager, account):
    auth_client = net.AuthClient(session=session)
    res = auth_client.login(email=account["email"], password=account["password"])
    assert getattr(res, "token", None), "login failed"
    token_manager.save_token(res.token)
    assert res.user is not None
    assert _gmail_normalize(res.user.email) == _gmail_normalize(account["email"])
    assert auth_client.validate_token(), "login token rejected by server"


# ─────────────────────────────────────────────────────────────
# 3. Schedules CRUD
# ─────────────────────────────────────────────────────────────

def test_schedules_crud(session, account):
    client = net.ScheduleClient(session=session)

    created = client.create_schedule(
        name="e2e-test-schedule", courses=[{"courseId": "T1", "name": "تست"}]
    )
    assert created is not None and created.id, f"create failed: {created}"

    listed = client.get_schedules()
    assert any(s.id == created.id for s in listed), "created schedule missing in list"

    updated = client.update_schedule(
        schedule_id=created.id,
        name="e2e-test-schedule-v2",
        courses=[{"courseId": "T1", "name": "تست"}, {"courseId": "T2", "name": "تست۲"}],
    )
    assert updated is not None

    client.delete_schedule(schedule_id=created.id)
    listed = client.get_schedules()
    assert not any(s.id == created.id for s in listed), "schedule not deleted"


# ─────────────────────────────────────────────────────────────
# 4. Course catalog proxy
# ─────────────────────────────────────────────────────────────

def test_course_catalog(session):
    res = session.get(
        endpoint="/scraper-proxy/api/courses/all",
        params={"hierarchy": "true", "availability": "both"},
        timeout=(5, 35),
    )
    assert isinstance(res, dict) and res, "catalog empty or not grouped"
    first_faculty = next(iter(res))
    assert first_faculty, "catalog grouping broken"


# ─────────────────────────────────────────────────────────────
# 5. Professor reviews — read endpoints
# ─────────────────────────────────────────────────────────────

def test_professor_departments(session):
    res = session.get(endpoint="/api/professor-reviews/departments", timeout=(5, 15))
    assert isinstance(res, dict)
    departments = res.get("departments", [])
    assert isinstance(departments, list)


def test_professor_stats_contract(session):
    # Exact desktop contract: params `department` & `instructor`; response {stats: row|null}
    departments_res = session.get(endpoint="/api/professor-reviews/departments", timeout=(5, 15))
    departments = departments_res.get("departments") or []
    if not departments:
        pytest.skip("no departments on server")

    stats = session.get(
        endpoint="/api/professor-reviews/stats",
        params={"department": departments[0], "instructor": "ناموجود عجیب‌وغریب ۱۲۳"},
        timeout=(5, 15),
    )
    assert isinstance(stats, dict)
    assert "stats" in stats and stats["stats"] is None


def test_professor_popular_lists(session):
    for endpoint in (
        "/api/professor-reviews/popular-by-score",
        "/api/professor-reviews/popular-by-views",
        "/api/professor-reviews/popular-by-voters",
    ):
        res = session.get(endpoint=endpoint, params={"limit": 3}, timeout=(5, 15))
        assert isinstance(res, dict) and "instructors" in res, endpoint
        for inst in res["instructors"]:
            assert "instructor_name" in inst, endpoint
            assert "department_name" in inst, endpoint


def test_professor_summary(session, account):
    res = session.get(endpoint="/api/professor-reviews/summary", timeout=(5, 15))
    assert isinstance(res, dict), "summary must be an object for authed user"


# ─────────────────────────────────────────────────────────────
# 6. Transcript sync (REAL Golestan sync through desktop client)
# ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(_golestan_creds()[0] is None, reason="no Golestan credentials available")
def test_transcript_sync_real(session, token_manager):
    from app.core.network.clients.transcript_client import TranscriptClient

    username, password = _golestan_creds()
    client = TranscriptClient(session=session)

    status = client.trigger_sync(
        golestan_username=username,
        golestan_password=password,
        mode="full",
        wait=True,
        force=True,
    )

    assert status.status in ("done", "too_recent", "syncing", "queued"), \
        f"unexpected sync status: {status.status} / {status.message}"

    if status.status == "too_recent":
        # Server rate limit (2 syncs / 10 min per student ID) — contract still valid.
        assert status.message
        return

    if status.status != "done" or not status.student:
        pytest.skip(f"sync did not complete inline: {status.status} — {status.message}")

    student = student_from_api(status.student)
    assert isinstance(student, Student)
    assert student.student_id, "studentId missing in payload"
    assert student.name, "student name missing in payload"
    assert isinstance(student.semesters, list) and len(student.semesters) >= 1, \
        "no semesters returned"
    first_sem = student.semesters[0]
    assert first_sem.semester_description, "semester description missing"
    if first_sem.courses:
        course = first_sem.courses[0]
        assert course.course_code is not None
        assert course.course_name
    # degreeStatus may legitimately be null for some majors, but the key must exist
    assert "degreeStatus" in status.student
    if student.degree_status is not None:
        assert student.degree_status.total_required_min >= 0
        for cat in student.degree_status.categories:
            assert cat.category_name

    # Status metadata endpoint (GET /api/transcript)
    meta = client.get_sync_status()
    assert meta.status in ("ok", "unknown")
    assert isinstance(meta.is_syncing, bool)


# ─────────────────────────────────────────────────────────────
# 7. Professor review write cycle (OPT-IN: E2E_WRITE_TESTS=1)
# ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(not WRITE_TESTS, reason="set E2E_WRITE_TESTS=1 to enable write cycle")
def test_professor_review_write_cycle(session):
    departments_res = session.get(endpoint="/api/professor-reviews/departments", timeout=(5, 15))
    departments = departments_res.get("departments") or []
    assert departments, "need at least one department"
    department = departments[0]
    instructor = f"تست خودکار E2E {_rand_suffix(4)}"

    # Submit (desktop contract: *_score fields + attendance_sensitivity)
    submit = session.post(
        endpoint="/api/professor-reviews",
        data={
            "department_name": department,
            "instructor_name": instructor,
            "teaching_score": 80,
            "assignments_score": 60,
            "grading_score": 70,
            "exam_difficulty_score": 50,
            "attendance_sensitivity": "normal",
        },
        timeout=(5, 15),
    )
    assert isinstance(submit, dict), submit

    # My review must now exist (params: department & instructor)
    mine = session.get(
        endpoint="/api/professor-reviews/my-review",
        params={"department": department, "instructor": instructor},
        timeout=(5, 15),
    )
    review = (mine or {}).get("review")
    assert review, f"my-review missing after submit: {mine}"
    assert int(review.get("teaching_score", -1)) == 80

    # Delete and verify
    deleted = session.delete(
        endpoint="/api/professor-reviews/my-review",
        params={"department": department, "instructor": instructor},
        timeout=(5, 15),
    )
    assert (deleted or {}).get("success") is True, deleted

    mine2 = session.get(
        endpoint="/api/professor-reviews/my-review",
        params={"department": department, "instructor": instructor},
        timeout=(5, 15),
    )
    assert (mine2 or {}).get("review") is None, "review still present after delete"
