# 다채널 홍보/여론 데이터 수집기

## 목적
네이버 뉴스, 네이버 블로그, YouTube 데이터를 동일한 키워드와 기준일(KST)로 자동 수집하고, 정규화 및 중복제거를 거쳐 엑셀, CSV, JSON 형태의 리포트 데이터를 생성하는 운영용 데이터 수집 파이프라인입니다.

## 사용 API
- **네이버 뉴스 검색 API**: `https://openapi.naver.com/v1/search/news.json`
- **네이버 블로그 검색 API**: `https://openapi.naver.com/v1/search/blog.json`
- **YouTube Data API v3**: `https://www.googleapis.com/youtube/v3/search`
- **Google Gemini API** (선택): weak_match 항목 2차 판별용

## config.json 설정 방법
`config.json` 파일에 다음 정보들을 기입해야 합니다:
- `naver_client_id`, `naver_client_secret`: 네이버 개발자 센터에서 발급받은 검색 API 인증 정보.
- `youtube_api_key`: Google Cloud Console에서 발급받은 YouTube Data API v3 인증 키.
- `keywords`: 검색할 키워드 배열 (예: `["삼성전자", "LG전자"]`).
- `target_date`: 수집할 기준일 (`YYYY-MM-DD` 형식).
- `sources`: 수집 대상 채널 (`naver_news`, `naver_blog`, `youtube`).

## 실행 방법
### 기본 실행 (config.json 사용)
```bash
python main.py
```

### CLI 옵션을 이용한 실행
명령줄 인자를 통해 `config.json`의 설정을 오버라이드할 수 있습니다.
```bash
python main.py --keyword "인공지능" --date 2026-05-01 --sources naver_news,youtube --max-pages 5 --detail
```

## 출력 파일 설명
실행이 완료되면 `outputs/` 디렉토리에 다음과 같은 파일들이 생성됩니다 (`{target_date}_{keyword}` 접두사 사용):
- `*_summary.xlsx`: 요약, 상세, 원천 통계 데이터를 각각의 시트로 포함하는 엑셀 파일.
- `*_summary.csv`: 채널별 수집/중복제거 건수 및 성공 여부 요약 CSV.
- `*_details.csv`: **public 노출 대상만** 포함하는 최종 상세 리스트 CSV.
- `*_details.json`: **public 노출 대상만** 포함하는 최종 정규화/중복제거된 상세 데이터 JSON.
- `*_filter_audit.json`: 수집 후 분류된 **모든 결과**(제외 항목 포함)를 저장하는 감사용 JSON.
- `*_raw.json`: API 원천 응답 및 호출 기록 JSON.

실행 로그는 `logs/` 디렉토리에 저장됩니다.

---

## 🔍 검색 결과 필터링 시스템

### 네이버 검색 API 특성과 타 행사 결과 혼입
네이버 검색 API는 관련도 기반으로 결과를 반환하기 때문에, "국제정원박람회"로 검색하면 **고양꽃박람회**, **순천만국제정원박람회** 등 타 행사 결과가 섞일 수 있습니다. 또한 정치인(오세훈, 정원오, 구청장 등)이나 이슈(포켓몬, 성수동 인파 등) 관련 결과도 함께 수집됩니다.

### 분류 정책: 삭제하지 않고 분류하여 보존
본 프로젝트는 검색 결과를 **무조건 삭제하지 않고** 모든 결과를 `filter_audit.json`에 보존합니다.
- **public details** (`*_details.json`)에는 서울국제정원박람회와 관련 있는 결과만 저장됩니다.
- **filter_audit** (`*_filter_audit.json`)에는 제외된 결과까지 포함하여 전체 분류 결과가 저장됩니다.

