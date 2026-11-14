"""영화진흥위원회(KOBIS) 오픈 API MCP 서버.

API 문서: https://www.kobis.or.kr/kobisopenapi/homepg/apiservice/searchServiceInfo.do
API 키는 환경변수 KOBIS_API_KEY 또는 같은 폴더의 .env 파일에서 읽습니다.
"""

from __future__ import annotations

import logging
import os
import ssl
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv(Path(__file__).with_name(".env"))

# httpx 요청 로그에는 쿼리스트링(API 키 포함)이 그대로 찍히므로 숨깁니다.
logging.getLogger("httpx").setLevel(logging.WARNING)

BASE_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest"

# OS 인증서 저장소를 사용합니다(사내 프록시 인증서, KOBIS 중간 인증서 누락 대응).
SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

mcp = MCPServer("kobis")


def _api_key() -> str:
    key = (os.environ.get("KOBIS_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "KOBIS_API_KEY가 설정되지 않았습니다. 환경변수나 .env 파일에 키를 넣어주세요."
        )
    return key


async def _get(path: str, **params: Any) -> dict:
    """KOBIS API를 호출하고 JSON을 반환합니다. 값이 None/빈 문자열인 파라미터는 제외합니다."""
    query = {k: v for k, v in params.items() if v not in (None, "")}
    query["key"] = _api_key()
    async with httpx.AsyncClient(timeout=20, verify=SSL_CONTEXT) as client:
        resp = await client.get(f"{BASE_URL}/{path}.json", params=query)
        resp.raise_for_status()
        data = resp.json()
    if "faultInfo" in data:
        fault = data["faultInfo"]
        raise RuntimeError(f"KOBIS API 오류: {fault.get('message')} ({fault.get('errorCode')})")
    return data


def _yn(value: bool | None) -> str | None:
    return None if value is None else ("Y" if value else "N")


def _default_date() -> str:
    # 일별 박스오피스는 전날까지만 집계됩니다.
    return (date.today() - timedelta(days=1)).strftime("%Y%m%d")


def _default_week() -> str:
    # 주간 박스오피스는 지난주 일요일 이전 날짜를 넣어야 완결된 주가 나옵니다.
    return (date.today() - timedelta(days=7)).strftime("%Y%m%d")


# ---------------------------------------------------------------- 박스오피스


@mcp.tool()
async def daily_boxoffice(
    target_date: str | None = None,
    item_per_page: int = 10,
    multi_movie: bool | None = None,
    nation: Literal["K", "F"] | None = None,
    area_code: str | None = None,
) -> dict:
    """일별 박스오피스 순위를 조회합니다.

    Args:
        target_date: 조회 날짜(YYYYMMDD). 생략하면 어제.
        item_per_page: 결과 개수(최대 10).
        multi_movie: True=다양성 영화만, False=상업 영화만, 생략=전체.
        nation: "K"=한국 영화, "F"=외국 영화, 생략=전체.
        area_code: 지역 코드(code_list의 "0105000000" 지역 코드 참고).
    """
    data = await _get(
        "boxoffice/searchDailyBoxOfficeList",
        targetDt=target_date or _default_date(),
        itemPerPage=item_per_page,
        multiMovieYn=_yn(multi_movie),
        repNationCd=nation,
        wideAreaCd=area_code,
    )
    return data["boxOfficeResult"]


@mcp.tool()
async def weekly_boxoffice(
    target_date: str | None = None,
    week_type: Literal["week", "weekend", "weekday"] = "week",
    item_per_page: int = 10,
    multi_movie: bool | None = None,
    nation: Literal["K", "F"] | None = None,
    area_code: str | None = None,
) -> dict:
    """주간/주말 박스오피스 순위를 조회합니다.

    Args:
        target_date: 해당 주에 속하는 날짜(YYYYMMDD). 생략하면 지난주.
        week_type: "week"=주간(월~일), "weekend"=주말(금~일), "weekday"=주중(월~목).
        item_per_page: 결과 개수(최대 10).
        multi_movie: True=다양성 영화만, False=상업 영화만, 생략=전체.
        nation: "K"=한국 영화, "F"=외국 영화, 생략=전체.
        area_code: 지역 코드.
    """
    week_gb = {"week": "0", "weekend": "1", "weekday": "2"}[week_type]
    data = await _get(
        "boxoffice/searchWeeklyBoxOfficeList",
        targetDt=target_date or _default_week(),
        weekGb=week_gb,
        itemPerPage=item_per_page,
        multiMovieYn=_yn(multi_movie),
        repNationCd=nation,
        wideAreaCd=area_code,
    )
    return data["boxOfficeResult"]


# ---------------------------------------------------------------- 영화


@mcp.tool()
async def search_movies(
    movie_name: str | None = None,
    director_name: str | None = None,
    open_start_year: str | None = None,
    open_end_year: str | None = None,
    prdt_start_year: str | None = None,
    prdt_end_year: str | None = None,
    nation_code: str | None = None,
    movie_type_code: str | None = None,
    page: int = 1,
    item_per_page: int = 10,
) -> dict:
    """영화 목록을 검색합니다. 영화 코드(movieCd)를 얻어 movie_info에 사용하세요.

    Args:
        movie_name: 영화명(일부 일치).
        director_name: 감독명.
        open_start_year / open_end_year: 개봉연도 범위(YYYY).
        prdt_start_year / prdt_end_year: 제작연도 범위(YYYY).
        nation_code: 국적 코드(예: 한국 22041011, 대륙별 목록은 code_list("220310") 등).
        movie_type_code: 영화 유형 코드(code_list "2201000000").
        page: 페이지 번호.
        item_per_page: 페이지당 결과 수(최대 100).
    """
    data = await _get(
        "movie/searchMovieList",
        movieNm=movie_name,
        directorNm=director_name,
        openStartDt=open_start_year,
        openEndDt=open_end_year,
        prdtStartYear=prdt_start_year,
        prdtEndYear=prdt_end_year,
        repNationCd=nation_code,
        movieTypeCd=movie_type_code,
        curPage=page,
        itemPerPage=item_per_page,
    )
    return data["movieListResult"]


@mcp.tool()
async def movie_info(movie_code: str) -> dict:
    """영화 상세 정보(감독, 배우, 장르, 상영시간, 관람등급, 제작사 등)를 조회합니다.

    Args:
        movie_code: 영화 코드(movieCd). search_movies나 박스오피스 결과에서 얻습니다.
    """
    data = await _get("movie/searchMovieInfo", movieCd=movie_code)
    return data["movieInfoResult"]["movieInfo"]


# ---------------------------------------------------------------- 영화사


@mcp.tool()
async def search_companies(
    company_name: str | None = None,
    ceo_name: str | None = None,
    company_part_code: str | None = None,
    page: int = 1,
    item_per_page: int = 10,
) -> dict:
    """영화사 목록을 검색합니다.

    Args:
        company_name: 영화사명.
        ceo_name: 대표자명.
        company_part_code: 분류 코드(code_list "2601000000", 예: 제작사/배급사).
        page: 페이지 번호.
        item_per_page: 페이지당 결과 수.
    """
    data = await _get(
        "company/searchCompanyList",
        companyNm=company_name,
        ceoNm=ceo_name,
        companyPartCd=company_part_code,
        curPage=page,
        itemPerPage=item_per_page,
    )
    return data["companyListResult"]


@mcp.tool()
async def company_info(company_code: str) -> dict:
    """영화사 상세 정보(대표자, 분류, 필모그래피)를 조회합니다.

    Args:
        company_code: 영화사 코드(companyCd).
    """
    data = await _get("company/searchCompanyInfo", companyCd=company_code)
    return data["companyInfoResult"]["companyInfo"]


# ---------------------------------------------------------------- 영화인


@mcp.tool()
async def search_people(
    people_name: str | None = None,
    filmo_name: str | None = None,
    page: int = 1,
    item_per_page: int = 10,
) -> dict:
    """영화인(배우, 감독, 스태프) 목록을 검색합니다.

    Args:
        people_name: 영화인 이름.
        filmo_name: 참여 영화명(동명이인 구분용).
        page: 페이지 번호.
        item_per_page: 페이지당 결과 수.
    """
    data = await _get(
        "people/searchPeopleList",
        peopleNm=people_name,
        filmoNames=filmo_name,
        curPage=page,
        itemPerPage=item_per_page,
    )
    return data["peopleListResult"]


@mcp.tool()
async def people_info(people_code: str) -> dict:
    """영화인 상세 정보(성별, 분야, 필모그래피)를 조회합니다.

    Args:
        people_code: 영화인 코드(peopleCd).
    """
    data = await _get("people/searchPeopleInfo", peopleCd=people_code)
    return data["peopleInfoResult"]["peopleInfo"]


# ---------------------------------------------------------------- 공통 코드


@mcp.tool()
async def code_list(com_code: str = "0105000000") -> list[dict]:
    """KOBIS 공통 코드 목록을 조회합니다.

    자주 쓰는 상위 코드:
        0105000000 지역, 2201000000 영화 유형, 2202000000 제작 상태,
        2205000000 장르, 2206000000 언어, 2304000000 관람등급,
        2601000000 영화사 분류, 2203000000 대륙.
    국적 코드는 대륙 코드 아래에 있습니다. 예: code_list("220310") → 아시아 국가 목록
    (한국 = 22041011).

    Args:
        com_code: 상위 공통 코드.
    """
    data = await _get("code/searchCodeList", comCode=com_code)
    return data["codes"]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
