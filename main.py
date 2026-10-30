
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------
# 1. 기본 화면 설정
# --------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.write("KOBIS 공식 API를 통해 어제의 영화 관객 현황을 확인합니다.")


# --------------------------------
# 2. 한국 시간 기준 어제 날짜 계산
# --------------------------------

# 서버의 시간대와 관계없이 한국 시간을 사용합니다.
korea_time = datetime.now(ZoneInfo("Asia/Seoul"))

# 한국 시간 기준 하루 전 날짜를 계산합니다.
yesterday = korea_time.date() - timedelta(days=1)

# API에서 요구하는 YYYYMMDD 형식으로 변환합니다.
target_date = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜 형식입니다.
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------
# 3. API 데이터 가져오기
# --------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/"
    "webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# 숫자로 변환하는 함수입니다.
def convert_number(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


# API 요청 결과를 1시간 동안 캐싱합니다.
# 같은 날짜와 인증키로 다시 요청하면 저장된 결과를 사용합니다.
@st.cache_data(ttl=3600, show_spinner=False)
def get_boxoffice_data(api_key, target_dt):

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    # API에 요청을 보냅니다.
    response = requests.get(
        API_URL,
        params=params,
        timeout=15
    )

    # HTTP 요청이 실패하면 오류를 발생시킵니다.
    response.raise_for_status()

    # JSON 형식으로 응답을 읽습니다.
    data = response.json()

    # 인증키 오류 등의 API 오류를 확인합니다.
    if "faultInfo" in data:
        fault = data["faultInfo"]

        if isinstance(fault, dict):
            message = fault.get("message", "상세 오류 정보 없음")
            error_code = fault.get("errorCode", "코드 없음")
            raise ValueError(
                f"KOBIS API 오류 ({error_code}): {message}"
            )

        raise ValueError(f"KOBIS API 오류: {fault}")

    # 정상적인 응답 구조인지 확인합니다.
    if "boxOfficeResult" not in data:
        raise ValueError(
            "응답에 boxOfficeResult가 없습니다. "
            "API 응답 구조를 확인해 주세요."
        )

    movie_list = data["boxOfficeResult"].get(
        "dailyBoxOfficeList", []
    )

    # 영화 목록이 비어 있는 경우입니다.
    if not movie_list:
        return []

    return movie_list


# --------------------------------
# 4. API 인증키 불러오기 및 오류 처리
# --------------------------------

try:
    # Streamlit Cloud의 Secrets에서 인증키를 불러옵니다.
    api_key = st.secrets["KOBIS_KEY"]

    if not api_key:
        st.error(
            "인증키가 비어 있습니다. "
            "Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해 주세요."
        )
        st.stop()

except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 Settings → Secrets에서 "
        "인증키를 등록했는지 확인해 주세요."
    )
    st.stop()

except Exception as e:
    st.error(f"Secrets 설정을 확인해 주세요. 오류 내용: {e}")
    st.stop()


# --------------------------------
# 5. 영화 데이터 조회
# --------------------------------

st.subheader(f"📅 조회 날짜: {display_date}")

try:
    with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
        movie_list = get_boxoffice_data(api_key, target_date)

except requests.exceptions.Timeout:
    st.error(
        "API 요청 시간이 초과되었습니다. "
        "인터넷 연결이나 KOBIS 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        "API 서버에 연결하지 못했습니다. "
        "인터넷 연결과 KOBIS API 주소를 확인해 주세요.\n\n"
        f"오류 내용: {e}"
    )
    st.stop()

except ValueError as e:
    st.error(
        "박스오피스 데이터를 가져오는 과정에서 오류가 발생했습니다.\n\n"
        f"{e}\n\n"
        "인증키와 API 응답 내용을 확인해 주세요."
    )
    st.stop()

except Exception as e:
    st.error(
        f"예상하지 못한 오류가 발생했습니다: {e}"
    )
    st.stop()


# --------------------------------
# 6. 영화 데이터 정리
# --------------------------------

if not movie_list:
    st.warning(
        "해당 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
        "조회 날짜, KOBIS API 응답 및 집계 여부를 확인해 주세요."
    )
    st.stop()


# API에서 받은 데이터를 표에 사용할 형태로 변환합니다.
movie_data = []

for movie in movie_list:

    movie_data.append({
        "순위": convert_number(movie.get("rank")),
        "영화명": movie.get("movieNm", "정보 없음"),
        "개봉일": movie.get("openDt", "정보 없음"),
        "관객수": convert_number(movie.get("audiCnt")),
        "누적관객": convert_number(movie.get("audiAcc")),
        "스크린수": convert_number(movie.get("scrnCnt"))
    })


# 데이터프레임으로 변환합니다.
df = pd.DataFrame(movie_data)

# 순위를 기준으로 오름차순 정렬합니다.
df = df.sort_values(by="순위", ascending=True)


# --------------------------------
# 7. 1위 영화 지표 카드 3개
# --------------------------------

first_movie = df.iloc[0]

st.divider()
st.header("🏆 오늘의 박스오피스 1위")

st.subheader(first_movie["영화명"])

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="일일 관객수",
        value=f'{first_movie["관객수"]:,}명'
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f'{first_movie["누적관객"]:,}명'
    )

with col3:
    st.metric(
        label="스크린 수",
        value=f'{first_movie["스크린수"]:,}개'
    )


# --------------------------------
# 8. 전체 박스오피스 순위 표
# --------------------------------

st.divider()
st.header("📊 전체 박스오피스 순위")

st.caption(
    f"{display_date} 기준 영화별 관객 및 상영 현황입니다."
)

# 천 단위 쉼표가 표시되도록 숫자 형식을 지정합니다.
st.dataframe(
    df.style.format({
        "관객수": "{:,}",
        "누적관객": "{:,}",
        "스크린수": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)


# --------------------------------
# 9. 관객수 상위 5개 영화 막대그래프
# --------------------------------

st.divider()
st.header("📈 관객수 상위 5개 영화")

# 관객수가 많은 순서대로 5개 영화를 선택합니다.
top5 = df.sort_values(
    by="관객수",
    ascending=False
).head(5)

# 그래프에서는 관객수가 많은 영화가 위에 표시되도록 정렬합니다.
chart_data = top5.sort_values(
    by="관객수",
    ascending=True
).set_index("영화명")[["관객수"]]

st.bar_chart(
    chart_data,
    horizontal=True,
    x_label="영화명",
    y_label="관객수 (명)"
)

st.caption(
    "※ 관객수는 해당 날짜의 일일 관객수이며, "
    "누적 관객수가 아닙니다."
)


# --------------------------------
# 10. 데이터 출처 및 안내
# --------------------------------

st.divider()

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 공식 API"
)

st.caption(
    "조회 기준: 한국 시간(Asia/Seoul) 기준 전날"
)

st.caption(
    "데이터는 조회 후 약 1시간 동안 캐싱됩니다."
)

