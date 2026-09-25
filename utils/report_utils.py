"""Builds a single self-contained HTML report: screenshots and failure logs
are embedded as data URIs / inline text, so the file works standalone and
can be emailed, copied, or published as-is.

Screenshots are downscaled/re-encoded as JPEG before embedding - the raw
PNGs on disk are full-page captures (200-350KB each) and a run with
hundreds of step-evidence shots would otherwise produce a multi-hundred-MB
HTML file. Full-resolution PNGs remain untouched on disk under
screenshots/; only the inlined report copy is compressed."""
import base64
import html
import io
import json
from pathlib import Path

from PIL import Image

from config.settings import PROJECT_ROOT, LOGS_DIR

CARD_RESULT_CLASS = {"PASS": "pass", "FAIL": "fail", "BLOCKED": "blocked"}


def _b64_image(rel_path: str, max_width: int = 900, quality: int = 60) -> str:
    full = PROJECT_ROOT / rel_path
    if not full.exists():
        return ""
    try:
        with Image.open(full) as img:
            img = img.convert("RGB")
            if img.width > max_width:
                new_height = round(img.height * (max_width / img.width))
                img = img.resize((max_width, new_height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{data}"
    except Exception:
        # Fall back to the raw file if it isn't a decodable image for any reason.
        data = base64.b64encode(full.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"


def _failure_log_text(feature: str, case_id: str) -> str:
    log_path = LOGS_DIR / feature / f"{case_id}_failure.log"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")
    return ""


def _assertions_html(assertions) -> str:
    if not assertions:
        return "<p class='muted'>No recorded assertions.</p>"
    items = []
    for a in assertions:
        mark = "check" if a["passed"] else "cross"
        items.append(
            f"<li class='{mark}'><span class='sym'>{'✓' if a['passed'] else '✗'}</span> "
            f"{html.escape(a['text'])}"
            + (f"<div class='ae'><b>Expected:</b> {html.escape(a['expected'])}<br>"
               f"<b>Actual:</b> {html.escape(a['actual'])}</div>" if not a["passed"] else "")
            + "</li>"
        )
    return "<ul class='assertions'>" + "".join(items) + "</ul>"


_KIND_LABEL = {"click": "Click", "type": "Type", "verify": "Verify", "check": "Assert", "navigate": "Navigate"}


def _execution_log_html(case: dict) -> str:
    """A per-case, chronological transcript reconstructed from the case's
    own recorded evidence (every click/fill/verify/check) and assertions -
    shown for every case, pass or fail, not just failures."""
    lines = []
    for e in case.get("evidence") or []:
        kind_label = _KIND_LABEL.get(e.get("kind", ""), str(e.get("kind", "")).title())
        lines.append(f"[STEP {e.get('n')}] {kind_label}: {e.get('label', '')}")
    assertions = case.get("assertions") or []
    if assertions:
        if lines:
            lines.append("")
        lines.append("-- Assertions --")
        for a in assertions:
            mark = "PASS" if a["passed"] else "FAIL"
            lines.append(f"[{mark}] {a['text']}")
            if not a["passed"]:
                lines.append(f"    Expected: {a['expected']}")
                lines.append(f"    Actual:   {a['actual']}")
    if not lines:
        return ""
    text = "\n".join(lines)
    return f"<div><b>Execution Log</b><pre class='exec-log'>{html.escape(text)}</pre></div>"


def _evidence_gallery_html(case: dict) -> str:
    """Renders the step-by-step screenshot gallery: one labeled, highlighted
    screenshot per click/fill/verify_visible/check(locator=...) call, so the
    red highlight from every step - not just the final state - is visible
    in the saved evidence."""
    evidence = case.get("evidence") or []
    figures = []
    for e in evidence:
        img = _b64_image(e.get("screenshot", ""), max_width=420, quality=50)
        if not img:
            continue
        kind_label = _KIND_LABEL.get(e.get("kind", ""), str(e.get("kind", "")).title())
        caption = f"Step {e.get('n')} &mdash; {kind_label}: {html.escape(str(e.get('label', '')))}"
        figures.append(
            f"<figure class='evidence-shot'><img src='{img}' alt='{html.escape(caption)}' "
            f"loading='lazy'/><figcaption>{caption}</figcaption></figure>"
        )
    if not figures:
        return ""
    return (f"<div><b>Step-by-Step Evidence ({len(figures)})</b>"
            f"<div class='evidence-gallery'>{''.join(figures)}</div></div>")


def _case_card(case: dict) -> str:
    result = case["result"]
    css = CARD_RESULT_CLASS.get(result, "")
    img = _b64_image(case.get("screenshot", ""))
    img_html = f"<img src='{img}' alt='{case['id']} screenshot'/>" if img else "<p class='muted'>No screenshot.</p>"
    failure_log = _failure_log_text(case["feature"], case["id"]) if result != "PASS" else ""
    failure_html = f"<pre class='failure-log'>{html.escape(failure_log)}</pre>" if failure_log else ""
    evidence_html = _evidence_gallery_html(case)
    exec_log_html = _execution_log_html(case)
    search_blob = html.escape(f"{case['id']} {case['title']} {case['feature']}".lower())

    return f"""
<div class="case {css}" data-feature="{html.escape(case['feature'])}" data-result="{result}" data-search="{search_blob}">
  <button class="case-head" onclick="this.parentElement.classList.toggle('open')">
    <span class="badge {css}">{result}</span>
    <span class="case-id">{html.escape(case['id'])}</span>
    <span class="case-title">{html.escape(case['title'])}</span>
    <span class="chev">&#9662;</span>
  </button>
  <div class="case-body">
    <div class="grid">
      <div><b>Description</b><p>{html.escape(case.get('description',''))}</p></div>
      <div><b>Precondition</b><p>{html.escape(case.get('precondition',''))}</p></div>
      <div><b>Test Data</b><p>{html.escape(case.get('test_data','')) or '-'}</p></div>
      <div><b>Steps</b><p style="white-space:pre-line">{html.escape(case.get('steps',''))}</p></div>
      <div><b>Expected Result</b><p>{html.escape(case.get('expected',''))}</p></div>
      <div><b>Actual Result</b><p>{html.escape(case.get('actual',''))}</p></div>
    </div>
    <div><b>Assertions</b>{_assertions_html(case.get('assertions', []))}</div>
    {f"<div><b>Failure Diagnostics</b>{failure_html}</div>" if failure_html else ""}
    {exec_log_html}
    {evidence_html}
    <div><b>Final State Screenshot</b><div class="shot">{img_html}</div></div>
  </div>
</div>
"""


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
  :root {{
    --bg:#f1f5f9; --card:#ffffff; --ink:#0f172a; --muted:#64748b;
    --pass:#16a34a; --pass-soft:#dcfce7; --fail:#dc2626; --fail-soft:#fee2e2;
    --blocked:#d97706; --blocked-soft:#fef3c7;
    --brand:#4338ca; --brand2:#6d28d9; --border:#e2e8f0;
    --shadow:0 1px 2px rgba(15,23,42,.04), 0 8px 24px -12px rgba(15,23,42,.12);
    --shadow-hover:0 4px 10px rgba(15,23,42,.06), 0 16px 32px -14px rgba(15,23,42,.18);
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  @keyframes fadeUp {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
  @keyframes fillBar {{ from {{ width:0; }} }}
  header {{
    background:linear-gradient(135deg,#1e1b4b,var(--brand) 45%,var(--brand2));
    color:#fff; padding:36px 32px 30px; animation:fadeUp .5s ease both;
    box-shadow:0 12px 28px -16px rgba(67,56,202,.55);
  }}
  header .inner {{ max-width:1120px; margin:0 auto; }}
  header h1 {{ margin:0 0 6px; font-size:23px; font-weight:700; letter-spacing:-.01em; }}
  header .sub {{ opacity:.82; font-size:13px; }}
  .stats {{ display:flex; gap:12px; margin-top:20px; flex-wrap:wrap; }}
  .stat {{
    background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.14);
    border-radius:12px; padding:12px 20px; min-width:108px;
    backdrop-filter:blur(6px); transition:transform .2s ease, background .2s ease;
  }}
  .stat:hover {{ transform:translateY(-2px); background:rgba(255,255,255,.16); }}
  .stat .n {{ font-size:25px; font-weight:700; line-height:1.1; }}
  .stat .l {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; opacity:.78; margin-top:2px; }}
  .wrap {{ max-width:1120px; margin:0 auto; padding:26px 20px 60px; }}

  .deploy-banner {{
    display:flex; align-items:center; justify-content:space-between; gap:20px;
    background:var(--card); border:1px solid var(--border); border-radius:14px;
    padding:18px 24px; margin:-46px 0 22px; box-shadow:var(--shadow-hover);
    animation:fadeUp .5s .05s ease both; flex-wrap:wrap;
  }}
  .deploy-banner.ok {{ border-left:5px solid var(--pass); }}
  .deploy-banner.blocked {{ border-left:5px solid var(--fail); }}
  .deploy-left {{ display:flex; align-items:center; gap:14px; }}
  .deploy-icon {{
    width:42px; height:42px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; font-size:20px; font-weight:700; color:#fff; flex-shrink:0;
  }}
  .deploy-icon.ok {{ background:var(--pass); }}
  .deploy-icon.blocked {{ background:var(--fail); }}
  .deploy-title {{ font-size:15px; font-weight:700; }}
  .deploy-title.ok {{ color:var(--pass); }}
  .deploy-title.blocked {{ color:var(--fail); }}
  .deploy-sub {{ font-size:12.5px; color:var(--muted); margin-top:2px; }}
  .gauge {{ width:66px; height:66px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
  .gauge-inner {{
    width:76%; height:76%; border-radius:50%; background:var(--card);
    display:flex; align-items:center; justify-content:center;
    font-weight:700; font-size:13px; color:var(--ink);
  }}

  .meta {{
    background:var(--card); border:1px solid var(--border); border-radius:12px;
    padding:16px 20px; margin-bottom:22px; font-size:13px; color:var(--muted);
    display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px;
    box-shadow:var(--shadow);
  }}
  .meta b {{ color:var(--ink); font-size:11px; text-transform:uppercase; letter-spacing:.04em; display:block; margin-bottom:2px; }}

  section h2.section-title {{ font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; margin:0 0 12px; font-weight:700; }}

  .feature-summary {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:12px; margin-bottom:26px; }}
  .fs-card {{
    background:var(--card); border:1px solid var(--border); border-radius:12px;
    padding:15px 17px; box-shadow:var(--shadow); transition:transform .18s ease, box-shadow .18s ease;
  }}
  .fs-card:hover {{ transform:translateY(-3px); box-shadow:var(--shadow-hover); }}
  .fs-card .fs-name {{ font-weight:600; font-size:13px; margin-bottom:10px; }}
  .fs-bar {{ height:7px; border-radius:4px; background:#eef2f7; overflow:hidden; display:flex; margin-bottom:9px; }}
  .fs-bar span {{ height:100%; animation:fillBar .7s ease both; }}
  .fs-bar .p {{ background:var(--pass); }}
  .fs-bar .f {{ background:var(--fail); }}
  .fs-bar .b {{ background:var(--blocked); }}
  .fs-nums {{ font-size:11.5px; color:var(--muted); display:flex; justify-content:space-between; }}

  .toolbar {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:18px; }}
  .filters {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .filters button {{
    border:1px solid var(--border); background:#fff; padding:7px 15px; border-radius:20px;
    font-size:12.5px; font-weight:600; cursor:pointer; color:var(--ink);
    transition:background .15s ease, color .15s ease, border-color .15s ease, transform .1s ease;
  }}
  .filters button:hover {{ transform:translateY(-1px); border-color:var(--brand); }}
  .filters button.active {{ background:var(--brand); color:#fff; border-color:var(--brand); }}
  .toolbar select, .toolbar input[type=text] {{
    padding:8px 13px; border:1px solid var(--border); border-radius:9px; font-size:13px;
    background:#fff; color:var(--ink); transition:border-color .15s ease, box-shadow .15s ease;
  }}
  .toolbar select:focus, .toolbar input[type=text]:focus {{
    outline:none; border-color:var(--brand); box-shadow:0 0 0 3px rgba(67,56,202,.12);
  }}
  .toolbar input[type=text] {{ flex:1; min-width:220px; }}

  .feature-group h2 {{ font-size:14.5px; margin:28px 0 10px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; font-weight:700; }}
  .case {{
    background:var(--card); border:1px solid var(--border); border-radius:12px;
    margin-bottom:10px; overflow:hidden; box-shadow:var(--shadow);
    transition:box-shadow .18s ease, border-color .18s ease;
  }}
  .case:hover {{ box-shadow:var(--shadow-hover); }}
  .case-head {{
    width:100%; display:flex; align-items:center; gap:12px; padding:14px 18px;
    background:none; border:none; cursor:pointer; text-align:left; font-size:14px;
    transition:background .15s ease;
  }}
  .case-head:hover {{ background:#f8fafc; }}
  .badge {{ font-size:10.5px; font-weight:700; padding:4px 10px; border-radius:20px; color:#fff; letter-spacing:.03em; }}
  .badge.pass {{ background:var(--pass); }}
  .badge.fail {{ background:var(--fail); }}
  .badge.blocked {{ background:var(--blocked); }}
  .case-id {{ font-weight:600; color:var(--muted); min-width:90px; font-size:12.5px; }}
  .case-title {{ flex:1; }}
  .chev {{ transition:transform .2s ease; color:var(--muted); }}
  .case.open .chev {{ transform:rotate(180deg); }}
  .case-body {{ display:none; padding:2px 20px 22px; border-top:1px solid var(--border); animation:fadeUp .25s ease both; }}
  .case.open .case-body {{ display:block; }}
  .grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; margin:16px 0; }}
  .grid p {{ margin:4px 0 0; font-size:13px; color:#334155; }}
  .grid b {{ font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }}
  .assertions {{ list-style:none; padding:0; margin:8px 0 16px; font-size:13px; }}
  .assertions li {{ padding:7px 0; border-bottom:1px dashed var(--border); }}
  .assertions li.check .sym {{ color:var(--pass); font-weight:700; margin-right:6px; }}
  .assertions li.cross .sym {{ color:var(--fail); font-weight:700; margin-right:6px; }}
  .ae {{ font-size:12px; color:var(--muted); margin-top:4px; }}
  .failure-log {{ background:#0f172a; color:#e2e8f0; padding:14px; border-radius:10px; font-size:12px; overflow-x:auto; white-space:pre; }}
  .shot img {{ max-width:100%; border:1px solid var(--border); border-radius:10px; margin-top:8px; transition:transform .2s ease; }}
  .shot img:hover {{ transform:scale(1.01); }}
  .evidence-gallery {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; margin:8px 0 16px; }}
  .evidence-shot {{
    margin:0; background:#f8fafc; border:1px solid var(--border); border-radius:10px; padding:6px;
    transition:transform .15s ease, box-shadow .15s ease;
  }}
  .evidence-shot:hover {{ transform:translateY(-2px); box-shadow:var(--shadow); }}
  .evidence-shot img {{ width:100%; border-radius:6px; display:block; border:1px solid var(--border); }}
  .evidence-shot figcaption {{ font-size:11px; color:var(--muted); margin-top:6px; line-height:1.35; }}
  .exec-log {{ background:#0f172a; color:#93c5fd; padding:14px; border-radius:10px; font-size:12px; overflow-x:auto; white-space:pre-wrap; line-height:1.5; }}
  .muted {{ color:var(--muted); font-size:13px; }}
  footer {{ text-align:center; color:var(--muted); font-size:12px; padding:26px 0 10px; }}
  .no-results {{ text-align:center; color:var(--muted); padding:30px; font-size:13px; display:none; }}

  @media (max-width:760px) {{
    header {{ padding:28px 18px 60px; }}
    header h1 {{ font-size:19px; }}
    .deploy-banner {{ margin-top:-52px; padding:16px 18px; flex-direction:column; align-items:flex-start; }}
    .wrap {{ padding:20px 14px 50px; }}
    .grid {{ grid-template-columns:1fr; }}
    .case-title {{ font-size:13px; }}
    .toolbar input[type=text] {{ min-width:100%; order:3; }}
  }}
</style>
</head>
<body>
<header>
  <div class="inner">
    <h1>{title}</h1>
    <div class="sub">{app_url} &middot; {env_line}</div>
    <div class="stats">
      <div class="stat"><div class="n">{total}</div><div class="l">Total</div></div>
      <div class="stat"><div class="n" style="color:#bbf7d0">{passed}</div><div class="l">Passed</div></div>
      <div class="stat"><div class="n" style="color:#fecaca">{failed}</div><div class="l">Failed</div></div>
      <div class="stat"><div class="n" style="color:#fde68a">{blocked}</div><div class="l">Blocked</div></div>
      <div class="stat"><div class="n">{pass_rate}%</div><div class="l">Pass Rate</div></div>
    </div>
  </div>
</header>
<div class="wrap">
  <div class="deploy-banner {deploy_css}">
    <div class="deploy-left">
      <div class="deploy-icon {deploy_css}">{deploy_glyph}</div>
      <div>
        <div class="deploy-title {deploy_css}">{deploy_title}</div>
        <div class="deploy-sub">{deploy_sub}</div>
      </div>
    </div>
    <div class="gauge" style="background:conic-gradient(var(--{deploy_gauge_color}) {pass_rate}%, #e6eaf0 0)">
      <div class="gauge-inner">{pass_rate}%</div>
    </div>
  </div>
  <div class="meta">
    <div><b>Execution Start</b>{start}</div>
    <div><b>Execution End</b>{end}</div>
    <div><b>Duration</b>{duration}</div>
    <div><b>Browser</b>{browser}</div>
    <div><b>Mode</b>{mode}</div>
    <div><b>Deployment Threshold</b>{deployment_threshold}%</div>
  </div>
  <section>
    <h2 class="section-title">Feature-wise Results</h2>
    <div class="feature-summary">{feature_summary}</div>
  </section>
  <div class="toolbar">
    <div class="filters" id="filters">
      <button data-f="all" class="active">All ({total})</button>
      <button data-f="PASS">Passed ({passed})</button>
      <button data-f="FAIL">Failed ({failed})</button>
      <button data-f="BLOCKED">Blocked ({blocked})</button>
    </div>
    <select id="featureFilter">
      <option value="all">All Features</option>
      {feature_options}
    </select>
    <input type="text" id="searchBox" placeholder="Search by Test Case ID or title...">
  </div>
  {feature_groups}
  <p class="no-results" id="noResults">No test cases match the current filters.</p>
  <footer>Generated by QA_Automation &middot; Playwright + Pytest &middot; {generated_at}</footer>
</div>
<script>
const state = {{ status: 'all', feature: 'all', search: '' }};

function applyFilters() {{
  let anyVisible = false;
  document.querySelectorAll('.case').forEach(c => {{
    const matchesStatus = state.status === 'all' || c.dataset.result === state.status;
    const matchesFeature = state.feature === 'all' || c.dataset.feature === state.feature;
    const matchesSearch = !state.search || c.dataset.search.includes(state.search);
    const visible = matchesStatus && matchesFeature && matchesSearch;
    c.style.display = visible ? '' : 'none';
    if (visible) anyVisible = true;
  }});
  document.querySelectorAll('.feature-group').forEach(g => {{
    const groupHasVisible = [...g.querySelectorAll('.case')].some(c => c.style.display !== 'none');
    g.style.display = groupHasVisible ? '' : 'none';
  }});
  document.getElementById('noResults').style.display = anyVisible ? 'none' : 'block';
}}

document.getElementById('filters').addEventListener('click', (e) => {{
  const btn = e.target.closest('button');
  if (!btn) return;
  document.querySelectorAll('#filters button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.status = btn.dataset.f;
  applyFilters();
}});

document.getElementById('featureFilter').addEventListener('change', (e) => {{
  state.feature = e.target.value;
  applyFilters();
}});

document.getElementById('searchBox').addEventListener('input', (e) => {{
  state.search = e.target.value.trim().toLowerCase();
  applyFilters();
}});
</script>
</body>
</html>
"""


def build_html_report(cases: list, meta: dict, out_path: Path) -> Path:
    total = len(cases)
    passed = sum(1 for c in cases if c["result"] == "PASS")
    failed = sum(1 for c in cases if c["result"] == "FAIL")
    blocked = sum(1 for c in cases if c["result"] == "BLOCKED")
    executed = passed + failed
    pass_rate = round((passed / executed * 100), 2) if executed else 0.0

    # Dynamic deployment status: configurable via DEPLOYMENT_SUCCESS_THRESHOLD
    # in .env (config/settings.py), passed through as meta["deployment_threshold"].
    deployment_threshold = float(meta.get("deployment_threshold", 95))
    deployment_ok = executed > 0 and pass_rate >= deployment_threshold
    if executed == 0:
        deploy_css, deploy_glyph, deploy_title, deploy_gauge_color = (
            "blocked", "?", "DEPLOYMENT STATUS UNKNOWN", "blocked",
        )
        deploy_sub = "No test cases were executed - nothing to evaluate against the threshold."
    elif deployment_ok:
        deploy_css, deploy_glyph, deploy_title, deploy_gauge_color = (
            "ok", "&#10003;", "DEPLOYMENT SUCCESSFUL", "pass",
        )
        deploy_sub = f"Pass rate {pass_rate}% meets the configured {deployment_threshold}% threshold."
    else:
        deploy_css, deploy_glyph, deploy_title, deploy_gauge_color = (
            "blocked", "&#33;", "DEPLOYMENT BLOCKED", "fail",
        )
        deploy_sub = f"Pass rate {pass_rate}% is below the configured {deployment_threshold}% threshold."

    by_feature = {}
    for c in cases:
        by_feature.setdefault(c["feature"], []).append(c)

    groups_html = []
    summary_html = []
    options_html = []
    for feature, feature_cases in by_feature.items():
        cards = "".join(_case_card(c) for c in feature_cases)
        groups_html.append(
            f'<div class="feature-group"><h2>{html.escape(feature)} '
            f'({len(feature_cases)})</h2>{cards}</div>'
        )

        f_total = len(feature_cases)
        f_passed = sum(1 for c in feature_cases if c["result"] == "PASS")
        f_failed = sum(1 for c in feature_cases if c["result"] == "FAIL")
        f_blocked = sum(1 for c in feature_cases if c["result"] == "BLOCKED")
        pct = lambda n: (n / f_total * 100) if f_total else 0
        summary_html.append(f"""
<div class="fs-card">
  <div class="fs-name">{html.escape(feature)}</div>
  <div class="fs-bar">
    <span class="p" style="width:{pct(f_passed):.1f}%"></span>
    <span class="f" style="width:{pct(f_failed):.1f}%"></span>
    <span class="b" style="width:{pct(f_blocked):.1f}%"></span>
  </div>
  <div class="fs-nums">
    <span>Total: {f_total}</span>
    <span style="color:var(--pass)">P: {f_passed}</span>
    <span style="color:var(--fail)">F: {f_failed}</span>
    <span style="color:var(--blocked)">B: {f_blocked}</span>
  </div>
</div>""")
        options_html.append(
            f'<option value="{html.escape(feature)}">{html.escape(feature)} ({f_total})</option>'
        )

    html_out = TEMPLATE.format(
        title=meta.get("title", "QA Automation Report"),
        app_url=html.escape(meta.get("app_url", "")),
        env_line=html.escape(meta.get("env_line", "")),
        total=total, passed=passed, failed=failed, blocked=blocked, pass_rate=pass_rate,
        start=meta.get("start", ""), end=meta.get("end", ""), duration=meta.get("duration", ""),
        browser=meta.get("browser", ""), mode=meta.get("mode", ""),
        deployment_threshold=deployment_threshold,
        deploy_css=deploy_css, deploy_glyph=deploy_glyph, deploy_title=deploy_title,
        deploy_sub=deploy_sub, deploy_gauge_color=deploy_gauge_color,
        feature_summary="".join(summary_html),
        feature_options="".join(options_html),
        feature_groups="".join(groups_html),
        generated_at=meta.get("generated_at", ""),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding="utf-8")
    return out_path
