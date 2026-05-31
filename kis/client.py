# -*- coding: utf-8 -*-
"""
KIS Open API 클라이언트
- REST API 호출 래퍼
- 자동 페이징, 에러 처리
- pandas DataFrame 반환
"""

import logging
import random
import time

import pandas as pd
import requests

from kis.auth import HTTP_TIMEOUT, KISAuth

logger = logging.getLogger(__name__)

# 재시도 설정 (#10 I8). KIS 는 KR 일간 경로에서 ~99콜 직렬이라 누적 지연을 막기
# 위해 보수적으로 1회만 재시도(attempts=2)하고 백오프 상한도 짧게 둔다. 더해서
# set_budget() 으로 전체 wall-clock 예산(deadline)을 걸어, retry 누적이 잡
# 타임아웃(flow-kr 5분)을 넘겨 부분실패 노출 자체를 막는 일이 없게 한다.
_RETRY_ATTEMPTS = 2
_RETRY_BASE = 0.3
_RETRY_MAX = 1.0


class _KISTransient(RuntimeError):
    """KIS 5xx 등 일시 서버 오류 — 재시도 유도용 신호."""


class _KISRateLimited(RuntimeError):
    """EGW00201(초당 거래건수 초과) — 재시도 유도용 신호."""


class _KISDeadlineExceeded(RuntimeError):
    """KIS 호출 예산(deadline) 초과 — 남은 GET 을 네트워크 대기 없이 중단(#10 I8)."""


def _is_rate_limited(data: dict) -> bool:
    """KIS 레이트리밋(EGW00201) 응답인지 판정. msg_cd/msg1 로 식별."""
    if not isinstance(data, dict):
        return False
    return data.get("msg_cd") == "EGW00201" or "EGW00201" in str(data.get("msg1", ""))


