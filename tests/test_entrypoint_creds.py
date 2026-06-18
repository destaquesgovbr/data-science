"""
Smoke test dos shims de entrypoint dos Cloud Run Jobs: o parsing de
AWS_BEDROCK_CONNECTION_URI (formato Airflow aws://KEY:SECRET@/?region_name=...)
deve exportar AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
discretos, e o shim deve `exec`utar o CLI correto repassando "$@".

Não executa o CLI real: substitui o último `exec ...` por um eco do ambiente AWS
e dos argumentos, de modo a validar SÓ o shim (sem Bedrock/DB).
"""

import os
import re
import stat
import subprocess

import pytest

_REPO = os.path.join(os.path.dirname(__file__), "..")
CANON_SH = os.path.join(_REPO, "docker", "canonicalization-job", "entrypoint.sh")
NER_SH = os.path.join(_REPO, "docker", "ner-backfill-job", "entrypoint.sh")

# URI com caracteres que exigem URL-decode (secret com '/', '+', '%').
SECRET_RAW = "abc/def+ghi=="
SECRET_ENC = "abc%2Fdef%2Bghi%3D%3D"
URI = f"aws://AKIAEXAMPLE:{SECRET_ENC}@/?region_name=sa-east-1"


def _make_test_shim(tmp_path, src_path, exec_marker):
    """Copia o shim trocando a linha `exec ...` por um eco do ambiente/args."""
    with open(src_path, "r") as f:
        content = f.read()
    assert exec_marker in content, f"esperava {exec_marker!r} no shim"
    patched = re.sub(
        r"^exec .*$",
        'echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"\n'
        'echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"\n'
        'echo "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"\n'
        'echo "ARGS=$*"',
        content,
        flags=re.M,
    )
    dest = tmp_path / "shim.sh"
    dest.write_text(patched)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    return str(dest)


def _run(shim, env, args):
    base = {"PATH": os.environ["PATH"]}
    base.update(env)
    out = subprocess.run(
        [shim, *args], env=base, capture_output=True, text=True, check=True
    )
    return dict(
        line.split("=", 1) for line in out.stdout.strip().splitlines() if "=" in line
    )


@pytest.mark.parametrize("shim_src,marker", [
    (CANON_SH, "news_enrichment.canonicalization_job"),
    (NER_SH, "scripts/backfill_ner_corpus.py"),
])
def test_parses_connection_uri_into_discrete_creds(tmp_path, shim_src, marker):
    shim = _make_test_shim(tmp_path, shim_src, marker)
    parsed = _run(shim, {"AWS_BEDROCK_CONNECTION_URI": URI}, ["--limit", "20"])
    assert parsed["AWS_ACCESS_KEY_ID"] == "AKIAEXAMPLE"
    assert parsed["AWS_SECRET_ACCESS_KEY"] == SECRET_RAW  # URL-decoded
    assert parsed["AWS_DEFAULT_REGION"] == "sa-east-1"
    assert parsed["ARGS"] == "--limit 20"  # "$@" repassado ao CLI


@pytest.mark.parametrize("shim_src,marker", [
    (CANON_SH, "news_enrichment.canonicalization_job"),
    (NER_SH, "scripts/backfill_ner_corpus.py"),
])
def test_discrete_creds_not_overwritten(tmp_path, shim_src, marker):
    """Se AWS_ACCESS_KEY_ID/SECRET já vêm no ambiente, o shim não sobrescreve."""
    shim = _make_test_shim(tmp_path, shim_src, marker)
    parsed = _run(
        shim,
        {
            "AWS_BEDROCK_CONNECTION_URI": URI,
            "AWS_ACCESS_KEY_ID": "PRESET_KEY",
            "AWS_SECRET_ACCESS_KEY": "PRESET_SECRET",
        },
        [],
    )
    assert parsed["AWS_ACCESS_KEY_ID"] == "PRESET_KEY"
    assert parsed["AWS_SECRET_ACCESS_KEY"] == "PRESET_SECRET"


@pytest.mark.parametrize("shim_src,marker", [
    (CANON_SH, "news_enrichment.canonicalization_job"),
    (NER_SH, "scripts/backfill_ner_corpus.py"),
])
def test_correct_cli_target(shim_src, marker):
    """O shim correto invoca o CLI correto (canon vs ner)."""
    with open(shim_src) as f:
        content = f.read()
    assert 'exec "$PYBIN"' in content
    assert marker in content
