"""
Escolha do script pelo entrypoint do Cloud Run Job de backfill (ner-backfill-job).

Contrato com o DAG `enrichment_backfill` (data-platform), que passa a env por
container override:
  - BACKFILL_SCRIPT ausente ou vazia      -> scripts/backfill_ner_corpus.py (default;
    o DAG `ner_backfill` não passa a env e segue igual);
  - BACKFILL_SCRIPT=backfill_ner_corpus.py       -> o mesmo script NER;
  - BACKFILL_SCRIPT=reenrich_combined_window.py  -> scripts/reenrich_combined_window.py;
  - qualquer outro valor (inclusive caminhos)    -> erro com exit != 0, ANTES de
    executar qualquer coisa (nem o parse de credenciais).
Em todos os casos os args do Job ("$@") são repassados intactos e o parse de
AWS_BEDROCK_CONNECTION_URI continua o mesmo.

Diferente de test_entrypoint_creds.py, aqui o entrypoint roda SEM alterações: um
`python` falso à frente no PATH registra cada chamada; o heredoc do parse de
credenciais (`python -`) é repassado ao Python real, e o `exec` final só ecoa o
script, os args e o ambiente AWS (sem Bedrock/DB).
"""

import os
import stat
import subprocess
import sys

import pytest

_REPO = os.path.join(os.path.dirname(__file__), "..")
NER_SH = os.path.abspath(os.path.join(_REPO, "docker", "ner-backfill-job", "entrypoint.sh"))

NER_SCRIPT = "scripts/backfill_ner_corpus.py"
REENRICH_SCRIPT = "scripts/reenrich_combined_window.py"

SECRET_RAW = "abc/def+ghi=="
SECRET_ENC = "abc%2Fdef%2Bghi%3D%3D"
URI = f"aws://AKIAEXAMPLE:{SECRET_ENC}@/?region_name=sa-east-1"

REENRICH_ARGS = [
    "--select", "mock",
    "--date-from", "2025-09-01",
    "--date-to", "2026-03-01",
    "--limit", "500",
    "--workers", "2",
]


