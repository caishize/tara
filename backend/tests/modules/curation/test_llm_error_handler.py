"""
Unit tests for LLM Error Handler.

Tests the fallback mechanisms for LLM failures including:
- Timeout scenarios
- Format error scenarios
- Empty result scenarios
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from src.modules.curation.services.llm_error_handler import LLMErrorHandler


@pytest.fixture
def error_handler():
    """Create an LLM error handler with short timeout for testing."""
    return LLMErrorHandler(timeout=1.0)


@pytest.fixture
def mock_llm_func():
    """Create a mock LLM function."""
    return AsyncMock()


@pytest.fixture
def mock_fallback_func():
    """Create a mock fallback function."""
    return AsyncMock()


class TestLLMErrorHandler:
    """Test suite for LLM Error Handler."""
    
    @pytest.mark.asyncio
    async def test_successful_llm_call(self, error_handler, mock_llm_func, mock_fallback_func):
        """Test that successful LLM calls return the result without fallback."""
        # Arrange
        expected_result = {"associations": [{"title": "Test"}]}
        mock_llm_func.return_value = expected_result
        
        # Act
        result = await error_handler.call_llm_with_fallback(
            mock_llm_func,
            mock_fallback_func,
        )
        
        # Assert
        assert result == expected_result
        mock_llm_func.assert_called_once()
        mock_fallback_func.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_llm_timeout_fallback(self, error_handler, mock_llm_func, mock_fallback_func):
        """Test that LLM timeout triggers fallback to rule engine."""
        # Arrange
        async def slow_llm():
            await asyncio.sleep(2.0)  # Longer than timeout
            return {"result": "too slow"}
        
        mock_llm_func.side_effect = slow_llm
        fallback_result = [{"title": "Fallback association"}]
        mock_fallback_func.return_value = fallback_result
        
        # Act
        result = await error_handler.call_llm_with_fallback(
            mock_llm_func,
            mock_fallback_func,
        )
        
        # Assert
        assert result == fallback_result
        mock_llm_func.assert_called_once()
        mock_fallback_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_llm_format_error_fallback(self, error_handler, mock_llm_func, mock_fallback_func):
        """Test that LLM format errors trigger fallback to rule engine."""
        # Arrange
        mock_llm_func.side_effect = ValueError("Invalid JSON format")
        fallback_result = [{"title": "Fallback association"}]
        mock_fallback_func.return_value = fallback_result
        
        # Act
        result = await error_handler.call_llm_with_fallback(
            mock_llm_func,
            mock_fallback_func,
        )
        
        # Assert
        assert result == fallback_result
        mock_llm_func.assert_called_once()
        mock_fallback_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_llm_empty_result_fallback(self, error_handler, mock_llm_func, mock_fallback_func):
        """Test that empty LLM results trigger fallback to rule engine."""
        # Arrange
        mock_llm_func.return_value = []  # Empty list
        fallback_result = [{"title": "Fallback association"}]
        mock_fallback_func.return_value = fallback_result
        
        # Act
        result = await error_handler.call_llm_with_fallback(
            mock_llm_func,
            mock_fallback_func,
        )
        
        # Assert
        assert result == fallback_result
        mock_llm_func.assert_called_once()
        mock_fallback_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_llm_none_result_fallback(self, error_handler, mock_llm_func, mock_fallback_func):
        """Test that None LLM results trigger fallback to rule engine."""
        # Arrange
        mock_llm_func.return_value = None
        fallback_result = [{"title": "Fallback association"}]
        mock_fallback_func.return_value = fallback_result
        
        # Act
        result = await error_handler.call_llm_with_fallback(
            mock_llm_func,
            mock_fallback_func,
        )
        
        # Assert
        assert result == fallback_result
        mock_llm_func.assert_called_once()
        mock_fallback_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fallback_with_arguments(self, error_handler, mock_llm_func, mock_fallback_func):
        """Test that arguments are passed correctly to both LLM and fallback."""
        # Arrange
        mock_llm_func.side_effect = Exception("LLM error")
        fallback_result = [{"title": "Fallback"}]
        mock_fallback_func.return_value = fallback_result
        
        test_arg1 = "arg1"
        test_arg2 = "arg2"
        test_kwarg = "kwarg_value"
        
        # Act
        result = await error_handler.call_llm_with_fallback(
            mock_llm_func,
            mock_fallback_func,
            test_arg1,
            test_arg2,
            test_key=test_kwarg,
        )
        
        # Assert
        assert result == fallback_result
        mock_llm_func.assert_called_once_with(test_arg1, test_arg2, test_key=test_kwarg)
        mock_fallback_func.assert_called_once_with(test_arg1, test_arg2, test_key=test_kwarg)
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_success_on_second_attempt(self, error_handler):
        """Test that retry mechanism succeeds on second attempt."""
        # Arrange
        mock_func = AsyncMock()
        mock_func.side_effect = [
            Exception("First attempt failed"),
            {"result": "success"},
        ]
        
        # Act
        result = await error_handler.call_with_retry(mock_func, max_retries=2)
        
        # Assert
        assert result == {"result": "success"}
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_all_attempts_fail(self, error_handler):
        """Test that retry mechanism returns None after all attempts fail."""
        # Arrange
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Always fails")
        
        # Act
        result = await error_handler.call_with_retry(mock_func, max_retries=2)
        
        # Assert
        assert result is None
        assert mock_func.call_count == 3  # Initial + 2 retries
    
    def test_validate_llm_result_valid_dict(self, error_handler):
        """Test validation of valid dict results."""
        assert error_handler._validate_llm_result({"key": "value"}) is True
    
    def test_validate_llm_result_valid_list(self, error_handler):
        """Test validation of valid list results."""
        assert error_handler._validate_llm_result([1, 2, 3]) is True
        assert error_handler._validate_llm_result([]) is True  # Empty list is valid
    
    def test_validate_llm_result_none(self, error_handler):
        """Test validation of None results."""
        assert error_handler._validate_llm_result(None) is False
    
    def test_is_empty_result_empty_list(self, error_handler):
        """Test empty result detection for empty list."""
        assert error_handler._is_empty_result([]) is True
    
    def test_is_empty_result_empty_dict(self, error_handler):
        """Test empty result detection for empty dict."""
        assert error_handler._is_empty_result({}) is True
    
    def test_is_empty_result_empty_string(self, error_handler):
        """Test empty result detection for empty string."""
        assert error_handler._is_empty_result("") is True
    
    def test_is_empty_result_none(self, error_handler):
        """Test empty result detection for None."""
        assert error_handler._is_empty_result(None) is True
    
    def test_is_empty_result_non_empty(self, error_handler):
        """Test empty result detection for non-empty values."""
        assert error_handler._is_empty_result([1]) is False
        assert error_handler._is_empty_result({"key": "value"}) is False
        assert error_handler._is_empty_result("text") is False
