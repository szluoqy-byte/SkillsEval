from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


ALLOWED_FRONTMATTER_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
SCRIPT_SUFFIXES = {".py", ".sh", ".js", ".ts", ".bash"}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
    ".sh",
    ".js",
    ".ts",
    ".bash",
    ".env",
}
SAFE_DOMAINS = {"example.com", "example.org", "localhost", "127.0.0.1"}
RESERVED_WORDS = {"anthropic", "claude"}
STANDARD_SCAN_DIRS = {"scripts", "agents"}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    item: str
    severity: str
    title: str
    fix: str


@dataclass
class ParsedSkillMd:
    path: Path | None
    relative_path: str | None
    content: str
    body: str
    frontmatter: dict[str, Any]
    parse_error: str | None = None
    frontmatter_closed: bool = False
    frontmatter_is_mapping: bool = True
    frontmatter_line_count: int = 0


RULES: dict[str, Rule] = {}


def register(rule_id: str, category: str, item: str, severity: str, title: str, fix: str) -> None:
    RULES[rule_id] = Rule(rule_id, category, item, severity, title, fix)


def _register_rules() -> None:
    register("STRUCT-001", "Structure", "Skill must be a directory", "critical", "Skill package root is not a directory", "Package the skill as a directory containing SKILL.md.")
    register("STRUCT-002", "Structure", "SKILL.md exists", "critical", "Skill Markdown file is missing", "Add SKILL.md to the skill root.")
    register("FRONTMATTER-001", "Frontmatter", "YAML frontmatter exists", "critical", "SKILL.md must start with YAML frontmatter", "Start SKILL.md with a YAML frontmatter block delimited by --- lines.")
    register("FRONTMATTER-002", "Frontmatter", "YAML frontmatter closes", "critical", "YAML frontmatter is not closed", "Add the closing --- line after frontmatter.")
    register("FRONTMATTER-003", "Frontmatter", "YAML frontmatter parses", "critical", "YAML frontmatter is invalid", "Use key-value YAML frontmatter with valid scalar or mapping values.")
    register("FRONTMATTER-004", "Frontmatter", "YAML frontmatter mapping", "critical", "YAML frontmatter must be a mapping", "Use key-value fields at the top level.")
    register("FRONTMATTER-005", "Frontmatter", "name exists", "critical", "Frontmatter is missing name", "Add a name field.")
    register("FRONTMATTER-006", "Frontmatter", "description exists", "critical", "Frontmatter is missing description", "Add a description field.")
    register("FRONTMATTER-007", "Frontmatter", "No unknown fields", "critical", "Frontmatter contains unexpected fields", "Keep only name, description, license, allowed-tools, metadata, and compatibility.")
    register("NAME-001", "Name", "name type", "critical", "name must be a string", "Set name to a non-empty lowercase string.")
    register("NAME-002", "Name", "name non-empty", "critical", "name cannot be empty", "Set name to a non-empty lowercase string.")
    register("NAME-003", "Name", "name NFKC normalized", "critical", "name changes after NFKC normalization", "Use the normalized name value in SKILL.md.")
    register("NAME-004", "Name", "name length", "critical", "name must be 1-64 characters", "Shorten name to 64 characters or fewer.")
    register("NAME-005", "Name", "name lowercase", "critical", "name must be lowercase", "Use lowercase characters in name.")
    register("NAME-006", "Name", "name character set", "critical", "name contains invalid characters", "Use Unicode lowercase alphanumeric characters and hyphens only.")
    register("NAME-007", "Name", "name start hyphen", "critical", "name cannot start with hyphen", "Remove the leading hyphen.")
    register("NAME-008", "Name", "name end hyphen", "critical", "name cannot end with hyphen", "Remove the trailing hyphen.")
    register("NAME-009", "Name", "name repeated hyphen", "critical", "name cannot contain consecutive hyphens", "Replace repeated hyphens with a single hyphen.")
    register("NAME-010", "Name", "name matches parent directory", "critical", "name must match the skill directory name", "Rename the skill directory or frontmatter name so they match.")
    register("DESCRIPTION-001", "Description", "description type", "critical", "description must be a string", "Set description to a non-empty string.")
    register("DESCRIPTION-002", "Description", "description non-empty", "critical", "description cannot be empty", "Write a concise capability description.")
    register("DESCRIPTION-003", "Description", "description length", "critical", "description must be 1-1024 characters", "Shorten description to 1024 characters or fewer.")
    register("OPTIONAL-002", "Optional Fields", "compatibility type", "major", "compatibility must be a string", "Set compatibility to a string.")
    register("OPTIONAL-003", "Optional Fields", "compatibility length", "major", "compatibility must be 1-500 characters", "Keep compatibility between 1 and 500 characters.")
    register("OPTIONAL-004", "Optional Fields", "compatibility non-empty", "critical", "compatibility cannot be empty when provided", "Remove compatibility or set a non-empty string.")
    register("OPTIONAL-006", "Optional Fields", "metadata mapping", "major", "metadata should be a mapping", "Use metadata as a key-value mapping.")
    register("OPTIONAL-008", "Optional Fields", "allowed-tools format", "critical", "allowed-tools must be a space-separated string", "Use a space-separated allowed-tools string.")
    register("BODY-001", "Body", "Markdown body exists", "critical", "SKILL.md body cannot be empty", "Add instructions after the frontmatter block.")
    register("BODY-002", "Body", "SKILL.md line count", "major", "SKILL.md should be under 500 lines", "Move long reference material into referenced files.")
    register("BODY-003", "Body", "Instruction token estimate", "major", "Instructions should be under 5000 estimated tokens", "Reduce main instructions or move detail into references.")
    register("FILE-001", "File Reference", "Relative references", "critical", "File references must be relative", "Use paths relative to the skill root.")
    register("FILE-003", "File Reference", "Referenced files exist", "critical", "Referenced file does not exist", "Add the referenced file or update the path.")
    register("FILE-004", "File Reference", "References stay in root", "critical", "Referenced file escapes the skill root", "Do not reference files outside the skill package.")
    register("FILE-005", "File Reference", "Reference depth", "minor", "File references should stay one level deep", "Keep referenced files directly under one folder from SKILL.md.")
    register("FILE-006", "File Reference", "Reference chain depth", "minor", "Avoid deeply nested reference chains", "Flatten reference chains and link directly from SKILL.md.")
    register("AWS-STR-016", "Structure Quality", "README and SKILL.md coexist", "minor", "README.md beside SKILL.md can confuse entry points", "Keep README concise or move details into SKILL.md/references.")
    register("AWS-STR-017", "Script Quality", "Script shebang", "minor", "Script is missing a shebang", "Add a shebang to executable scripts.")
    register("AWS-STR-018", "Structure Quality", "Reserved name words", "major", "Skill name contains a reserved word", "Remove vendor-reserved terms from the skill name.")
    register("AWS-STR-019", "Description Quality", "Description XML/HTML", "major", "description should not contain XML/HTML tags", "Remove markup from description.")
    register("AWS-STR-020", "Description Quality", "Description perspective", "minor", "description should avoid first or second person", "Use capability-oriented description text.")
    register("AWS-SEC-001", "Security", "Hardcoded secret", "critical", "Potential hardcoded secret detected", "Remove secrets and use environment or secret storage.")
    register("AWS-SEC-002", "Security", "External URL surface", "major", "External URL or endpoint detected", "Review external endpoints and document why they are needed.")
    register("AWS-SEC-003", "Security", "Subprocess or dynamic execution", "major", "Command or dynamic code execution detected", "Avoid executing shell commands or user-provided code.")
    register("AWS-SEC-004", "Security", "Unsafe dependency install", "critical", "Unsafe dependency install pattern detected", "Use pinned lockfiles or requirements files; avoid curl | sh.")
    register("AWS-SEC-005", "Security", "Prompt injection surface", "major", "Prompt injection surface detected", "Constrain user input handling and document boundaries.")
    register("AWS-SEC-006", "Security", "Unsafe deserialization", "critical", "Unsafe deserialization detected", "Use safe parsers such as json or yaml.safe_load.")
    register("AWS-SEC-007", "Security", "Dynamic import/code generation", "major", "Dynamic import or code generation detected", "Prefer static imports and auditable execution paths.")
    register("AWS-SEC-008", "Security", "Base64 payload", "major", "Base64 payload or obfuscation detected", "Avoid obfuscated payloads and decode-only-then-execute patterns.")
    register("AWS-SEC-009", "Security", "MCP supply chain", "major", "MCP configuration or supply-chain risk detected", "Review MCP servers and avoid implicit external package execution.")
    register("AWS-PERM-001", "Permission", "Unrestricted shell", "major", "allowed-tools grants unrestricted shell access", "Scope shell permissions narrowly or remove them.")
    register("AWS-PERM-002", "Permission", "High-risk tool", "minor", "allowed-tools includes high-risk tools", "Review high-risk tools and reduce permission scope.")
    register("AWS-PERM-003", "Permission", "Too many tools", "minor", "allowed-tools grants too many tools", "Limit allowed-tools to the minimum required set.")
    register("AWS-PERM-004", "Permission", "Implicit permission need", "major", "Skill text implies sensitive permissions", "Remove sensitive access or make permission boundaries explicit.")


