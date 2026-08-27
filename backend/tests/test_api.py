import io
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("AI_STYLIST_DEMO_MODE", "1")

from main import app
from app.routers import stylist, vision


client = TestClient(app)


def make_image_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color=(220, 180, 160))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def test_legacy_entrypoint_exports_canonical_app():
    from app.main import app as legacy_app

    assert legacy_app is app


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_tags_endpoint_returns_sorted_unique_tags():
    response = client.get("/stylist/tags")
    assert response.status_code == 200
    tags = response.json()["tags"]
    assert isinstance(tags, list)
    assert tags == sorted(set(tags))


def test_recommendation_requires_image_and_tags():
    response = client.post("/stylist/recommend/", data={"tags": "Thanh lịch"})
    assert response.status_code == 422


def test_recommendation_endpoint_returns_demo_advice(monkeypatch):
    class FakeEngine:
        is_loaded = True

        def load_model(self):
            self.is_loaded = True

        def get_style_advice(self, image_path, selected_tags, user_profile):
            assert Path(image_path).exists()
            assert selected_tags == ["Thanh lịch", "Năng động"]
            assert user_profile["body_type"] == "Dáng Đồng Hồ Cát"
            return "recommendation-for-test"

    monkeypatch.setattr(stylist, "stylist_engine", FakeEngine())
    response = client.post(
        "/stylist/recommend/",
        files={"image": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
        data={
            "tags": "Thanh lịch,Năng động",
            "body_type": "Dáng Đồng Hồ Cát",
            "skin_tone": "Trung tính",
            "hair_type": "Tóc dài thẳng",
            "face_shape": "Mặt trái xoan",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["ai_reasoning_and_recommendation"] == "recommendation-for-test"


def test_vision_rejects_non_image_upload():
    response = client.post(
        "/vision/upload-clothing/",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "File must be an image"


def test_vision_upload_returns_processed_data(monkeypatch, tmp_path):
    def fake_process(image_bytes):
        assert image_bytes.startswith(b"\xff\xd8")
        return {"image_url": "/uploads/test.png", "attributes": {"category": "top"}}

    monkeypatch.setattr(vision.cv_engine, "process_and_save_clothing_image", fake_process)
    response = client.post(
        "/vision/upload-clothing/",
        files={"file": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Image processed successfully"
    assert response.json()["data"]["attributes"]["category"] == "top"


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base, get_db

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        app.dependency_overrides.pop(get_db, None)


def test_wardrobe_user_and_item_crud_endpoints(db_session):
    from app.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    user_payload = {
        "username": "demo-user",
        "email": "demo@example.com",
        "height_cm": 170,
        "weight_kg": 60,
    }
    user_response = client.post("/wardrobe/users/", json=user_payload)
    assert user_response.status_code == 200
    user_id = user_response.json()["id"]

    duplicate = client.post("/wardrobe/users/", json=user_payload)
    assert duplicate.status_code == 400

    missing_user = client.get("/wardrobe/users/9999")
    assert missing_user.status_code == 404

    item_response = client.post(
        f"/wardrobe/users/{user_id}/items/",
        json={"name": "Blazer", "category": "top", "color": "black"},
    )
    assert item_response.status_code == 200
    assert item_response.json()["owner_id"] == user_id

    items_response = client.get(f"/wardrobe/users/{user_id}/items/")
    assert items_response.status_code == 200
    assert len(items_response.json()) == 1

    missing_item_owner = client.post(
        "/wardrobe/users/9999/items/",
        json={"name": "Shoes", "category": "shoes", "color": "white"},
    )
    assert missing_item_owner.status_code == 404


def test_vision_returns_500_when_processor_fails(monkeypatch):
    def failing_processor(_image_bytes):
        raise RuntimeError("processor failure")

    monkeypatch.setattr(vision.cv_engine, "process_and_save_clothing_image", failing_processor)
    response = client.post(
        "/vision/upload-clothing/",
        files={"file": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
    )
    assert response.status_code == 500
    assert "Image processing failed" in response.json()["detail"]


def test_recommendation_returns_500_when_engine_fails(monkeypatch):
    class FailingEngine:
        is_loaded = True

        def get_style_advice(self, **_kwargs):
            raise RuntimeError("inference failure")

    monkeypatch.setattr(stylist, "stylist_engine", FailingEngine())
    response = client.post(
        "/stylist/recommend/",
        files={"image": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
        data={"tags": "Thanh lịch"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "inference failure"


def test_demo_engine_formats_profile_and_tags():
    from app.services.ai_stylist import DemoStylistEngine

    result = DemoStylistEngine().get_style_advice(
        "unused.jpg",
        ["Thanh lịch"],
        {"body_type": "Dáng Chữ Nhật", "skin_tone": "Trung tính"},
    )
    assert "KẾT QUẢ DEMO LOCAL" in result
    assert "Thanh lịch" in result
    assert "Dáng Chữ Nhật" in result


def test_cv_engine_helpers_and_save(monkeypatch, tmp_path):
    from app.services import cv_engine

    payload = make_image_bytes()
    assert cv_engine.remove_background(payload) == payload
    assert cv_engine.extract_attributes(payload)["category"] == "top"

    upload_dir = tmp_path / "clothing"
    monkeypatch.setattr(cv_engine, "UPLOAD_DIR", str(upload_dir))
    result = cv_engine.process_and_save_clothing_image(payload)
    assert result["image_url"].startswith(f"/{upload_dir}")
    assert result["attributes"]["style"] == "casual"
    assert len(list(upload_dir.glob("*.png"))) == 1


def test_tags_endpoint_handles_missing_taxonomy(monkeypatch):
    monkeypatch.setattr(stylist.os.path, "exists", lambda _path: False)
    response = client.get("/stylist/tags")
    assert response.status_code == 200
    assert response.json() == {"tags": []}


def test_recommendation_loads_engine_lazily(monkeypatch):
    class LazyFakeEngine:
        is_loaded = False

        def load_model(self):
            self.is_loaded = True

        def get_style_advice(self, **_kwargs):
            return "lazy-loaded-recommendation"

    engine = LazyFakeEngine()
    monkeypatch.setattr(stylist, "stylist_engine", engine)
    response = client.post(
        "/stylist/recommend/",
        files={"image": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
        data={"tags": "Thanh lịch"},
    )
    assert response.status_code == 200
    assert engine.is_loaded is True
    assert response.json()["data"]["ai_reasoning_and_recommendation"] == "lazy-loaded-recommendation"


def test_wardrobe_can_read_created_user(db_session):
    from app.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    created = client.post(
        "/wardrobe/users/",
        json={"username": "reader", "email": "reader@example.com"},
    )
    user_id = created.json()["id"]
    response = client.get(f"/wardrobe/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["email"] == "reader@example.com"


def test_service_can_select_real_pipeline_without_importing_weights(monkeypatch):
    import importlib
    import types

    fake_module = types.ModuleType("ai_training.vlm_inference")

    class FakePipeline:
        pass

    fake_module.MasterStylistPipeline = FakePipeline
    monkeypatch.setitem(sys.modules, "ai_training.vlm_inference", fake_module)
    monkeypatch.setenv("AI_STYLIST_DEMO_MODE", "0")

    import app.services.ai_stylist as service

    loaded = importlib.reload(service)
    assert isinstance(loaded.stylist_engine, FakePipeline)

    monkeypatch.setenv("AI_STYLIST_DEMO_MODE", "1")
    importlib.reload(service)


def test_recommendation_can_enqueue_job_without_redis(monkeypatch):
    import types

    class FakeTask:
        id = "job-test-1"

        @staticmethod
        def delay(*args):
            assert str(args[1][0]) == "Thanh lịch"
            return FakeTask()

    fake_tasks = types.ModuleType("app.tasks")
    fake_tasks.generate_recommendation = FakeTask
    monkeypatch.setitem(sys.modules, "app.tasks", fake_tasks)
    monkeypatch.setattr(stylist, "QUEUE_MODE", "celery")

    response = client.post(
        "/stylist/recommend/",
        files={"image": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
        data={"tags": "Thanh lịch"},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "queued", "job_id": "job-test-1"}

    monkeypatch.setattr(stylist, "QUEUE_MODE", "inline")


def test_queue_status_completed(monkeypatch):
    import app.queue as queue

    class Completed:
        state = "SUCCESS"
        result = {"ai_reasoning_and_recommendation": "queued-result"}

    monkeypatch.setattr(queue.celery_app, "AsyncResult", lambda _job_id: Completed())
    monkeypatch.setattr(stylist, "QUEUE_MODE", "celery")
    response = client.get("/stylist/recommend/job-1")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["data"]["ai_reasoning_and_recommendation"] == "queued-result"
    monkeypatch.setattr(stylist, "QUEUE_MODE", "inline")


def test_queue_status_failure(monkeypatch):
    import app.queue as queue

    class Failed:
        state = "FAILURE"
        result = RuntimeError("worker failed")

    monkeypatch.setattr(queue.celery_app, "AsyncResult", lambda _job_id: Failed())
    monkeypatch.setattr(stylist, "QUEUE_MODE", "celery")
    response = client.get("/stylist/recommend/job-2")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    monkeypatch.setattr(stylist, "QUEUE_MODE", "inline")


def test_queue_status_rejects_when_disabled():
    response = client.get("/stylist/recommend/job-disabled")
    assert response.status_code == 404


def test_celery_task_runs_and_removes_upload(monkeypatch, tmp_path):
    from app import tasks

    class FakeEngine:
        is_loaded = True

        def get_style_advice(self, **_kwargs):
            return "worker-result"

    monkeypatch.setattr(tasks, "stylist_engine", FakeEngine())
    upload = tmp_path / "queued.jpg"
    upload.write_bytes(make_image_bytes())
    result = tasks.generate_recommendation.run(str(upload), ["Thanh lịch"], None)
    assert result["ai_reasoning_and_recommendation"] == "worker-result"
    assert not upload.exists()


def test_measurement_recommendation_endpoint():
    response = client.post(
        "/stylist/measurement-recommend/",
        json={
            "measurements": {
                "height": 170,
                "weight": 60,
                "shoulder": 42,
                "bust": 88,
                "waist": 72,
                "hip": 94,
                "inseam": 78,
            },
            "selected_tags": ["Thanh lịch"],
        },
    )
    assert response.status_code == 200
    assert "Số đo" in response.json()["data"]["ai_reasoning_and_recommendation"]


def test_measurement_recommendation_validates_ranges():
    response = client.post(
        "/stylist/measurement-recommend/",
        json={
            "measurements": {
                "height": 20,
                "weight": 60,
                "shoulder": 42,
                "bust": 88,
                "waist": 72,
                "hip": 94,
                "inseam": 78,
            },
            "selected_tags": ["Thanh lịch"],
        },
    )
    assert response.status_code == 422


def test_measurement_recommendation_handles_special_body_features():
    response = client.post(
        "/stylist/measurement-recommend/",
        json={
            "measurements": {
                "height": 170, "weight": 60, "shoulder": 42,
                "bust": 82, "waist": 72, "hip": 94, "inseam": 78,
                "shoulder_slope": "sloped", "chest_profile": "flat", "leg_alignment": "bowed",
            },
            "selected_tags": ["Hack chiều cao"],
        },
    )
    assert response.status_code == 200
    advice = response.json()["data"]["ai_reasoning_and_recommendation"]
    assert "vai xuôi" in advice
    assert "ngực lép" in advice
    assert "chân vòng kiềng" in advice


def test_default_database_generator_closes():
    from app.database import get_db

    generator = get_db()
    database_session = next(generator)
    assert database_session is not None
    generator.close()


def test_demo_engine_not_loaded_and_load_branch():
    from app.services.ai_stylist import DemoStylistEngine

    engine = DemoStylistEngine()
    engine.is_loaded = False
    assert "chưa sẵn sàng" in engine.get_measurement_advice({}, [])
    engine.load_model()
    assert engine.is_loaded is True


def test_recommendation_rejects_non_image():
    response = client.post(
        "/stylist/recommend/",
        files={"image": ("note.txt", b"hello", "text/plain")},
        data={"tags": "Thanh lịch"},
    )
    assert response.status_code == 400


def test_recommendation_rejects_empty_tags():
    response = client.post(
        "/stylist/recommend/",
        files={"image": ("outfit.jpg", make_image_bytes(), "image/jpeg")},
        data={"tags": " , "},
    )
    assert response.status_code == 422


def test_measurement_recommendation_rejects_empty_tags():
    response = client.post(
        "/stylist/measurement-recommend/",
        json={
            "measurements": {"height": 170, "weight": 60, "shoulder": 42, "bust": 88, "waist": 72, "hip": 94, "inseam": 78},
            "selected_tags": [],
        },
    )
    assert response.status_code == 422


def test_measurement_recommendation_queue_submission(monkeypatch):
    import types

    class FakeTask:
        id = "measurement-job-1"

        @staticmethod
        def delay(payload, selected_tags):
            assert payload["shoulder_slope"] == "sloped"
            assert selected_tags == ["Hack chiều cao"]
            return FakeTask()

    fake_tasks = types.ModuleType("app.tasks")
    fake_tasks.generate_measurement_recommendation = FakeTask
    monkeypatch.setitem(sys.modules, "app.tasks", fake_tasks)
    monkeypatch.setattr(stylist, "QUEUE_MODE", "celery")
    response = client.post(
        "/stylist/measurement-recommend/",
        json={
            "measurements": {"height": 170, "weight": 60, "shoulder": 42, "bust": 88, "waist": 72, "hip": 94, "inseam": 78, "shoulder_slope": "sloped"},
            "selected_tags": ["Hack chiều cao"],
        },
    )
    assert response.status_code == 202
    assert response.json()["job_id"] == "measurement-job-1"
    monkeypatch.setattr(stylist, "QUEUE_MODE", "inline")


def test_queue_status_pending(monkeypatch):
    import app.queue as queue

    class Pending:
        state = "PENDING"
        result = None

    monkeypatch.setattr(queue.celery_app, "AsyncResult", lambda _job_id: Pending())
    monkeypatch.setattr(stylist, "QUEUE_MODE", "celery")
    response = client.get("/stylist/recommend/pending-job")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    monkeypatch.setattr(stylist, "QUEUE_MODE", "inline")


def test_measurement_worker_loads_engine(monkeypatch):
    from app import tasks

    class LazyEngine:
        is_loaded = False

        def load_model(self):
            self.is_loaded = True

        def get_measurement_advice(self, measurements, selected_tags):
            return "measurement-worker-result"

    monkeypatch.setattr(tasks, "stylist_engine", LazyEngine())
    result = tasks.generate_measurement_recommendation.run({"height": 170}, ["Thanh lịch"])
    assert result["ai_reasoning_and_recommendation"] == "measurement-worker-result"


PHASE_A_MEASUREMENTS = {
    "height_cm": 162,
    "weight_kg": 56,
    "shoulder_cm": 39,
    "bust_cm": 82,
    "waist_cm": 67,
    "hip_cm": 94,
    "inseam_cm": 74,
    "shoulder_slope": "sloped",
    "chest_profile": "flat",
    "leg_alignment": "bowed",
}


def test_phase_a_body_contract_derives_shape_and_joint_scales():
    response = client.post("/phase-a/body-contract", json=PHASE_A_MEASUREMENTS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "1.0"
    assert payload["skeleton_id"] == "mixamo-humanoid-v1"
    assert "sloped_shoulders" in payload["visual_flags"]
    assert "bowed_leg_alignment" in payload["visual_flags"]
    assert 0.8 <= payload["bone_length_scales"]["upper_leg"] <= 1.2


def test_phase_a_catalog_lists_and_filters_active_canonical_garments():
    response = client.get("/phase-a/catalog?category=top")
    assert response.status_code == 200
    payload = response.json()
    assert payload["catalog_version"] == "1.0.0-seed"
    assert len(payload["garments"]) >= 2
    assert all(garment["category"] == "top" for garment in payload["garments"])
    assert payload["garments"][0]["asset"]["compatible_skeleton_ids"] == ["mixamo-humanoid-v1"]


def test_phase_a_catalog_returns_404_for_unknown_garment():
    response = client.get("/phase-a/catalog/gar_unknown")
    assert response.status_code == 404


def test_phase_a_outfit_decision_returns_evidence_and_confirmation():
    body_response = client.post("/phase-a/body-contract", json=PHASE_A_MEASUREMENTS)
    request = {
        "body": body_response.json(),
        "context": {
            "occasion": "work",
            "preferred_styles": ["business", "classic"],
            "season": "autumn",
            "fit_preference": "tailored",
            "required_slots": ["base_top", "bottom"],
        },
        "top_k": 2,
    }
    response = client.post("/phase-a/outfit-decisions", json=request)
    assert response.status_code == 200
    payload = response.json()
    assert payload["abstained"] is False
    assert payload["candidates"]
    candidate = payload["candidates"][0]
    assert len(candidate["garment_ids"]) == 2
    assert candidate["confidence"] > 0
    assert candidate["evidence"]
    assert candidate["needs_user_confirmation"]


def test_phase_a_outfit_decision_abstains_for_unknown_candidate_ids():
    body_response = client.post("/phase-a/body-contract", json=PHASE_A_MEASUREMENTS)
    response = client.post(
        "/phase-a/outfit-decisions",
        json={
            "body": body_response.json(),
            "context": {"occasion": "work", "required_slots": ["base_top", "bottom"]},
            "candidate_garment_ids": ["gar_not_available"],
        },
    )
    assert response.status_code == 200
    assert response.json()["abstained"] is True


def test_phase_a_body_contract_validates_enumerated_visual_features():
    invalid = {**PHASE_A_MEASUREMENTS, "leg_alignment": "unknown"}
    response = client.post("/phase-a/body-contract", json=invalid)
    assert response.status_code == 422


def test_phase_b_import_creates_canonical_proxy_manifest_and_binding():
    response = client.post(
        "/phase-b/garment-imports",
        files={"file": ("white-shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    manifest = payload["manifest"]
    assert manifest["rig_status"] == "canonical_proxy"
    assert manifest["conversion_backend"] == "canonical_proxy"
    assert manifest["target_skeleton_id"] == "mixamo-humanoid-v1"
    assert manifest["selected_garment_id"].startswith("gar_")

    read_response = client.get(f"/phase-b/garment-imports/{manifest['import_id']}")
    assert read_response.status_code == 200
    binding_response = client.post("/phase-b/try-on-bindings", json={"import_ids": [manifest["import_id"]]})
    assert binding_response.status_code == 200
    binding = binding_response.json()[0]
    assert binding["category"] == "top"
    assert binding["rig_status"] == "canonical_proxy"


def test_phase_b_import_rejects_non_image_upload():
    response = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 422


def test_phase_b_missing_import_returns_404():
    response = client.get("/phase-b/garment-imports/imp_000000000000")
    assert response.status_code == 404


def test_phase_b_binding_rejects_unknown_import():
    response = client.post("/phase-b/try-on-bindings", json={"import_ids": ["imp_000000000000"]})
    assert response.status_code == 404


@pytest.fixture
def phase_b_storage(monkeypatch, tmp_path):
    from app.services import garment_import, garment_segmentation

    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(garment_import, "GARMENT_UPLOAD_DIR", upload_root / "garments")
    monkeypatch.setattr(garment_import, "MANIFEST_DIR", upload_root / "garment_manifests")
    monkeypatch.setattr(garment_segmentation, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(garment_segmentation, "SEGMENT_DIR", upload_root / "garment_segments")
    return upload_root


def make_png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (24, 24), color=(32, 48, 64, 255)).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "payload", "mime", "expected"),
    [
        ("shirt.jpg", make_image_bytes(), "text/plain", "Content type must be an image"),
        ("shirt.txt", make_image_bytes(), "image/jpeg", "Unsupported file extension"),
        ("shirt.png", make_image_bytes(), "image/jpeg", "File extension does not match"),
        ("shirt.gif", make_png_bytes(), "image/gif", "Unsupported file extension"),
        ("shirt.jpg", b"", "image/jpeg", "Garment image is empty"),
        ("shirt.jpg", b"not-a-real-image", "image/jpeg", "Uploaded content is not a valid image"),
    ],
)
def test_phase_b_import_rejects_invalid_format_cases(phase_b_storage, filename, payload, mime, expected):
    response = client.post("/phase-b/garment-imports", files={"file": (filename, payload, mime)})
    assert response.status_code == 422
    assert expected in response.json()["detail"]


def test_phase_b_import_rejects_missing_file_field():
    response = client.post("/phase-b/garment-imports", data={"category": "top"})
    assert response.status_code == 422


def test_phase_b_import_rejects_oversized_image_before_decode(phase_b_storage):
    response = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")},
    )
    assert response.status_code == 422
    assert "10 MB" in response.json()["detail"]


def test_phase_b_import_rejects_invalid_category_override(phase_b_storage):
    response = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "cape"},
    )
    assert response.status_code == 422
    assert "Unsupported garment category" in response.json()["detail"]


def test_phase_b_manifest_and_static_upload_share_one_absolute_root():
    response = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    )
    assert response.status_code == 200
    source_uri = response.json()["manifest"]["source_image_uri"]
    from main import UPLOAD_ROOT

    assert (UPLOAD_ROOT / source_uri.removeprefix("/uploads/")).exists()


def test_phase_b_reconstruction_submission_and_duplicate_guard(monkeypatch, phase_b_storage):
    from app.routers import phase_b

    imported = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    ).json()["manifest"]

    class FakeJob:
        id = "reconstruction-job-1"

    monkeypatch.setattr(phase_b.process_garment_reconstruction, "delay", lambda import_id: FakeJob())
    response = client.post(f"/phase-b/garment-imports/{imported['import_id']}/reconstruct")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["job_id"] == "reconstruction-job-1"

    duplicate = client.post(f"/phase-b/garment-imports/{imported['import_id']}/reconstruct")
    assert duplicate.status_code == 409


def test_phase_b_reconstruction_job_polling(monkeypatch):
    from app.routers import phase_b

    class FinishedTask:
        state = "SUCCESS"
        result = {"reconstruction": {"pipeline_state": "pending_reconstruction"}}

        @staticmethod
        def successful():
            return True

    monkeypatch.setattr(phase_b, "AsyncResult", lambda _job_id, app: FinishedTask())
    response = client.get("/phase-b/garment-reconstruction-jobs/job-1")
    assert response.status_code == 200
    assert response.json()["celery_state"] == "SUCCESS"


def test_phase_c_gpu_preflight_reports_insufficient_vram(monkeypatch):
    import types
    from app.services.garment_reconstruction import gpu_preflight

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def get_device_properties(_index):
            return types.SimpleNamespace(name="Test GPU", total_memory=4 * 1024 ** 3)

    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(cuda=FakeCuda()))
    report = gpu_preflight(min_vram_gb=12)
    assert report.eligible is False
    assert report.vram_gb == 4
    assert "below" in report.reason


def test_phase_c_segmentation_fallback_writes_normalized_png(phase_b_storage):
    from app.services.garment_import import import_garment_image
    from app.services.garment_segmentation import SEGMENT_DIR, segment_garment

    manifest = import_garment_image("shirt.png", make_png_bytes(), "image/png", "top")
    artifact = segment_garment(manifest)
    assert artifact.asset_uri == f"/uploads/garment_segments/{manifest.import_id}.png"
    assert (SEGMENT_DIR / f"{manifest.import_id}.png").exists()
    assert artifact.quality in {"verified", "unverified"}


def test_phase_c_worker_marks_missing_quality_gate_pending(monkeypatch, phase_b_storage):
    from app import tasks
    from app.services.garment_import import import_garment_image
    from app.services.garment_segmentation import segment_garment

    manifest = import_garment_image("shirt.png", make_png_bytes(), "image/png", "top")
    monkeypatch.setattr(tasks, "segment_garment", segment_garment)
    monkeypatch.setattr(tasks, "reconstruct_rigged_garment", lambda imported: imported)
    result = tasks.process_garment_reconstruction.run(manifest.import_id)
    assert result["rig_status"] == "pending_reconstruction"
    assert result["reconstruction"]["pipeline_state"] == "pending_reconstruction"
    assert "quality gate" in result["reconstruction"]["failure_reason"]


def test_phase_c_worker_accepts_mock_rigged_output_only_after_quality_gate(monkeypatch, phase_b_storage):
    from app import tasks
    from app.phase_b_schemas import MeshQualityGateV1
    from app.services.garment_import import import_garment_image
    from app.services.garment_segmentation import segment_garment

    manifest = import_garment_image("shirt.png", make_png_bytes(), "image/png", "top")

    def mock_reconstructor(imported):
        imported.generated_asset_uri = "/uploads/garment_meshes/mock-shirt.glb"
        imported.quality_gate = MeshQualityGateV1(
            asset_exists=True,
            glb_valid=True,
            skeleton_id="mixamo-humanoid-v1",
            rest_pose="a_pose",
            anchors_present=True,
            skin_weights_valid=True,
            scale_valid=True,
            bounds_valid=True,
            intersection_check="passed",
            review_status="approved",
        )
        return imported

    monkeypatch.setattr(tasks, "segment_garment", segment_garment)
    monkeypatch.setattr(tasks, "reconstruct_rigged_garment", mock_reconstructor)
    result = tasks.process_garment_reconstruction.run(manifest.import_id)
    assert result["rig_status"] == "rigged_template"
    assert result["reconstruction"]["pipeline_state"] == "rigged_template"


def test_phase_c_worker_records_segmentation_and_provider_failures(monkeypatch, phase_b_storage):
    from app import tasks
    from app.services.garment_import import import_garment_image

    manifest = import_garment_image("shirt.png", make_png_bytes(), "image/png", "top")
    monkeypatch.setattr(tasks, "segment_garment", lambda _manifest: (_ for _ in ()).throw(RuntimeError("mask error")))
    segmentation_failure = tasks.process_garment_reconstruction.run(manifest.import_id)
    assert segmentation_failure["reconstruction"]["pipeline_state"] == "failed"
    assert "Segmentation failed" in segmentation_failure["reconstruction"]["failure_reason"]

    manifest = import_garment_image("shirt-two.png", make_png_bytes(), "image/png", "top")
    from app.services.garment_segmentation import segment_garment
    monkeypatch.setattr(tasks, "segment_garment", segment_garment)
    monkeypatch.setattr(tasks, "reconstruct_rigged_garment", lambda _manifest: (_ for _ in ()).throw(ValueError("mesh crash")))
    provider_failure = tasks.process_garment_reconstruction.run(manifest.import_id)
    assert provider_failure["reconstruction"]["pipeline_state"] == "failed"
    assert "Reconstruction provider failed" in provider_failure["reconstruction"]["failure_reason"]


def test_phase_b_binding_rejects_skeleton_contract_mismatch(phase_b_storage):
    imported = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    ).json()["manifest"]
    response = client.post(
        "/phase-b/try-on-bindings",
        json={"import_ids": [imported["import_id"]], "target_skeleton_id": "different-skeleton"},
    )
    assert response.status_code == 409
    assert "Skeleton contract mismatch" in response.json()["detail"]


def test_phase_b_rejects_malformed_persisted_manifest(phase_b_storage):
    from app.services.garment_import import MANIFEST_DIR

    import_id = "imp_abcdef123456"
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / f"{import_id}.json").write_text("{not-json", encoding="utf-8")
    response = client.get(f"/phase-b/garment-imports/{import_id}")
    assert response.status_code == 409
    assert "malformed" in response.json()["detail"]


def test_phase_c_worker_records_expected_pending_provider_states(monkeypatch, phase_b_storage):
    from app import tasks
    from app.services.garment_import import import_garment_image
    from app.services.garment_segmentation import segment_garment

    manifest = import_garment_image("shirt.png", make_png_bytes(), "image/png", "top")
    monkeypatch.setattr(tasks, "segment_garment", segment_garment)
    monkeypatch.setattr(tasks, "reconstruct_rigged_garment", lambda _manifest: (_ for _ in ()).throw(NotImplementedError("provider absent")))
    no_provider = tasks.process_garment_reconstruction.run(manifest.import_id)
    assert no_provider["reconstruction"]["pipeline_state"] == "pending_reconstruction"
    assert no_provider["reconstruction"]["provider_version"] == "provider-not-configured"

    manifest = import_garment_image("shirt-three.png", make_png_bytes(), "image/png", "top")
    monkeypatch.setattr(tasks, "reconstruct_rigged_garment", lambda _manifest: (_ for _ in ()).throw(RuntimeError("4 GB is insufficient")))
    preflight_pending = tasks.process_garment_reconstruction.run(manifest.import_id)
    assert preflight_pending["reconstruction"]["pipeline_state"] == "pending_reconstruction"
    assert "insufficient" in preflight_pending["reconstruction"]["failure_reason"]


WORKFLOW_CONTEXT = {
    "occasion": "work",
    "preferred_styles": ["business", "classic"],
    "season": "autumn",
    "fit_preference": "tailored",
    "required_slots": ["base_top", "bottom"],
}


def workflow_meta(actor_id: int, key: str) -> dict:
    return {"actor_id": actor_id, "idempotency_key": f"workflow-test-{key}"}


@pytest.fixture
def workflow_db(db_session):
    from app.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield db_session
    app.dependency_overrides.pop(get_db, None)


def create_workflow_user(username: str = "workflow-user") -> int:
    response = client.post(
        "/wardrobe/users/",
        json={"username": username, "email": f"{username}@example.com"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_workflow_rejects_unknown_actor_before_persistence(workflow_db):
    payload = {
        **workflow_meta(99999, "unknown-actor"),
        "measurements": PHASE_A_MEASUREMENTS,
    }
    response = client.post("/workflow/body-profiles", json=payload)
    assert response.status_code == 404
    assert "actor" in response.json()["detail"]


def test_workflow_body_profile_requires_confirmation_and_is_idempotent(workflow_db):
    actor_id = create_workflow_user("body-workflow")
    payload = {**workflow_meta(actor_id, "body-create"), "measurements": PHASE_A_MEASUREMENTS}
    created = client.post("/workflow/body-profiles", json=payload)
    assert created.status_code == 201
    assert created.json()["status"] == "calibrated"
    profile_id = created.json()["profile_id"]

    replay = client.post("/workflow/body-profiles", json=payload)
    assert replay.status_code == 201
    assert replay.json()["profile_id"] == profile_id

    confirm = client.post(
        f"/workflow/body-profiles/{profile_id}/confirm",
        json={**workflow_meta(actor_id, "body-confirm"), "confirmation_note": "User confirmed calibration"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "active"

    invalid_reconfirm = client.post(
        f"/workflow/body-profiles/{profile_id}/confirm",
        json={**workflow_meta(actor_id, "body-confirm-again")},
    )
    assert invalid_reconfirm.status_code == 409

    events = client.get(f"/workflow/audit-events/{profile_id}")
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == ["BodyProfileCalibrated", "BodyProfileActivated"]


def test_workflow_wardrobe_asset_lifecycle_requires_activation(workflow_db):
    actor_id = create_workflow_user("asset-workflow")
    canonical = client.get("/phase-a/catalog?category=top").json()["garments"][0]["garment_id"]
    created = client.post(
        "/workflow/wardrobe-assets",
        json={**workflow_meta(actor_id, "asset-create"), "name": "Verified work shirt", "category": "top", "canonical_garment_id": canonical},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "normalized"
    asset_id = created.json()["asset_id"]

    approved = client.post(
        f"/workflow/wardrobe-assets/{asset_id}/approve",
        json={**workflow_meta(actor_id, "asset-approve"), "approval_note": "Metadata reviewed"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "active"
    assert approved.json()["quality_summary"]["eligible_for_decision"] is True

    duplicate_approval = client.post(
        f"/workflow/wardrobe-assets/{asset_id}/approve",
        json={**workflow_meta(actor_id, "asset-approve-again")},
    )
    assert duplicate_approval.status_code == 409


def test_workflow_session_decision_selection_try_on_and_audit(workflow_db):
    actor_id = create_workflow_user("session-workflow")
    body = client.post(
        "/workflow/body-profiles",
        json={**workflow_meta(actor_id, "session-body"), "measurements": PHASE_A_MEASUREMENTS},
    ).json()
    client.post(
        f"/workflow/body-profiles/{body['profile_id']}/confirm",
        json={**workflow_meta(actor_id, "session-body-confirm")},
    )

    active_assets = []
    for category in ("top", "bottom"):
        catalog_item = client.get(f"/phase-a/catalog?category={category}").json()["garments"][0]
        created = client.post(
            "/workflow/wardrobe-assets",
            json={
                **workflow_meta(actor_id, f"session-asset-{category}"),
                "name": f"Workflow {category}",
                "category": category,
                "canonical_garment_id": catalog_item["garment_id"],
            },
        ).json()
        approved = client.post(
            f"/workflow/wardrobe-assets/{created['asset_id']}/approve",
            json={**workflow_meta(actor_id, f"session-approve-{category}")},
        )
        assert approved.status_code == 200
        active_assets.append(created["asset_id"])

    session = client.post(
        "/workflow/styling-sessions",
        json={
            **workflow_meta(actor_id, "session-create"),
            "body_profile_id": body["profile_id"],
            "context": WORKFLOW_CONTEXT,
            "wardrobe_asset_ids": active_assets,
        },
    )
    assert session.status_code == 201
    assert session.json()["status"] == "inputs_resolved"
    assert len(session.json()["wardrobe_snapshot"]) == 2
    session_id = session.json()["session_id"]

    decision = client.post(
        f"/workflow/styling-sessions/{session_id}/outfit-decisions",
        json={**workflow_meta(actor_id, "session-decision"), "top_k": 2},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "ready"
    candidate_id = decision.json()["decision"]["candidates"][0]["outfit_id"]

    selected = client.post(
        f"/workflow/styling-sessions/{session_id}/select-outfit",
        json={**workflow_meta(actor_id, "session-select"), "outfit_id": candidate_id},
    )
    assert selected.status_code == 200
    assert selected.json()["status"] == "outfit_selected"

    try_on = client.post(
        f"/workflow/styling-sessions/{session_id}/try-on",
        json={**workflow_meta(actor_id, "session-try-on"), "render_mode": "canonical_proxy"},
    )
    assert try_on.status_code == 201
    assert try_on.json()["status"] == "proxy_fallback"
    assert "not a reconstructed" in try_on.json()["limitations"][0]

    events = client.get(f"/workflow/audit-events/{session_id}").json()
    assert [event["event_type"] for event in events] == [
        "StylingSessionInputsResolved", "OutfitDecisionCompleted", "OutfitSelected"
    ]


def test_workflow_session_blocks_inactive_body_and_unapproved_asset(workflow_db):
    actor_id = create_workflow_user("workflow-invariant")
    body = client.post(
        "/workflow/body-profiles",
        json={**workflow_meta(actor_id, "invariant-body"), "measurements": PHASE_A_MEASUREMENTS},
    ).json()
    inactive_session = client.post(
        "/workflow/styling-sessions",
        json={**workflow_meta(actor_id, "inactive-session"), "body_profile_id": body["profile_id"], "context": WORKFLOW_CONTEXT},
    )
    assert inactive_session.status_code == 409

    client.post(
        f"/workflow/body-profiles/{body['profile_id']}/confirm",
        json={**workflow_meta(actor_id, "invariant-confirm")},
    )
    item = client.get("/phase-a/catalog?category=top").json()["garments"][0]
    asset = client.post(
        "/workflow/wardrobe-assets",
        json={**workflow_meta(actor_id, "unapproved-asset"), "name": "Not yet active", "category": "top", "canonical_garment_id": item["garment_id"]},
    ).json()
    blocked = client.post(
        "/workflow/styling-sessions",
        json={
            **workflow_meta(actor_id, "unapproved-session"),
            "body_profile_id": body["profile_id"],
            "context": WORKFLOW_CONTEXT,
            "wardrobe_asset_ids": [asset["asset_id"]],
        },
    )
    assert blocked.status_code == 409


def test_workflow_rigged_request_without_approved_evidence_returns_truthful_proxy_fallback(workflow_db):
    actor_id = create_workflow_user("workflow-render-gate")
    body = client.post(
        "/workflow/body-profiles",
        json={**workflow_meta(actor_id, "render-body"), "measurements": PHASE_A_MEASUREMENTS},
    ).json()
    client.post(
        f"/workflow/body-profiles/{body['profile_id']}/confirm",
        json={**workflow_meta(actor_id, "render-confirm")},
    )
    asset_ids = []
    for category in ("top", "bottom"):
        catalog = client.get(f"/phase-a/catalog?category={category}").json()["garments"][0]
        asset = client.post(
            "/workflow/wardrobe-assets",
            json={**workflow_meta(actor_id, f"render-{category}"), "name": f"Render {category}", "category": category, "canonical_garment_id": catalog["garment_id"]},
        ).json()
        client.post(f"/workflow/wardrobe-assets/{asset['asset_id']}/approve", json=workflow_meta(actor_id, f"render-approve-{category}"))
        asset_ids.append(asset["asset_id"])
    session = client.post(
        "/workflow/styling-sessions",
        json={**workflow_meta(actor_id, "render-session"), "body_profile_id": body["profile_id"], "context": WORKFLOW_CONTEXT, "wardrobe_asset_ids": asset_ids},
    ).json()
    decision = client.post(
        f"/workflow/styling-sessions/{session['session_id']}/outfit-decisions",
        json={**workflow_meta(actor_id, "render-decision")},
    ).json()
    client.post(
        f"/workflow/styling-sessions/{session['session_id']}/select-outfit",
        json={**workflow_meta(actor_id, "render-select"), "outfit_id": decision["decision"]["candidates"][0]["outfit_id"]},
    )
    response = client.post(
        f"/workflow/styling-sessions/{session['session_id']}/try-on",
        json={**workflow_meta(actor_id, "render-rigged"), "render_mode": "rigged_template"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "proxy_fallback"
    assert response.json()["render_mode"] == "canonical_proxy"
    assert response.json()["requested_render_mode"] == "rigged_template"
    assert response.json()["quality_status"] == "pending_review"
    assert "quality evidence" in response.json()["limitations"][0]


def test_workflow_links_phase_b_import_to_reviewable_wardrobe_revision(workflow_db, phase_b_storage):
    actor_id = create_workflow_user("workflow-import-link")
    imported = client.post(
        "/phase-b/garment-imports",
        files={"file": ("work-shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    )
    assert imported.status_code == 200
    manifest = imported.json()["manifest"]
    created = client.post(
        "/workflow/wardrobe-assets",
        json={
            **workflow_meta(actor_id, "import-link-create"),
            "name": "Imported work shirt",
            "category": "top",
            "import_id": manifest["import_id"],
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["import_id"] == manifest["import_id"]
    assert payload["canonical_garment_id"] == manifest["selected_garment_id"]
    assert payload["quality_summary"]["source"] == "garment_import_manifest"
    assert payload["quality_summary"]["eligible_for_decision"] is False

    active = client.post(
        f"/workflow/wardrobe-assets/{payload['asset_id']}/approve",
        json={**workflow_meta(actor_id, "import-link-approve")},
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"


def test_workflow_query_endpoints_restore_aggregate_and_enforce_owner(workflow_db):
    actor_id = create_workflow_user("workflow-query-owner")
    other_actor_id = create_workflow_user("workflow-query-other")
    body = client.post(
        "/workflow/body-profiles",
        json={**workflow_meta(actor_id, "query-body"), "measurements": PHASE_A_MEASUREMENTS},
    ).json()
    body_read = client.get(f"/workflow/body-profiles/{body['profile_id']}?actor_id={actor_id}")
    assert body_read.status_code == 200
    assert body_read.json()["profile_id"] == body["profile_id"]
    denied_body = client.get(f"/workflow/body-profiles/{body['profile_id']}?actor_id={other_actor_id}")
    assert denied_body.status_code == 404

    client.post(f"/workflow/body-profiles/{body['profile_id']}/confirm", json=workflow_meta(actor_id, "query-confirm"))
    session = client.post(
        "/workflow/styling-sessions",
        json={**workflow_meta(actor_id, "query-session"), "body_profile_id": body["profile_id"], "context": WORKFLOW_CONTEXT},
    ).json()
    session_read = client.get(f"/workflow/styling-sessions/{session['session_id']}?actor_id={actor_id}")
    assert session_read.status_code == 200
    assert session_read.json()["status"] == "inputs_resolved"
    denied_session = client.get(f"/workflow/styling-sessions/{session['session_id']}?actor_id={other_actor_id}")
    assert denied_session.status_code == 404


def test_workflow_wardrobe_asset_query_returns_latest_revision_and_enforces_owner(workflow_db):
    actor_id = create_workflow_user("workflow-asset-query-owner")
    other_actor_id = create_workflow_user("workflow-asset-query-other")
    canonical = client.get("/phase-a/catalog?category=top").json()["garments"][0]
    asset = client.post(
        "/workflow/wardrobe-assets",
        json={
            **workflow_meta(actor_id, "asset-query-create"),
            "name": "Query shirt",
            "category": "top",
            "canonical_garment_id": canonical["garment_id"],
        },
    ).json()
    draft_read = client.get(f"/workflow/wardrobe-assets/{asset['asset_id']}?actor_id={actor_id}")
    assert draft_read.status_code == 200
    assert draft_read.json()["status"] == "normalized"
    denied = client.get(f"/workflow/wardrobe-assets/{asset['asset_id']}?actor_id={other_actor_id}")
    assert denied.status_code == 404
    missing = client.get(f"/workflow/wardrobe-assets/wad_000000000000?actor_id={actor_id}")
    assert missing.status_code == 404

    client.post(
        f"/workflow/wardrobe-assets/{asset['asset_id']}/approve",
        json=workflow_meta(actor_id, "asset-query-approve"),
    )
    active_read = client.get(f"/workflow/wardrobe-assets/{asset['asset_id']}?actor_id={actor_id}")
    assert active_read.status_code == 200
    assert active_read.json()["status"] == "active"


def test_phase_b_semantic_tagging_reports_unavailable_without_config(monkeypatch, phase_b_storage):
    monkeypatch.setenv("GARMENT_TAGGER_PROVIDER", "disabled")
    imported = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    ).json()["manifest"]
    response = client.post(f"/phase-b/garment-imports/{imported['import_id']}/semantic-tags")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["manifest"]["analysis"]["semantic_tagging"]["status"] == "unavailable"
    assert payload["manifest"]["analysis"]["semantic_tagging"]["candidate_metadata"] is None


def test_phase_b_semantic_tagging_queue_and_duplicate_guard(monkeypatch, phase_b_storage):
    from app.routers import phase_b

    monkeypatch.setenv("GARMENT_TAGGER_PROVIDER", "qwen25vl")

    class FakeJob:
        id = "semantic-tag-job-1"

    monkeypatch.setattr(phase_b.semantic_tag_garment_import, "delay", lambda import_id: FakeJob())
    imported = client.post(
        "/phase-b/garment-imports",
        files={"file": ("shirt.jpg", make_image_bytes(), "image/jpeg")},
        data={"category": "top"},
    ).json()["manifest"]
    response = client.post(f"/phase-b/garment-imports/{imported['import_id']}/semantic-tags")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["job_id"] == "semantic-tag-job-1"

    duplicate = client.post(f"/phase-b/garment-imports/{imported['import_id']}/semantic-tags")
    assert duplicate.status_code == 409
