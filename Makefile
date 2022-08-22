setup-pre-commit:
	@echo "Setting up pre-commit github hooks"
	brew install pre-commit || brew upgrade pre-commit
	pre-commit install
	pre-commit --version

setup-terraform-macos:
	@echo "Setting up terraform"
	brew install tfenv; tfenv install 1.2.5
	terraform --version
