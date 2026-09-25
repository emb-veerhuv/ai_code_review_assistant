from __future__ import annotations
import re
from pathlib import PurePosixPath
from .models import Finding




def finding(
   rule_id: str,
   category: str,
   severity: str,
   path: str,
   line: int,
   title: str,
   evidence: str,
   remediation: str,
   confidence: float = .9,
   source: str = "deterministic",
   suggested_change: str | None = None,
   verification: str | None = None,
   suggested_patch: str = ""
) -> Finding:
   # Normalize rule_id to avoid duplicates (e.g., FILE-001 deterministic vs OpenAI)
   rule_id = rule_id.split()[0]
   return {
       "rule_id": rule_id,
       "category": category,
       "severity": severity.capitalize(),
       "file": path,
       "line": line,
       "title": title,
       "evidence": evidence,
       "remediation": remediation,
       "suggested_change": suggested_change or remediation,
       "verification": verification or "Run the target build and relevant unit or integration tests.",
       "suggested_patch": suggested_patch,
       "confidence": confidence,
       "source": source,
   }




def language_for(path: str, rules: dict) -> str:
   return rules.get("repository", {}).get("source_extension_map", {}).get(PurePosixPath(path).suffix.lower(), "")




def scan_checklist(path: str, text: str, rules: dict) -> list[Finding]:
   lang = language_for(path, rules)
   output = []
   for rule in rules.get("checklist", []):
       if lang not in rule.get("applies_to", ["c", "cpp"]):
           continue
       pattern = rule.get("pattern")
       if not pattern:
           continue
       try:
           matcher = re.compile(pattern)
       except re.error:
           continue
       for n, line in enumerate(text.splitlines(), 1):
           if matcher.search(line):
               output.append(
                   finding(
                       rule.get("id", "CUSTOM"),
                       "checklist",
                       rule.get("severity", "medium"),
                       path,
                       n,
                       rule.get("title", "Custom rule"),
                       rule.get("message", "Pattern matched"),
                       rule.get("remediation", "Review the pattern."),
                   )
               )
   return output




def scan_repository(paths: list[str], files: dict[str, str], rules: dict) -> list[Finding]:
   out = []
   # Default allowed extensions if YAML doesn’t specify
   allowed = set(rules.get("repository", {}).get("allowed_file_extensions", [".c", ".cpp", ".cc", ".h", ".hpp"]))
   file_rules = rules.get("files", {})
   src_re = re.compile(file_rules.get("source_regex", r"^[a-z][a-z0-9_]*\.(c|cpp|cc)$"))
   hdr_re = re.compile(file_rules.get("header_regex", r"^[a-z][a-z0-9_]*\.(h|hpp)$"))
   roots = set(rules.get("repository", {}).get("source_roots", []))
   max_lines = int(rules.get("repository", {}).get("max_source_file_lines", 500))
   for path in paths:
       p = PurePosixPath(path)
       ext = p.suffix.lower()
       if ext and ext not in allowed:
           out.append(
               finding(
                   "FILE-001",
                   "structure",
                   "medium",
                   path,
                   1,
                   "Unsupported file extension",
                   ext,
                   "Move generated or unrelated files outside the reviewed source tree.",
               )
           )
       if len(p.parts) and roots and p.parts[0] not in roots:
           out.append(
               finding(
                   "DIR-001",
                   "structure",
                   "medium",
                   path,
                   1,
                   "Unexpected top-level folder",
                   p.parts[0],
                   "Place source under an approved folder such as src, include or tests.",
               )
           )
       if ext in {".c", ".cpp", ".cc"} and not src_re.match(p.name):
           out.append(
               finding(
                   "FILE-002",
                   "naming",
                   "medium",
                   path,
                   1,
                   "Source file name violates convention",
                   p.name,
                   "Use lower_snake_case for source names.",
               )
           )
       if ext in {".h", ".hpp"} and not hdr_re.match(p.name):
           out.append(
               finding(
                   "FILE-003",
                   "naming",
                   "medium",
                   path,
                   1,
                   "Header file name violates convention",
                   p.name,
                   "Use lower_snake_case for header names.",
               )
           )
       if ext in {".c", ".cpp", ".cc", ".h", ".hpp"} and len(files.get(path, "").splitlines()) > max_lines:
           out.append(
               finding(
                   "FILE-004",
                   "maintainability",
                   "low",
                   path,
                   max_lines,
                   "File is too large",
                   f"{len(files[path].splitlines())} lines",
                   "Split responsibilities into smaller translation units.",
               )
           )
   return out




def scan_classes(path: str, text: str, rules: dict) -> list[Finding]:
   regex = rules.get("classes", {}).get("regex", r"^[A-Z][A-Za-z0-9]*$")
   matcher = re.compile(regex)
   out = []
   if PurePosixPath(path).suffix.lower() not in {".cpp", ".hpp", ".cc", ".h"}:
       return out
   for n, line in enumerate(text.splitlines(), 1):
       for kind, name in re.findall(r"\b(class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)", line):
           if kind == "struct" and not rules.get("classes", {}).get("check_structs", True):
               continue
           if not matcher.fullmatch(name):
               out.append(
                   finding(
                       "NAME-001",
                       "naming",
                       "medium",
                       path,
                       n,
                       f"{kind.capitalize()} name violates convention",
                       name,
                       "Use PascalCase, for example MotorController.",
                   )
               )
   return out




def scan_includes(path: str, text: str, rules: dict) -> list[Finding]:
   if not rules.get("includes", {}).get("require_system_before_local", True):
       return []
   seen_local = False
   for n, line in enumerate(text.splitlines(), 1):
       if re.match(r"^\s*#include\s+\"", line):
           seen_local = True
       elif seen_local and re.match(r"^\s*#include\s+<", line):
           return [
               finding(
                   "INC-001",
                   "maintainability",
                   "low",
                   path,
                   n,
                   "System include follows local include",
                   line.strip(),
                   "Group angle-bracket includes before quoted project includes.",
                   .82,
               )
           ]
   return []




def generate_docs(path: str, text: str) -> list[dict]:
   docs = []
   lines = text.splitlines()
   for n, line in enumerate(lines, 1):
       m = re.search(r"\b(class|struct)\s+([A-Za-z_]\w*)", line)
       recent_lines = lines[max(0, n - 3):n]
       if m and not any("/**" in l for l in recent_lines):
           docs.append({
               "file": path,
               "line": n,
               "symbol": m.group(2),
               "comment": f"/** {m.group(2)} represents a documented {m.group(1)}. Add responsibilities, invariants, ownership and thread-safety guarantees. */"
           })
   return docs