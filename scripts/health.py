"""수집·사이트 배포가 멈췄는지 확인하고, 멈췄거나 회복되면 디스코드로 알린다."""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import notify

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
STATE_PATH = ROOT / "state" / "health.json"
KST = timezone(timedelta(hours=9))
FORMAT = "%Y-%m-%d %H:%M:%S"
# 배포가 계속 안 될 때 다시 알리는 간격
REMIND_EVERY = timedelta(hours=3)
# 사이트 배포는 화면 파일이 바뀔 때와 한 시간에 한 번만 하므로, 이보다 오래 성공이 없을 때만 알린다.
DEPLOY_LIMIT = timedelta(hours=2)


def github(path):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
            "User-Agent": "yangdoki-clips-health",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def last_deploy_success():
    """GitHub Pages에 마지막으로 배포가 성공한 시각(KST)을 돌려준다. 알 수 없으면 None."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo or not os.environ.get("GH_TOKEN"):
        return None
    if github(f"/repos/{repo}/pages").get("build_type") != "workflow":
        return None
    for deployment in github(f"/repos/{repo}/deployments?environment=github-pages&per_page=15"):
        statuses = github(f"/repos/{repo}/deployments/{deployment['id']}/statuses?per_page=1")
        if statuses and statuses[0].get("state") == "success":
            created = datetime.strptime(statuses[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            return created.replace(tzinfo=timezone.utc).astimezone(KST).replace(tzinfo=None)
    return None


def minutes(delta):
    return int(delta.total_seconds() // 60)


def say(text):
    url = os.environ.get(notify.WEBHOOK_ENV, "").strip()
    if not url:
        print("상태 알림: 웹후크 주소가 없어서 건너뜀 —", text)
        return
    notify.post(url, {"username": notify.USERNAME, "avatar_url": notify.AVATAR_URL, "content": text})
    print("상태 알림 보냄:", text)


def main():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    settings = config.get("discord") or {}
    if settings.get("enabled") is False or settings.get("health_alerts") is False:
        return
    limit = timedelta(minutes=int(settings.get("health_minutes") or 30))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    now = datetime.now(KST).replace(tzinfo=None)

    # 1. 수집 간격: 직전 수집과 너무 벌어졌으면 cron-job.org가 멈췄거나 실행이 계속 실패한 것.
    last_run = state.get("last_run")
    collection_gap = False
    if last_run:
        gap = now - datetime.strptime(last_run, FORMAT)
        if gap > limit:
            collection_gap = True
            say(
                f"⚠️ 클립 수집이 **{minutes(gap)}분** 동안 돌지 않았어요 (마지막: {last_run[5:16]}).\n"
                "cron-job.org 작업이 꺼졌거나 오류가 났는지 확인해 주세요."
            )

    # 2. 사이트 배포: 마지막 성공이 너무 오래됐으면 알리고, 회복되면 한 번 알린다.
    #    수집 자체가 멈췄던 거라면 배포가 밀린 건 당연하므로 이번에는 따로 알리지 않는다.
    success = None
    if not collection_gap:
        try:
            success = last_deploy_success()
        except Exception as error:
            print(f"배포 상태 확인 실패: {error}", file=sys.stderr)
    if success is not None:
        age = now - success
        alerted = state.get("deploy_alert_at")
        if age > max(limit, DEPLOY_LIMIT):
            if not alerted or now - datetime.strptime(alerted, FORMAT) >= REMIND_EVERY:
                say(
                    f"⚠️ 사이트 배포가 **{minutes(age)}분째** 안 되고 있어요 (마지막 성공: {success.strftime('%m-%d %H:%M')}).\n"
                    "수집과 알림, 사이트 목록 갱신은 계속 되고 있어요. 화면 파일 변경만 GitHub Pages가 회복되면 반영돼요."
                )
                state["deploy_alert_at"] = now.strftime(FORMAT)
        elif alerted:
            say(f"✅ 사이트 배포가 다시 정상이에요. {notify.SITE_URL}")
            state.pop("deploy_alert_at", None)

    state["last_run"] = now.strftime(FORMAT)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # 감시 기능 때문에 수집 결과 저장이 막히면 안 된다.
        print(f"상태 점검 실패: {error}", file=sys.stderr)
