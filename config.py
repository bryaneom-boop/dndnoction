"""
설정 상수 모음.

값 우선순위:  환경변수  >  local_settings.py(로컬 전용)  >  빈 값
  - GitHub Actions(CI) 에서는 환경변수(GitHub Secrets)로 주입됩니다.
  - 로컬에서는 local_settings.py 에 넣어두면 자동으로 읽어옵니다.

⚠️ 이 파일에는 비밀값을 직접 넣지 마세요. (git 에 커밋됩니다)
   비밀값은 local_settings.py 또는 GitHub Secrets 에만 두세요.
"""

import os

# 로컬 전용 비밀값 (있으면 사용, 없으면 무시 — CI 에서는 없음)
try:
    import local_settings as _local
except ImportError:
    _local = None


def _secret(env_key, default=""):
    """환경변수 > local_settings.py > default 순으로 값을 읽는다."""
    val = os.environ.get(env_key)
    if val:
        return val
    if _local is not None:
        return getattr(_local, env_key, default)
    return default


# ----------------------------------------------------------------------
# Notion
# ----------------------------------------------------------------------
NOTION_TOKEN = _secret("NOTION_TOKEN")
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")

# ----------------------------------------------------------------------
# 메일(SMTP) 설정
# ----------------------------------------------------------------------
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = _secret("SMTP_USER")
SMTP_PASSWORD = _secret("SMTP_PASSWORD")
FROM_NAME = os.environ.get("FROM_NAME", "D&D 프로젝트 리포트")

# 각 담당자 -> 받는 메일 주소
RECIPIENTS = {
    "Bryan": _secret("MAIL_BRYAN"),
    "Eric": _secret("MAIL_ERIC"),
    "Alex": _secret("MAIL_ALEX"),
    "Michael": _secret("MAIL_MICHAEL"),
    "Hailey": _secret("MAIL_HAILEY"),
    "Trisha": _secret("MAIL_TRISHA"),
    "Calvin": _secret("MAIL_CALVIN"),   # 관리자
    "Jason": _secret("MAIL_JASON"),     # 관리자
}
