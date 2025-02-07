# Recruitment task

Hey! Your task is implement simple parser for raydium swaps. Here are instructions:
1. Fork this repo
2. Use `json` block encoding (you shouldn't change `rpc_utils.py`)
3. In `raydium_parser.py` implement parser for block that will parse all raydium transactions to `RaydiumSwap` format
4. Implement basic tests in `test_raydium_parser.py`
5. After you finish go back to @PawelRainer

Good luck!

# About 

A minimal, conservative Python project template configured with:
- **Poetry** for dependency management
- **Ruff** for linting & formatting
- **Pyright** for type-checking
- **Pytest** for testing
- **Wily** for code complexity analysis
- **GitHub Actions** for CI (lint, test, complexity check)
- **Makefile** with handy developer commands

## Usage

- **Install dependencies**: `make sync`
- **Run linting**: `make lint`
- **Run type checks**: `make typecheck`
- **Run tests**: `make test`
- **View additional commands**: `make help`
