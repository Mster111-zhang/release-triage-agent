"""离线验收。在评测层维护预期结论，调查工作流不读这些标签。"""

from .agent import investigate
from .data import SCENARIOS, evidence_database, query_evidence

EXPECTED = {
    "case-01": ("release_timeout", {"R-11", "L-11", "M-11"}),
    "case-02": ("dependency_latency", {"R-21", "L-21", "M-21"}),
    "case-03": ("pool_limit", {"R-31", "L-31", "M-31"}),
    "case-04": ("insufficient", {"R-41", "M-41"}),
    "case-05": ("release_timeout", {"R-51", "L-51", "M-51"}),
    "case-06": ("no_impact", {"L-61", "M-61"}),
}


def evaluate():
    print("案例       预期                 实际                 引用          基线正确")
    correct = baseline_correct = anchored = 0
    for case, (expected, required_ids) in EXPECTED.items():
        report = investigate(case, SCENARIOS[case][1])
        observed_ids = {record["id"] for record in report["evidence"]}
        cited_ids = set(report["citations"])
        sources = {step["tool"] for step in report["trace"]}
        with evidence_database() as conn:
            release_exists = bool(query_evidence(conn, case, "releases"))
        baseline = "release_timeout" if release_exists else "insufficient"
        passed = report["category"] == expected
        supported = required_ids <= cited_ids <= observed_ids
        assert len(sources) == len(report["trace"]) <= 3
        correct += passed
        baseline_correct += baseline == expected
        anchored += supported
        print(f"{case:<10} {expected:<20} {report['category']:<20} {'通过' if supported else '失败':<8} {'是' if baseline == expected else '否'}")
    print(f"本地 Agent 分类 {correct}/{len(EXPECTED)}；引用校验 {anchored}/{len(EXPECTED)}；只看是否发版的基线 {baseline_correct}/{len(EXPECTED)}。")
    assert correct == anchored == len(EXPECTED)
    assert len(investigate("case-06", SCENARIOS["case-06"][1])["trace"]) == 2


if __name__ == "__main__":
    evaluate()
