# Rate Limit Handling - Quick Reference

## 🚀 Quick Start

### 1. Update Configuration (Optional)
```bash
# Copy example configuration
cp .env.example .env

# Edit rate limit settings
nano .env
```

### 2. Key Settings

```env
# For Groq Free Tier (~6K TPM)
BATCH_SIZE=2
BATCH_DELAY=15.0
REQUEST_THROTTLE_DELAY=1.0

# For Groq Paid Tier (~30K TPM)
BATCH_SIZE=5
BATCH_DELAY=5.0
REQUEST_THROTTLE_DELAY=0.5
```

### 3. Test It
```bash
python test_rate_limit.py
```

## 📊 Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_RETRIES` | 5 | Max retry attempts on rate limit |
| `RETRY_BASE_DELAY` | 1.0s | Base delay for exponential backoff |
| `RETRY_BUFFER` | 2.0s | Extra buffer added to API delay |
| `REQUEST_THROTTLE_DELAY` | 0.5s | Delay between requests |
| `BATCH_DELAY` | 5.0s | Delay between batches |
| `TPM_BUDGET` | 30000 | Tokens per minute limit |

## 🔧 Tuning Guide

### Hitting Rate Limits?
```env
# Reduce throughput
BATCH_SIZE=3              # ⬇️ Smaller batches
BATCH_DELAY=10.0          # ⬆️ Longer delays
REQUEST_THROTTLE_DELAY=1.0 # ⬆️ More throttling
```

### Too Slow?
```env
# Increase throughput (if not hitting limits)
BATCH_SIZE=10             # ⬆️ Larger batches
BATCH_DELAY=2.0           # ⬇️ Shorter delays
REQUEST_THROTTLE_DELAY=0.2 # ⬇️ Less throttling
```

### Frequent Retries?
```env
# More conservative
RETRY_BUFFER=5.0          # ⬆️ Longer buffer
MAX_RETRIES=10            # ⬆️ More attempts
```

## 📝 Log Messages

### Normal Operation
```
INFO - Processing batch 1/10
INFO - Batch 1 complete: 5 valid, 0 invalid
INFO - Waiting 5.0s before next batch...
```

### Rate Limit Hit (Recoverable)
```
WARNING - Rate limit hit (attempt 1/5). Waiting 3.00s before retry.
```

### Rate Limit Exhausted
```
ERROR - Rate limit exceeded after 5 retries. Stopping pipeline.
```

## 🔍 Troubleshooting

### Problem: Constant Rate Limits
**Solution**: Increase delays
```env
BATCH_DELAY=15.0
REQUEST_THROTTLE_DELAY=1.0
```

### Problem: Pipeline Too Slow
**Solution**: Check if you're hitting limits
- If no rate limit warnings → Increase `BATCH_SIZE`
- If rate limit warnings → Keep current settings

### Problem: HTTP 429 Errors
**Solution**: Adjust configuration
```env
# Reduce load
BATCH_SIZE=2
BATCH_DELAY=20.0

# Or upgrade API plan
TPM_BUDGET=60000
```

## 🎯 Presets

### Conservative (Guaranteed to work)
```env
BATCH_SIZE=2
BATCH_DELAY=15.0
REQUEST_THROTTLE_DELAY=1.0
MAX_RETRIES=10
```

### Balanced (Recommended)
```env
BATCH_SIZE=5
BATCH_DELAY=5.0
REQUEST_THROTTLE_DELAY=0.5
MAX_RETRIES=5
```

### Aggressive (High-tier plans only)
```env
BATCH_SIZE=10
BATCH_DELAY=2.0
REQUEST_THROTTLE_DELAY=0.2
MAX_RETRIES=3
```

## 📈 Monitoring

### Check Logs
```bash
# Watch logs in real-time
docker-compose logs -f decision-generator

# Search for rate limit events
docker-compose logs decision-generator | grep "Rate limit"
```

### Key Metrics
- **Retry Count**: How often rate limits are hit
- **Batch Completion Time**: Time per batch
- **Valid/Invalid Ratio**: Quality of generation

## ✅ Verification

```bash
# Test rate limit handling
python test_rate_limit.py

# Verify configuration
python -c "from app.config import settings; print(f'Batch delay: {settings.BATCH_DELAY}s')"

# Check imports
python -c "from app.llm.openai_client import OpenAIClient; print('✓ OK')"
```

## 🆘 Common Issues

### Issue: "Rate limit exceeded after 5 retries"
- **Cause**: API plan limit reached
- **Fix**: Reduce `BATCH_SIZE` or increase `BATCH_DELAY`

### Issue: Pipeline very slow
- **Cause**: Delays too conservative
- **Fix**: Reduce delays if not hitting rate limits

### Issue: HTTP 500 errors
- **Cause**: Non-rate-limit error
- **Fix**: Check logs for actual error message

## 📚 Documentation

- **Detailed Guide**: `RATE_LIMIT_HANDLING.md`
- **Implementation**: `CHANGELOG_RATE_LIMITS.md`
- **Summary**: `IMPLEMENTATION_SUMMARY.md`
- **Tests**: `test_rate_limit.py`

## 💡 Tips

1. **Start Conservative**: Use lower `BATCH_SIZE` initially
2. **Monitor Logs**: Watch for rate limit warnings
3. **Tune Gradually**: Increase throughput slowly
4. **Match Your Plan**: Set `TPM_BUDGET` to your actual limit
5. **Test First**: Run `test_rate_limit.py` after changes

## 🔗 Quick Links

- [Groq API Docs](https://console.groq.com/docs/rate-limits)
- [Configuration Guide](README.md#configuration)
- [Test Suite](test_rate_limit.py)