### 웹 기본 화면에서 제외되는 카테고리
다음 카테고리는 public details에 포함되지 않으므로 **웹 기본 화면과 count에서 제외**됩니다:
- `other_event_only`: 타 행사(고양꽃박람회, 순천만 등)만 다루는 글
- `irrelevant`: 어떤 관련 키워드도 매칭되지 않는 글
- `ai_irrelevant`: Gemini AI가 무관으로 판정한 글

### 카테고리 분류 기준

| 카테고리 | 설명 | 웹 노출 |
|----------|------|---------|
| `confirmed` | **순수 행사 관련.** 정치/이슈/타행사 맥락 없이 서울국제정원박람회만 다루는 글 | ✅ |
| `related_issue` | **행사 연계 이슈.** 포켓몬/인파/혼잡/교통/행사 중단 등 행사에서 파생된 이슈를 다루는 글 | ✅ |
| `comparison` | **타 행사 비교.** 고양꽃박람회/순천만 등 타 행사와 서울국제정원박람회를 함께 다루는 글 | ✅ |
| `political_context` | **정치 맥락.** 오세훈/정원오/구청장/선거/공약 등 정치 맥락에서 행사를 언급하는 글 | ✅ |
| `weak_match` | **약한 매칭.** "국제정원박람회"만 있고 서울 장소 단서가 없는 글 (AI 검토 대상) | ✅ |
| `other_event_only` | **타 행사 단독.** 고양꽃박람회, 순천만 등 타 행사만 다루고 본행사 관련성이 없는 글 | ❌ |
| `irrelevant` | **무관.** 어떤 관련 키워드도 매칭되지 않는 글 | ❌ |
| `ai_irrelevant` | **AI 판정 무관.** Gemini AI가 무관으로 판정한 글 | ❌ |

> [!IMPORTANT]
> **맥락 카테고리 우선 원칙**: 본행사 관련성이 확인된 상태에서 정치/이슈/타행사 맥락이 동시에 존재하면, **comparison > political_context > related_issue > confirmed** 순서로 분류됩니다.
> 
> - "오세훈 + 서울국제정원박람회" → `political_context` (confirmed가 아님)
> - "포켓몬 인파 + 서울국제정원박람회" → `related_issue` (confirmed가 아님)
> - "고양꽃박람회 + 서울국제정원박람회 비교" → `comparison` (confirmed가 아님)
> - `other_event_only`, `irrelevant`, `ai_irrelevant`는 **public details에 저장되지 않고** filter_audit에만 저장됩니다.

---

## 🤖 Gemini AI 2차 판별

### 선택적 사용
Gemini API는 전체 결과에 호출하지 않고, **`weak_match`(약한 매칭) 결과에만 선택적으로 호출**합니다. 이를 통해 API 비용을 절감하면서 분류 정확도를 높입니다.

### 활성화 방법
`config.json`에서 `ambiguous_ai_enabled`를 `true`로 변경합니다:
```json
{
  "relevance_filter": {
    "ambiguous_ai_enabled": true
  }
}
```

기본값은 `true`이며, API 비용 절감 등 운영자가 원할 때만 `false`로 비활성화합니다.

### Gemini API Key 설정

#### 방법 1: secret.json
```json
{
  "naver_client_id": "...",
  "naver_client_secret": "...",
  "youtube_api_key": "...",
  "gemini_api_key": "YOUR_GEMINI_API_KEY"
}
```

#### 방법 2: 환경변수
```bash
export GEMINI_API_KEY=your_api_key_here
```

#### 방법 3: SECRET_JSON 환경변수 (GitHub Actions 등)
```bash
export SECRET_JSON='{"gemini_api_key": "your_api_key_here", ...}'
```

우선순위: 환경변수 `GEMINI_API_KEY` → `secret.json` → `SECRET_JSON`

> **참고**: API 키가 없고 `ambiguous_ai_enabled=true`인 경우, 전체 실행은 중단되지 않습니다. Warning 로그만 남기고 weak_match 상태를 유지합니다.

---

## 🔄 기존 적재 데이터 중복 방지

