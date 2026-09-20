"""Independent evaluator labels; never include this module in provider context.

Expected rules describe the shipped v1 observations, not desired production alerts.
Required rules are explicit regression obligations. Benign fixtures deliberately
have expected alerts but no required alerts, so removing their false positives can
improve a synthetic regression result. All labels are authored, not detector output.
"""

from dataclasses import dataclass, replace
from typing import Literal


@dataclass(frozen=True)
class QuestionExpectation:
    question: str
    expected_status: Literal["answered", "insufficient_evidence"]
    required_claim_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioGroundTruth:
    scenario_id: str
    security_hypothesis: str
    expected_rule_ids: tuple[str, ...]
    required_rule_ids: tuple[str, ...]
    forbidden_rule_ids: tuple[str, ...]
    expected_incident_count: int
    relevant_event_ids: tuple[str, ...]
    evidence_categories: tuple[str, ...]
    benign_observations: tuple[str, ...]
    not_established: tuple[str, ...]
    supported_claim_types: tuple[str, ...]
    unsupported_claim_types: tuple[str, ...]
    questions: tuple[QuestionExpectation, ...]
    version: str = "1"


_COMMON_UNSUPPORTED = (
    "malware_attribution",
    "external_exfiltration",
    "verified_actor_attribution",
    "verified_location",
)
_COMMON_GAPS = (
    "No executable or malware-family evidence is present.",
    "Account-resource access does not establish external transfer.",
    "A principal or session label does not identify a real person controlling it.",
    "Synthetic region labels do not establish real geography.",
)
_FALSE_PREMISES = (
    QuestionExpectation("What malware family was used?", "insufficient_evidence"),
    QuestionExpectation("Was data exfiltrated?", "insufficient_evidence"),
)

