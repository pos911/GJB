# 다채널 홍보/여론 데이터 수집기

## 목적
네이버 뉴스, 네이버 블로그, YouTube 데이터를 동일한 키워드와 기준일(KST)로 자동 수집하고, 정규화 및 중복제거를 거쳐 엑셀, CSV, JSON 형태의 리포트 데이터를 생성하는 운영용 데이터 수집 파이프라인입니다.

## 사용 API
- **네이버 뉴스 검색 API**: `https://openapi.naver.com/v1/search/news.json`
- **네이버 블로그 검색 API**: `https://openapi.naver.com/v1/search/blog.json`
- **YouTube Data API v3**: `https://www.googleapis.com/youtube/v3/search`

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
- `*_details.csv`: 중복이 제거된 최종 상세 리스트 CSV.
- `*_details.json`: 최종 정규화/중복제거된 상세 데이터 JSON.
- `*_raw.json`: API 원천 응답 및 호출 기록 JSON.

실행 로그는 `logs/` 디렉토리에 저장됩니다.

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