동일한 기사/블로그/영상이 여러 날에 걸쳐 중복 적재되는 것을 방지합니다.
- `web/public/data/index.json`에 등록된 기존 details 파일을 읽어 중복을 판별합니다.
- 중복 기준: `external_id` → `canonical_url` → `original_url` → `title + date`
- 같은 날짜를 재실행할 때는 기존 동일 report를 덮어쓸 수 있습니다 (`allow_overwrite_same_report_id: true`).

---

## 🔎 제외 결과 검수 방법

### filter_audit.json
`outputs/` 또는 `web/public/data/`에 생성되는 `*_filter_audit.json` 파일에서 제외된 결과를 확인할 수 있습니다.

```bash
# 파이썬으로 제외 항목만 필터링
python -c "
import json
with open('outputs/2026-05-01_국제정원박람회_filter_audit.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
excluded = [d for d in data if d.get('filter_status') == 'excluded']
for item in excluded:
    print(f\"[{item['category']}] {item['title']}\")
    print(f\"  사유: {item['filter_reason']}\")
"
```

### 웹 화면 검수 모드
웹 대시보드에서 **"제외 후보 보기 (검수 모드)"** 버튼을 클릭하면 제외된 결과를 확인할 수 있습니다. 각 항목에는 제외 사유(`filter_reason`), 매칭된 키워드, AI 판별 결과가 표시됩니다.

---

## 🎛️ 웹 화면 토글 필터

### 카테고리 필터
상단 카테고리 칩을 클릭하여 특정 분류만 표시할 수 있습니다:
- 전체 / 확정 관련 / 연계 이슈 / 비교/연관 / 정치/선거 / 검토 필요

### 빠른 숨김 토글
상세 필터를 펼치면 다음 토글이 제공됩니다:
- 포켓몬 숨기기
- 정치인 전체/개별(오세훈, 정원오, 구청장) 숨기기
- 정치/선거 글 숨기기
- 검토 필요 글 숨기기

### 직접 제외 키워드 입력
쉼표로 구분하여 여러 키워드를 입력하면, 해당 키워드가 포함된 결과를 화면에서 숨깁니다.

### 본행사 강한 키워드 우선
기본값 ON. "서울국제정원박람회" 등 확실한 키워드가 포함된 결과는 제외 키워드가 있어도 숨기지 않습니다.

### localStorage 저장
토글 상태는 브라우저의 localStorage에 저장되어 새로고침 후에도 유지됩니다.

> **중요**: 웹 토글은 데이터를 삭제하지 않습니다. public details 안에서 화면 표시만 제어합니다.

---

## ⚠️ 중요 주의사항

### 1. KST (Asia/Seoul) 날짜 기준
본 시스템은 모든 날짜 처리를 KST 기준으로 수행합니다. 
- 네이버 API 응답에 포함된 timezone 문자열을 해석하여 KST로 변환 후 필터링합니다.
- YouTube API는 입력된 KST `target_date`를 UTC 기간으로 변환하여 요청하고, 응답받은 데이터도 다시 KST로 변환 후 비교합니다.

### 2. 네이버 API 조회 한계
네이버 검색 API는 `start` 파라미터가 최대 **1000**까지만 허용됩니다. 따라서 `page_size=100` 기준으로 최대 10페이지만 수집 가능합니다. 그 이상 조회 시도 시 API가 에러를 반환하며 수집 한계 경고가 Summary에 기록됩니다.

### 3. YouTube API Quota 유의사항
YouTube `search.list` API는 호출 비용이 큽니다(1회 호출 당 약 100 Quota). 기본 제공되는 일일 할당량(10,000)을 고려하여 `max_pages` 및 호출 주기를 적절히 조절해야 `quotaExceeded` 오류를 피할 수 있습니다.