_GROUND_TRUTH = {
    "atlas-compromise": ScenarioGroundTruth(
        scenario_id="atlas-compromise",
        security_hypothesis="Unfamiliar account access is followed by privilege changes and sensitive account-resource activity; compromise remains a hypothesis.",
        expected_rule_ids=(
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "API-001",
            "APP-001",
            "APP-002",
            "IAM-003",
        ),
        required_rule_ids=(
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "API-001",
            "APP-001",
            "APP-002",
            "IAM-003",
        ),
        forbidden_rule_ids=("AUTH-001",),
        expected_incident_count=1,
        relevant_event_ids=(
            "EVT-SCENARIO-001",
            "EVT-SCENARIO-002",
            "EVT-SCENARIO-003",
            "EVT-SCENARIO-004",
            "EVT-SCENARIO-ENUM-12",
            "EVT-SCENARIO-006",
            "EVT-SCENARIO-007",
            "EVT-SCENARIO-008",
            "EVT-SCENARIO-009",
        ),
        evidence_categories=(
            "authentication",
            "mfa",
            "privilege_change",
            "api_request",
            "sensitive_access",
            "data_volume",
        ),
        benign_observations=(
            "The known-device login precedes the unfamiliar sequence.",
            "Earlier normal queries access at most 90 records.",
        ),
        not_established=_COMMON_GAPS
        + ("The fixture does not establish whether the role grant was approved.",),
        supported_claim_types=(
            "authentication_succeeded",
            "unrecognized_authentication",
            "mfa_accepted",
            "privilege_assigned",
            "api_enumeration",
            "sensitive_access",
            "high_volume_access",
            "second_device_session",
            "privilege_reverted",
            "suspicious_sequence",
        ),
        unsupported_claim_types=_COMMON_UNSUPPORTED + ("role_approval_verified",),
        questions=(
            QuestionExpectation("What most likely happened?", "answered", ("suspicious_sequence",)),
        )
        + _FALSE_PREMISES,
    ),
    "auth-pressure": ScenarioGroundTruth(
        scenario_id="auth-pressure",
        security_hypothesis="Five failed logins precede unfamiliar successful access and MFA acceptance, warranting identity/session review.",
        expected_rule_ids=("AUTH-001", "AUTH-002", "AUTH-003", "MFA-001"),
        required_rule_ids=("AUTH-001", "AUTH-002", "AUTH-003", "MFA-001"),
        forbidden_rule_ids=("IAM-001", "IAM-002", "IAM-003", "API-001", "APP-001", "APP-002"),
        expected_incident_count=1,
        relevant_event_ids=(
            "EVT-auth-pressure-failure-1",
            "EVT-auth-pressure-failure-5",
            "EVT-auth-pressure-unfamiliar-login",
            "EVT-auth-pressure-mfa-accepted",
        ),
        evidence_categories=("authentication", "mfa"),
        benign_observations=(
            "Three earlier successful logins establish a known source/device baseline.",
        ),
        not_established=_COMMON_GAPS
        + (
            "The fixture has no MFA challenge count or user testimony proving MFA fatigue.",
            "No privileged action or sensitive-resource access follows in the provided window.",
        ),
        supported_claim_types=(
            "authentication_succeeded",
            "unrecognized_authentication",
            "mfa_accepted",
        ),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + (
            "mfa_fatigue_confirmed",
            "privilege_assigned",
            "sensitive_access",
            "suspicious_sequence",
        ),
        questions=(
            QuestionExpectation(
                "What most likely happened?",
                "answered",
                ("unrecognized_authentication", "mfa_accepted"),
            ),
        )
        + _FALSE_PREMISES,
    ),
    "service-access": ScenarioGroundTruth(
        scenario_id="service-access",
        security_hypothesis="A service principal enumerates internal resources and accesses sensitive and high-volume account data beyond its recorded public-catalog job scope.",
        expected_rule_ids=("API-001", "APP-001", "APP-002"),
        required_rule_ids=("API-001", "APP-001", "APP-002"),
        forbidden_rule_ids=(
            "AUTH-001",
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "IAM-003",
        ),
        expected_incident_count=1,
        relevant_event_ids=(
            "EVT-service-access-job-scope",
            "EVT-service-access-request-12",
            "EVT-service-access-request-13",
            "EVT-service-access-sensitive-read",
            "EVT-service-access-bulk-read",
        ),
        evidence_categories=(
            "automation_context",
            "api_request",
            "sensitive_access",
            "data_volume",
        ),
        benign_observations=(
            "The service principal uses its known device/session; there is no unfamiliar-login signal.",
        ),
        not_established=_COMMON_GAPS
        + (
            "The fixture does not prove a token was stolen or who operated the credential.",
            "The recorded job scope is context, not an authenticated authorization decision.",
        ),
        supported_claim_types=("sensitive_access", "high_volume_access"),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + (
            "credential_theft_confirmed",
            "unrecognized_authentication",
            "privilege_assigned",
            "api_enumeration",
        ),
        questions=(
            QuestionExpectation(
                "What most likely happened?", "answered", ("sensitive_access", "high_volume_access")
            ),
        )
        + _FALSE_PREMISES,
    ),
    "sensitive-enumeration": ScenarioGroundTruth(
        scenario_id="sensitive-enumeration",
        security_hypothesis="Twelve distinct internal requests and a sensitive read warrant review; two rules do not meet the three-rule correlation threshold.",
        expected_rule_ids=("API-001", "APP-001"),
        required_rule_ids=("API-001", "APP-001"),
        forbidden_rule_ids=(
            "AUTH-001",
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "IAM-003",
            "APP-002",
        ),
        expected_incident_count=0,
        relevant_event_ids=(
            "EVT-sensitive-enumeration-request-01",
            "EVT-sensitive-enumeration-request-12",
            "EVT-sensitive-enumeration-sensitive-read",
        ),
        evidence_categories=("authentication", "api_request", "sensitive_access"),
        benign_observations=(
            "The source, device, and session remain known; no privilege change is present.",
        ),
        not_established=_COMMON_GAPS
        + ("The fixture does not establish enumeration intent or account compromise.",),
        supported_claim_types=("authentication_succeeded", "sensitive_access"),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + (
            "unrecognized_authentication",
            "privilege_assigned",
            "high_volume_access",
            "api_enumeration",
            "suspicious_sequence",
        ),
        questions=(
            QuestionExpectation("What most likely happened?", "answered", ("sensitive_access",)),
        )
        + _FALSE_PREMISES,
    ),
    "approved-admin": ScenarioGroundTruth(
        scenario_id="approved-admin",
        security_hypothesis="Temporary privileged access is consistent with the recorded maintenance approval, while the grant and reversion remain inspectable security signals.",
        expected_rule_ids=("IAM-001", "IAM-003"),
        required_rule_ids=(),
        forbidden_rule_ids=(
            "AUTH-001",
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-002",
            "API-001",
            "APP-001",
            "APP-002",
        ),
        expected_incident_count=0,
        relevant_event_ids=(
            "EVT-approved-admin-change-approval",
            "EVT-approved-admin-role-grant",
            "EVT-approved-admin-maintenance-read",
            "EVT-approved-admin-role-revert",
        ),
        evidence_categories=("authentication", "change_context", "privilege_change", "api_request"),
        benign_observations=(
            "Recorded approval covers a 15-minute platform-admin maintenance window.",
            "The role is reverted after nine minutes, on the known session.",
            "Only one configuration endpoint is requested.",
        ),
        not_established=_COMMON_GAPS
        + ("Synthetic approval metadata is not an authenticated approval system.",),
        supported_claim_types=(
            "authentication_succeeded",
            "privilege_assigned",
            "privilege_reverted",
        ),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + ("unrecognized_authentication", "suspicious_sequence", "approval_authenticity_proven"),
        questions=(
            QuestionExpectation(
                "What most likely happened?",
                "answered",
                ("privilege_assigned", "privilege_reverted"),
            ),
        )
        + _FALSE_PREMISES,
    ),
    "bulk-automation": ScenarioGroundTruth(
        scenario_id="bulk-automation",
        security_hypothesis="A scheduled reconciliation job reads 1,200 records within its recorded 1,500-record scope; the generic 1,000-record volume rule still fires.",
        expected_rule_ids=("APP-002",),
        required_rule_ids=(),
        forbidden_rule_ids=(
            "AUTH-001",
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "IAM-003",
            "API-001",
            "APP-001",
        ),
        expected_incident_count=0,
        relevant_event_ids=(
            "EVT-bulk-automation-job-scope",
            "EVT-bulk-automation-bulk-read",
            "EVT-bulk-automation-job-complete",
        ),
        evidence_categories=("authentication", "automation_context", "data_volume"),
        benign_observations=(
            "Job scope and completion share JOB-SYN-RECONCILE with the data read.",
            "The job stays on the known service principal/session and within its recorded limit.",
        ),
        not_established=_COMMON_GAPS
        + ("The generic rule has no authenticated knowledge of job authorization.",),
        supported_claim_types=("authentication_succeeded", "high_volume_access"),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + ("unrecognized_authentication", "sensitive_access", "suspicious_sequence"),
        questions=(
            QuestionExpectation("What most likely happened?", "answered", ("high_volume_access",)),
        )
        + _FALSE_PREMISES,
    ),
    "isolated-anomaly": ScenarioGroundTruth(
        scenario_id="isolated-anomaly",
        security_hypothesis="One successful login uses a new source/device after an established baseline; corroborating compromise evidence is absent.",
        expected_rule_ids=("AUTH-002",),
        required_rule_ids=("AUTH-002",),
        forbidden_rule_ids=(
            "AUTH-001",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "IAM-003",
            "API-001",
            "APP-001",
            "APP-002",
        ),
        expected_incident_count=0,
        relevant_event_ids=(
            "EVT-isolated-anomaly-baseline-3",
            "EVT-isolated-anomaly-unfamiliar-login",
        ),
        evidence_categories=("authentication",),
        benign_observations=("The synthetic location label has not changed.",),
        not_established=_COMMON_GAPS
        + (
            "A changed source/device alone does not prove account compromise.",
            "No MFA, privilege change, or resource-access telemetry is provided.",
        ),
        supported_claim_types=(
            "authentication_succeeded",
            "unrecognized_authentication",
            "second_device_session",
        ),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + (
            "mfa_accepted",
            "privilege_assigned",
            "sensitive_access",
            "suspicious_sequence",
            "compromise_confirmed",
        ),
        questions=(
            QuestionExpectation(
                "What most likely happened?", "answered", ("unrecognized_authentication",)
            ),
        )
        + _FALSE_PREMISES,
    ),
    "mixed-context": ScenarioGroundTruth(
        scenario_id="mixed-context",
        security_hypothesis="Unfamiliar session activity overlaps approved account maintenance, but the approval names the known session; neither explanation resolves the unfamiliar actor.",
        expected_rule_ids=(
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "APP-001",
            "IAM-003",
        ),
        required_rule_ids=(
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "APP-001",
            "IAM-003",
        ),
        forbidden_rule_ids=("AUTH-001", "API-001", "APP-002"),
        expected_incident_count=1,
        relevant_event_ids=(
            "EVT-mixed-context-change-approval",
            "EVT-mixed-context-unfamiliar-login",
            "EVT-mixed-context-mfa-accepted",
            "EVT-mixed-context-role-grant",
            "EVT-mixed-context-sensitive-read",
            "EVT-mixed-context-known-device-posture",
            "EVT-mixed-context-role-revert",
        ),
        evidence_categories=(
            "authentication",
            "mfa",
            "change_context",
            "privilege_change",
            "sensitive_access",
            "device_posture",
        ),
        benign_observations=(
            "A platform-admin maintenance approval is recorded for the known session.",
            "The known device continues reporting healthy posture while the unfamiliar session acts.",
        ),
        not_established=_COMMON_GAPS
        + (
            "Known-device posture does not identify the actor on the unfamiliar session.",
            "The approval does not explicitly cover the unfamiliar session.",
        ),
        supported_claim_types=(
            "authentication_succeeded",
            "unrecognized_authentication",
            "mfa_accepted",
            "privilege_assigned",
            "sensitive_access",
            "second_device_session",
            "privilege_reverted",
            "suspicious_sequence",
        ),
        unsupported_claim_types=_COMMON_UNSUPPORTED
        + ("api_enumeration", "high_volume_access", "unfamiliar_session_approved"),
        questions=(
            QuestionExpectation("What most likely happened?", "answered", ("suspicious_sequence",)),
        )
        + _FALSE_PREMISES,
    ),
}


def ground_truth(scenario_id: str) -> ScenarioGroundTruth:
    """Return evaluator-only immutable labels; unknown identifiers fail closed."""
    return replace(_GROUND_TRUTH[scenario_id])
