# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=12", "playwright==1.64.1", "pypdf>=6", "zxing-cpp>=3"]
# ///
"""Print both website handouts and make their thumbnails from the finished PDFs.

Install the frontend dependencies and Poppler (pdftoppm). Once per machine, run
`uvx --from playwright==1.64.1 playwright install chromium`. Rebuild with
`uv run scripts/resources/build_handout.py` from the repository root.
"""
import os
from io import BytesIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
import zxingcpp

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
RESOURCES = FRONTEND / "public" / "resources"
REGISTER = "https://goldenplate.ca/getting-started"


def verify_page(pdf):
    reader = PdfReader(pdf)
    if len(reader.pages) != 1:
        raise ValueError(f"{pdf.name} has {len(reader.pages)} pages; expected one.")
    page = reader.pages[0]
    if (page.mediabox.width, page.mediabox.height) != (612, 792):
        raise ValueError(f"{pdf.name} must be US Letter.")
    words = " ".join(page.extract_text().split())
    if "Golden Plate" not in words or "goldenplate.ca/getting-started" not in words:
        raise ValueError(f"Missing searchable school or registration text in {pdf.name}.")
    links = [annotation.get_object().get("/A", {}).get("/URI") for annotation in page.get("/Annots", [])]
    if REGISTER not in links:
        raise ValueError(f"Missing registration link in {pdf.name}.")
    fonts = page["/Resources"]["/Font"]
    for font_reference in fonts.values():
        font = font_reference.get_object()
        for face in font.get("/DescendantFonts", [font]):
            descriptor = face.get_object().get("/FontDescriptor")
            if not descriptor or not any(key in descriptor.get_object() for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                raise ValueError(f"Font {font.get('/BaseFont')} isn't embedded in {pdf.name}.")


def print_handout(page, base, theme, folder):
    stem = "golden-plate-school-overview" + ("-dark" if theme == "dark" else "")
    pdf = folder / f"{stem}.pdf"
    page.emulate_media(media="print", color_scheme=theme)
    page.goto(f"{base}/print/school-overview/index.html?theme={theme}")
    page.locator("[data-print-ready=true] .school-handout").wait_for()
    page.pdf(path=pdf, format="Letter", prefer_css_page_size=True, print_background=True, tagged=True)
    verify_page(pdf)

    raster = folder / f"{stem}-page"
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-r", "144", "-png", pdf, raster], check=True)
    with Image.open(raster.with_suffix(".png")) as image:
        codes = zxingcpp.read_barcodes(image)
        if not any(code.text == REGISTER for code in codes):
            raise ValueError(f"Couldn't scan the registration QR from {pdf.name}.")
        image.resize((700, 906), Image.Resampling.LANCZOS).save(folder / f"{stem}.webp", quality=88, method=6)
    return [pdf, folder / f"{stem}.webp"]


def main():
    # Stage both themes on the same filesystem as the public files. Publish only
    # after validation succeeds for every PDF and thumbnail.
    with TemporaryDirectory(prefix=".handout-", dir=FRONTEND) as tmp:
        folder = Path(tmp)
        server = subprocess.Popen(
            ["node", FRONTEND / "print/serve-handout.mjs", folder],
            stdout=subprocess.PIPE, text=True,
        )
        try:
            origin = server.stdout.readline().strip()
            if not origin.startswith("http://127.0.0.1:"):
                raise RuntimeError("The handout print server could not start.")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 816, "height": 1056})
                def local_assets(route):
                    if urlsplit(route.request.url).netloc == urlsplit(origin).netloc:
                        route.continue_()
                    else:
                        route.abort()

                page.route("**/*", local_assets)
                # Chromium embeds a decoded WebP photo losslessly in the PDF.
                # Feed it a full-resolution JPEG it can embed directly.
                photo = "/images/initiative/compost-coaches.webp"
                stream = BytesIO()
                with Image.open(FRONTEND / "public" / photo.lstrip("/")) as image:
                    image.convert("RGB").save(stream, "JPEG", quality=92, optimize=True)
                page.route(origin + photo, lambda route: route.fulfill(content_type="image/jpeg", body=stream.getvalue()))
                outputs = []
                for theme in ("light", "dark"):
                    outputs.extend(print_handout(page, origin, theme, folder))
                browser.close()
            for source in outputs:
                os.replace(source, RESOURCES / source.name)
                print((RESOURCES / source.name).relative_to(ROOT))
        finally:
            server.terminate()
            server.wait()


if __name__ == "__main__":
    main()