_register_rules()


def scan_skill_version(artifact_root: str | Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(artifact_root)
    manifest = manifest or {}
    scanner = StaticScanner(root, manifest)
    findings = scanner.scan()
    counts = severity_counts(findings)
    score = static_score(counts)
    return {
        "score": score,
        "status": scan_status(counts),
        "summary": summarize(counts),
        "metrics": {
            **counts,
            "total_findings": len(findings),
            "rules_evaluated": len(RULES),
            "files_scanned": scanner.files_scanned,
        },
        "findings": findings,
    }


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical_count": 0, "major_count": 0, "minor_count": 0, "info_count": 0}
    for finding in findings:
        severity = finding["severity"]
        key = f"{severity}_count"
        if key in counts:
            counts[key] += 1
    return counts


def static_score(counts: dict[str, int]) -> float:
    value = 100 - counts["critical_count"] * 25 - counts["major_count"] * 10 - counts["minor_count"] * 3 - counts["info_count"]
    return float(max(0, min(100, value)))


def scan_status(counts: dict[str, int]) -> str:
    if counts["critical_count"]:
        return "critical"
    if counts["major_count"] or counts["minor_count"]:
        return "warning"
    return "passed"


def summarize(counts: dict[str, int]) -> str:
    if counts["critical_count"]:
        return f"Static scan found {counts['critical_count']} critical findings."
    if counts["major_count"] or counts["minor_count"]:
        return f"Static scan found {counts['major_count']} major and {counts['minor_count']} minor findings."
    return "Static scan found no active findings."


class StaticScanner:
    def __init__(self, root: Path, manifest: dict[str, Any]) -> None:
        self.root = root
        self.manifest = manifest
        self.findings: list[dict[str, Any]] = []
        self.files_scanned = 0

    def scan(self) -> list[dict[str, Any]]:
        if not self.root.exists() or not self.root.is_dir():
            self.add("STRUCT-001", None, None, str(self.root))
            return self.findings
        skill_md = self.parse_skill_md()
        self.scan_frontmatter_and_body(skill_md)
        self.scan_file_references(skill_md)
        self.scan_structure_quality(skill_md)
        self.scan_files_for_security(skill_md)
        self.scan_permissions(skill_md)
        return self.findings

    def add(self, rule_id: str, file_path: str | None = None, line_number: int | None = None, context: str | None = None, severity: str | None = None) -> None:
        rule = RULES[rule_id]
        detail = rule.title if context is None else f"{rule.title}: {context}"
        self.findings.append(
            {
                "code": rule.rule_id,
                "severity": severity or rule.severity,
                "title": rule.title,
                "detail": detail,
                "file_path": file_path,
                "line_number": line_number,
                "fix": rule.fix,
            }
        )

    def relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def parse_skill_md(self) -> ParsedSkillMd:
        candidates = [self.root / "SKILL.md", self.root / "skill.md"]
        path = next((candidate for candidate in candidates if candidate.exists() and candidate.is_file()), None)
        if path is None:
            self.add("STRUCT-002")
            return ParsedSkillMd(None, None, "", "", {})
        content = read_text(path)
        parsed = parse_skill_markdown(content)
        parsed.path = path
        parsed.relative_path = self.relative(path)
        return parsed

    def scan_frontmatter_and_body(self, skill_md: ParsedSkillMd) -> None:
        if skill_md.path is None:
            return
        rel = skill_md.relative_path
        if not skill_md.content.lstrip().startswith("---"):
            self.add("FRONTMATTER-001", rel, 1)
            return
        if not skill_md.frontmatter_closed:
            self.add("FRONTMATTER-002", rel, 1)
        if skill_md.parse_error:
            self.add("FRONTMATTER-003", rel, 1, skill_md.parse_error)
        if not skill_md.frontmatter_is_mapping:
            self.add("FRONTMATTER-004", rel, 1)

        metadata = skill_md.frontmatter
        missing = [("name", "FRONTMATTER-005"), ("description", "FRONTMATTER-006")]
        for field, rule_id in missing:
            if field not in metadata:
                self.add(rule_id, rel, 1)
        unknown = sorted(set(metadata) - ALLOWED_FRONTMATTER_FIELDS)
        if unknown:
            self.add("FRONTMATTER-007", rel, 1, ", ".join(unknown))

        self.scan_name(metadata.get("name"), rel)
        self.scan_description(metadata.get("description"), rel)
        self.scan_optional_fields(metadata, rel)

        if not skill_md.body.strip():
            self.add("BODY-001", rel, 1)
        if len(skill_md.content.splitlines()) > 500:
            self.add("BODY-002", rel, 501, f"{len(skill_md.content.splitlines())} lines")
        estimated_tokens = max(1, len(re.findall(r"\S+", skill_md.content)))
        if estimated_tokens > 5000:
            self.add("BODY-003", rel, None, f"estimated {estimated_tokens} tokens")

    def scan_name(self, value: Any, rel: str | None) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            self.add("NAME-001", rel, 1)
            return
        raw = value.strip()
        normalized = unicodedata.normalize("NFKC", raw)
        if not raw:
            self.add("NAME-002", rel, 1)
            return
        if normalized != raw:
            self.add("NAME-003", rel, 1, normalized)
        if len(normalized) > 64:
            self.add("NAME-004", rel, 1, f"{len(normalized)} characters")
        if normalized != normalized.lower():
            self.add("NAME-005", rel, 1, normalized)
        if any(not (char.isalnum() or char == "-") for char in normalized):
            self.add("NAME-006", rel, 1, normalized)
        if normalized.startswith("-"):
            self.add("NAME-007", rel, 1)
        if normalized.endswith("-"):
            self.add("NAME-008", rel, 1)
        if "--" in normalized:
            self.add("NAME-009", rel, 1)
        original_parent = skill_parent_from_manifest(self.manifest)
        if original_parent and unicodedata.normalize("NFKC", original_parent.strip()) != normalized:
            self.add("NAME-010", rel, 1, f"name={normalized}, directory={original_parent}")
        if any(word in normalized.lower() for word in RESERVED_WORDS):
            self.add("AWS-STR-018", rel, 1, normalized)

    def scan_description(self, value: Any, rel: str | None) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            self.add("DESCRIPTION-001", rel, 1)
            return
        if not value.strip():
            self.add("DESCRIPTION-002", rel, 1)
        if len(value) > 1024:
            self.add("DESCRIPTION-003", rel, 1, f"{len(value)} characters")
        if re.search(r"<[a-zA-Z][^>]*>", value):
            self.add("AWS-STR-019", rel, 1)
        if re.search(r"\b(I|we)\s+can\b", value, re.IGNORECASE) or re.search(r"\byou\s+can\b", value, re.IGNORECASE):
            self.add("AWS-STR-020", rel, 1)

    def scan_optional_fields(self, metadata: dict[str, Any], rel: str | None) -> None:
        compatibility = metadata.get("compatibility")
        if "compatibility" in metadata:
            if not isinstance(compatibility, str):
                self.add("OPTIONAL-002", rel, 1)
            else:
                if len(compatibility) > 500:
                    self.add("OPTIONAL-003", rel, 1, f"{len(compatibility)} characters")
                if not compatibility.strip():
                    self.add("OPTIONAL-004", rel, 1)
        if "metadata" in metadata and not isinstance(metadata["metadata"], dict):
            self.add("OPTIONAL-006", rel, 1)
        if "allowed-tools" in metadata and not isinstance(metadata["allowed-tools"], str):
            self.add("OPTIONAL-008", rel, 1)

    def scan_file_references(self, skill_md: ParsedSkillMd) -> None:
        if skill_md.path is None:
            return
        refs = extract_local_refs(skill_md.body)
        for ref in refs:
            if is_absolute_ref(ref):
                self.add("FILE-001", skill_md.relative_path, None, ref)
                continue
            normalized = PurePosixPath(ref)
            if ".." in normalized.parts:
                self.add("FILE-004", skill_md.relative_path, None, ref)
                continue
            target = (self.root / Path(*normalized.parts)).resolve()
            try:
                target.relative_to(self.root.resolve())
            except ValueError:
                self.add("FILE-004", skill_md.relative_path, None, ref)
                continue
            if not target.exists():
                self.add("FILE-003", skill_md.relative_path, None, ref)
                continue
            if len([part for part in normalized.parts if part not in {"."}]) > 2:
                self.add("FILE-005", skill_md.relative_path, None, ref)
        if reference_chain_depth(self.root, refs) > 2:
            self.add("FILE-006", skill_md.relative_path)

    def scan_structure_quality(self, skill_md: ParsedSkillMd) -> None:
        if skill_md.path and (self.root / "README.md").exists():
            self.add("AWS-STR-016", "README.md")
        scripts_dir = self.root / "scripts"
        if scripts_dir.exists():
            for path in scripts_dir.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".sh"}:
                    first_line = read_text(path).splitlines()[0] if read_text(path).splitlines() else ""
                    if not first_line.startswith("#!"):
                        self.add("AWS-STR-017", self.relative(path), 1)

    def scan_files_for_security(self, skill_md: ParsedSkillMd) -> None:
        for path in self.iter_standard_scan_files():
            self.files_scanned += 1
            rel = self.relative(path)
            text = read_text(path)
            lines = text.splitlines()
            for index, line in enumerate(lines, start=1):
                self.scan_line_security(path, rel, line, index)
            if re.search(r"base64\.(b64decode|decodebytes)|atob\(", text):
                severity = "critical" if re.search(r"(eval|exec)\s*\(", text) else "major"
                self.add("AWS-SEC-008", rel, None, "base64 decode call", severity)
            if re.search(r"[A-Za-z0-9+/]{120,}={0,2}", text):
                self.add("AWS-SEC-008", rel, None, "long base64-like payload")

    def scan_line_security(self, path: Path, rel: str, line: str, line_number: int) -> None:
        stripped = line.strip()
        if secret_pattern(line) and not is_allowlisted_secret(line):
            self.add("AWS-SEC-001", rel, line_number)
        for url in re.findall(r"https?://[^\s)'\"<>]+", line):
            if safe_url(url):
                continue
            severity = "minor" if stripped.startswith(("#", "//")) or path.suffix == ".md" else "major"
            self.add("AWS-SEC-002", rel, line_number, url, severity)
        if re.search(r"(curl|wget).*\|\s*(sh|bash|zsh)", line):
            self.add("AWS-SEC-004", rel, line_number, severity="critical")
        if path.suffix in SCRIPT_SUFFIXES:
            if re.search(r"\b(subprocess\.(run|call|Popen|check_output)|os\.system|os\.popen|shell\s*=\s*True|eval\s*\(|exec\s*\()", line):
                self.add("AWS-SEC-003", rel, line_number)
            if unsafe_install_pattern(line):
                severity = "critical" if re.search(r"(curl|wget).*\|\s*(sh|bash|zsh)", line) else "major"
                self.add("AWS-SEC-004", rel, line_number, severity=severity)
            if re.search(r"\b(pickle|cPickle|marshal)\.(load|loads)\b|shelve\.open\b", line):
                self.add("AWS-SEC-006", rel, line_number, severity="critical")
            if "yaml.load" in line and "safe_load" not in line and "SafeLoader" not in line:
                self.add("AWS-SEC-006", rel, line_number, "yaml.load without SafeLoader", "major")
            if re.search(r"\b(importlib\.import_module|__import__|compile)\s*\(", line):
                self.add("AWS-SEC-007", rel, line_number)
        if re.search(r"\b(read|accept|take|use|process)\s+(any|all|user|any user|all user)\s+(input|content|data|text)\b", line, re.IGNORECASE):
            self.add("AWS-SEC-005", rel, line_number)
        if re.search(r"\b(run|execute|eval)\s+(user|provided).*(code|command|script|query)\b", line, re.IGNORECASE):
            self.add("AWS-SEC-005", rel, line_number)
        if re.search(r"\b(write|save|create)\s+to\s+(any|user|given).*(path|location|directory|file)\b", line, re.IGNORECASE):
            self.add("AWS-SEC-005", rel, line_number)
        if re.search(r"\bmcpServers\b|\bmcp_servers\b|npx\s+-y\b|https?://[^\s)'\"<>]+/(mcp|sse)\b", line):
            severity = "critical" if "npx -y" in line else "major"
            self.add("AWS-SEC-009", rel, line_number, severity=severity)

    def scan_permissions(self, skill_md: ParsedSkillMd) -> None:
        metadata = skill_md.frontmatter
        rel = skill_md.relative_path
        tools = parse_allowed_tools(metadata.get("allowed-tools"))
        unrestricted = {"bash", "bash(*)", "shell", "terminal"}
        risk_tools = {"bash", "shell", "execute", "httprequest", "terminal"}
        if any(tool.lower() in unrestricted for tool in tools):
            self.add("AWS-PERM-001", rel, 1)
        high_risk = [tool for tool in tools if tool.split("(", 1)[0].lower() in risk_tools]
        if high_risk:
            self.add("AWS-PERM-002", rel, 1, ", ".join(high_risk))
        if len(tools) > 15:
            self.add("AWS-PERM-003", rel, 1, f"{len(tools)} tools")
        for path in self.iter_standard_scan_files():
            rel_path = self.relative(path)
            for index, line in enumerate(read_text(path).splitlines(), start=1):
                if re.search(r"(~/(?:\.ssh|\.aws|\.kube)|/etc/passwd|sudo|as root|root access|0\.0\.0\.0|all interfaces|credentials|password|token|private key)", line, re.IGNORECASE):
                    severity = "major" if re.search(r"(~/(?:\.ssh|\.aws|\.kube)|sudo|root|credentials|password|token|private key)", line, re.IGNORECASE) else "minor"
                    self.add("AWS-PERM-004", rel_path, index, severity=severity)

    def iter_standard_scan_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or not should_read_text(path):
                continue
            try:
                rel = path.relative_to(self.root)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) == 1 or parts[0] in STANDARD_SCAN_DIRS:
                files.append(path)
        return sorted(files)


