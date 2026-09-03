"""
這幾天 GitHub Actions 的 backend-test job 一直失敗，原因是 main.py 的 import chain
在「載入模組」的當下（不是執行測試的當下）就需要幾個環境變數，CI 卻沒有帶進去：
- db/security.py 缺 CLERK_JWKS_URL / CLERK_ISSUER 會直接 raise RuntimeError
- routers/webhook.py 缺 GEMINI_API_KEY，建立 genai.Client 會直接 raise ValueError

這份測試做兩件事：
1. 用 subprocess 真的重現「缺變數就掛」的行為，證明這不是憑空猜測。
2. 檢查 .github/workflows/deploy.yml 的 backend-test job 確實有把這幾個變數帶進去，
   避免以後有人改 workflow 時又把它們拿掉、CI 又悄悄變紅。
"""
import os
import subprocess
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKFLOW_PATH = os.path.abspath(
    os.path.join(BACKEND_DIR, "..", ".github", "workflows", "deploy.yml")
)

REQUIRED_ENV_VARS = ["CLERK_ISSUER", "CLERK_JWKS_URL", "GEMINI_API_KEY"]


def _run_import_in_clean_process(code: str, env_overrides: dict) -> subprocess.CompletedProcess:
    """在乾淨的子行程跑一段 import，模擬 CI 上沒有 .env、也沒有繼承任何本機環境變數的情況。"""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd="/tmp",  # 故意跑在 repo 之外，確保不會撿到 Backend/.env
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": BACKEND_DIR, **env_overrides},
        capture_output=True,
        text=True,
    )


def test_missing_clerk_env_vars_breaks_import():
    result = _run_import_in_clean_process("import db.security", env_overrides={})

    assert result.returncode != 0
    assert "Missing environment variable" in result.stderr


def test_clerk_env_vars_present_allows_import():
    result = _run_import_in_clean_process(
        "import db.security",
        env_overrides={
            "CLERK_JWKS_URL": "https://fake.clerk.dev/.well-known/jwks.json",
            "CLERK_ISSUER": "https://fake.clerk.dev",
        },
    )

    assert result.returncode == 0, result.stderr


def test_missing_gemini_api_key_breaks_webhook_import():
    result = _run_import_in_clean_process("import routers.webhook", env_overrides={})

    assert result.returncode != 0
    assert "Missing key inputs argument" in result.stderr


def test_gemini_api_key_present_allows_webhook_import():
    result = _run_import_in_clean_process(
        "import routers.webhook", env_overrides={"GEMINI_API_KEY": "fake-key"}
    )

    assert result.returncode == 0, result.stderr


def _get_job_block(workflow_text: str, job_name: str) -> str:
    """抓出指定 job（2 個空白縮排的頂層 key）底下的內容，抓到下一個同層級 key 為止。"""
    lines = workflow_text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip() == f"  {job_name}:"), None
    )
    assert start is not None, f"workflow 裡找不到 job '{job_name}'"

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith("   "):
            end = i
            break
    return "\n".join(lines[start:end])


def test_backend_test_job_has_required_env_vars_wired_in_ci():
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        workflow_text = f.read()

    job_block = _get_job_block(workflow_text, "backend-test")

    for var in REQUIRED_ENV_VARS:
        assert var in job_block, (
            f"{var} 沒有出現在 backend-test job 裡——main.py 的 import chain 需要它，"
            "少了它 pytest 連收集測試都會失敗（見 db/security.py、routers/webhook.py）"
        )
