"""Compatibility entry point for the repository's existing top-level package."""

from src.nepafact.run_model_only import main


if __name__ == "__main__":
    raise SystemExit(main())
