"""Ações de agente: parser de comandos shell e de chamadas de ferramenta de arquivo."""
from __future__ import annotations

import re
import shlex
from urllib.parse import urlparse

from ..models import Context, Finding

DEFAULT_ALLOWED_HOSTS = (
    "github.com", "api.github.com", "raw.githubusercontent.com", "pypi.org",
    "files.pythonhosted.org", "registry.npmjs.org", "npmjs.com", "localhost", "127.0.0.1",
)
TEMPLATE_SUFFIX = re.compile(r"\.(?:example|sample|template|dist|pub)$")
SENSITIVE_READ = re.compile(
    r"(?:^|/)\.env(?:\.[\w.-]+)?$|\.aws/credentials|\.ssh/id_[a-z0-9]+(?![\w.])|"
    r"\.npmrc$|\.netrc$|\.pypirc$|\.kube/config|\.git-credentials|/etc/(?:shadow|sudoers)|\.docker/config\.json|"
    r"\.gnupg/|service[-_]account.*\.json$|credentials\.json$|id_rsa$|id_ed25519$")


def is_sensitive_read(path: str) -> bool:
    p = path.replace("~", "").lstrip("@=")
    return not TEMPLATE_SUFFIX.search(p) and bool(SENSITIVE_READ.search(p))


SENSITIVE_WRITE = re.compile(
    r"^(?:/etc/|/usr/|/bin/|/sbin/|/boot/|/root/|/var/spool/cron|/lib/systemd|~/\.ssh/|~/\.(?:bashrc|zshrc|profile|bash_profile)|"
    r"\$HOME/\.(?:ssh|bashrc|zshrc|profile)|~/\.config/|~/\.aws/|/home/[^/]+/\.(?:ssh|bashrc|zshrc|profile|aws)(?:/|$))")
READERS = {"cat", "less", "more", "head", "tail", "cp", "scp", "rsync", "base64", "xxd", "strings", "grep", "rg",
           "awk", "sed", "type", "tar", "zip", "source", ".", "openssl", "nl", "bat"}
NETWORK = {"curl", "wget", "nc", "ncat", "netcat", "scp", "sftp", "ftp", "rsync", "http", "httpie"}
PKG = {"pip", "pip3", "npm", "pnpm", "yarn", "gem", "cargo", "apt", "apt-get", "yum", "brew", "uv", "poetry"}
SEP = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
URL_RE = re.compile(r"(?:https?|ftp)://[^\s'\"]+|git\+(?:https?|ssh)://[^\s'\"]+")
HOST_ARG = re.compile(r"^[\w.-]+\.[a-z]{2,}(?::\d+)?(?:/|$)", re.I)


def _split(cmd: str) -> list[tuple[list[str], bool]]:
    """Divide em segmentos simples; devolve (tokens, tem_pipe_para_shell)."""
    segs = []
    pipe_to_sh = bool(re.search(r"\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b|\|\s*(?:python3?|perl|ruby|node)\b", cmd))
    for part in SEP.split(cmd):
        part = part.strip()
        if not part:
            continue
        try:
            toks = shlex.split(part, posix=True)
        except ValueError:
            toks = part.split()
        while toks and (toks[0] in ("sudo", "doas", "nohup", "time", "env") or re.match(r"^\w+=\S*$", toks[0])):
            toks = toks[1:]
        if toks:
            segs.append((toks, pipe_to_sh))
    return segs


def _flags(tokens: list[str]) -> str:
    return "".join(t.lstrip("-") for t in tokens if t.startswith("-") and not t.startswith("--")) + " " + \
        " ".join(t for t in tokens if t.startswith("--"))


def _broad_target(tok: str) -> bool:
    t = tok.rstrip("/") or "/"
    if t in ("/", "~", "$HOME", "${HOME}", "*", ".", "..", "./*", "~/*", "$HOME/*", "/*", "../*"):
        return True
    if re.match(r"^(?:/|~/|\$HOME/)[\w.-]*/?\*?$", tok) and t.count("/") <= 2 and not t.startswith("~/.cache"):
        return t.split("/")[-1] not in ("node_modules", "build", "dist", "tmp", "__pycache__", ".cache")
    return bool(re.match(r"^(?:~|\$HOME|/home/[^/]+)/[^/]+/?\*$", tok)) or bool(re.match(r"^/home/[^/]+/?\*$", tok)) \
        or bool(re.match(r"^/(?:etc|usr|var|boot|bin|sbin|lib|opt|root)(?:/|$)", t))


