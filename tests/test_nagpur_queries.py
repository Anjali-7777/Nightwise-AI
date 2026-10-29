import pytest
from backend.services.geocode import geocode
from backend.agent.tools import execute_route_workflow

@pytest.mark.anyio
async def test_nagpur_landmark_resolution():
    # 1. Test colloquial / typo "RUB Collage Nagpur"
    res_rub = await geocode("RUB Collage Nagpur")
    assert len(res_rub) > 0
    assert abs(res_rub[0]["lat"] - 21.1767) < 0.01
    assert abs(res_rub[0]["lon"] - 79.0620) < 0.01
    assert "Ramdeobaba" in res_rub[0]["name"] or "RBU" in res_rub[0]["name"]

    # 2. Test "VR mall nagpur"
    res_vr = await geocode("VR mall nagpur")
    assert len(res_vr) > 0
    assert abs(res_vr[0]["lat"] - 21.1320) < 0.01
    assert abs(res_vr[0]["lon"] - 79.0962) < 0.01
    assert "VR Mall" in res_vr[0]["name"] or "Trillium" in res_vr[0]["name"]

@pytest.mark.anyio
async def test_nagpur_route_execution():
    workflow = await execute_route_workflow(
        origin_query="RUB Collage Nagpur",
        destination_query="VR mall nagpur",
        mode="walking",
        departure_time_str="10:00 PM"
    )
    assert "routes" in workflow
    assert len(workflow["routes"]) >= 2
    # Verify origin and destination are in Nagpur
    assert abs(workflow["origin"]["lat"] - 21.1767) < 0.01
    assert abs(workflow["destination"]["lat"] - 21.1320) < 0.01
    for r in workflow["routes"]:
        assert r["night_score"] >= 0 and r["night_score"] <= 100
        assert r["distance_m"] > 3000 # ~7.8 km corridor
