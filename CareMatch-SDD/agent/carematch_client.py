import httpx


class CareMatchClient:
    """Minimal HTTP client for the CareMatch API, used by agent tools."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, token: str | None = None, **kwargs) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(base_url=self.base_url, timeout=60.0) as client:
            resp = client.request(method, path, headers=headers, **kwargs)
            payload = None
            try:
                payload = resp.json()
            except Exception:
                payload = {"status_code": resp.status_code, "body": resp.text[:2000]}
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"CareMatch API {method} {path} returned {resp.status_code}: {payload}"
                )
            return payload

    # --- Auth ---
    def login(self, username: str, password: str) -> dict:
        return self._request(
            "POST", "/api/v1/auth/token", json={"username": username, "password": password}
        )

    def me(self, token: str) -> dict:
        return self._request("GET", "/api/v1/auth/me", token=token)

    # --- Trials ---
    def create_trial(
        self,
        token: str,
        trial_name: str,
        protocol_text: str | None = None,
        nct_number: str | None = None,
        rules: list | None = None,
    ) -> dict:
        body: dict = {"trial_name": trial_name}
        if protocol_text is not None:
            body["protocol_text"] = protocol_text
        if nct_number is not None:
            body["nct_number"] = nct_number
        if rules is not None:
            body["rules"] = rules
        return self._request("POST", "/api/v1/trials/create", token=token, json=body)

    def list_trials(self, token: str, offset: int = 0, limit: int = 50) -> dict:
        return self._request(
            "GET", "/api/v1/trials", token=token, params={"offset": offset, "limit": limit}
        )

    def get_trial(self, token: str, trial_id: str) -> dict:
        return self._request("GET", f"/api/v1/trials/{trial_id}", token=token)

    def update_trial(self, token: str, trial_id: str, **updates) -> dict:
        return self._request("PUT", f"/api/v1/trials/{trial_id}", token=token, json=updates)

    # --- Eligibility ---
    def evaluate(self, token: str, trial_id: str, fhir_bundle: dict) -> dict:
        return self._request(
            "POST",
            "/api/v1/patients/evaluate-eligibility",
            token=token,
            json={"trial_id": trial_id, "fhir_bundle": fhir_bundle},
        )

    # --- Caregivers ---
    def create_caregiver(self, token: str, caregiver: dict) -> dict:
        return self._request("POST", "/api/v1/caregivers", token=token, json=caregiver)

    def list_caregivers(self, token: str, patient_id: str) -> dict:
        return self._request("GET", f"/api/v1/patients/{patient_id}/caregivers", token=token)

    # --- Assessments ---
    def list_assessments(self, token: str, offset: int = 0, limit: int = 50) -> dict:
        return self._request(
            "GET", "/api/v1/assessments", token=token, params={"offset": offset, "limit": limit}
        )

    def get_assessment(self, token: str, assessment_id: str) -> dict:
        return self._request("GET", f"/api/v1/assessments/{assessment_id}", token=token)

    def approve_assessment(self, token: str, assessment_id: str) -> dict:
        return self._request("PUT", f"/api/v1/assessments/{assessment_id}/approve", token=token)

    def override_rule(
        self,
        token: str,
        assessment_id: str,
        rule_eval_id: str,
        new_status: str,
        reasoning: str,
    ) -> dict:
        return self._request(
            "PUT",
            f"/api/v1/assessments/{assessment_id}/override",
            token=token,
            json={"rule_eval_id": rule_eval_id, "new_status": new_status, "reasoning": reasoning},
        )

    def list_overrides(self, token: str, assessment_id: str) -> dict:
        return self._request("GET", f"/api/v1/assessments/{assessment_id}/overrides", token=token)

    # --- Audit / metrics ---
    def audit_logs(self, token: str, offset: int = 0, limit: int = 50) -> dict:
        return self._request(
            "GET", "/api/v1/audit/logs", token=token, params={"offset": offset, "limit": limit}
        )

    def metrics(self) -> dict:
        return self._request("GET", "/api/v1/metrics")