def _url_host(u: str) -> str:
    return (urlparse(u).hostname or "").lower()


def _allowed(host: str, allowed: tuple[str, ...]) -> bool:
    return any(host == a or host.endswith("." + a) for a in allowed)


def detect_command(cmd: str, allowed_hosts: tuple[str, ...] = ()) -> list[Finding]:
    cmd_text = cmd
    allowed = tuple(allowed_hosts) + DEFAULT_ALLOWED_HOSTS
    out: list[Finding] = []
    segs = _split(cmd)
    for toks, pipe_to_sh in segs:
        prog = toks[0].split("/")[-1]
        args = toks[1:]
        flags = _flags(args)
        # --- destrutivo
        rm_recursive = prog == "rm" and (re.search(r"[rR]", flags.split(" ")[0]) or "--recursive" in args)
        rm_force = prog == "rm" and (re.search(r"f", flags.split(" ")[0]) or "--force" in args)
        if rm_recursive and rm_force:
            targets = [a for a in args if not a.startswith("-")]
            if any(_broad_target(a) for a in targets):
                out.append(Finding("shell_destrutivo", 0.95, "rm -rf em alvo amplo", "shell"))
        elif prog in ("mkfs", "mkfs.ext4", "shred", "wipefs") or prog.startswith("mkfs."):
            out.append(Finding("shell_destrutivo", 0.9, f"{prog} (apaga dados)", "shell"))
        elif prog == "dd" and any(a.startswith("of=/dev/") for a in args):
            out.append(Finding("shell_destrutivo", 0.95, "dd gravando em dispositivo", "shell"))
        elif prog == "find" and "-delete" in args and any(a in ("/", "~", "$HOME") for a in args):
            out.append(Finding("shell_destrutivo", 0.9, "find -delete em raiz ou home", "shell"))
        elif prog == "git" and args[:1] == ["clean"] and re.search(r"f", flags) and re.search(r"x", flags):
            out.append(Finding("shell_destrutivo", 0.6, "git clean -fdx (apaga arquivos não rastreados)", "shell"))
        # --- permissões
        if prog == "chmod" and (re.search(r"\b(?:0?777|0?666|a\+rwx|ugo\+rwx|o\+w)\b", " ".join(args))):
            out.append(Finding("alteracao_permissao", 0.9, "chmod amplo (777/666/o+w)", "shell"))
        elif prog == "chown" and "-R" in args and any(a in ("/", "/etc", "/usr", "/var", "root:root") or a.startswith("root") for a in args):
            out.append(Finding("alteracao_permissao", 0.8, "chown recursivo para root", "shell"))
        elif prog in ("visudo", "usermod", "setfacl") or (prog == "chattr"):
            out.append(Finding("alteracao_permissao", 0.7, f"{prog} altera permissões do sistema", "shell"))
        if re.search(r"NOPASSWD", " ".join(args)):
            out.append(Finding("alteracao_permissao", 0.9, "sudoers NOPASSWD", "shell"))
        # --- leitura de credenciais
        paths = [a for a in args if not a.startswith("-")]
        if prog in READERS:
            if any(is_sensitive_read(p) for p in paths):
                out.append(Finding("leitura_env", 0.92, "Leitura de .env, credenciais ou chave SSH", "shell"))
        if prog in ("printenv",) or (prog == "env" and not args) or \
                (prog == "echo" and any(re.search(r"\$\{?(?:\w*(?:KEY|TOKEN|SECRET|PASSWORD)\w*)\}?", a) for a in args)):
            out.append(Finding("leitura_env", 0.6, "Exibe variáveis de ambiente (podem conter segredos)", "shell"))
        # --- rede
        if prog in NETWORK or prog == "ssh":
            urls = URL_RE.findall(" ".join(args))
            hosts = {_url_host(u) for u in urls}
            if not urls:
                hosts |= {a.split(":")[0].split("/")[0].lower() for a in args if HOST_ARG.match(a)}
                if prog in ("ssh", "scp", "rsync", "sftp"):
                    hosts |= {a.split("@")[-1].split(":")[0].lower() for a in args if "@" in a and not a.startswith(("@", "-"))}
            foreign = {h for h in hosts if h and not _allowed(h, allowed)}
            if foreign:
                conf = 0.9 if pipe_to_sh else 0.7
                out.append(Finding("rede_externa", conf,
                                   "Download executado direto no shell" if pipe_to_sh else "Conexão para host fora da lista permitida",
                                   "shell"))
            upload = any(a in ("-d", "--data", "--data-binary", "--data-raw", "-T", "--upload-file", "-F", "--form", "--json")
                         or a.startswith(("--data=", "-d@")) for a in args)
            sends_file = any(a.startswith("@") or "@" in a and a.split("@", 1)[0] in ("", "file", "data") for a in args)
            nc_feed = prog in ("nc", "ncat", "netcat") and bool(re.search(r"<|\|\s*(?:nc|ncat|netcat)\b|\s-e\s", cmd_text))
            if any(is_sensitive_read(x) for x in args) and prog in ("curl", "wget", "http", "httpie"):
                out.append(Finding("leitura_env", 0.9, "Lê arquivo sensível para enviar", "shell"))
            if foreign and (upload or sends_file or nc_feed or prog in ("scp", "rsync")):
                sensitive = any(is_sensitive_read(a) for a in args)
                out.append(Finding("exfiltracao_ferramenta", 0.9 if sensitive else 0.75,
                                   "Envio de dados para host externo", "shell"))
        # --- pacotes
        if prog in PKG and any(a in ("install", "add", "i", "get") for a in args[:2]):
            risky = [a for a in args if a.startswith(("http://", "git+", "http", "--index-url", "--extra-index-url", "-i"))
                     or "://" in a or a in ("--no-verify", "--trusted-host", "--ignore-scripts=false")]
            untrusted = any(("://" in a and not _allowed(_url_host(a), allowed)) or a == "--trusted-host" for a in args)
            if untrusted or (risky and any(a.startswith("http://") for a in args)):
                out.append(Finding("instalacao_pacote", 0.9, "Instalação de pacote de origem não padrão", "shell"))
            elif not any(a in ("-r", "--requirement", "-e", ".") or a.startswith("-r") for a in args) and \
                    not (args[:2] in (["install"], ["i"]) and len(args) <= 2):
                out.append(Finding("instalacao_pacote", 0.35, "Instalação de pacote", "shell"))
        # --- escrita
    out.extend(_writes(cmd, segs))
    return out


