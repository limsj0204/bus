# 양도끼 클립 모음

SOOP에서 제목에 키워드가 들어간 최근 **클립·캐치**를 10분마다 모아서 보여주는 사이트예요.
다시보기는 넣지 않고, 양도끼(`yangdoki`) 본인 방송 영상은 빼요.

## 구성

| 파일 | 역할 |
|---|---|
| `config.yml` | 키워드, 제외할 단어와 스트리머, 영상 종류 설정 |
| `scripts/fetch.py` | SOOP 검색 결과를 받아서 `docs/data.json`에 저장 |
| `.github/workflows/update.yml` | 10분마다 `fetch.py` 실행 |
| `docs/index.html` | 목록을 보여주는 페이지 (GitHub Pages) |

## 키워드 바꾸기

GitHub에서 `config.yml`을 열고 연필 아이콘으로 고친 뒤 저장하면 돼요. 저장하면 바로 한 번 실행돼요.

```yaml
keywords:
  - 도끼
  - 양도
```

## 처음 한 번 설정

1. 저장소 **Settings → Pages**에서 Source를 **Deploy from a branch**로 하고, 기본 브랜치와 `/docs` 폴더를 골라요. 예약 실행도 기본 브랜치에서만 돌아가요.
2. **Actions** 탭 → **클립 업데이트** → **Run workflow**로 처음 한 번 직접 실행해요.

## 직접 실행

```bash
pip install pyyaml
python scripts/fetch.py
```

## 디스코드 알림

새 클립·캐치가 모이면 디스코드 채널로 알려줘요.

1. 디스코드 서버의 채널 설정 → **연동(Integrations)** → **웹후크** → **새 웹후크** → **웹후크 URL 복사**
2. 이 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: 복사한 웹후크 URL
3. 끄거나 특정 방송만 받으려면 `config.yml`의 `discord` 항목을 고쳐요.
