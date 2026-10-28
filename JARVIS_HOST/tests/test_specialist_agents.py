from core.specialist_agents import get_agent, list_agents, prepare_expert_task, route_agent


def test_all_domain_specialists_have_profiles():
    agents = list_agents()
    assert len(agents) >= 12
    for agent in agents:
        assert get_agent(agent["id"])
        assert agent["mission"]


def test_domain_router_prefers_specific_tools():
    assert route_agent("Dante Controller clock master ve subscription sorunu") == "dante_network_engineer"
    assert route_agent("SPL hesabı ref_db=100 ref_m=1 target_m=10") == "spl_calculator"
    assert route_agent("Rider içindeki monitör ve input list maddeleri") == "rider_analyst"
    assert route_agent("Merhaba, saat kaç?") is None


def test_spl_distance_tool_returns_transparent_free_field_estimate():
    _, result = prepare_expert_task("spl_calculator", "ref_db=100 ref_m=1 target_m=10 power_ratio=1 sources=1")
    assert "80.00 dB" in result
    assert "serbest alan tahmini" in result.lower()
    assert "Yansıma" in result


def test_spl_tool_understands_spoken_turkish_distances():
    _, result = prepare_expert_task("spl_calculator", "100 dB 1 metrede, 10 metrede yaklaşık kaç dB olur?")
    assert "80.00 dB" in result


def test_delay_tool_computes_ms_and_assumption():
    _, result = prepare_expert_task("system_tech", "delay_distance_m=10")
    assert "29.15 ms" in result
    assert "343 m/s" in result


def test_dmx_fixture_range_is_validated():
    _, result = prepare_expert_task("lighting_tech", "address=501 channels=20 universe=1")
    assert "DMX 512 sınırını aşar" in result


def test_dante_subnet_tool_detects_mismatched_network():
    _, result = prepare_expert_task("dante_network_engineer", "device_ip=192.168.1.10 subnet_mask=255.255.255.0 peer_ip=192.168.2.20")
    assert "aynı alt ağda DEĞİL" in result


def test_foh_headroom_tool_computes_required_trim():
    _, result = prepare_expert_task("foh_engineer", "peak_dbfs=-2 target_peak_dbfs=-6")
    assert "4.00 dB kazanç azaltımı" in result


def test_invalid_spl_distance_is_rejected():
    _, result = prepare_expert_task("spl_calculator", "ref_db=100 ref_m=0 target_m=10")
    assert "HESAPLAMA HATASI" in result


def test_unknown_agent_does_not_create_fake_expert():
    assert get_agent("worlds_best_agent") is None


def test_expert_instructions_are_domain_specific():
    system, _ = prepare_expert_task("rf_engineer", "Dört kablosuz mikrofon planla")
    assert "RF" in system
    assert "scan verisi" in system
    assert "Fiziksel ölçüm" in system
