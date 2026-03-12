"""Tests for the Scope Guard — query classification and refusal logic."""

from src.guardrails.scope_guard import ScopeLevel, check_scope, extract_tickers

# ============================================================
# Ticker Extraction
# ============================================================


class TestExtractTickers:
    def test_apple_name(self):
        assert "AAPL" in extract_tickers("What was Apple's revenue?")

    def test_ticker_symbol(self):
        assert "MSFT" in extract_tickers("Show me MSFT earnings")

    def test_google_aliases(self):
        assert "GOOGL" in extract_tickers("How is Google doing?")
        assert "GOOGL" in extract_tickers("Alphabet revenue trends")

    def test_jpmorgan_aliases(self):
        assert "JPM" in extract_tickers("JPMorgan net income")
        assert "JPM" in extract_tickers("JP Morgan earnings")
        assert "JPM" in extract_tickers("Chase bank revenue")

    def test_amazon(self):
        assert "AMZN" in extract_tickers("Amazon cash flow")

    def test_multiple_tickers(self):
        tickers = extract_tickers("Compare Apple and Microsoft revenue")
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_no_tickers(self):
        assert extract_tickers("What is the weather?") == []

    def test_case_insensitive(self):
        assert "AAPL" in extract_tickers("APPLE revenue")
        assert "AAPL" in extract_tickers("apple revenue")


# ============================================================
# Investment Advice Refusal
# ============================================================


class TestInvestmentAdviceRefusal:
    def test_should_i_buy(self):
        result = check_scope("Should I buy Apple stock?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE
        assert result.detected_intent == "investment_advice"

    def test_good_investment(self):
        result = check_scope("Is MSFT a good investment?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_sell_recommendation(self):
        result = check_scope("Should I sell GOOGL?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_stock_prediction(self):
        result = check_scope("What is the stock price target for AAPL?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_portfolio_advice(self):
        result = check_scope("Portfolio allocation advice for tech stocks")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_invest_in(self):
        result = check_scope("Should I invest in Amazon?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_refusal_has_suggestion(self):
        result = check_scope("Should I buy Apple stock?")
        assert result.suggestion is not None
        assert len(result.suggestion) > 0


# ============================================================
# Non-Financial Refusal
# ============================================================


class TestNonFinancialRefusal:
    def test_weather(self):
        result = check_scope("What's the weather in NYC?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE
        assert result.detected_intent == "non_financial"

    def test_code_request(self):
        result = check_scope("Write me a Python script")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_sports(self):
        result = check_scope("Who won the game last night?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE


# ============================================================
# Future Projection Refusal
# ============================================================


class TestFutureProjectionRefusal:
    def test_predict_revenue(self):
        result = check_scope("Predict Apple's revenue next quarter")
        assert result.level == ScopeLevel.OUT_OF_SCOPE
        assert result.detected_intent == "future_projection"

    def test_forecast_earnings(self):
        result = check_scope("Forecast MSFT earnings for next year")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_what_will_be(self):
        result = check_scope("What will Google's revenue be next quarter?")
        assert result.level == ScopeLevel.OUT_OF_SCOPE


# ============================================================
# In-Scope Queries
# ============================================================


class TestInScopeQueries:
    def test_revenue_query(self):
        result = check_scope("What was Apple's revenue last quarter?")
        assert result.level == ScopeLevel.IN_SCOPE
        assert "AAPL" in result.detected_tickers

    def test_margin_comparison(self):
        result = check_scope("Compare operating margins for AAPL and MSFT")
        assert result.level == ScopeLevel.IN_SCOPE
        assert "AAPL" in result.detected_tickers
        assert "MSFT" in result.detected_tickers

    def test_trend_query(self):
        result = check_scope("How has GOOGL earnings trended?")
        assert result.level == ScopeLevel.IN_SCOPE
        assert "GOOGL" in result.detected_tickers

    def test_eps_query(self):
        result = check_scope("What is Amazon's EPS?")
        assert result.level == ScopeLevel.IN_SCOPE

    def test_cash_flow_query(self):
        result = check_scope("Show JPMorgan's cash flow")
        assert result.level == ScopeLevel.IN_SCOPE

    def test_debt_query(self):
        result = check_scope("What is AAPL's debt to equity ratio?")
        assert result.level == ScopeLevel.IN_SCOPE


# ============================================================
# Partial Scope
# ============================================================


class TestPartialScope:
    def test_financial_no_company(self):
        result = check_scope("What is revenue growth?")
        assert result.level == ScopeLevel.PARTIAL
        assert result.detected_tickers == []

    def test_ticker_unclear_intent(self):
        result = check_scope("Tell me about Apple")
        assert result.level in (ScopeLevel.PARTIAL, ScopeLevel.OUT_OF_SCOPE)


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    def test_empty_query(self):
        result = check_scope("")
        assert result.level == ScopeLevel.OUT_OF_SCOPE

    def test_scope_result_has_all_fields(self):
        result = check_scope("What was Apple's revenue?")
        assert hasattr(result, "level")
        assert hasattr(result, "reason")
        assert hasattr(result, "suggestion")
        assert hasattr(result, "detected_tickers")
        assert hasattr(result, "detected_intent")