def _writes(cmd: str, segs: list[tuple[list[str], bool]]) -> list[Finding]:
    out = []
    for m in re.finditer(r">{1,2}\s*([^\s;&|]+)", cmd):
        tgt = m.group(1).strip("'\"")
        if SENSITIVE_WRITE.match(tgt):
            out.append(Finding("escrita_fora_projeto", 0.9, f"Redirecionamento para {tgt}", "shell"))
    for toks, _ in segs:
        prog = toks[0].split("/")[-1]
        paths = [a.strip("'\"") for a in toks[1:] if not a.startswith("-")]
        paths = [p for p in paths if p not in ("<", ">", ">>", "|")]
        targets = paths if prog == "tee" else paths[-1:]
        if prog in ("tee", "cp", "mv", "ln", "install", "touch", "mkdir", "rsync") and \
                any(SENSITIVE_WRITE.match(p) for p in targets):
            out.append(Finding("escrita_fora_projeto", 0.85, f"{prog} grava em caminho de sistema", "shell"))
    return out


def detect_file_tool(ctx: Context) -> list[Finding]:
    """Ferramentas de edição de arquivo (Write/Edit/Read) com `file_path` em tool_input."""
    ti = ctx.tool_input or {}
    path = ti.get("file_path") or ti.get("path")
    if not isinstance(path, str):
        return []
    name = (ctx.tool_name or "").lower()
    out = []
    if name in ("write", "edit", "multiedit", "notebookedit") and (SENSITIVE_WRITE.match(path) or ".." in path.split("/")):
        out.append(Finding("escrita_fora_projeto", 0.9, f"Escrita em {path}", "file"))
    if name in ("read",) and is_sensitive_read(path):
        out.append(Finding("leitura_env", 0.9, f"Leitura de {path}", "file"))
    return out


def detect(ctx: Context) -> list[Finding]:
    out = detect_file_tool(ctx)
    cmd = ctx.command
    if cmd:
        out += detect_command(cmd, ctx.allowed_hosts)
    return out