def parse_skill_markdown(content: str) -> ParsedSkillMd:
    parsed = ParsedSkillMd(None, None, content, content, {})
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return parsed
    close_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_index = index
            break
    if close_index is None:
        parsed.frontmatter_line_count = max(0, len(lines) - 1)
        return parsed
    parsed.frontmatter_closed = True
    frontmatter_lines = lines[1:close_index]
    parsed.frontmatter_line_count = len(frontmatter_lines)
    parsed.body = "\n".join(lines[close_index + 1 :])
    metadata, error, is_mapping = parse_frontmatter_lines(frontmatter_lines)
    parsed.frontmatter = metadata
    parsed.parse_error = error
    parsed.frontmatter_is_mapping = is_mapping
    return parsed


def parse_frontmatter_lines(lines: list[str]) -> tuple[dict[str, Any], str | None, bool]:
    metadata: dict[str, Any] = {}
    current_map: str | None = None
    is_mapping = True
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and current_map:
            if ":" not in raw:
                return metadata, f"invalid nested frontmatter line: {raw.strip()}", is_mapping
            key, value = raw.strip().split(":", 1)
            if not isinstance(metadata.get(current_map), dict):
                metadata[current_map] = {}
            metadata[current_map][key.strip()] = parse_scalar(value.strip())
            continue
        current_map = None
        if raw.lstrip().startswith("-"):
            is_mapping = False
            return metadata, None, is_mapping
        if ":" not in raw:
            return metadata, f"invalid frontmatter line: {raw.strip()}", is_mapping
        key, value = raw.split(":", 1)
        clean_key = key.strip()
        if not clean_key:
            return metadata, "empty frontmatter key", is_mapping
        clean_value = value.strip()
        if clean_value == "":
            metadata[clean_key] = {}
            current_map = clean_key
        else:
            metadata[clean_key] = parse_scalar(clean_value)
    return metadata, None, is_mapping


