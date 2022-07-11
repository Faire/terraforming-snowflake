setup-pre-commit:
	@echo "Setting up pre-commit github hooks"
	brew install pre-commit || brew upgrade pre-commit
	pre-commit install
	pre-commit --version
