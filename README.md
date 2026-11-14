# KOBIS MCP 서버

영화진흥위원회(KOBIS) 오픈 API를 Claude 같은 MCP 클라이언트에서 쓸 수 있게 해 주는 서버입니다.

## 도구

| 도구 | 설명 |
|---|---|
| `daily_boxoffice` | 일별 박스오피스 (기본: 어제) |
| `weekly_boxoffice` | 주간 / 주말 / 주중 박스오피스 (기본: 지난주) |
| `search_movies` | 영화 목록 검색 (영화명, 감독, 개봉/제작연도, 국적, 유형) |
| `movie_info` | 영화 상세 (감독, 배우, 장르, 상영시간, 등급, 영화사) |
| `search_companies` / `company_info` | 영화사 검색 / 상세 |
| `search_people` / `people_info` | 영화인 검색 / 상세 (필모그래피) |
| `code_list` | 공통 코드 (지역, 장르, 국적, 등급 등) |

## 설치

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

API 키는 같은 폴더의 `.env`에 둡니다 (또는 환경변수 `KOBIS_API_KEY`). `.env.example`을 복사해서 만드세요.

```
KOBIS_API_KEY=발급받은키
```

키 발급: https://www.kobis.or.kr/kobisopenapi/homepg/main/main.do

## 연결

### Claude Code

```powershell
claude mcp add kobis -- "<이 폴더 경로>\.venv\Scripts\python.exe" "<이 폴더 경로>\kobis_mcp.py"
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "kobis": {
      "command": "C:\\...\\11-14\\.venv\\Scripts\\python.exe",
      "args": ["C:\\...\\11-14\\kobis_mcp.py"]
    }
  }
}
```

## 참고

- HTTPS 인증서는 OS 인증서 저장소(`truststore`)로 검증합니다. 사내 프록시 환경에서도 검증을 끄지 않고 동작합니다.
- httpx 요청 로그는 API 키가 노출되지 않도록 꺼 두었습니다.
- 국적 코드는 대륙 아래에 있습니다: `code_list("220310")` → 아시아 국가 (한국 `22041011`).

## 라이선스

[MIT](LICENSE)
