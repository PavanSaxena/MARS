import pytest

from app.agents.finance_agent import parse_finance_output


class TestParseFinanceOutput:
    def test_full_valid_output(self):
        text = (
            "Response:\nProceed with investment.\n\n"
            "Reasoning:\nROI is strong.\n\n"
            "Confidence:\n0.85"
        )
        result = parse_finance_output(text)
        assert "Proceed" in result["response"]
        assert result["confidence"] == pytest.approx(0.85)
        assert "ROI" in result["reasoning"]

    def test_invalid_confidence_defaults(self):
        text = "Response:\nok\nReasoning:\nok\nConfidence:\nnot_a_number"
        result = parse_finance_output(text)
        assert result["confidence"] == pytest.approx(0.5)

    def test_empty_string_returns_defaults(self):
        result = parse_finance_output("")
        assert result["confidence"] == pytest.approx(0.5)

    def test_confidence_inline_same_line(self):
        text = "Response: Go ahead\nReasoning: Strong margin\nConfidence: 0.82"
        result = parse_finance_output(text)
        assert result["confidence"] == pytest.approx(0.82)

    def test_json_output_parsed(self):
        text = '{"response":"Proceed","reasoning":"Strong ROI","confidence":0.9}'
        result = parse_finance_output(text)
        assert result["response"] == "Proceed"
        assert result["reasoning"] == "Strong ROI"
        assert result["confidence"] == pytest.approx(0.9)

    def test_confidence_clamped_high(self):
        text = '{"response":"Proceed","reasoning":"Test","confidence":1.7}'
        result = parse_finance_output(text)
        assert result["confidence"] == pytest.approx(1.0)

    def test_confidence_clamped_low(self):
        text = '{"response":"Proceed","reasoning":"Test","confidence":-0.3}'
        result = parse_finance_output(text)
        assert result["confidence"] == pytest.approx(0.0)
