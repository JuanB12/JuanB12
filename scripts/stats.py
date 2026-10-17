"""Genera una tarjeta SVG animada con las estadísticas del perfil de GitHub.

Se ejecuta a diario desde .github/workflows/perfil.yml. Solo usa la librería estándar.
Uso: GITHUB_TOKEN=... python scripts/stats.py <usuario> <archivo_salida>
"""

import datetime
import json
import os
import sys
import urllib.request
from html import escape

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
# Los notebooks pesan mucho por las salidas guardadas y distorsionan el porcentaje
IGNORAR_LENGUAJES = {"Jupyter Notebook"}
COLORES = ["#3776AB", "#FFD43B", "#4E9BCD", "#C9A227", "#7FB0D9", "#9FB3D1"]


def pedir(url, cuerpo=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(cuerpo).encode() if cuerpo else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "perfil-stats",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def datos(usuario):
    perfil = pedir(f"{API}/users/{usuario}")
    repos, pagina = [], 1
    while True:
        lote = pedir(f"{API}/users/{usuario}/repos?per_page=100&type=owner&page={pagina}")
        repos += lote
        if len(lote) < 100:
            break
        pagina += 1
    propios = [r for r in repos if not r["fork"] and r["name"].lower() != usuario.lower()]

    lenguajes = {}
    for r in propios:
        for nombre, bytes_ in pedir(r["languages_url"]).items():
            if nombre not in IGNORAR_LENGUAJES:
                lenguajes[nombre] = lenguajes.get(nombre, 0) + bytes_
    total = sum(lenguajes.values()) or 1
    top = sorted(lenguajes.items(), key=lambda kv: kv[1], reverse=True)[:6]
    top = [(n, b / total * 100) for n, b in top]

    consulta = {
        "query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions}}}}",
        "variables": {"u": usuario},
    }
    contribuciones = pedir(f"{API}/graphql", consulta)["data"]["user"][
        "contributionsCollection"]["contributionCalendar"]["totalContributions"]

    desde = datetime.datetime.fromisoformat(perfil["created_at"].replace("Z", "+00:00"))
    return {
        "contribuciones": contribuciones,
        "repos": perfil["public_repos"],
        "estrellas": sum(r["stargazers_count"] for r in propios),
        "seguidores": perfil["followers"],
        "desde": desde.year,
        "lenguajes": top,
    }


def svg(d):
    metricas = [
        ("Contribuciones (último año)", d["contribuciones"]),
        ("Repositorios públicos", d["repos"]),
        ("Estrellas recibidas", d["estrellas"]),
        ("Seguidores", d["seguidores"]),
    ]
    tiles = []
    for i, (etiqueta, valor) in enumerate(metricas):
        x = 32 + (i % 2) * 232
        y = 74 + (i // 2) * 92
        retraso = 0.15 + i * 0.18
        tiles.append(f"""
    <g transform="translate({x} {y})">
      <rect width="216" height="78" rx="14" fill="#10203A" stroke="#1F3557"/>
      <rect width="4" height="40" x="0" y="19" rx="2" fill="{COLORES[i % 2]}"/>
      <text x="20" y="28" class="label">{escape(etiqueta)}</text>
      <text x="20" y="62" class="num up" style="animation-delay:{retraso:.2f}s">{valor}</text>
    </g>""")

    barra_x, barra_w = 540, 428
    segmentos, leyenda, x = [], [], barra_x
    for i, (nombre, pct) in enumerate(d["lenguajes"]):
        w = barra_w * pct / 100
        color = COLORES[i % len(COLORES)]
        segmentos.append(
            f'<rect x="{x:.1f}" y="104" width="{w:.1f}" height="14" fill="{color}" '
            f'class="grow" style="animation-delay:{0.3 + i * 0.12:.2f}s"/>')
        x += w
        lx = barra_x + (i % 2) * 220
        ly = 152 + (i // 2) * 30
        leyenda.append(f"""
    <g class="up" style="animation-delay:{0.6 + i * 0.1:.2f}s">
      <circle cx="{lx + 6}" cy="{ly - 5}" r="6" fill="{color}"/>
      <text x="{lx + 20}" y="{ly}" class="leg">{escape(nombre)} <tspan class="pct">{pct:.1f}%</tspan></text>
    </g>""")

    anios = datetime.date.today().year - d["desde"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="292" viewBox="0 0 1000 292" role="img" aria-label="Estadísticas de GitHub">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0B1220"/><stop offset="1" stop-color="#0F2342"/>
    </linearGradient>
    <linearGradient id="brillo" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="barra"><rect x="{barra_x}" y="104" width="{barra_w}" height="14" rx="7"/></clipPath>
    <style>
      text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif; }}
      .title {{ font-size: 20px; font-weight: 700; fill: #FFD43B; }}
      .sub {{ font-size: 13px; fill: #6F86A8; }}
      .label {{ font-size: 13px; fill: #9FB3D1; }}
      .num {{ font-size: 30px; font-weight: 800; fill: #FFFFFF; }}
      .leg {{ font-size: 14px; fill: #DCE7F7; }}
      .pct {{ fill: #9FB3D1; }}
      .up {{ opacity: 0; animation: up .7s cubic-bezier(.2,.8,.2,1) forwards; }}
      @keyframes up {{ from {{ opacity: 0; transform: translateY(12px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      .grow {{ transform-box: fill-box; transform-origin: left center; transform: scaleX(0); animation: grow .9s cubic-bezier(.2,.8,.2,1) forwards; }}
      @keyframes grow {{ to {{ transform: scaleX(1); }} }}
      .shine {{ animation: shine 3.5s ease-in-out 1.5s infinite; }}
      @keyframes shine {{ from {{ transform: translateX(-140px); }} to {{ transform: translateX({barra_w + 140}px); }} }}
      .pulse {{ animation: pulse 2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
      @keyframes pulse {{ 0%,100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: .35; transform: scale(1.6); }} }}
    </style>
  </defs>
  <rect width="1000" height="292" rx="20" fill="url(#bg)" stroke="#1F3557"/>

  <text x="32" y="46" class="title">Mi actividad en GitHub</text>
  <circle cx="844" cy="40" r="5" fill="#28C840" class="pulse"/>
  <text x="856" y="45" class="sub">actualizado a diario</text>
  {"".join(tiles)}

  <text x="{barra_x}" y="88" class="label">Lenguajes más usados</text>
  <rect x="{barra_x}" y="104" width="{barra_w}" height="14" rx="7" fill="#10203A"/>
  <g clip-path="url(#barra)">
    {"".join(segmentos)}
    <rect class="shine" x="{barra_x}" y="104" width="120" height="14" fill="url(#brillo)"/>
  </g>
  {"".join(leyenda)}

  <text x="32" y="274" class="sub">En GitHub desde {d["desde"]} · {anios} años aprendiendo y construyendo</text>
</svg>
"""


if __name__ == "__main__":
    usuario, salida = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(svg(datos(usuario)))
    print(f"Tarjeta generada en {salida}")
