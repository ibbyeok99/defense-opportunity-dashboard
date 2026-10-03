"""서버 내부 한국어 OCR. 원본·이미지를 외부 서비스에 보내거나 디스크에 저장하지 않는다."""
import csv
import os
import re
import shutil
import subprocess
from io import BytesIO, StringIO
from pathlib import Path

MAX_PIXELS = 12_000_000
MAX_OCR_PAGES = 10


def ocr_command():
    local = Path(__file__).resolve().parents[2] / ".ocr-runtime"
    command = os.environ.get("FRONTLINE_TESSERACT") or shutil.which("tesseract")
    if not command and (local / "Library/bin/tesseract.exe").is_file():
        command = str(local / "Library/bin/tesseract.exe")
    if not command:
        raise ValueError("한국어 OCR 엔진 없음·원문 수동 확인 필요")
    tessdata = os.environ.get("FRONTLINE_TESSDATA")
    bundled = Path(__file__).resolve().parents[1] / "assets/ocr"
    if not tessdata and (bundled / "kor.traineddata").is_file():
        tessdata = str(bundled)
    elif not tessdata and (local / "share/tessdata/kor.traineddata").is_file():
        tessdata = str(local / "share/tessdata")
    return command, tessdata


def recognize(image, timeout=12):
    if image.width * image.height > MAX_PIXELS:
        raise ValueError("OCR 이미지 크기 한도 초과")
    command, tessdata = ocr_command()
    # 한국어 공고에서 영문 모델이 한글을 영문으로 오인하는 것을 줄인다. 숫자는 kor도 인식한다.
    args = [command, "stdin", "stdout", "-l", "kor", "--oem", "1", "--psm", "6"]
    if tessdata:
        args.extend(["--tessdata-dir", tessdata])
    # 일부 배포 패키지는 tsv 설정 파일을 포함하지 않는다. 출력 변수를 직접 지정한다.
    args.extend(["-c", "tessedit_create_tsv=1"])
    payload = BytesIO()
    image.convert("RGB").save(payload, format="PNG")
    response = subprocess.run(args, input=payload.getvalue(), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=timeout, check=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                              env=dict(os.environ, OMP_THREAD_LIMIT="1"))
    lines, words = {}, []
    for row in csv.DictReader(StringIO(response.stdout.decode("utf-8")), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        key = tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num"))
        word = {"text": row["text"], "confidence": float(row["conf"]),
                "box": [int(row[k]) for k in ("left", "top", "width", "height")]}
        lines.setdefault(key, []).append(word)
        words.append(word)
    if not words:
        raise ValueError("OCR 인식 텍스트 없음·원문 수동 확인 필요")
    return {"text": "\n".join(_line_text(v) for v in lines.values()), "words": words,
            "mean_confidence": round(sum(w['confidence'] for w in words) / len(words), 1) if words else 0,
            "low_confidence_words": sum(w['confidence'] < 80 for w in words),
            "image_size": [image.width, image.height], "requires_review": True}


def _line_text(words):
    """TSV가 한글 음절을 나눠 반환해도 실제 글자 간격만 복원한다. 글자를 교정하지 않는다."""
    result, previous = "", None
    for word in words:
        separator = " " if previous else ""
        if previous:
            left, _, width, height = previous['box']
            gap = word['box'][0] - left - width
            korean_boundary = re.search(r"[가-힣]$", previous['text']) or re.match(r"[가-힣]", word['text'])
            if korean_boundary and gap <= .55 * max(height, word['box'][3]):
                separator = ""
        result += separator + word['text']
        previous = word
    return result


def render_page(blob, index):
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(blob) as document:
        page = document[index]
        width, height = page.get_size()
        scale = 2.5
        if width * height * scale * scale > MAX_PIXELS:
            page.close()
            raise ValueError("OCR 페이지 이미지 크기 한도 초과")
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil().copy()
        bitmap.close()
        page.close()
        return image
