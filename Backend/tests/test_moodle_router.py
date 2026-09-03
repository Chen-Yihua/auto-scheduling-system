import pytest
from fastapi import HTTPException, Response

import routers.moodle as moodle_router

mock_user = {"sub": "test_user_123"}


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return [dict(d) for d in self._docs]


class FakeMoodleAssignments:
    def __init__(self, initial=None):
        self._docs = list(initial or [])

    async def update_one(self, filter, update, upsert=False):
        doc = update["$set"]
        for i, existing in enumerate(self._docs):
            if all(existing.get(k) == v for k, v in filter.items()):
                self._docs[i] = {**existing, **doc}
                return
        if upsert:
            self._docs.append(dict(doc))

    def find(self, filter):
        matched = [d for d in self._docs if all(d.get(k) == v for k, v in filter.items())]
        return FakeCursor(matched)


@pytest.mark.asyncio
async def test_get_assignments_success(monkeypatch):
    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        return [
            {
                "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "course_name": "資料結構",
                "assignment_title": "HW1",
                "assignment_url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "due_date": "2026-09-10",
            }
        ]

    fake_collection = FakeMoodleAssignments()
    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", fake_collection)

    response = Response()
    result = await moodle_router.get_assignments(response=response, clerk_user=mock_user)

    assert result[0]["assignment_title"] == "HW1"
    assert response.headers["X-Data-Stale"] == "false"
    assert len(fake_collection._docs) == 1


@pytest.mark.asyncio
async def test_get_assignments_falls_back_to_cache_when_scrape_fails(monkeypatch):
    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        raise Exception("Moodle 登入失敗，使用者：stu001")

    cached_doc = {
        "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "course_name": "資料結構",
        "assignment_title": "HW1（上次抓到的）",
        "assignment_url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "due_date": "2026-09-10",
        "user_id": mock_user["sub"],
    }
    fake_collection = FakeMoodleAssignments(initial=[cached_doc])
    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", fake_collection)

    response = Response()
    result = await moodle_router.get_assignments(response=response, clerk_user=mock_user)

    assert result[0]["assignment_title"] == "HW1（上次抓到的）"
    assert response.headers["X-Data-Stale"] == "true"


@pytest.mark.asyncio
async def test_get_assignments_raises_401_when_scrape_fails_and_no_cache(monkeypatch):
    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        raise Exception("Moodle 登入失敗，使用者：stu001")

    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", FakeMoodleAssignments())

    with pytest.raises(HTTPException) as exc_info:
        await moodle_router.get_assignments(response=Response(), clerk_user=mock_user)

    assert exc_info.value.status_code == 401
    assert "Moodle 登入失敗" in str(exc_info.value.detail)
