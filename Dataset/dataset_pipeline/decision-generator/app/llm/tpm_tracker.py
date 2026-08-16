"""
Rolling TPM (Tokens Per Minute) Budget Tracker

Tracks token usage across a rolling 60-second window to prevent
exceeding provider rate limits.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageRecord:
    """Record of token usage for a single request"""
    timestamp: float
    estimated_input_tokens: int
    requested_completion_tokens: int
    estimated_processed_tokens: int


class TPMTracker:
    """
    Tracks token usage across a rolling 60-second window.
    
    Provides methods to:
    - Check if a request would exceed the TPM budget
    - Calculate required wait time before proceeding
    - Record token usage after requests
    """
    
    def __init__(self, tpm_budget: int):
        """
        Initialize TPM tracker.
        
        Args:
            tpm_budget: Maximum tokens per minute allowed
        """
        self.tpm_budget = tpm_budget
        self.usage_history: Deque[TokenUsageRecord] = deque()
        self._window_seconds = 60.0
    
    def _prune_old_records(self) -> None:
        """Remove records older than 60 seconds"""
        current_time = time.time()
        cutoff_time = current_time - self._window_seconds
        
        while self.usage_history and self.usage_history[0].timestamp < cutoff_time:
            self.usage_history.popleft()
    
    def get_current_usage(self) -> int:
        """
        Get current token usage in the rolling window.
        
        Returns:
            Total tokens processed in the last 60 seconds
        """
        self._prune_old_records()
        return sum(record.estimated_processed_tokens for record in self.usage_history)
    
    def get_remaining_budget(self) -> int:
        """
        Get remaining TPM budget.
        
        Returns:
            Remaining tokens available in current window
        """
        current_usage = self.get_current_usage()
        return max(0, self.tpm_budget - current_usage)
    
    def would_exceed_budget(
        self,
        estimated_input_tokens: int,
        requested_completion_tokens: int
    ) -> bool:
        """
        Check if a request would exceed the TPM budget.
        
        Args:
            estimated_input_tokens: Estimated input tokens for request
            requested_completion_tokens: Requested completion tokens
            
        Returns:
            True if request would exceed budget
        """
        estimated_processed = estimated_input_tokens + requested_completion_tokens
        current_usage = self.get_current_usage()
        return (current_usage + estimated_processed) > self.tpm_budget
    
    def calculate_wait_time(
        self,
        estimated_input_tokens: int,
        requested_completion_tokens: int
    ) -> float:
        """
        Calculate required wait time before request can proceed.
        
        Args:
            estimated_input_tokens: Estimated input tokens for request
            requested_completion_tokens: Requested completion tokens
            
        Returns:
            Seconds to wait (0 if no wait needed)
        """
        if not self.would_exceed_budget(estimated_input_tokens, requested_completion_tokens):
            return 0.0
        
        estimated_processed = estimated_input_tokens + requested_completion_tokens
        current_usage = self.get_current_usage()
        tokens_over_budget = (current_usage + estimated_processed) - self.tpm_budget
        
        # Find the oldest record that would need to age out
        if not self.usage_history:
            return 0.0
        
        current_time = time.time()
        tokens_to_free = tokens_over_budget
        
        for record in self.usage_history:
            tokens_to_free -= record.estimated_processed_tokens
            if tokens_to_free <= 0:
                # This record aging out would free enough tokens
                record_age = current_time - record.timestamp
                wait_time = self._window_seconds - record_age
                return max(0.0, wait_time)
        
        # Fallback: wait for oldest record to age out
        oldest_record = self.usage_history[0]
        record_age = current_time - oldest_record.timestamp
        return max(0.0, self._window_seconds - record_age)
    
    def record_usage(
        self,
        estimated_input_tokens: int,
        requested_completion_tokens: int
    ) -> None:
        """
        Record token usage for a request.
        
        Args:
            estimated_input_tokens: Estimated input tokens used
            requested_completion_tokens: Requested completion tokens
        """
        record = TokenUsageRecord(
            timestamp=time.time(),
            estimated_input_tokens=estimated_input_tokens,
            requested_completion_tokens=requested_completion_tokens,
            estimated_processed_tokens=estimated_input_tokens + requested_completion_tokens
        )
        self.usage_history.append(record)
        self._prune_old_records()
    
    def get_usage_stats(self) -> dict:
        """
        Get current usage statistics.
        
        Returns:
            Dictionary with usage stats
        """
        current_usage = self.get_current_usage()
        remaining = self.get_remaining_budget()
        
        return {
            "rolling_tpm_usage": current_usage,
            "tpm_budget": self.tpm_budget,
            "remaining_budget": remaining,
            "utilization_percent": (current_usage / self.tpm_budget * 100) if self.tpm_budget > 0 else 0,
            "records_in_window": len(self.usage_history)
        }