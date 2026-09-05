from challenges.models import Challenge
from pilots.models import KPI, Milestone, Pilot, PilotEvidence
from startups.models import Startup, StartupEvidence


def _node(node_id, node_type, label, **extra):
    data = {"id": str(node_id), "type": node_type, "label": label}
    data.update(extra)
    return data


def _edge(source, target, relationship, **extra):
    data = {
        "source": str(source),
        "target": str(target),
        "relationship": relationship,
    }
    data.update(extra)
    return data


def build_startup_graph(startup: Startup) -> dict:
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()

    def add_node(node_id, node_type, label, **extra):
        key = (str(node_id), node_type)
        if key not in seen_nodes:
            seen_nodes.add(key)
            nodes.append(_node(node_id, node_type, label, **extra))

    def add_edge(source, target, relationship, **extra):
        key = (str(source), str(target), relationship)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append(_edge(source, target, relationship, **extra))

    add_node(startup.id, "startup", startup.company_name)
    for evidence in startup.evidence.all():
        add_node(evidence.id, "startup_evidence", evidence.title, verified=evidence.verified, evidence_type=evidence.evidence_type)
        add_edge(startup.id, evidence.id, "SUPPORTED_BY" if evidence.verified else "HAS_EVIDENCE")

    for pilot in startup.pilots.select_related("challenge", "created_by").prefetch_related("kpis", "milestones", "evidence").all():
        add_node(pilot.id, "pilot", pilot.title, status=pilot.status)
        add_edge(startup.id, pilot.id, "PARTICIPATED_IN")

        add_node(pilot.challenge.id, "challenge", pilot.challenge.title, status=pilot.challenge.status)
        add_edge(pilot.id, pilot.challenge.id, "FOR_CHALLENGE")

        add_node(pilot.created_by.id, "government", pilot.created_by.name, role="government")
        add_edge(pilot.id, pilot.created_by.id, "CONDUCTED_BY")

        for kpi in pilot.kpis.all():
            add_node(
                kpi.id,
                "kpi",
                kpi.name,
                status=kpi.status,
                baseline=float(kpi.baseline) if kpi.baseline is not None else None,
                target=float(kpi.target) if kpi.target is not None else None,
                actual=float(kpi.actual) if kpi.actual is not None else None,
            )
            add_edge(pilot.id, kpi.id, "MEASURED_BY")

        for milestone in pilot.milestones.all():
            add_node(milestone.id, "milestone", milestone.title, status=milestone.status)
            add_edge(pilot.id, milestone.id, "HAS_MILESTONE")

            for evidence in milestone.evidence.all():
                add_node(
                    evidence.id,
                    "pilot_evidence",
                    evidence.title,
                    verified=evidence.verified,
                    evidence_type=evidence.evidence_type,
                )
                add_edge(milestone.id, evidence.id, "SUPPORTED_BY" if evidence.verified else "HAS_EVIDENCE")

        # Some evidence records may not be reachable from milestones in malformed/legacy data.
        for evidence in pilot.evidence.all():
            add_node(
                evidence.id,
                "pilot_evidence",
                evidence.title,
                verified=evidence.verified,
                evidence_type=evidence.evidence_type,
            )
            add_edge(pilot.id, evidence.id, "SUPPORTED_BY" if evidence.verified else "HAS_EVIDENCE")

    return {"nodes": nodes, "edges": edges}


def build_pilot_graph(pilot: Pilot) -> dict:
    startup = pilot.startup
    return build_startup_graph(startup)
