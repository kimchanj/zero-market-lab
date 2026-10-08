"""Package a synthetic, read-only GitHub Pages artifact without local market data."""

from datetime import date
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_public_demo import build  # noqa: E402


def build_site(output: Path, end: date | None = None) -> Path:
    synthetic = output / "generated"
    build(end=end, output=synthetic)
    source = ROOT / "experiments/tiger_etf_v2"
    output.mkdir(parents=True, exist_ok=True)
    stale_research = output / "research.js"
    if stale_research.exists():
        stale_research.unlink()
    html = (source / "index.html").read_text(encoding="utf-8")
    html = html.replace('../lightweight_charts/vendor/lightweight-charts.standalone.production.js',
                        'vendor/lightweight-charts.standalone.production.js')
    html = html.replace('<script src="chart.js"></script>',
                        '<script>window.ZML_STATIC_DEMO=true;</script>\n  <script src="chart.js"></script>')
    html = html.replace('<details class="workspace-section research-fold">',
                        '<details class="workspace-section research-fold" hidden>')
    html = html.replace('<a class="local-only" href="../samsung_strategy_family/">삼성전자 전략 비교</a>', '')
    html = html.replace('<a class="local-only" href="../asset_discovery/">종목 발굴</a>', '')
    html = html.replace('  <script src="research.js"></script>\n', '')
    html = html.replace('RESEARCH WORKSTATION V2', 'SYNTHETIC READ-ONLY DEMO')
    (output / "index.html").write_text(html, encoding="utf-8")
    for name in ("chart.css", "hover.js"):
        shutil.copyfile(source / name, output / name)
    chart_js = (source / "chart.js").read_text(encoding="utf-8")
    start_marker = "  async function runSimulation() {"
    end_marker = "  $('simulation-form').addEventListener"
    prefix, dynamic = chart_js.split(start_marker, 1)
    _, suffix = dynamic.split(end_marker, 1)
    chart_js = prefix + "  async function runSimulation() { return; }\n" + end_marker + suffix
    (output / "chart.js").write_text(chart_js, encoding="utf-8")
    for name in ("tiger_data.js", "simulation_data.js"):
        shutil.copyfile(synthetic / name, output / name)
    vendor = output / "vendor"
    vendor.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "experiments/lightweight_charts/vendor/lightweight-charts.standalone.production.js",
                    vendor / "lightweight-charts.standalone.production.js")
    for path in synthetic.iterdir():
        path.unlink()
    synthetic.rmdir()
    (output / ".nojekyll").touch()
    return output


if __name__ == "__main__":
    build_site(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/pages_demo")
