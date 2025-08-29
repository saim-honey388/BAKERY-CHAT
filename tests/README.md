# BAKERY-CHAT Test Suite

## Overview

This directory contains comprehensive test suites for the BAKERY-CHAT application. All tests are designed to validate the functionality, reliability, and robustness of the bakery chatbot system.

## Test Structure

### Test Files

1. **`test_order_agent_basic.py`**
   - **Purpose**: Basic functionality testing for OrderAgent
   - **Created**: January 2025
   - **Coverage**: Cart management, product parsing, basic order flow
   - **Dependencies**: unittest, mock objects

2. **`test_order_agent_comprehensive.py`** (Planned)
   - **Purpose**: Comprehensive testing for OrderAgent
   - **Created**: January 2025
   - **Coverage**: Full order workflow, database integration, edge cases
   - **Dependencies**: unittest, SQLAlchemy, mock objects

3. **`test_integration.py`** (Planned)
   - **Purpose**: End-to-end integration testing
   - **Created**: January 2025
   - **Coverage**: Complete user workflows, API endpoints
   - **Dependencies**: FastAPI TestClient, database setup

4. **`test_rag_pipeline.py`** (Planned)
   - **Purpose**: RAG pipeline testing
   - **Created**: January 2025
   - **Coverage**: Retrieval, reranking, generation
   - **Dependencies**: FAISS, Whoosh, sentence-transformers

## Running Tests

### Prerequisites

1. **Virtual Environment**: Ensure you're in the virtual environment
   ```bash
   source venv/bin/activate
   ```

2. **Dependencies**: Install test dependencies
   ```bash
   pip install pytest pytest-cov
   ```

### Running Individual Test Files

```bash
# Run basic OrderAgent tests
python -m pytest tests/test_order_agent_basic.py -v

# Run with coverage
python -m pytest tests/test_order_agent_basic.py --cov=backend.agents.order_agent -v

# Run specific test method
python -m pytest tests/test_order_agent_basic.py::TestOrderAgentBasic::test_cart_initialization -v
```

### Running All Tests

```bash
# Run all tests in the tests directory
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=backend --cov-report=html -v
```

### Running Tests with Different Output

```bash
# Verbose output
python -m pytest tests/ -v

# Show print statements
python -m pytest tests/ -s

# Stop on first failure
python -m pytest tests/ -x

# Run tests in parallel (requires pytest-xdist)
python -m pytest tests/ -n auto
```

## Test Categories

### Unit Tests
- **Purpose**: Test individual components in isolation
- **Scope**: Single class or function
- **Speed**: Fast execution
- **Examples**: Cart operations, validation logic

### Integration Tests
- **Purpose**: Test component interactions
- **Scope**: Multiple components working together
- **Speed**: Medium execution
- **Examples**: Order flow, database operations

### End-to-End Tests
- **Purpose**: Test complete user workflows
- **Scope**: Full application stack
- **Speed**: Slower execution
- **Examples**: Complete order placement, API endpoints

## Test Data Management

### Test Database
- Tests use temporary SQLite databases
- Each test class creates its own database
- Databases are cleaned up after tests complete

### Mock Data
- Sample products with realistic bakery items
- Test customers with various scenarios
- Mock external dependencies (APIs, services)

## Best Practices

### Test Organization
- Each test file focuses on a specific component
- Test methods have descriptive names
- Tests are independent and can run in any order

### Documentation
- Each test file has comprehensive docstrings
- Purpose, creation date, and coverage are documented
- Usage instructions are provided

### Error Handling
- Tests validate both success and failure scenarios
- Edge cases and boundary conditions are covered
- Error messages and responses are verified

## Continuous Integration

### GitHub Actions (Planned)
- Automated test runs on pull requests
- Coverage reporting
- Test result notifications

### Local Development
- Run tests before committing changes
- Ensure all tests pass locally
- Update tests when adding new features

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure virtual environment is activated
   - Check Python path configuration
   - Verify backend directory structure

2. **Database Errors**
   - Check database file permissions
   - Ensure SQLite is available
   - Verify model definitions

3. **Mock Issues**
   - Check mock object setup
   - Verify patch decorators
   - Ensure proper cleanup

### Debug Mode

```bash
# Run tests with debug output
python -m pytest tests/ -v -s --tb=long

# Run single test with debugger
python -m pytest tests/test_order_agent_basic.py::TestOrderAgentBasic::test_cart_initialization -s --pdb
```

## Contributing

### Adding New Tests
1. Create test file with proper documentation
2. Follow naming conventions
3. Include comprehensive docstrings
4. Add to appropriate test category
5. Update this README

### Test Standards
- Use descriptive test method names
- Include setup and teardown methods
- Mock external dependencies
- Test both success and failure cases
- Maintain test independence

## Contact

For questions about the test suite, please refer to the main project documentation or create an issue in the project repository.
