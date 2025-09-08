import os
from pathlib import Path

from ruamel.yaml import YAML

SETTINGS_FILENAME = "settings.yml"


def get_user_settings_file() -> Path:
    def get_user_data_folder() -> Path:
        config_home = os.getenv("XDG_CONFIG_HOME")
        if config_home is None or not Path(config_home).is_dir():
            parent_dir = Path.home()
        else:
            parent_dir = Path(config_home)
        return parent_dir / ".semgrep"

    path = os.getenv("SEMGREP_SETTINGS_FILE", str(get_user_data_folder() / SETTINGS_FILENAME))
    return Path(path)


def get_semgrep_app_token() -> str | None:
    """
    Returns the deployment ID the token is for, if token is valid
    """

    # Prioritize environment variable first
    env_token = os.environ.get("SEMGREP_APP_TOKEN")
    if env_token is not None:
        return env_token

    # Fall back to settings file if environment variable is not set
    user_settings_file = get_user_settings_file()
    if user_settings_file.exists():
        with open(user_settings_file) as f:
            yaml = YAML(typ='safe', pure=True)
            settings = yaml.load(f)
            return settings.get("api_token")

    return None
