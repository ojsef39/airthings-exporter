{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: {
  # https://devenv.sh/packages/
  packages = [
    pkgs.git
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    version = "3.12";

    venv.enable = true;
    venv.requirements = ./requirements.txt;

    # Install dev dependencies
    poetry = {
      enable = false;
    };
  };

  # https://devenv.sh/processes/
  # processes.cargo-watch.exec = "cargo-watch";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.d-run.exec = ''
    if [ -z "$AIRTHINGS_CLIENT_ID" ] || [ -z "$AIRTHINGS_CLIENT_SECRET" ] || [ -z "$AIRTHINGS_DEVICE_ID" ]; then
      echo "Error: Required environment variables not set"
      echo ""
      echo "Please set the following environment variables:"
      echo "  export AIRTHINGS_CLIENT_ID='your_client_id'"
      echo "  export AIRTHINGS_CLIENT_SECRET='your_client_secret'"
      echo "  export AIRTHINGS_DEVICE_ID='your_device_id'"
      echo ""
      echo "Optional:"
      echo "  export AIRTHINGS_PORT=8000"
      exit 1
    fi

    PORT=''${AIRTHINGS_PORT:-8000}
    echo "Starting Airthings Exporter on port $PORT..."
    python -m airthings.main \
      --client-id "$AIRTHINGS_CLIENT_ID" \
      --client-secret "$AIRTHINGS_CLIENT_SECRET" \
      --device-id "$AIRTHINGS_DEVICE_ID" \
      --port "$PORT"
  '';

  scripts.d-test.exec = ''
    python -m pytest tests/ -v
  '';

  scripts.d-lint.exec = ''
    echo "Running pylint..."
    python -m pylint src/airthings
    echo "Running black check..."
    python -m black --check src/ tests/
    echo "Running isort check..."
    python -m isort --check-only src/ tests/
  '';

  scripts.d-format.exec = ''
    echo "Running black..."
    python -m black src/ tests/
    echo "Running isort..."
    python -m isort src/ tests/
  '';

  enterShell = ''
    echo "🚀 Airthings Exporter Development Environment"
    echo "$(python --version)"
    echo ""
    echo "Installing dev dependencies..."
    pip install -q -e ".[dev]"
    echo ""
    echo "Available commands:"
    echo "  d-run    - Run the exporter locally (requires env vars)"
    echo "  d-test   - Run pytest tests"
    echo "  d-lint   - Run linters (pylint, black, isort)"
    echo "  d-format - Auto-format code (black, isort)"
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    python -m pytest tests/ -v
  '';

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
