"""Native pair results are additive and retain the NR reference labels."""

from adroit.orchestrator import single_idea as idea
from adroit.parameter_space.native_joint import JointSettings, JointResult, Calibration
from adroit.parameter_space.classes import Point
from adroit.parameter_space.simplified import model


def test_native_settings_roundtrip_and_report_has_separate_calibration():
    request = idea.SingleIdeaRequest(
        experiment="CDMS II Si (2013)",
        spec=model("vector", 60, 125),
        masses_gev=[50, 70],
        native_joint=JointSettings(toys=20),
    )
    assert idea.SingleIdeaRequest.model_validate_json(request.model_dump_json()) == request
    result = JointResult(
        settings=request.native_joint,
        masses_gev=[50, 70],
        complete=True,
        best_point=Point(m_chi=50, m_med=125, g_chi=0.001),
        observed_max_q0=2.0,
        background_theta=1.0,
        calibration=Calibration(
            complete=True,
            toys_requested=20,
            toys_completed=20,
            seed=3,
            toy_fits=40,
            exceedances=1,
            p_mc=2 / 21,
            p_interval_95=(0.001, 0.25),
            z_mc=1.3,
            minimum_resolvable_p=1 / 21,
        ),
    )
    text = "\n".join(idea._native_report(result))
    assert "Calibrated physical-domain" in text and "signal-only" in text
    assert "NR-reference" in text
    failed = result.model_copy(
        update={
            "complete": False,
            "calibration": Calibration(toys_requested=20, seed=3, reason="coverage incomplete"),
        }
    )
    text = "\n".join(idea._native_report(failed))
    assert "No calibrated p-value" in text and "Calibrated physical-domain p_MC=" not in text
