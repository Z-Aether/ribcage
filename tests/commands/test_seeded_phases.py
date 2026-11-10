from io import StringIO

import pytest
from django.core.management import call_command

from ribcage.phase.history import current
from ribcage.phase.order import PHASES

pytestmark = pytest.mark.usefixtures("fast_hashing")


@pytest.mark.parametrize("phase", PHASES)
def test_seed_runs_and_lands_in_each_phase(transactional_db, debug_on, phase):
    call_command("seed", "--phase", phase, stdout=StringIO())

    assert current() is phase