def parse_scalar(value: str) -> Any:
    clean = value.strip()
    if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
        return clean[1:-1]
    if clean in {"true", "false"}:
        return clean == "true"
    return clean


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def should_read_text(path: Path) -> bool:
    if path.suffix in TEXT_SUFFIXES:
        return True
    if path.name in {"SKILL.md", "skill.md", "README.md"}:
        return True
    return False


def skill_parent_from_manifest(manifest: dict[str, Any]) -> str | None:
    skill_md_path = manifest.get("skill_md_path")
    if not isinstance(skill_md_path, str):
        return None
    parent = PurePosixPath(skill_md_path).parent
    if str(parent) == ".":
        return None
    return parent.name


def extract_local_refs(markdown: str) -> list[str]:
    refs: list[str] = []
    refs.extend(match.strip() for match in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown))
    refs.extend(match.strip() for match in re.findall(r"`((?:references|scripts|assets|agents)/[^`]+)`", markdown))
    clean_refs: list[str] = []
    for ref in refs:
        target = ref.split("#", 1)[0].strip()
        if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            continue
        clean_refs.append(target)
    return clean_refs


def is_absolute_ref(ref: str) -> bool:
    return ref.startswith(("/", "~/")) or bool(re.match(r"^[a-zA-Z]:[\\/]", ref))


