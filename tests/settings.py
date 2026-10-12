from pathlib import Path

from ribcage import environment

# The suite runs on the committed example's placeholders, never on a developer's .env (#45).
environment.load_file(Path(__file__).parents[1] / ".env.example")

from ribcage.settings import *  # noqa: E402, F403
