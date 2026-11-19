#!/usr/bin/env python3
"""Gera assets/github-stats.svg com dados reais do GitHub (tema dark/roxo).

Uso:
  GH_TOKEN=xxx GH_USER=ArthurdevjuniorIA python scripts/generate_stats.py
  python scripts/generate_stats.py --demo      # dados de exemplo
AUTHOR_EMAILS=e1@x.com,e2@y.com (e-mails dos seus commits)
Variáveis opcionais: TZ_OFFSET (horas, padrão -3 = Natal/RN), OUT (caminho do SVG)
"""
import json, os, sys, urllib.request, urllib.error
from datetime import date, datetime, timedelta, timezone
from html import escape

USER = os.environ.get("GH_USER", "ArthurdevjuniorIA")
TOKEN = os.environ.get("GH_TOKEN", "")
TZ = int(os.environ.get("TZ_OFFSET", "-3"))
OUT = os.environ.get("OUT", "assets/github-stats.svg")
PALETTE = ["#A78BFA", "#F472B6", "#38BDF8", "#FBBF24", "#34D399", "#FB7185"]


# ---------------------------------------------------------------- dados
def api(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "stats-gen"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def graphql(query):
    return api("https://api.github.com/graphql",
               json.dumps({"query": query}).encode())["data"]


def commit_hours(repos):
    """Conta commits por hora clonando os repositórios e filtrando por e-mail.
    AUTHOR_EMAILS = e-mails usados nos seus commits, separados por vírgula."""
    import subprocess, tempfile
    emails = {e.strip().lower() for e in os.environ.get("AUTHOR_EMAILS", "").split(",") if e.strip()}
    hours = [0] * 24
    if not emails:
        print("AUTHOR_EMAILS vazio: gráfico de horas ficará zerado", file=sys.stderr)
        return hours
    auth = f"x-access-token:{TOKEN}@" if TOKEN else ""
    with tempfile.TemporaryDirectory() as tmp:
        for name in repos:
            dest = os.path.join(tmp, name)
            url = f"https://{auth}github.com/{USER}/{name}.git"
            if subprocess.run(["git", "clone", "-q", "--bare", "--filter=blob:none", url, dest],
                              capture_output=True).returncode != 0:
                continue
            out = subprocess.run(["git", "-C", dest, "log", "--all", "--format=%ae|%at"],
                                 capture_output=True, text=True).stdout
            for line in out.splitlines():
                e, t = line.split("|")
                if e.lower() in emails:
                    dt = datetime.fromtimestamp(int(t), timezone.utc) + timedelta(hours=TZ)
                    hours[dt.hour] += 1
    return hours


def fetch():
    meta = graphql('{ user(login:"%s"){ createdAt repositories(first:100, ownerAffiliations:OWNER, isFork:false){ nodes{ name primaryLanguage{name color} languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{name color} } } } } } }' % USER)["user"]
    created = datetime.fromisoformat(meta["createdAt"].replace("Z", "+00:00"))

    days = {}
    for year in range(created.year, date.today().year + 1):
        a = max(created, datetime(year, 1, 1, tzinfo=timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        b = f"{year}-12-31T23:59:59Z"
        q = '{ user(login:"%s"){ contributionsCollection(from:"%s", to:"%s"){ contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }' % (USER, a, b)
        cal = graphql(q)["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    hours = commit_hours([r["name"] for r in meta["repositories"]["nodes"]])

    by_repo, by_size = {}, {}
    colors = {}
    for repo in meta["repositories"]["nodes"]:
        pl = repo["primaryLanguage"]
        if pl:
            by_repo[pl["name"]] = by_repo.get(pl["name"], 0) + 1
            colors[pl["name"]] = pl["color"]
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            by_size[n] = by_size.get(n, 0) + e["size"]
            colors.setdefault(n, e["node"]["color"])
    return dict(days=days, hours=hours, by_repo=by_repo, by_size=by_size,
                created=created.date(), colors=colors)


def demo():
    import random
    random.seed(7)
    today = date.today()
    days = {}
    for i in range(500):
        d = today - timedelta(days=i)
        days[d.isoformat()] = 0 if i > 52 and random.random() < .5 else random.randint(1, 9)
    return dict(days=days,
                hours=[6, 34, 31, 31, 17, 20, 18, 11, 9, 14, 2, 3, 2, 5, 3, 9, 7, 7, 18, 1, 17, 24, 22, 13],
                by_repo={"Python": 5, "JavaScript": 3, "C++": 2, "C": 1, "HTML": 1},
                by_size={"Python": 52, "C++": 40, "JavaScript": 5, "HTML": 2, "C": 1},
                created=today - timedelta(days=500), colors={})


# ---------------------------------------------------------------- cálculos
def streaks(days):
    ds = sorted(days)
    longest = cur = 0
    best_end = None
    run_start = None
    for d in ds:
        if days[d] > 0:
            cur += 1
            run_start = run_start if cur > 1 else d
            if cur > longest:
                longest, best_end, best_start = cur, d, run_start
        else:
            cur = 0
    # streak atual (hoje sem commit ainda não quebra)
    d = date.today()
    if days.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    n, start = 0, None
    while days.get(d.isoformat(), 0) > 0:
        n += 1
        start = d
        d -= timedelta(days=1)
    cur_range = (start, start + timedelta(days=n - 1)) if n else None
    long_range = (date.fromisoformat(best_start), date.fromisoformat(best_end)) if longest else None
    return n, cur_range, longest, long_range


def fmt(d):
    meses = "jan fev mar abr mai jun jul ago set out nov dez".split()
    return f"{d.day} {meses[d.month - 1]} {d.year}"


def rng(r):
    return f"{fmt(r[0])} a {fmt(r[1])}" if r else "—"


# ---------------------------------------------------------------- SVG
def donut(cx, cy, r, items, colors):
    total = sum(v for _, v in items) or 1
    C = 2 * 3.14159265 * r
    out, off = [], 0
    for i, (name, v) in enumerate(items):
        ln = C * v / total
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colors[i]}" stroke-width="22" '
                   f'stroke-dasharray="{ln:.2f} {C - ln:.2f}" stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        off += ln
    pct = round(100 * items[0][1] / total) if items else 0
    out.append(f'<text x="{cx}" y="{cy + 2}" text-anchor="middle" class="big2">{pct}%</text>')
    out.append(f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="muted">{escape(items[0][0]) if items else ""}</text>')
    return "".join(out)


def legend(x, y, items, colors):
    total = sum(v for _, v in items) or 1
    out = []
    for i, (name, v) in enumerate(items):
        yy = y + i * 28
        out.append(f'<circle cx="{x}" cy="{yy - 4}" r="5" fill="{colors[i]}"/>'
                   f'<text x="{x + 16}" y="{yy}" class="txt">{escape(name)}</text>'
                   f'<text x="{x + 170}" y="{yy}" text-anchor="end" class="muted">{round(100 * v / total)}%</text>')
    return "".join(out)


def top(d, n=5):
    return sorted(d.items(), key=lambda kv: -kv[1])[:n]


def build(data):
    days, hours = data["days"], data["hours"]
    total = sum(days.values())
    cur, cur_r, lon, lon_r = streaks(days)
    prog = 1 if lon == 0 else min(cur / lon, 1)
    R = 46
    C = 2 * 3.14159265 * R

    # barras
    mx = max(hours) or 1
    peak = set(sorted(range(24), key=lambda h: -hours[h])[:3]) if max(hours) else set()
    bars = []
    for h in range(24):
        bh = max(3, 110 * hours[h] / mx)
        x = 75 + h * 32
        fill = "url(#barHi)" if h in peak else "url(#bar)"
        bars.append(f'<rect x="{x}" y="{445 - bh:.1f}" width="20" height="{bh:.1f}" rx="5" fill="{fill}"/>')
        if h % 3 == 0:
            bars.append(f'<text x="{x + 10}" y="{464}" text-anchor="middle" class="axis">{h:02d}</text>')

    repo_items = top(data["by_repo"])
    size_items = top(data["by_size"])
    col = PALETTE
    now = datetime.now().strftime("%d/%m/%Y")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="730" viewBox="0 0 900 730" role="img" aria-label="Estatísticas do GitHub de {USER}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#241548"/><stop offset=".5" stop-color="#0D1117"/><stop offset="1" stop-color="#150B2E"/></linearGradient>
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5EEAD4"/><stop offset=".5" stop-color="#A78BFA"/><stop offset="1" stop-color="#7C3AED"/></linearGradient>
  <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7C3AED"/><stop offset="1" stop-color="#3B2A8C"/></linearGradient>
  <linearGradient id="barHi" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5EEAD4"/><stop offset="1" stop-color="#7C3AED"/></linearGradient>
  <style>
    text{{font-family:'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif}}
    .title{{font-size:26px;font-weight:700;fill:#fff}} .sub{{font-size:12px;fill:#8B8FA8}}
    .lbl{{font-size:13px;font-weight:600;fill:#A9A7C7}} .big{{font-size:56px;font-weight:700;fill:#fff;letter-spacing:1px}}
    .big2{{font-size:22px;font-weight:700;fill:#fff}} .unit{{font-size:18px;fill:#8B8FA8}}
    .acc{{font-size:12px;font-weight:600;fill:#5EEAD4}} .muted{{font-size:11px;fill:#8B8FA8}}
    .txt{{font-size:13px;fill:#E5E7EB}} .axis{{font-size:10px;fill:#6B6F8A}} .h{{font-size:15px;font-weight:700;fill:#fff}}
  </style>
</defs>
<rect width="900" height="730" rx="24" fill="url(#bg)" stroke="#2D2552"/>
<text x="40" y="58" class="title">GitHub stats</text>
<text x="40" y="78" class="sub">@{escape(USER)} · atualizado em {now}</text>

<rect x="30" y="100" width="250" height="150" rx="16" fill="#ffffff" fill-opacity=".04" stroke="#34295F"/>
<text x="52" y="132" class="lbl">Total de contribuições</text>
<text x="52" y="196" class="big">{total}</text>
<text x="52" y="228" class="acc">desde {fmt(data["created"])}</text>

<rect x="300" y="100" width="310" height="150" rx="16" fill="#ffffff" fill-opacity=".05" stroke="#6D5BD0"/>
<circle cx="372" cy="175" r="{R}" fill="none" stroke="#2A2150" stroke-width="9"/>
<circle cx="372" cy="175" r="{R}" fill="none" stroke="url(#ring)" stroke-width="9" stroke-linecap="round" stroke-dasharray="{C * prog:.1f} {C}" transform="rotate(-90 372 175)"/>
<text x="372" y="184" text-anchor="middle" class="big2" style="font-size:30px">{cur}</text>
<text x="372" y="202" text-anchor="middle" class="muted">dias</text>
<text x="448" y="162" style="font-size:17px;font-weight:700;fill:#fff">Streak atual</text>
<text x="444" y="184" class="acc" style="font-size:11.5px">{escape(rng(cur_r))}</text>
<text x="448" y="204" class="muted">{"Igual ao maior streak" if cur and cur == lon else "Meta: bater o recorde"}</text>

<rect x="630" y="100" width="240" height="150" rx="16" fill="#ffffff" fill-opacity=".04" stroke="#34295F"/>
<text x="652" y="132" class="lbl">Maior streak</text>
<text x="652" y="196" class="big">{lon}</text><text x="{652 + 36 * len(str(lon)) + 14}" y="196" class="unit">dias</text>
<text x="652" y="228" class="acc">{escape(rng(lon_r))}</text>

<rect x="30" y="270" width="840" height="215" rx="16" fill="#ffffff" fill-opacity=".04" stroke="#34295F"/>
<text x="52" y="302" class="h">Commits por hora</text>
<text x="848" y="302" text-anchor="end" class="muted">UTC{TZ:+d} · horários de pico em destaque</text>
{"".join(bars)}

<rect x="30" y="505" width="410" height="195" rx="16" fill="#ffffff" fill-opacity=".04" stroke="#34295F"/>
<text x="52" y="537" class="h">Top linguagens por repositório</text>
{legend(58, 575, repo_items, col)}
{donut(370, 600, 48, repo_items, col)}

<rect x="460" y="505" width="410" height="195" rx="16" fill="#ffffff" fill-opacity=".04" stroke="#34295F"/>
<text x="482" y="537" class="h">Top linguagens por código</text>
{legend(488, 575, size_items, col)}
{donut(800, 600, 48, size_items, col)}
</svg>'''


if __name__ == "__main__":
    data = demo() if "--demo" in sys.argv else fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build(data))
    print("gerado:", OUT)
