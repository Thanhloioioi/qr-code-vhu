import streamlit as st
import qrcode
import requests
import re
import zipfile
import unicodedata

from io import BytesIO
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="VHU Book QR Generator",
    page_icon="📚",
    layout="wide"
)

BASE_URL = (
    "https://lib.vhu.edu.vn/Portal/"
    "BookDetail?bibid="
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
}

st.title("📚 VHU Book QR Generator")

st.write("Công cụ tạo mã QR cho thông tin sách "
    "tại thư viện Trường Đại học Văn Hiến."
)

st.divider()

@st.cache_data(ttl=3600, show_spinner=False)
def get_book_name(bibid):

    url = BASE_URL + bibid

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )
        candidates = []
        for selector in [
            'meta[property="og:title"]',
            'meta[name="twitter:title"]'
        ]:

            tag = soup.select_one(selector)

            if tag and tag.get("content"):
                candidates.append(tag["content"])
        if soup.title and soup.title.string:
            candidates.append(soup.title.string)
        for selector in [
            "h1",
            ".book-title",
            ".title",
            "h2"
        ]:

            tag = soup.select_one(selector)

            if tag:
                candidates.append(tag.get_text(" ", strip=True))

        for name in candidates:
            name = re.sub(
                r"\s+",
                " ",
                str(name)
            ).strip()

            name = re.split(
                r"\s+[|–—-]\s+",
                name
            )[0].strip()

            if (
                    name
                    and len(name) >= 3
                    and "Trường Đại học Văn Hiến" not in name
                    and "Trung tâm Học liệu" not in name
                    and "Đang tải dữ liệu" not in name
            ):
                return name


        return None

    except requests.RequestException:
        return None

def create_qr(bibid):

    url = BASE_URL + bibid

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )

    qr.add_data(url)

    qr.make(fit=True)

    img = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = BytesIO()

    img.save(buffer, format="PNG")

    return url, buffer.getvalue()

def safe_filename(name):

    name = str(name).strip()

    name = unicodedata.normalize(
        "NFKD",
        name
    )

    name = "".join(
        c for c in name
        if not unicodedata.combining(c)
    )

    name = name.replace("đ", "d")
    name = name.replace("Đ", "D")

    name = re.sub(
        r"[^a-zA-Z0-9]+",
        "",
        name
    )

    return name.strip("")[:200] or "Khong_ten"

def process_codes(raw_codes):

    valid_codes = []
    invalid_codes = []

    seen = set()

    for value in raw_codes:

        code = str(value).strip()

        if not re.fullmatch(r"\d+", code):

            invalid_codes.append(code)

            continue

        if code in seen:
            continue

        seen.add(code)

        valid_codes.append(code)

    return valid_codes, invalid_codes

if "qr_results" not in st.session_state:
    st.session_state.qr_results = []

if "invalid_codes" not in st.session_state:
    st.session_state.invalid_codes = []

if "failed_codes" not in st.session_state:
    st.session_state.failed_codes = []

st.subheader("1. Chọn phương thức tạo QR")

mode = st.radio(
    "Chế độ:",
    [
        "Tạo một mã",
        "Tạo nhiều mã"
    ],
    horizontal=True
)
if mode == "Tạo một mã":

    bibid_input = st.text_input(
        "Nhập mã sách:",
        placeholder="Ví dụ: 17869"
    )

    if st.button(
        "TẠO QR CODE",
        type="primary",
        use_container_width=True
    ):

        code = bibid_input.strip()

        if not re.fullmatch(r"\d+", code):

            st.error("Vui lòng nhập mã sách hợp lệ!")

        else:

            with st.spinner("Đang lấy thông tin sách..."):

                book_name = get_book_name(code)

            if not book_name:

                st.error(
                    "Không lấy được tên sách từ thư viện. "
                    "Bạn hãy kiểm tra mã sách hoặc thử lại sau."
                )

            else:

                url, qr_image = create_qr(code)

                st.session_state.qr_results = [
                    {
                        "bibid": code,
                        "name": book_name,
                        "url": url,
                        "image": qr_image
                    }
                ]

                st.session_state.invalid_codes = []
                st.session_state.failed_codes = []

                st.success("Đã tạo QR Code thành công!")

