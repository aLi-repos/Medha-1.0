"""Secure Analysis Pipeline — security tests.

28 test scenarios covering:
- Authentication for analysis endpoints
- RBAC authorization for analysis actions
- Task Passport enforcement in analysis pipeline
- Tool validation and blocked actions
- Handover approval/rejection security
- Input validation
- Data classification verification
- Pipeline integrity checks
"""

import pytest
from fastapi.testclient import TestClient


# ── Authentication Tests ──

class TestAnalysisAuth:
    def test_run_analysis_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/analysis/run", json={"task_id": "test-123"})
        assert resp.status_code == 401

    def test_handover_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/analysis/handover", json={"task_id": "test-123", "approved": True})
        assert resp.status_code == 401

    def test_excel_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/analysis/excel", json={"task_id": "test-123"})
        assert resp.status_code == 401

    def test_dataset_endpoint_public(self, client: TestClient) -> None:
        resp = client.get("/api/analysis/dataset")
        assert resp.status_code == 200
        data = resp.json()
        assert "failures" in data
        assert "equipment" in data
        assert data["equipment"]["id"] == "P-204"

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": "test-123"},
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401


# ── RBAC Tests ──

class TestAnalysisRBAC:
    def test_operator_can_run_analysis(self, client: TestClient, operator_token: str) -> None:
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Analysis Task", "purpose": "Pump analysis"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["pipeline_events"]

    def test_engineer_can_run_analysis(self, client: TestClient, engineer_token: str) -> None:
        headers = {"Authorization": f"Bearer {engineer_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Analysis Task", "purpose": "Pump analysis"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_admin_can_approve_handover(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Analysis Task", "purpose": "Pump analysis"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/handover",
            json={"task_id": task_id, "approved": True, "reason": "Approved for release"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["handover_status"] == "approved"

    def test_reject_handover(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Analysis Task", "purpose": "Pump analysis"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/handover",
            json={"task_id": task_id, "approved": False, "reason": "Insufficient data"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["handover_status"] == "rejected"


# ── Pipeline Integrity Tests ──

class TestPipelineIntegrity:
    def test_pipeline_executes_all_stages(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Pipeline Test", "purpose": "Verify all stages"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        assert resp.status_code == 200
        events = resp.json()["pipeline_events"]
        stages = [e["stage"] for e in events]
        assert "authentication" in stages
        assert "rbac_check" in stages
        assert "task_passport" in stages
        assert "action_gate" in stages
        assert "permission_rag" in stages
        assert "model_routing" in stages
        assert "agent_planning" in stages
        assert "tool_validation" in stages
        assert "controlled_execution" in stages
        assert "output_verification" in stages
        assert "audit_trail" in stages

    def test_pipeline_has_blocked_action(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Blocked Test", "purpose": "Verify blocked tool"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        events = resp.json()["pipeline_events"]
        blocked = [e for e in events if e["status"] == "denied"]
        assert len(blocked) >= 1
        assert any("email_sender" in e["detail"] for e in blocked)

    def test_all_stages_have_timestamps(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Timestamp Test", "purpose": "Verify timestamps"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        events = resp.json()["pipeline_events"]
        for event in events:
            assert "timestamp" in event
            assert event["timestamp"]

    def test_pipeline_returns_equipment_data(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Equipment Test", "purpose": "Verify equipment info"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        data = resp.json()
        equipment = data["equipment_info"]
        assert equipment["id"] == f"TASK-{task_id[:8].upper()}"
        assert equipment["owner"] == "USR-00000004"

    def test_pipeline_returns_risk_assessment(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Risk Test", "purpose": "Verify risk assessment"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        risk = resp.json()["risk_assessment"]
        assert "risk_level" in risk
        assert "risk_score" in risk
        assert risk["risk_level"] in ("critical", "high", "moderate")

    def test_pipeline_returns_recommendations(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Recs Test", "purpose": "Verify recommendations"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        recs = resp.json()["recommendations"]
        assert len(recs) >= 3
        for rec in recs:
            assert "id" in rec
            assert "priority" in rec
            assert "action" in rec

    def test_pipeline_returns_graph_data(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Graph Test", "purpose": "Verify graph data"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        graphs = resp.json()["graph_data"]
        assert "failure_frequency" in graphs
        assert "downtime_trend" in graphs
        assert "cost_trend" in graphs
        assert len(graphs["failure_frequency"]["labels"]) > 0

    def test_data_classification_is_synthetic(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Classification Test", "purpose": "Verify data classification"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        assert resp.json()["data_classification"] == "synthetic-demo"

    def test_disclaimer_present(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Disclaimer Test", "purpose": "Verify disclaimer"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        disclaimer = resp.json()["disclaimer"]
        assert "illustrative" in disclaimer.lower() or "synthetic" in disclaimer.lower()
        assert "MRPL" in disclaimer

    def test_handover_status_starts_pending(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Handover Pending Test", "purpose": "Verify initial handover status"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": task_id},
            headers=headers,
        )
        assert resp.json()["handover_status"] == "pending"


# ── Input Validation Tests ──

class TestAnalysisInputValidation:
    def test_empty_task_id_rejected(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post(
            "/api/analysis/run",
            json={"task_id": ""},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_missing_task_id_rejected(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post(
            "/api/analysis/run",
            json={},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_handover_missing_approved_rejected(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post(
            "/api/analysis/handover",
            json={"task_id": "test-123"},
            headers=headers,
        )
        assert resp.status_code == 422


# ── Tool Registry Tests ──

class TestToolRegistry:
    def test_new_tools_registered(self) -> None:
        from app.services.agent.tool_registry import tool_registry
        tools = [t.name for t in tool_registry.list_all()]
        assert "graph_generator" in tools
        assert "excel_generator" in tools
        assert "report_generator" in tools

    def test_graph_generator_risk_level(self) -> None:
        from app.services.agent.tool_registry import tool_registry
        tool = tool_registry.get("graph_generator")
        assert tool is not None
        assert tool.risk.value == "low"
        assert tool.requires_approval is False

    def test_excel_generator_risk_level(self) -> None:
        from app.services.agent.tool_registry import tool_registry
        tool = tool_registry.get("excel_generator")
        assert tool is not None
        assert tool.risk.value == "medium"

    def test_report_generator_risk_level(self) -> None:
        from app.services.agent.tool_registry import tool_registry
        tool = tool_registry.get("report_generator")
        assert tool is not None
        assert tool.risk.value == "medium"

    def test_email_sender_requires_approval(self) -> None:
        from app.services.agent.tool_registry import tool_registry
        tool = tool_registry.get("email_sender")
        assert tool is not None
        assert tool.requires_approval is True
        assert tool.risk.value == "high"


# ── Excel Generation Tests ──

class TestExcelGeneration:
    def test_excel_endpoint_returns_workbook(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Excel Test", "purpose": "Generate Excel"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/excel",
            json={"task_id": task_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert len(resp.content) > 1000

    def test_excel_has_correct_filename(self, client: TestClient, admin_token: str) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        task = client.post(
            "/api/tasks",
            json={"title": "Excel Filename Test", "purpose": "Check filename"},
            headers=headers,
        )
        task_id = task.json()["task_id"]
        resp = client.post(
            "/api/analysis/excel",
            json={"task_id": task_id},
            headers=headers,
        )
        assert "MEDHA_Excel_Filename_Test_Secure_Analysis.xlsx" in resp.headers.get("content-disposition", "")
