# AGENTS.md - Development Guide

## Build/Lint/Test Commands

### Running Tests
```bash
# Run specific test file
python test_overfitting.py

# Run main application
python main.py

# View statistics
python main.py --stats
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt
```

### Project Structure
```
encrypt_monitor/
├── exchanges/         # Exchange API implementations
├── analyzers/         # Sentiment and signal analysis
├── database/          # SQLite3 data persistence
├── notifiers/         # Telegram notifications
└── utils/             # Helper functions
```

## Code Style Guidelines

### Imports
- Standard library imports first, then third-party, then local
- Use type hints from `typing` module: `Dict`, `List`, `Optional`
- Relative imports for same-package modules: `from .base import ExchangeBase`

### Type Annotations
- ALL functions must have type hints for parameters and return types
- Use `Optional[T]` for nullable values
- Example: `def get_spot_price(self, symbol: str) -> Optional[float]:`

### Naming Conventions
- **Classes**: PascalCase (`OKXExchange`, `SentimentAnalyzer`)
- **Functions/Methods**: snake_case (`get_spot_price`, `_format_message`)
- **Private methods**: prefix with underscore (`_make_request`)
- **Constants**: UPPER_SNAKE_CASE (`BASE_URL`)
- **Variables**: snake_case (`fg_value`, `funding_pct`)

### Docstrings
- Module-level docstrings with triple quotes
- Method docstrings use `:param` and `:return` format
- Use Chinese for user-facing documentation

### Error Handling
- Use try-except blocks with specific exception types
- Log errors with `logger.error()` and include `exc_info=True` when useful
- Return `None` for API failures instead of raising
- Database operations: call `conn.rollback()` on error
- Always log warnings for expected failures (e.g., `logger.warning()`)

### Logging
- Define logger at module level: `logger = logging.getLogger(__name__)`
- Use appropriate levels: `debug()`, `info()`, `warning()`, `error()`
- Log meaningful messages that aid debugging

### Code Organization
- Use abstract base classes (`ABC`) for defining interfaces
- Factory pattern for component creation (see `exchanges/__init__.py`)
- Separate data collection, analysis, and notification concerns
- Each module should have a single responsibility

### API Requests
- Use `requests.Session()` for connection pooling
- Include timeout (10-30 seconds)
- Implement retry logic with exponential backoff
- Handle rate limiting with `time.sleep()` between requests

### Database Operations
- Always use parameterized queries to prevent SQL injection
- Wrap operations in try-except with rollback
- Use `sqlite3.Row` for dict-like row access
- Commit explicitly after successful operations

### Configuration
- All config loaded from `config.yaml` using `PyYAML`
- Use `config.get('key', default)` pattern for optional keys
- Never commit sensitive values (tokens, API keys)