else:

    st.write(
        "Nhập danh sách mã sách. "
        "Mỗi mã sách nằm trên một dòng."
    )

    codes_input = st.text_area(
        "Danh sách mã sách:",
        placeholder=(
            "17869\n"
            "17870\n"
            "17871\n"
            "17872\n"
            "17873"
        ),
        height=200
    )

    if st.button(
        " TẠO HÀNG LOẠT QR CODE",
        type="primary",
        use_container_width=True
    ):

        raw_codes = codes_input.splitlines()

        valid_codes, invalid_codes = process_codes(
            raw_codes
        )

        if not raw_codes or not any(
            code.strip() for code in raw_codes
        ):

            st.warning("Vui lòng nhập mã sách!")

        elif not valid_codes:

            st.error("Không có mã sách hợp lệ!")

        else:

            results = []
            failed_codes = []

            progress = st.progress(0)

            status = st.empty()

            total = len(valid_codes)

            for index, code in enumerate(valid_codes):

                status.write(
                    f"Đang xử lý sách {index + 1}/{total}: {code}"
                )

                book_name = get_book_name(code)

                if not book_name:
                    failed_codes.append(code)

                    progress.progress(
                        (index + 1) / total
                    )

                    continue

                url, qr_image = create_qr(code)

                results.append({

                    "bibid": code,

                    "name": book_name,

                    "url": url,

                    "image": qr_image

                })

                progress.progress(
                    (index + 1) / total
                )

            st.session_state.qr_results = results

            st.session_state.invalid_codes = invalid_codes

            st.session_state.failed_codes = failed_codes

            status.success("Đã xử lý xong danh sách sách!")


results = st.session_state.qr_results

invalid_codes = st.session_state.invalid_codes

failed_codes = st.session_state.failed_codes

if results:

    st.divider()

    st.subheader("2. Kết quả tạo QR Code")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "QR Code thành công",
        len(results)
    )

    col2.metric(
        "Mã không hợp lệ",
        len(invalid_codes)
    )

    col3.metric(
        "Không lấy được tên sách",
        len(failed_codes)
    )

    if invalid_codes:

        with st.expander("⚠️ Mã sách không hợp lệ"):

            st.write(invalid_codes)

    if failed_codes:

        with st.expander("⚠️ Không lấy được tên sách"):

            st.write(failed_codes)

            st.caption(
                "Các mã này chưa được đưa vào file ZIP. "
                "Bạn có thể thử lại sau."
            )

    zip_buffer = BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for item in results:
            filename = safe_filename(
                item["name"]
            )

            file_name = (
                f"{item['bibid']}_{filename}.png"
            )

            zip_file.writestr(
                file_name,
                item["image"]
            )

    st.subheader("3. Tải QR Code")

    st.download_button(

        label="📦 TẢI TẤT CẢ QR CODE (ZIP)",

        data=zip_buffer.getvalue(),

        file_name="VHU_Book_QR.zip",

        mime="application/zip",

        use_container_width=True

    )

    st.divider()

    st.subheader("4. Danh sách QR Code")

    for start in range(0, len(results), 3):

        cols = st.columns(3)

        for j, col in enumerate(cols):

            index = start + j

            if index >= len(results):
                break

            item = results[index]

            with col:

                st.markdown(
                    f"📖 {item['name']}"
                )

                st.caption(
                    f"Mã sách: {item['bibid']}"
                )

                st.image(
                    item["image"],
                    width=220
                )

                filename = safe_filename(
                    item["name"]
                )

                st.download_button(

                    label="⬇️ Tải QR Code",

                    data=item["image"],

                    file_name=(
                        f"{item['bibid']}{filename}.png"
                    ),

                    mime="image/png",

                    key=f"download_{index}"

                )

                st.caption(item["url"])

                st.divider()

st.markdown(
    """
    <div style="text-align:center; color:gray;">
        VHU Book QR Generator
        <br>
        Công cụ tạo mã QR thông tin sách
        <br>
        © Van Hien University
    </div>
    """,
    unsafe_allow_html=True
)