def reference_chain_depth(root: Path, refs: list[str]) -> int:
    max_depth = 0
    seen: set[Path] = set()

    def walk(ref: str, depth: int) -> None:
        nonlocal max_depth
        if is_absolute_ref(ref) or ".." in PurePosixPath(ref).parts:
            return
        path = root / ref
        if path in seen or not path.exists() or path.suffix.lower() != ".md":
            max_depth = max(max_depth, depth)
            return
        seen.add(path)
        nested = extract_local_refs(read_text(path))
        if not nested:
            max_depth = max(max_depth, depth)
            return
        for item in nested:
            walk(item, depth + 1)

    for ref in refs:
        walk(ref, 1)
    return max_depth


def secret_pattern(line: str) -> bool:
    patterns = [
        r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"][^'\"]{12,}['\"]",
        r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
        r"(?i)(postgres|mysql|mongodb)://[^\\s]+:[^\\s]+@",
        r"sk-[A-Za-z0-9]{20,}",
    ]
    return any(re.search(pattern, line) for pattern in patterns)


def is_allowlisted_secret(line: str) -> bool:
    return bool(re.search(r"(?i)(example|dummy|test|placeholder|your[_-]?api[_-]?key|changeme)", line))


def safe_url(url: str) -> bool:
    try:
        host = re.sub(r"^www\.", "", re.match(r"https?://([^/:]+)", url).group(1).lower())  # type: ignore[union-attr]
    except AttributeError:
        return False
    return host in SAFE_DOMAINS


def unsafe_install_pattern(line: str) -> bool:
    if re.search(r"\bpip\s+install\b", line) and "pip install -r" not in line:
        return True
    return bool(re.search(r"\bnpm\s+install\b", line))


def parse_allowed_tools(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in re.split(r"\s+", value.strip()) if part.strip()]


def dumps_artifact(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": scan["score"],
        "status": scan["status"],
        "summary": scan["summary"],
        "metrics": scan["metrics"],
        "findings": scan["findings"],
        "rules": [rule.__dict__ for rule in RULES.values()],
    }


def encoded_sample_base64() -> str:
    return base64.b64encode(b"sample").decode("ascii")