## 자동 실행 예시
Cron이나 스케줄러에 등록하여 일일 단위로 실행할 수 있습니다.
```bash
# 매일 밤 11시 30분에 당일 데이터 수집
30 23 * * * cd /path/to/project && python main.py --date $(date +\%Y-\%m-\%d) >> /var/log/my_collector.log 2>&1
```

## 오류 발생 시 점검 방법
1. **API 키 오류**: `config.json`의 키가 유효한지 확인합니다. 네이버 `401`/`403`, YouTube `keyInvalid` 등의 오류는 키 문제일 확률이 높습니다.
2. **할당량 초과**: 네이버 `429`, YouTube `quotaExceeded`가 발생하면 일일 호출 횟수를 초과한 것입니다. 다음 날까지 대기하거나 할당량을 증설해야 합니다.
3. **상세 로그 확인**: 문제 발생 시 `logs/{target_date}_{keyword}_run.log` 파일을 열어 구체적인 에러 메시지와 스택 트레이스를 확인하세요.

---

## 운영 메모: Public count, 화면 표시, artifact

### Public 노출 count와 현재 표시 count

웹 상단 Summary Card의 큰 숫자는 **Public 노출** 기준입니다. 즉 수집/중복 제거/관련도 분류 파이프라인을 통과해 `*_details.json`에 저장된 건수입니다.

반면 FilterPanel의 **현재 표시** 숫자는 사용자가 웹에서 카테고리, 포켓몬 숨기기, 정치인 숨기기, 직접 제외 키워드 같은 토글을 적용한 뒤 실제 화면에 남아 있는 건수입니다. 웹 토글은 저장된 데이터를 삭제하거나 재분류하지 않고, public details 안에서 화면 표시만 제어합니다.

### public details와 filter_audit

`other_event_only`, `irrelevant`, `ai_irrelevant`는 public details에 저장하지 않습니다. 이 항목들은 `*_filter_audit.json`에만 남겨서 제외 후보 검수 화면에서 확인합니다.

`confirmed`, `related_issue`, `comparison`, `political_context`, `weak_match`는 기본 public 노출 대상입니다. 단, 웹 토글을 켜면 public details 안에서도 화면 표시가 일시적으로 숨겨질 수 있습니다.

### GitHub Actions 산출물 정책

GitHub Actions 자동 실행은 Vercel 화면에 필요한 `web/public/data/*.json`만 레포에 커밋합니다. `outputs/`와 `logs/`는 Git 레포에 커밋하지 않고, Actions artifact로 업로드합니다.

artifact 이름은 `gjb-run-${{ github.run_id }}` 형식이며 포함 대상은 다음과 같습니다.

```text
outputs/**
logs/**
```

Actions 실행 결과는 GitHub 저장소의 **Actions** 탭에서 해당 workflow run을 열어 확인합니다. 수집 로그와 Excel/CSV/원본 JSON 산출물은 run 하단의 Artifacts 영역에서 내려받아 검수할 수 있습니다.

### 자동 실행 확인 순서

1. GitHub Actions의 `Data Collector Pipeline` run이 성공했는지 확인합니다.
2. `Run Collector` 단계에서 수집 결과와 저장 경로가 출력되는지 확인합니다.
3. `Commit and Push` 단계에서 `web/public/data/` 변경분만 commit되는지 확인합니다.
4. `outputs/`와 `logs/`가 `gjb-run-${{ github.run_id }}` artifact에 포함되는지 확인합니다.
5. Vercel 배포 후 웹이 최신 `web/public/data/index.json`을 읽는지 확인합니다.
6. 웹의 `제외 후보 보기`에서 `other_event_only`, `irrelevant`, `ai_irrelevant`만 표시되는지 확인합니다.

### GitHub Actions Node.js warning

현재 workflow는 `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`를 사용합니다. GitHub-hosted action 내부 런타임에 대한 Node.js deprecation warning이 보일 수 있으나, 이는 현재 수집 실패의 직접 원인이 아닙니다. upstream action의 최신 major가 필요한 시점에 별도로 갱신합니다.
