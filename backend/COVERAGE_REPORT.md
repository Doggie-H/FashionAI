# Backend coverage report

Generated with:

```powershell
python -m pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml:coverage.xml -q tests
```

## Result

- **21 tests passed**.
- **1 GPU integration test skipped** unless `RUN_QWEN_INTEGRATION=1` is set.
- **95% line coverage** for the canonical `backend/app` package: 241 statements, 12 missed.
- HTML report: `backend/htmlcov/index.html`.
- Machine-readable report: `backend/coverage.xml`.

The queue modules are now covered: `app/queue.py` is 100%, `app/tasks.py` is 92%, and the queue submission/status paths in `app/routers/stylist.py` are exercised without requiring Redis. The remaining misses are mostly defensive branches, the default database generator, and an environment-dependent compatibility import.

The real Qwen2.5-VL-7B test is intentionally gated because it downloads weights and requires CUDA/VRAM. It must not run in the default unit-test job.

Known warnings are dependency deprecations involving Starlette/httpx, Pydantic class-based config, and SQLAlchemy's `datetime.utcnow()` default.
