"""홈 화면 아이콘을 만든다. 양도끼 SOOP 프로필 사진을 받아 쓰고, 못 받으면 기존 아이콘을 그대로 둔다.

python scripts/icons.py            # 하루에 한 번만 프로필 사진을 확인해 아이콘을 갱신
python scripts/icons.py --fallback # 민트색 '양' 글자 아이콘을 만든다 (프로필 사진이 없을 때용)
python scripts/icons.py --local    # 받아 둔 docs/icons/profile.jpg로 아이콘만 다시 만든다
"""

import io
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "docs" / "icons"
STAMP = ICON_DIR / "checked.txt"
KST = timezone(timedelta(hours=9))
PROFILE_URLS = [
    "https://stimg.sooplive.com/LOGO/ya/yangdoki/yangdoki.jpg",
    "https://stimg.sooplive.co.kr/LOGO/ya/yangdoki/yangdoki.jpg",
    "https://profile.img.sooplive.co.kr/LOGO/ya/yangdoki/yangdoki.jpg",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
# 파일 이름 → 한 변 크기
SIZES = {
    "icon-192.png": 192,
    "icon-512.png": 512,
    "apple-touch-icon.png": 180,
    "favicon-64.png": 64,
}
MINT = (13, 148, 136)
MINT_LIGHT = (45, 212, 191)


def download_profile():
    for url in PROFILE_URLS:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.sooplive.com/"})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read()
            image = Image.open(io.BytesIO(data))
            image.load()
            return data, image.convert("RGB")
        except Exception as error:
            print(f"프로필 사진 받기 실패 {url}: {error}")
    return None, None


def square(image):
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def fallback_image(size=512):
    """민트색 그라데이션 바탕에 '양' 글자."""
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        t = y / (size - 1)
        color = tuple(round(MINT_LIGHT[i] * (1 - t) + MINT[i] * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)
    font = None
    for path in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"]:
        try:
            font = ImageFont.truetype(path, int(size * 0.5))
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    draw.text((size / 2, size / 2), "양", font=font, fill="white", anchor="mm")
    return image


def maskable(base, size=512):
    """안드로이드가 원·물방울 모양으로 잘라도 얼굴이 남도록 가운데 80%에 그림을 둔다."""
    canvas = Image.new("RGB", (size, size), MINT)
    inner = int(size * 0.8)
    offset = (size - inner) // 2
    canvas.paste(base.resize((inner, inner), Image.LANCZOS), (offset, offset))
    return canvas


def write_if_changed(path, data):
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def save_icons(base):
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    changed = False
    for name, size in SIZES.items():
        buffer = io.BytesIO()
        base.resize((size, size), Image.LANCZOS).save(buffer, "PNG", optimize=True)
        changed |= write_if_changed(ICON_DIR / name, buffer.getvalue())
    buffer = io.BytesIO()
    maskable(base).save(buffer, "PNG", optimize=True)
    changed |= write_if_changed(ICON_DIR / "icon-maskable-512.png", buffer.getvalue())
    return changed


def main():
    if "--local" in sys.argv:
        # 이미 받아 둔 프로필 사진으로 아이콘만 다시 만든다.
        save_icons(square(Image.open(ICON_DIR / "profile.jpg").convert("RGB")))
        print("받아 둔 프로필 사진으로 아이콘을 다시 만들었어요")
        return
    if "--fallback" in sys.argv:
        save_icons(fallback_image())
        print("민트색 '양' 아이콘을 만들었어요")
        return

    today = datetime.now(KST).strftime("%Y-%m-%d")
    if STAMP.exists() and STAMP.read_text().strip() == today:
        return
    data, image = download_profile()
    if image is None:
        return  # 못 받으면 기존 아이콘을 유지하고 다음 실행 때 다시 시도한다.
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    changed = write_if_changed(ICON_DIR / "profile.jpg", data)
    changed |= save_icons(square(image))
    STAMP.write_text(today + "\n")
    print("프로필 아이콘 " + ("갱신" if changed else "변경 없음"))


if __name__ == "__main__":
    main()
