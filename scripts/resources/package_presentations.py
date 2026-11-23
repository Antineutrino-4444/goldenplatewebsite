"""Prepare static website downloads from the editable presentation drafts."""

import argparse
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData


def prepare_template(source, target):
    deck = Presentation(source)
    chart, = (shape.chart for slide in deck.slides for shape in slide.shapes if shape.has_chart)
    # The authoring library writes literal chart data. Embed the same cells so
    # PowerPoint's Edit Data command can open the chart's workbook offline.
    data = CategoryChartData()
    data.categories = [str(category) for category in chart.plots[0].categories]
    for series in chart.series:
        name = series._element.xpath("c:tx/c:v")[0].text
        data.add_series(name, series.values)
    chart.replace_data(data)
    deck.save(target)


def package(source, destination):
    with TemporaryDirectory(prefix="golden-plate-preview-") as tmp:
        work = Path(tmp)
        decks = []
        for draft in sorted(source.glob("*.pptx")):
            target = work / draft.name
            if draft.stem.startswith("presentation-template-"):
                prepare_template(draft, target)
            else:
                shutil.copyfile(draft, target)
            decks.append(target)

        profile = (work / "office").as_uri()
        subprocess.run(["soffice", f"-env:UserInstallation={profile}", "--headless",
                        "--convert-to", "pdf", "--outdir", work, *decks], check=True)
        artifacts = []
        for deck in decks:
            pdf = deck.with_suffix(".pdf")
            thumbnail = work / f"{deck.stem}-cover"
            subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile",
                            "-scale-to", "1040", "-png", pdf, thumbnail], check=True)
            cover = thumbnail.with_suffix(".webp")
            with Image.open(thumbnail.with_suffix(".png")) as image:
                image.save(cover, quality=88, method=6)
            artifacts.extend([deck, pdf, cover])

        destination.mkdir(parents=True, exist_ok=True)
        for artifact in artifacts:
            shutil.copyfile(artifact, destination / artifact.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    package(args.source, args.destination)
