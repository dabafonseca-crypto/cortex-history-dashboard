#!/usr/bin/env python3
"""Exporta somente dados historicos publicaveis da Cortex para o dashboard.

Leitura SQLite read-only. Nenhuma credencial, token, cookie ou sessao eh exportada.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE = Path.home() / "cortex-hotlist-collector"
DB = BASE / "archive" / "hotlist.sqlite3"
OUT = Path(__file__).resolve().parent / "data.json"

if DB.is_symlink() or not DB.is_file():
    raise SystemExit("ERRO: banco SQLite ausente ou invalido")
if OUT.is_symlink():
    raise SystemExit("ERRO: destino nao pode ser link simbolico")

with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as con:
    con.execute("PRAGMA query_only=ON")
    if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise SystemExit("ERRO: integridade do banco")
    rows = con.execute(
        "SELECT id, reference_date, collected_utc, source_updated_at, "
        "asset_count, payload_json FROM captures ORDER BY id"
    ).fetchall()

captures = []
campos = ("posicao", "ativo", "classe", "tendencia", "score", "barra_inicio", "barra_largura")
for ident, date, collected, updated, count, payload in rows:
    obj = json.loads(payload)
    ativos = obj.get("ativos")
    if not isinstance(ativos, list) or len(ativos) != count:
        raise SystemExit(f"ERRO: coleta {ident} inconsistente")
    saida = []
    for ativo in ativos:
        if any(k not in ativo for k in campos):
            raise SystemExit(f"ERRO: campos ausentes na coleta {ident}")
        saida.append({k: ativo[k] for k in campos})
    captures.append(dict(id=ident, reference_date=date, collected_utc=collected,
                         source_updated_at=updated, asset_count=count, ativos=saida))

dados = dict(version=1, generated_at=datetime.now(timezone.utc).isoformat(), captures=captures)
tmp = OUT.with_name(".data.json.tmp")
if tmp.exists() or tmp.is_symlink():
    raise SystemExit("ERRO: arquivo temporario existente")
try:
    with tmp.open("x", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        f.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, OUT)
finally:
    tmp.unlink(missing_ok=True)
# Também cria uma página 100% autossuficiente, para abrir sem servidor.
# A página original permanece intacta como modelo reutilizável.
template = OUT.parent / "index.html"
real_html = OUT.parent / "index-real.html"
if not template.is_file() or template.is_symlink() or real_html.is_symlink():
    raise SystemExit("ERRO: template ou destino HTML invalido")
start_marker = "// DASHBOARD_INLINE_DATA_START"
end_marker = "// DASHBOARD_INLINE_DATA_END"
html = template.read_text(encoding="utf-8")
if html.count(start_marker) != 1 or html.count(end_marker) != 1:
    raise SystemExit("ERRO: marcadores do template inesperados")
start = html.index(start_marker) + len(start_marker)
end = html.index(end_marker)
# Evita sequencias que poderiam encerrar uma tag <script> em dados JSON.
js_data = json.dumps(dados, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
js_data = js_data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
html = html[:start] + "\nconst DEMO = " + js_data + ";\n" + html[end:]
html = html.replace(
    "<strong>PRÉVIA:</strong> mostrando uma captura já confirmada em 11/10/2026 às 10:02. O arquivo exportado do seu SQLite substituirá esta amostra e disponibilizará todas as coletas.",
    "<strong>DADOS DO SQLITE:</strong> histórico real exportado do banco local, sem dados de autenticação."
).replace("PRÉVIA LOCAL</span>", "HISTÓRICO LOCAL</span>")
tmp_html = real_html.with_name(".index-real.html.tmp")
if tmp_html.exists() or tmp_html.is_symlink():
    raise SystemExit("ERRO: HTML temporario ja existe")
try:
    with tmp_html.open("x", encoding="utf-8") as f:
        f.write(html)
    os.chmod(tmp_html, 0o600)
    os.replace(tmp_html, real_html)
finally:
    tmp_html.unlink(missing_ok=True)

print("DASHBOARD:", real_html)
print("JSON:", OUT)
print("COLETAS EXPORTADAS:", len(captures))
print("OBSERVACOES:", sum(c["asset_count"] for c in captures))
print("SQLITE ORIGINAL: NAO MODIFICADO")
print("CREDENCIAIS: NAO EXPORTADAS")
