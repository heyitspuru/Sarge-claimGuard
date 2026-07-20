from claimguard.compliance_radar import radar


def test_generate_journey_deterministic_and_ordered():
    a = radar.generate_journey("R0001", "cashless")
    b = radar.generate_journey("R0001", "cashless")
    assert a == b
    offsets = [s.at_minutes for s in a.stages]
    assert offsets[0] == 0
    assert offsets == sorted(offsets)  # monotonic timeline
    assert [s.stage for s in a.stages] == radar.STAGE_ORDER


def test_all_three_breach_statuses_occur_across_records():
    seen = set()
    for i in range(30):
        j = radar.generate_journey(f"R{i:04d}", "cashless")
        seen.add(radar.analyze(j).breach_status)
    assert seen == {"ok", "pre_breach", "breach"}


def test_stage_gaps_sum_to_pre_submission_delay():
    j = radar.generate_journey("R0007", "reimbursement")
    rep = radar.analyze(j)
    assert sum(rep.stage_gaps.values()) == rep.pre_submission_delay_min
    # slowest_stage is the true max gap
    assert rep.stage_gaps[rep.slowest_stage] == max(rep.stage_gaps.values())


def test_report_is_labeled_synthetic():
    rep = radar.analyze(radar.generate_journey("R0002", "cashless"))
    assert rep.synthetic is True