def _fake_python(tmp_path):
    """`python` falso: `python -` (heredoc das creds) vai ao Python real; qualquer
    outra chamada (o exec final) só ecoa o script, cada arg e o ambiente AWS."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "calls.log"
    fake = bindir / "python"
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> "{calls}"\n'
        'if [ "$1" = "-" ]; then\n'
        f'    exec "{sys.executable}" "$@"\n'
        "fi\n"
        'echo "SCRIPT=$1"\n'
        "shift\n"
        'for a in "$@"; do echo "ARG=$a"; done\n'
        'echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"\n'
        'echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"\n'
        'echo "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return str(bindir), calls


def _run(tmp_path, env, args):
    bindir, calls = _fake_python(tmp_path)
    full_env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}
    full_env.update(env)
    proc = subprocess.run(
        ["/bin/sh", NER_SH, *args], env=full_env, cwd=str(tmp_path), capture_output=True, text=True
    )
    return proc, calls


def _parse(stdout):
    script, args, aws = None, [], {}
    for line in stdout.splitlines():
        key, _, value = line.partition("=")
        if key == "SCRIPT":
            script = value
        elif key == "ARG":
            args.append(value)
        elif key.startswith("AWS_"):
            aws[key] = value
    return script, args, aws


@pytest.mark.parametrize("env", [{}, {"BACKFILL_SCRIPT": ""}])
def test_default_sem_backfill_script_executa_o_ner(tmp_path, env):
    """Sem BACKFILL_SCRIPT (ou vazia): segue o NER, como o DAG ner_backfill espera."""
    proc, _ = _run(tmp_path, env, ["--limit", "20", "--order", "desc"])
    assert proc.returncode == 0, proc.stderr
    script, args, _ = _parse(proc.stdout)
    assert script == NER_SCRIPT
    assert args == ["--limit", "20", "--order", "desc"]


def test_backfill_script_ner_explicito(tmp_path):
    proc, _ = _run(tmp_path, {"BACKFILL_SCRIPT": "backfill_ner_corpus.py"}, ["--limit", "5"])
    assert proc.returncode == 0, proc.stderr
    script, args, _ = _parse(proc.stdout)
    assert script == NER_SCRIPT
    assert args == ["--limit", "5"]


def test_backfill_script_reenrich_repassa_args(tmp_path):
    proc, _ = _run(
        tmp_path, {"BACKFILL_SCRIPT": "reenrich_combined_window.py"}, REENRICH_ARGS
    )
    assert proc.returncode == 0, proc.stderr
    script, args, _ = _parse(proc.stdout)
    assert script == REENRICH_SCRIPT
    assert args == REENRICH_ARGS


def test_args_com_espaco_sao_preservados(tmp_path):
    """"$@" chega intacto (um arg com espaço continua um arg só)."""
    proc, _ = _run(
        tmp_path,
        {"BACKFILL_SCRIPT": "reenrich_combined_window.py"},
        ["--select", "mock", "--date-from", "2025-09-01 extra"],
    )
    assert proc.returncode == 0, proc.stderr
    _, args, _ = _parse(proc.stdout)
    assert args == ["--select", "mock", "--date-from", "2025-09-01 extra"]


@pytest.mark.parametrize("value", [
    "../x.py",
    "foo.py",
    "eval_ner_models.py",  # existe em scripts/, mas fora da allowlist
    "scripts/reenrich_combined_window.py",
    "../scripts/backfill_ner_corpus.py",
    "/app/scripts/reenrich_combined_window.py",
    "reenrich_combined_window.py ",
    "REENRICH_COMBINED_WINDOW.PY",
    "reenrich_combined_window.py;id",
])
def test_backfill_script_invalido_falha_sem_executar(tmp_path, value):
    proc, calls = _run(
        tmp_path,
        {"BACKFILL_SCRIPT": value, "AWS_BEDROCK_CONNECTION_URI": URI},
        ["--limit", "1"],
    )
    assert proc.returncode != 0
    assert "BACKFILL_SCRIPT" in proc.stderr
    assert "SCRIPT=" not in proc.stdout
    # Falha antes de qualquer chamada ao Python (nem o parse de credenciais).
    assert not calls.exists() or calls.read_text() == ""


@pytest.mark.parametrize("backfill_script,expected", [
    (None, NER_SCRIPT),
    ("reenrich_combined_window.py", REENRICH_SCRIPT),
])
def test_credenciais_continuam_exportadas(tmp_path, backfill_script, expected):
    env = {"AWS_BEDROCK_CONNECTION_URI": URI}
    if backfill_script is not None:
        env["BACKFILL_SCRIPT"] = backfill_script
    proc, _ = _run(tmp_path, env, [])
    assert proc.returncode == 0, proc.stderr
    script, _, aws = _parse(proc.stdout)
    assert script == expected
    assert aws["AWS_ACCESS_KEY_ID"] == "AKIAEXAMPLE"
    assert aws["AWS_SECRET_ACCESS_KEY"] == SECRET_RAW  # URL-decoded
    assert aws["AWS_DEFAULT_REGION"] == "sa-east-1"


def test_credenciais_discretas_nao_sao_sobrescritas_no_reenrich(tmp_path):
    proc, _ = _run(
        tmp_path,
        {
            "BACKFILL_SCRIPT": "reenrich_combined_window.py",
            "AWS_BEDROCK_CONNECTION_URI": URI,
            "AWS_ACCESS_KEY_ID": "PRESET_KEY",
            "AWS_SECRET_ACCESS_KEY": "PRESET_SECRET",
        },
        [],
    )
    assert proc.returncode == 0, proc.stderr
    _, _, aws = _parse(proc.stdout)
    assert aws["AWS_ACCESS_KEY_ID"] == "PRESET_KEY"
    assert aws["AWS_SECRET_ACCESS_KEY"] == "PRESET_SECRET"
