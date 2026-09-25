from app.analyzers import scan_checklist, scan_classes, scan_repository
from app.main import DEFAULT_RULES


def test_dynamic_allocation_is_found():
    findings = scan_checklist("src/controller.cpp", "auto p = new Motor();", DEFAULT_RULES)
    assert any(x["rule_id"] == "C-001" for x in findings)


def test_non_pascal_class_is_found():
    findings = scan_classes("src/controller.cpp", "class motorController {};", DEFAULT_RULES)
    assert any(x["rule_id"] == "NAME-001" for x in findings)


def test_source_naming_is_found():
    findings = scan_repository(["src/MotorController.cpp"], {"src/MotorController.cpp": "int x;"}, DEFAULT_RULES)
    assert any(x["rule_id"] == "FILE-002" for x in findings)