class KISClient:
    """한국투자증권 REST API 클라이언트"""

    def __init__(self, auth: KISAuth = None, svr: str = "prod"):
        self.auth = auth or KISAuth(svr=svr)
        self.auth.authenticate()
        # 전체 호출 예산(monotonic 절대 마감 시각). None 이면 예산 없음.
        self._deadline: float | None = None

    # ── 공통 API 호출 ───────────────────────────────────────────

    def set_budget(self, seconds: float | None) -> None:
        """이 시점부터 ``seconds`` 안에 KIS GET 을 마치도록 예산을 건다(#10 I8).

        잡 타임아웃(flow-kr 5분) 안에서 retry 누적 지연이 부분실패 노출을 막지
        않도록, 예산 초과 후의 GET 은 네트워크 대기 없이 즉시 실패시켜 빈 결과로
        degrade 한다 → 경고 노출 + 텔레그램 발송이 보장된다. ``None``/0 이면 예산
        해제(기존 동작). 진행 중인 1콜의 per-request 타임아웃(HTTP_TIMEOUT)까지는
        넘을 수 있으므로 호출부는 그만큼 여유를 둔다.
        """
        self._deadline = (time.monotonic() + seconds) if seconds else None

    def _budget_left(self) -> float | None:
        """예산 잔여 초. 예산이 없으면 None."""
        if self._deadline is None:
            return None
        return self._deadline - time.monotonic()

    def _get_json(self, url: str, headers: dict, params: dict):
        """멱등 GET 1요청 + 재시도(#10 I8) → (resp, parsed|None).

        네트워크 순단·5xx·EGW00201(레이트리밋)만 지수 백오프로 재시도하고, 4xx 등
        영구 오류는 1회로 끝낸다(그대로 반환). KIS 는 독립 패키지라 market_flow 의
        retry 헬퍼에 의존하지 않고 자체 백오프를 둔다. GET(멱등)에만 쓰며, 주문
        등 POST 에는 적용하지 않는다.
        """
        # 예산이 이미 소진됐으면 네트워크 대기 없이 즉시 중단(retry 누적 차단).
        left = self._budget_left()
        if left is not None and left <= 0:
            raise _KISDeadlineExceeded(f"예산 초과 ({url})")

        last_exc: Exception | None = None
        for i in range(_RETRY_ATTEMPTS):
            try:
                resp = requests.get(
                    url, headers=headers, params=params, timeout=HTTP_TIMEOUT
                )
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as exc:
                last_exc = exc
            else:
                if resp.status_code >= 500:
                    last_exc = _KISTransient(
                        f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                elif resp.status_code != 200:
                    return resp, None  # 4xx 등 영구 오류 — 재시도 무의미
                else:
                    data = resp.json()
                    if not _is_rate_limited(data):
                        return resp, data
                    last_exc = _KISRateLimited(str(data.get("msg1", "EGW00201")))
            if i < _RETRY_ATTEMPTS - 1:
                delay = random.random() * min(_RETRY_MAX, _RETRY_BASE * (2**i))
                # 재시도 대기가 예산을 넘기면 더 기다리지 않고 마지막 실패를 낸다.
                left = self._budget_left()
                if left is not None and left <= delay:
                    break
                logger.warning(
                    "KIS 재시도 %d/%d (%s): %s — %.2fs 후",
                    i + 1,
                    _RETRY_ATTEMPTS - 1,
                    url,
                    last_exc,
                    delay,
                )
                time.sleep(delay)
        assert last_exc is not None  # 루프에서 항상 설정됨
        raise last_exc

    def get(self, api_url: str, tr_id: str, params: dict, tr_cont: str = "") -> dict:
        """GET 방식 API 호출, 원시 응답 반환"""
        url = f"{self.auth.base_url}{api_url}"
        headers = self.auth.get_headers(tr_id, tr_cont)
        try:
            resp, data = self._get_json(url, headers, params)
        except (
            requests.exceptions.RequestException,
            _KISTransient,
            _KISRateLimited,
            _KISDeadlineExceeded,
        ) as e:
            logger.error("API %s 재시도 소진: %s", api_url, e)
            return {"rt_cd": "-1", "msg1": str(e)}
        if resp.status_code != 200 or data is None:
            logger.error("API %s → %d: %s", api_url, resp.status_code, resp.text[:200])
            return {"rt_cd": "-1", "msg1": f"HTTP {resp.status_code}"}
        return data

    def post(self, api_url: str, tr_id: str, body: dict, tr_cont: str = "") -> dict:
        """POST 방식 API 호출 (주문 등)"""
        url = f"{self.auth.base_url}{api_url}"
        headers = self.auth.get_headers(tr_id, tr_cont)
        resp = requests.post(url, headers=headers, json=body, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            logger.error("API %s → %d: %s", api_url, resp.status_code, resp.text[:200])
            return {"rt_cd": "-1", "msg1": f"HTTP {resp.status_code}"}
        return resp.json()

    def fetch_dataframe(
        self,
        api_url: str,
        tr_id: str,
        params: dict,
        output_key: str = "output",
        max_pages: int = 10,
    ) -> pd.DataFrame:
        """
        GET API 호출 → DataFrame 반환 (자동 페이징)

        Args:
            api_url: API 엔드포인트 경로
            tr_id: 트랜잭션 ID
            params: 요청 파라미터
            output_key: 응답 body에서 데이터 추출할 키 ("output", "output1", "output2")
            max_pages: 최대 연속조회 횟수
        """
        frames = []
        tr_cont = ""

        for page in range(max_pages):
            url = f"{self.auth.base_url}{api_url}"
            headers = self.auth.get_headers(tr_id, tr_cont)
            try:
                resp, data = self._get_json(url, headers, params)
            except (
                requests.exceptions.RequestException,
                _KISTransient,
                _KISRateLimited,
                _KISDeadlineExceeded,
            ) as e:
                logger.error("API %s 재시도 소진: %s", api_url, e)
                break

            if resp.status_code != 200 or data is None:
                logger.error("API error %d: %s", resp.status_code, resp.text[:200])
                break

            if data.get("rt_cd") != "0":
                logger.error(
                    "API rt_cd=%s, msg=%s", data.get("rt_cd"), data.get("msg1")
                )
                break

            output = data.get(output_key)
            if output:
                if isinstance(output, list):
                    frames.append(pd.DataFrame(output))
                elif isinstance(output, dict):
                    frames.append(pd.DataFrame([output]))

            # 연속조회 처리
            next_cont = resp.headers.get("tr_cont", "")
            if next_cont not in ("M", "F"):
                break
            tr_cont = "N"
            # 연속조회 키 업데이트
            if "ctx_area_fk100" in data:
                params["CTX_AREA_FK100"] = data["ctx_area_fk100"]
            if "ctx_area_nk100" in data:
                params["CTX_AREA_NK100"] = data["ctx_area_nk100"]
            if "ctx_area_fk200" in data:
                params["CTX_AREA_FK200"] = data["ctx_area_fk200"]
            if "ctx_area_nk200" in data:
                params["CTX_AREA_NK200"] = data["ctx_area_nk200"]
            self.auth.smart_sleep()

        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  국내주식 시세
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def inquire_price(self, stock_code: str, market: str = "J") -> pd.DataFrame:
        """주식/ETF 현재가 시세 조회

        Args:
            stock_code: 종목코드 (예: "005930", "069500")
            market: J=KRX, NX=NXT, UN=통합
        """
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": market, "FID_INPUT_ISCD": stock_code},
        )

    def inquire_daily_price(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        period: str = "D",
        adj_price: str = "0",
        market: str = "J",
    ) -> pd.DataFrame:
        """일/주/월/년봉 차트 데이터 조회

        Args:
            stock_code: 종목코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: D=일, W=주, M=월, Y=년
            adj_price: 0=수정주가, 1=원주가
        """
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            "FHKST03010100",
            {
                "FID_COND_MRKT_DIV_CODE": market,
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": period,
                "FID_ORG_ADJ_PRC": adj_price,
            },
            output_key="output2",
        )

    def inquire_asking_price(self, stock_code: str, market: str = "J") -> pd.DataFrame:
        """호가 조회"""
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            "FHKST01010200",
            {"FID_COND_MRKT_DIV_CODE": market, "FID_INPUT_ISCD": stock_code},
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ETF 전용
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def etf_price(self, etf_code: str, market: str = "J") -> pd.DataFrame:
        """ETF/ETN 현재가"""
        return self.fetch_dataframe(
            "/uapi/etfetn/v1/quotations/inquire-price",
            "FHPST02400000",
            {"FID_COND_MRKT_DIV_CODE": market, "FID_INPUT_ISCD": etf_code},
        )

    def etf_components(self, etf_code: str) -> dict:
        """ETF 구성종목 시세"""
        data = self.get(
            "/uapi/etfetn/v1/quotations/inquire-component-stock-price",
            "FHKST121600C0",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": etf_code,
                "FID_COND_SCR_DIV_CODE": "11216",
            },
        )
        return {
            "summary": pd.DataFrame([data.get("output1", {})]),
            "components": pd.DataFrame(data.get("output2", [])),
        }

    def etf_nav_daily(
        self, etf_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """ETF NAV 비교추이 (일별)"""
        return self.fetch_dataframe(
            "/uapi/etfetn/v1/quotations/nav-comparison-daily-trend",
            "FHPST02440200",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": etf_code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
            },
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  주문/매매
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def order_buy(
        self, stock_code: str, qty: int, price: int = 0, order_type: str = "00"
    ) -> dict:
        """현금 매수 주문

        Args:
            stock_code: 종목코드
            qty: 매수수량
            price: 매수가격 (0이면 시장가)
            order_type: 00=지정가, 01=시장가, ...
        """
        if price == 0:
            order_type = "01"  # 시장가
        tr_id = "TTTC0012U"  # 매수
        body = {
            "CANO": self.auth.account_no,
            "ACNT_PRDT_CD": self.auth.product_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
            "EXCG_ID_DVSN_CD": "KRX",
        }
        return self.post("/uapi/domestic-stock/v1/trading/order-cash", tr_id, body)

    def order_sell(
        self, stock_code: str, qty: int, price: int = 0, order_type: str = "00"
    ) -> dict:
        """현금 매도 주문"""
        if price == 0:
            order_type = "01"
        tr_id = "TTTC0011U"  # 매도
        body = {
            "CANO": self.auth.account_no,
            "ACNT_PRDT_CD": self.auth.product_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
            "EXCG_ID_DVSN_CD": "KRX",
        }
        return self.post("/uapi/domestic-stock/v1/trading/order-cash", tr_id, body)

    def order_cancel(
        self, org_order_no: str, stock_code: str, qty: int, cancel_type: str = "02"
    ) -> dict:
        """주문 정정/취소

        Args:
            org_order_no: 원주문번호
            stock_code: 종목코드
            qty: 수량
            cancel_type: 01=정정, 02=취소
        """
        tr_id = "TTTC0013U"
        body = {
            "CANO": self.auth.account_no,
            "ACNT_PRDT_CD": self.auth.product_cd,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": org_order_no,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": cancel_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }
        return self.post("/uapi/domestic-stock/v1/trading/order-rvsecncl", tr_id, body)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  잔고/계좌
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def inquire_balance(self) -> dict:
        """주식 잔고조회 → {holdings: DataFrame, summary: DataFrame}"""
        tr_id = "TTTC8434R"
        params = {
            "CANO": self.auth.account_no,
            "ACNT_PRDT_CD": self.auth.product_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        data = self.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance", tr_id, params
        )

        holdings = pd.DataFrame(data.get("output1", []))
        summary = pd.DataFrame(data.get("output2", []))
        return {"holdings": holdings, "summary": summary}

    def inquire_psbl_order(self, stock_code: str, price: int = 0) -> pd.DataFrame:
        """매수가능 금액 조회"""
        tr_id = "TTTC8908R"
        params = {
            "CANO": self.auth.account_no,
            "ACNT_PRDT_CD": self.auth.product_cd,
            "PDNO": stock_code,
            "ORD_UNPR": str(price),
            "ORD_DVSN": "00" if price > 0 else "01",
            "CMA_EVLU_AMT_ICLD_YN": "Y",
            "OVRS_ICLD_YN": "N",
        }
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/trading/inquire-psbl-order", tr_id, params
        )

    def inquire_daily_ccld(self, start_date: str, end_date: str) -> pd.DataFrame:
        """일별 체결내역 조회"""
        tr_id = "TTTC8001R"
        params = {
            "CANO": self.auth.account_no,
            "ACNT_PRDT_CD": self.auth.product_cd,
            "INQR_STRT_DT": start_date,
            "INQR_END_DT": end_date,
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld", tr_id, params
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  투자자별 매매동향
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def inquire_investor(
        self, stock_code: str, start_date: str, end_date: str, market: str = "J"
    ) -> pd.DataFrame:
        """종목별 투자자 매매동향 (일별)

        Args:
            stock_code: 종목코드 (예: "144600")
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            market: J=KRX

        Returns:
            DataFrame with columns:
            - stck_bsop_date: 영업일자
            - frgn_ntby_qty: 외국인 순매수 수량
            - orgn_ntby_qty: 기관계 순매수 수량
            - prsn_ntby_qty: 개인 순매수 수량
        """
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            "FHKST01010900",
            {
                "FID_COND_MRKT_DIV_CODE": market,
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D",
            },
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  순위/분석
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def volume_rank(self, market: str = "J") -> pd.DataFrame:
        """거래량 순위"""
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            "FHPST01710000",
            {
                "FID_COND_MRKT_DIV_CODE": market,
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": "",
            },
        )

    def fluctuation_rank(self, market: str = "J", sort: str = "0") -> pd.DataFrame:
        """등락률 순위 (sort: 0=상승률, 1=하락률)"""
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/ranking/fluctuation",
            "FHPST01700000",
            {
                "fid_cond_mrkt_div_code": market,
                "fid_cond_scr_div_code": "20170",
                "fid_input_iscd": "0000",
                "fid_rank_sort_cls_code": sort,
                "fid_input_cnt_1": "0",
                "fid_prc_cls_code": "0",
                "fid_input_price_1": "",
                "fid_input_price_2": "",
                "fid_vol_cnt": "",
                "fid_trgt_cls_code": "0",
                "fid_trgt_exls_cls_code": "0",
                "fid_div_cls_code": "0",
                "fid_rsfl_rate1": "",
                "fid_rsfl_rate2": "",
            },
        )

    def foreign_institution_total(
        self,
        market: str = "V",
        iscd: str = "0000",
        div: str = "1",
        sort: str = "0",
        etc: str = "0",
    ) -> pd.DataFrame:
        """국내기관·외국인 매매종목 가집계 (FHPTJ04400000, HTS [0440]).

        증권사 직원이 장중 집계·입력한 단순 누계(가집계=장중 추정치, 확정 아님).
        네이티브 순매수 거래대금(frgn/orgn_ntby_tr_pbmn)을 반환한다.

        Args:
            market: 조건 시장 분류 코드 (V).
            iscd: 0000:전체, 0001:코스피, 1001:코스닥.
            div: 0:수량정렬, 1:금액정렬.
            sort: 0:순매수상위, 1:순매도상위.
            etc: 0:전체, 1:외국인, 2:기관계, 3:기타.
        """
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
            "FHPTJ04400000",
            {
                "FID_COND_MRKT_DIV_CODE": market,
                "FID_COND_SCR_DIV_CODE": "16449",
                "FID_INPUT_ISCD": iscd,
                "FID_DIV_CLS_CODE": div,
                "FID_RANK_SORT_CLS_CODE": sort,
                "FID_ETC_CLS_CODE": etc,
            },
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  업종/시장 정보
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def check_holiday(self, date: str) -> pd.DataFrame:
        """휴장일 조회 (YYYYMMDD)"""
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/chk-holiday",
            "CTCA0903R",
            {
                "BASS_DT": date,
                "CTX_AREA_NK": "",
                "CTX_AREA_FK": "",
            },
        )

    def market_time(self) -> pd.DataFrame:
        """장운영시간 조회"""
        return self.fetch_dataframe(
            "/uapi/domestic-stock/v1/quotations/market-time",
            "FHPUP02100000",
            {},
        )
