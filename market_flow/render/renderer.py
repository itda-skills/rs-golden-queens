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
    width: int = 720,
    height: int = 1600,
    output_path: Optional[str] = None,
    trim_bg: Optional[tuple] = (15, 17, 21),
    trim_padding: int = 24,
) -> bytes:
    """HTML → PNG bytes.

    - viewport: ``width × height`` 로 캡처 (height 는 콘텐츠 최대 추정치)
    - trim_bg 지정 시 하단 배경색 영역을 자동 trim (padding 만큼 여백 보존)
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
        data = _trim_bottom(data, bg_color=trim_bg, padding=trim_padding)

    if output_path:
        Path(output_path).write_bytes(data)
    return data


def _trim_bottom(png_bytes: bytes, bg_color: tuple, padding: int, tol: int = 6) -> bytes:
    """이미지 하단의 배경색 영역을 잘라낸다. tol 만큼 색상 오차 허용."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    px = img.load()
    last_y = 0
    for y in range(h - 1, -1, -1):
        for x in range(0, w, 4):  # 샘플링 (속도)
            r, g, b = px[x, y]
            if (abs(r - bg_color[0]) > tol or
                abs(g - bg_color[1]) > tol or
                abs(b - bg_color[2]) > tol):
                last_y = y
                break
        if last_y:
            break
    if not last_y:
        return png_bytes
    new_h = min(h, last_y + padding)
    cropped = img.crop((0, 0, w, new_h))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
