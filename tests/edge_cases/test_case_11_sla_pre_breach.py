"""§9-11: SLA pre-breach alert fires BEFORE the 3h (180min) discharge breach."""
from claimguard.compliance_radar import radar
from claimguard.models import Journey, RadarStage


def _journey(delay_min: int) -> Journey:
    # a minimal journey whose submit lands at delay_min
    return Journey(record_id="RX", claim_type="cashless", stages=[
        RadarStage(stage="order", at_minutes=0),
        RadarStage(stage="summary", at_minutes=delay_min // 4),
        RadarStage(stage="code", at_minutes=delay_min // 2),
        RadarStage(stage="package", at_minutes=3 * delay_min // 4),
        RadarStage(stage="submit", at_minutes=delay_min),
        RadarStage(stage="decision", at_minutes=delay_min + 60),
    ])


def test_pre_breach_fires_before_the_180min_breach():
    rep = radar.analyze(_journey(150))  # in [120, 180)
    assert rep.breach_status == "pre_breach"
    assert rep.alert is True
    assert rep.pre_submission_delay_min < radar.DISCHARGE_SLA_MIN  # alerts BEFORE breach


def test_over_180_is_a_breach():
    rep = radar.analyze(_journey(200))
    assert rep.breach_status == "breach"
    assert rep.alert is True


def test_under_120_is_ok_no_alert():
    rep = radar.analyze(_journey(90))
    assert rep.breach_status == "ok"
    assert rep.alert is False


def test_prebreach_boundary_at_exactly_120():
    assert radar.analyze(_journey(120)).breach_status == "pre_breach"
    assert radar.analyze(_journey(119)).breach_status == "ok"
    assert radar.analyze(_journey(180)).breach_status == "pre_breach"  # 180 not yet breached
    assert radar.analyze(_journey(181)).breach_status == "breach"
