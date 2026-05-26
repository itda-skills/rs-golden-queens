"""HTML 문자열 → PNG bytes 변환.

GitHub Actions ubuntu-latest 의 사전 설치된 Chrome 또는 macOS 의 시스템 Chrome 을
``html2image`` 가 자동 탐색한다. 별도 브라우저 설치 단계 불필요.
"""
from __future__ import annotations

import io
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from html2image import Html2Image
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(name: str, context: dict) -> str:
    """Jinja2 템플릿 렌더 → HTML 문자열."""
    template = _env.get_template(name)
    return template.render(**context)


def html_to_png(
    html: str,
    width: int = 1400,
    height: int = 4800,
    output_path: Optional[str] = None,
    trim_bg: Optional[tuple] = (15, 17, 21),
    trim_padding: int = 0,
) -> bytes:
    """HTML → PNG bytes.

    body 는 ``display: inline-block`` 으로 콘텐츠 자연 폭/높이를 가지므로,
    viewport(``width × height``) 는 충분히 크게 잡고 trim 으로 정확히 잘라낸다.

    - trim_bg 지정 시 4방향 배경색 영역을 자동 trim
    - trim_padding 만큼 외곽 여백 보존 (body padding 외에 추가 여백)
    - output_path 지정 시 해당 경로에도 동시 저장
    """
    with tempfile.TemporaryDirectory() as td:
        hti = Html2Image(
            output_path=td,
            size=(width, height),
            custom_flags=[
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
            ],
        )
        filename = f"out-{uuid.uuid4().hex}.png"
        hti.screenshot(html_str=html, save_as=filename)
        png_path = os.path.join(td, filename)
        with open(png_path, "rb") as f:
            data = f.read()

    if trim_bg is not None:
        data = _trim_borders(data, bg_color=trim_bg, padding=trim_padding)

    if output_path:
        Path(output_path).write_bytes(data)
    return data


def _trim_borders(png_bytes: bytes, bg_color: tuple, padding: int = 0, tol: int = 6) -> bytes:
    """이미지의 4방향 배경색 영역을 모두 잘라낸다.

    tol 만큼 색상 오차 허용. 콘텐츠 박스 외곽에 padding 만큼 여백 보존.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    px = img.load()

    def is_bg(x, y):
        r, g, b = px[x, y]
        return (abs(r - bg_color[0]) <= tol and
                abs(g - bg_color[1]) <= tol and
                abs(b - bg_color[2]) <= tol)

    # 상하좌우 배경색 영역의 경계 찾기 (샘플링 4픽셀 간격)
    step = 4
    top = h
    for y in range(h):
        if any(not is_bg(x, y) for x in range(0, w, step)):
            top = y
            break
    bottom = 0
    for y in range(h - 1, -1, -1):
        if any(not is_bg(x, y) for x in range(0, w, step)):
            bottom = y
            break
    left = w
    for x in range(w):
        if any(not is_bg(x, y) for y in range(0, h, step)):
            left = x
            break
    right = 0
    for x in range(w - 1, -1, -1):
        if any(not is_bg(x, y) for y in range(0, h, step)):
            right = x
            break

    if bottom <= top or right <= left:
        return png_bytes  # 콘텐츠 없음 → 원본 반환

    box = (
        max(0, left - padding),
        max(0, top - padding),
        min(w, right + 1 + padding),
        min(h, bottom + 1 + padding),
    )
    cropped = img.crop(box)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
